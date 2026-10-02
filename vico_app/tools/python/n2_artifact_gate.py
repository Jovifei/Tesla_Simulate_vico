"""Fail-closed N2 pre-score evidence gate; never enables playback or scores an objective.

The authoritative ledger is a local, protected file, not a signed attestation. All cooperating
processes must use the same ledger path. Deleting/replacing it is outside this tool's authority.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import uuid

CANDIDATE = "C63_N2_CONTINUOUS_V1"
LIMITS = {"continuous": 48, "event": 24}
LOW_BAND_DB_LIMIT = MID_BAND_DB_LIMIT = SOURCE_RMS_DB_LIMIT = 1.0
SOURCE_SCALE = 13.728409855272066
LEGACY_EVENT_UNIT_ENERGY = 331.3820481828321
LEGACY_EVENT_UNIT_L2 = 18.2039020043
UNIT_PROFILE_ID = "98dec5a954e836a0105241a04e920b8209f239441a51d039a46eb6b4f8e287c0"
# Exact preregistration bytes at PR37 5382585. Changing this is a new contract, not a CLI option.
PREREGISTRATION_SHA256 = "16c22a5e313e49d10a8986312f6b63512bbdbc6fbf44f05276c4117f90e92b1f"
LEDGER_SCHEMA = "c63.n2.budget.v3"
RESULT_SCHEMA = "c63.n2.reference_result.v2"
RESERVATION_SCHEMA = "c63.n2.reservation.v3"
BINDING_KEYS = {"profile_sha256", "artifact_sha256", "preregistration_sha256",
                "reference_targets_sha256", "calibration_sha256"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sha(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("invalid_sha256")
    return value


def _finite_number(value, name):
    if type(value) not in (int, float):
        raise ValueError(name + "_missing_or_non_numeric")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(name + "_nonfinite") from exc
    if not math.isfinite(value):
        raise ValueError(name + "_nonfinite")
    return value


def _pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate_json_key:" + key)
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ValueError("nonfinite_json:" + value)


def _load_bytes(data):
    try:
        data = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_reject_constant,
                          parse_float=lambda s: _finite_number(float(s), "json"))
    except RecursionError as exc:
        raise ValueError("json_nesting_too_deep") from exc
    if not isinstance(data, dict):
        raise ValueError("json_root_must_be_object")
    return data


def load(path: Path):
    return _load_bytes(Path(path).read_bytes())


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def atomic_json(path: Path, value: dict):
    """Durable unique-temp replacement. Callers must hold the ledger's separate stable lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def _ledger_lock(path):
    # Fail closed on platforms without an OS process lock. A threading.Lock is insufficient.
    try:
        import fcntl
    except ImportError as exc:
        raise ValueError("process_lock_requires_posix") from exc
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield path
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _binary_identity(data):
    """Read the frozen Kotlin N2BinaryArtifact v2 format; never regenerate its kernels."""
    expected_bytes = 20 + 66 + 32 + 24 + 12 * 4 + (8 + 8 * 4096 + 3 * 12288) * 8
    if len(data) != expected_bytes:
        raise ValueError("artifact_size")
    if struct.unpack_from(">5i", data) != (0x4e324250, 2, 8, 4096, 12288):
        raise ValueError("artifact_header")
    if struct.unpack_from(">H", data, 20)[0] != 64:
        raise ValueError("artifact_identity_length")
    identity = _sha(data[22:86].decode("ascii"))
    scalars = struct.unpack_from(">4d", data, 86)
    if scalars != (SOURCE_SCALE, .08, LEGACY_EVENT_UNIT_L2, .20):
        raise ValueError("frozen_calibration_scalars")
    seeds = struct.unpack_from(">3q", data, 118)
    if seeds != (0x4e325f535243, 5900017, 0x4e325f525350):
        raise ValueError("artifact_seeds")
    offset = 142
    arrays = []
    for size in (8,) + (4096,) * 8 + (12288,) * 3:
        if struct.unpack_from(">i", data, offset)[0] != size:
            raise ValueError("artifact_array_dimensions")
        offset += 4
        values = struct.unpack_from(">" + str(size) + "d", data, offset)
        offset += size * 8
        if not all(math.isfinite(v) for v in values):
            raise ValueError("artifact_nonfinite")
        arrays.append(values)
    if arrays[0] != (.52, .46, .39, .33, .27, .22, .17, .12):
        raise ValueError("artifact_coefficients")
    for values in arrays[1:]:
        if abs(sum(values)) >= 1e-8 or abs(sum(v * v for v in values) - 1) >= 1e-6:
            raise ValueError("artifact_response_normalization")
    if sum(v * v for v in arrays[9][8192:]) <= 1e-8:
        raise ValueError("artifact_event_tail")
    def profile_identity(scale_values):
        digest = hashlib.sha256(CANDIDATE.encode("ascii"))
        digest.update(struct.pack("<6i", 48000, 8, 4096, 12288, 48, 24))
        digest.update(struct.pack("<4d3q", *scale_values, *seeds))
        for values in arrays:
            digest.update(struct.pack("<" + str(len(values)) + "d", *values))
        return digest.hexdigest()

    if profile_identity(scalars) != identity:
        raise ValueError("artifact_profile_identity")
    if profile_identity((1., .08, 1., .20)) != UNIT_PROFILE_ID:
        raise ValueError("artifact_frozen_unit_profile_identity")
    return identity


def bindings_from_files(artifact, preregistration, reference, calibration):
    artifact_bytes = Path(artifact).read_bytes()
    profile = _binary_identity(artifact_bytes)
    calibration_bytes = Path(calibration).read_bytes()
    reference_bytes = Path(reference).read_bytes()
    bindings = {
        "profile_sha256": profile,
        "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "preregistration_sha256": sha256_file(preregistration),
        "reference_targets_sha256": hashlib.sha256(reference_bytes).hexdigest(),
        "calibration_sha256": hashlib.sha256(calibration_bytes).hexdigest(),
    }
    if bindings["preregistration_sha256"] != PREREGISTRATION_SHA256:
        raise ValueError("preregistration_identity")
    if not reference_bytes:
        raise ValueError("empty_reference_targets")
    receipt = _load_bytes(calibration_bytes)
    expected = {
        "schema": "c63.n2.calibration.v1", "candidate": CANDIDATE,
        "profile_sha256": profile, "artifact_sha256": bindings["artifact_sha256"],
        "calibration_profile_id": UNIT_PROFILE_ID, "source_scale": SOURCE_SCALE,
        "event_unit_energy": LEGACY_EVENT_UNIT_ENERGY, "event_unit_l2": LEGACY_EVENT_UNIT_L2,
        "pre_objective": True, "heldout_used_for_fitting": False,
    }
    for key, value in expected.items():
        if receipt.get(key) != value or isinstance(value, bool) and receipt.get(key) is not value:
            raise ValueError("calibration_receipt:" + key)
    return bindings


def _validate_bindings(bindings):
    if not isinstance(bindings, dict) or set(bindings) != BINDING_KEYS:
        raise ValueError("bindings_schema")
    for value in bindings.values():
        _sha(value)


def _trial_id(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is None:
        raise ValueError("invalid_trial_id")


def _validate_ledger(state):
    if state.get("schema") != LEDGER_SCHEMA or state.get("candidate") != CANDIDATE:
        raise ValueError("ledger_identity")
    if _canonical(state.get("limits")) != _canonical(LIMITS):
        raise ValueError("ledger_limits")
    ledger_id = state.get("ledger_id")
    if not isinstance(ledger_id, str) or re.fullmatch(r"[0-9a-f]{32}", ledger_id) is None:
        raise ValueError("ledger_id")
    _validate_bindings(state.get("bindings"))
    trials = state.get("trials")
    if not isinstance(trials, list):
        raise ValueError("ledger_trials")
    counts = dict.fromkeys(LIMITS, 0)
    seen = set()
    for trial in trials:
        if not isinstance(trial, dict):
            raise ValueError("ledger_trial_schema")
        _trial_id(trial.get("trial_id"))
        kind = trial.get("kind")
        if kind not in LIMITS or trial["trial_id"] in seen:
            raise ValueError("ledger_duplicate_or_kind")
        seen.add(trial["trial_id"])
        counts[kind] += 1
        expected = _reservation(state, kind, trial["trial_id"], counts[kind])
        if _canonical(trial) != _canonical(expected) or counts[kind] > LIMITS[kind]:
            raise ValueError("ledger_reservation_integrity")
    results = state.get("results")
    if not isinstance(results, dict) or not set(results).issubset(seen):
        raise ValueError("ledger_results")
    for value in results.values():
        _sha(value)
    if state.get("stop_reason", "missing") not in (None, "identity_or_representation_failure"):
        raise ValueError("ledger_stop_reason")
    return counts


def _stop(path, state):
    state["stop_reason"] = "identity_or_representation_failure"
    atomic_json(path, state)


def _reservation(state, kind, trial_id, attempt):
    receipt = {"schema": RESERVATION_SCHEMA, "candidate": CANDIDATE,
               "ledger_id": state["ledger_id"], "trial_id": trial_id, "kind": kind,
               "attempt": attempt, "maximum": LIMITS[kind], "bindings": state["bindings"].copy()}
    receipt["reservation_sha256"] = _digest(receipt)
    return receipt


def reserve(ledger: Path, trial_id: str, kind: str, *, artifact: Path,
            preregistration: Path, reference: Path, calibration: Path):
    if kind not in LIMITS:
        raise ValueError("invalid_trial_kind")
    _trial_id(trial_id)
    with _ledger_lock(ledger) as path:
        state = load(path) if path.exists() else None
        if state is not None:
            _validate_ledger(state)
            if state["stop_reason"] is not None:
                raise ValueError("candidate_search_stopped")
        try:
            bindings = bindings_from_files(artifact, preregistration, reference, calibration)
        except ValueError:
            if state is not None:
                _stop(path, state)
            raise
        if state is None:
            state = {
                "schema": LEDGER_SCHEMA, "candidate": CANDIDATE, "ledger_id": uuid.uuid4().hex,
                "limits": LIMITS.copy(), "bindings": bindings, "trials": [],
                "results": {}, "stop_reason": None,
            }
        counts = _validate_ledger(state)
        if state["bindings"] != bindings:
            _stop(path, state)
            raise ValueError("ledger_binding_mismatch_no_restart")
        if any(x["trial_id"] == trial_id for x in state["trials"]):
            raise ValueError("duplicate_trial")
        if counts[kind] >= LIMITS[kind]:
            raise ValueError(kind + "_budget_exhausted_no_restart")
        trial = _reservation(state, kind, trial_id, counts[kind] + 1)
        state["trials"].append(trial)
        atomic_json(path, state)
    return trial


def rejection(reasons):
    return {"schema": "c63.n2.hard_gate.v2", "candidate": CANDIDATE,
            "status": "REJECTED_BEFORE_SCORING" if reasons else "FEASIBLE",
            "feasible": not reasons, "reasons": sorted(set(reasons))}


def verify(result: Path, ledger: Path, artifact: Path, trial_id: str, *,
           preregistration: Path, reference: Path, calibration: Path):
    """Verify real files and the reserved trial, then registered hard feasibility/acceptance rules."""
    try:
        _trial_id(trial_id)
        result_bytes = Path(result).read_bytes()
        r = _load_bytes(result_bytes)
        result_sha256 = hashlib.sha256(result_bytes).hexdigest()
        with _ledger_lock(ledger) as path:
            state = load(path)  # No absent/malformed-ledger fallback during verification.
            _validate_ledger(state)
            if state["stop_reason"] is not None:
                raise ValueError("candidate_search_stopped")
            trial = next((x for x in state["trials"] if x["trial_id"] == trial_id), None)
            if trial is None:
                raise ValueError("missing_reservation")
            try:
                if r.get("schema") != RESULT_SCHEMA or r.get("candidate") != CANDIDATE:
                    raise ValueError("result_identity")
                bindings = bindings_from_files(artifact, preregistration, reference, calibration)
                if state["bindings"] != bindings or r.get("bindings") != bindings:
                    raise ValueError("result_artifact_binding_mismatch")
                if (r.get("trial_id") != trial_id or r.get("kind") != trial["kind"]
                        or _canonical(r.get("reservation")) != _canonical(trial)):
                    raise ValueError("result_reservation_mismatch")
            except ValueError:
                _stop(path, state)
                raise
            sealed = state["results"].get(trial_id)
            if sealed is not None and sealed != result_sha256:
                raise ValueError("reservation_already_used_for_different_result")
            # Seal metric failures too: editing a failed result cannot reuse its attempt.
            if sealed is None:
                state["results"][trial_id] = result_sha256
                atomic_json(path, state)
            if __package__:
                from .n2_hard_gate import metric_reasons
            else:
                from n2_hard_gate import metric_reasons
            output = rejection(metric_reasons(r))
            output.update(result_sha256=result_sha256, reservation=trial, bindings=bindings,
                          trial_id=trial_id, kind=trial["kind"])
            return output
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, struct.error, OverflowError) as exc:
        return rejection(["invalid_evidence:" + str(exc)])


def add_artifact_arguments(parser):
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)


def file_arguments(args):
    return {key: getattr(args, key) for key in
            ("ledger", "trial_id", "artifact", "preregistration", "reference", "calibration")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path, required=True, help="Reference result JSON to validate")
    add_artifact_arguments(parser)
    args = parser.parse_args(argv)
    output = verify(args.verify, **file_arguments(args))
    print(json.dumps(output, sort_keys=True, allow_nan=False))
    return 0 if output["feasible"] else 2


if __name__ == "__main__":
    sys.exit(main())
