"""Independent Stage-AH report/WAV qualification.

The verifier treats stored reports as claims: it decodes each final WAV,
recomputes decoded-PCM identity and 4x/8x/16x reconstruction evidence, and
then compares the two feedback roles.  It never changes audio.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile

from .feedback_evidence import SCENES
from .reconstruction_peak import (
    DEFAULT_FACTORS,
    reconstructed_peak_ok,
    reconstructed_peak_receipt,
)

QUALIFICATION_SCHEMA = "s12.stage_ah.independent_qualification.v1"
QUALIFICATION_FILENAME = "qualification.json"
_BLOCKED_STATUS = "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK"
_SHA_LENGTH = 64


class QualificationError(ValueError):
    """Evidence is incomplete, malformed, inconsistent, or numerically unsafe."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_int(value: Any, *, minimum: int = 0) -> bool:
    return (not isinstance(value, (bool, np.bool_))
            and isinstance(value, (int, np.integer)) and int(value) >= minimum)


def _finite(value: Any) -> bool:
    return (not isinstance(value, (bool, np.bool_))
            and isinstance(value, (int, float, np.integer, np.floating))
            and math.isfinite(float(value)))


def _sha(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == _SHA_LENGTH
            and all(character in "0123456789abcdef" for character in value))


def numeric_ok(record: Mapping[str, Any]) -> bool:
    """Fail closed on malformed numerics while preserving pre-guard diagnostics."""
    try:
        if not isinstance(record, Mapping):
            return False
        normalization = record["normalization"]
        if not isinstance(normalization, Mapping):
            return False

        zero_counts = (
            normalization["post_guard_ceiling_exceedance_samples"],
            normalization["emergency_clip_count"],
            record["identity_layer_clip_count"],
            record["post_identity_clip_count"],
        )
        if any(not _strict_int(value) or int(value) != 0 for value in zero_counts):
            return False
        longest_run = normalization["pre_guard_exceedance_longest_run"]
        if isinstance(longest_run, Mapping):
            longest_run = longest_run["samples"]
        diagnostic_counts = (
            normalization["legacy_ceiling_input_exceedance_samples"], longest_run,
        )
        if any(not _strict_int(value) for value in diagnostic_counts):
            return False

        zero_errors = (
            normalization["emergency_clip_error"],
            normalization["emergency_clip_error_rms"],
            record["identity_layer_clip_error"],
            record["post_identity_clip_error"],
        )
        zero_errors += tuple(record[field] for field in (
            "identity_layer_clip_error_rms", "post_identity_clip_error_rms"
        ) if field in record)
        if any(not _finite(value) or float(value) != 0.0 for value in zero_errors):
            return False
        finite_values = (
            record["parent_peak"], record["candidate_raw_peak"],
            record["normalization_denominator"], record["final_peak"], record["final_rms"],
            record["peak_estimate_4x"]["peak"],
            normalization["normalization_denominator"],
            normalization["legacy_transfer_pre_guard_peak"], normalization["pre_guard_peak"],
            normalization["soft_guard_delta_peak"], normalization["soft_guard_delta_rms"],
            normalization["post_guard_peak"],
        )
        if any(not _finite(value) for value in finite_values):
            return False
        denominator = float(record["normalization_denominator"])
        if (denominator <= 0.0 or float(record["parent_peak"]) != denominator
                or float(normalization["normalization_denominator"]) != denominator):
            return False
        if (not isinstance(record["output_policy"], str) or not record["output_policy"]
                or normalization["output_policy"] != record["output_policy"]):
            return False
        return bool(
            0.0 < float(record["final_rms"]) <= float(record["final_peak"]) <= 0.94 + 1e-10
            and 0.0 <= float(record["peak_estimate_4x"]["peak"]) <= 1.0
            and reconstructed_peak_ok(record["reconstruction_peak"])
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _validate_report(record: Mapping[str, Any], vehicle: str, scene: str,
                     summary_policy: str) -> None:
    if not numeric_ok(record):
        if not reconstructed_peak_ok(record.get("reconstruction_peak", {})):
            raise QualificationError(f"{scene}: stored reconstructed-peak qualification failed")
        raise QualificationError(f"{scene}: report numeric qualification failed")
    if record.get("scene_id") != scene:
        raise QualificationError(f"{scene}: report scene identity mismatch")
    if record.get("vehicle") != vehicle:
        raise QualificationError(f"{scene}: report vehicle identity mismatch")
    if not _sha(record.get("trace_sha256")):
        raise QualificationError(f"{scene}: malformed trace SHA")
    for field, minimum in (("sample_rate_hz", 1), ("sample_count", 1), ("seed", 0)):
        if not _strict_int(record.get(field), minimum=minimum):
            raise QualificationError(f"{scene}: malformed {field}")
    if int(record["sample_rate_hz"]) != 48_000:
        raise QualificationError(f"{scene}: report sample rate is not 48 kHz")
    normalization = record["normalization"]
    for field in ("frame_count", "soft_guard_active_frames"):
        if not _strict_int(normalization.get(field), minimum=0):
            raise QualificationError(f"{scene}: malformed normalization {field}")
    if int(normalization["frame_count"]) != int(record["sample_count"]):
        raise QualificationError(f"{scene}: normalization frame count mismatch")
    flags = record.get("flags")
    if not isinstance(flags, list) or any(not isinstance(value, str) for value in flags):
        raise QualificationError(f"{scene}: malformed flags")
    if not isinstance(record.get("parent_peak_key"), str) or not record["parent_peak_key"]:
        raise QualificationError(f"{scene}: malformed parent peak key")
    if record["output_policy"] != summary_policy:
        raise QualificationError(f"{scene}: output policy mismatch")
    if not _sha(record.get("final_pcm_sha256")):
        raise QualificationError(f"{scene}: malformed final PCM identity")


def _decode_wav(path: Path) -> tuple[np.ndarray, bytes]:
    if path.is_symlink() or not path.is_file():
        raise QualificationError(f"missing final WAV: {path}")
    try:
        sample_rate, pcm = wavfile.read(path)
    except Exception as error:  # scipy reports several format-specific exception types
        raise QualificationError(f"cannot decode final WAV: {path}") from error
    if (not _strict_int(sample_rate, minimum=1) or int(sample_rate) != 48_000
            or not isinstance(pcm, np.ndarray) or pcm.ndim != 2 or pcm.shape[1] != 2
            or pcm.dtype.kind != "i" or pcm.dtype.itemsize != 2):
        raise QualificationError(f"final WAV must be 48 kHz stereo int16: {path}")
    pcm = np.ascontiguousarray(pcm, dtype="<i2")
    return pcm, pcm.tobytes()


def _qualify_role(root: Path, vehicle: str, role: str,
                  records: Mapping[str, Any], summary_policy: str) -> dict[str, Any]:
    if not isinstance(records, Mapping) or tuple(sorted(records)) != tuple(sorted(SCENES)):
        raise QualificationError(f"{vehicle}/{role}: exactly ten canonical scene keys required")
    scene_ids = [record.get("scene_id") if isinstance(record, Mapping) else None
                 for record in records.values()]
    if len(scene_ids) != len(set(scene_ids)) or set(scene_ids) != set(SCENES):
        raise QualificationError(f"{vehicle}/{role}: duplicate or missing report scenes")

    scenes: dict[str, Any] = {}
    for scene in SCENES:
        record = records[scene]
        _validate_report(record, vehicle, scene, summary_policy)
        wav_path = root / role / vehicle / "web_audio" / f"{scene}.wav"
        if not wav_path.resolve().is_relative_to(root):
            raise QualificationError(f"final WAV escapes qualification root: {wav_path}")
        pcm, pcm_bytes = _decode_wav(wav_path)
        if int(record["sample_count"]) != int(len(pcm)):
            raise QualificationError(f"{vehicle}/{role}/{scene}: decoded frame count mismatch")
        decoded_sha = hashlib.sha256(pcm_bytes).hexdigest()
        if decoded_sha != record["final_pcm_sha256"]:
            raise QualificationError(f"{vehicle}/{role}/{scene}: decoded PCM SHA mismatch")
        recomputed = reconstructed_peak_receipt(
            pcm.astype(np.float64) / 32767.0,
            sample_rate=48_000,
            factors=DEFAULT_FACTORS,
        )
        try:
            stored_matches = _canonical(record["reconstruction_peak"]) == _canonical(recomputed)
        except (TypeError, ValueError, OverflowError) as error:
            raise QualificationError(
                f"{vehicle}/{role}/{scene}: malformed stored reconstruction receipt"
            ) from error
        if not stored_matches:
            raise QualificationError(
                f"{vehicle}/{role}/{scene}: stored/recomputed reconstruction mismatch"
            )
        if not reconstructed_peak_ok(recomputed):
            raise QualificationError(
                f"{vehicle}/{role}/{scene}: recomputed reconstructed peak blocked"
            )
        report_sha = hashlib.sha256(_canonical(record)).hexdigest()
        scenes[scene] = {
            "status": "PASS",
            "wav_file_sha256": _sha_file(wav_path),
            "decoded_pcm_sha256": decoded_sha,
            "report_sha256": report_sha,
            "report_identity": {
                "vehicle": vehicle,
                "scene_id": scene,
                "trace_sha256": record["trace_sha256"],
                "seed": int(record["seed"]),
                "flags": list(record["flags"]),
                "parent_peak_key": record["parent_peak_key"],
                "normalization_denominator": float(record["normalization_denominator"]),
                "output_policy": record["output_policy"],
                "sample_rate_hz": int(record["sample_rate_hz"]),
            },
            "reconstruction": recomputed,
        }
    return {"status": "PASS", "scene_count": len(scenes), "scenes": scenes}


def _validate_role_match(vehicle: str, baseline: Mapping[str, Any], tuned: Mapping[str, Any]) -> None:
    fields = ("trace_sha256", "seed", "flags", "parent_peak_key",
              "normalization_denominator", "output_policy", "sample_rate_hz")
    for scene in SCENES:
        for field in fields:
            if _canonical(baseline[scene][field]) != _canonical(tuned[scene][field]):
                raise QualificationError(f"{vehicle}/{scene}: baseline/tuned {field} mismatch")


def build_qualification_receipt(root: Path, summary: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute an independent versioned receipt; failures return BLOCKED."""
    root = Path(root).resolve()
    vehicles: dict[str, Any] = {}
    qualified = 0
    try:
        rows = summary["vehicles"]
        summary_policy = summary["output_policy"]
        if not isinstance(rows, Mapping) or not rows or not isinstance(summary_policy, str):
            raise QualificationError("nonempty vehicles and output policy required")
        summary_sha = hashlib.sha256(_canonical(summary)).hexdigest()
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        return {
            "schema": QUALIFICATION_SCHEMA,
            "status": "BLOCKED",
            "reason": f"malformed run summary: {error}",
            "vehicles": {},
            "qualified_vehicle_count": 0,
        }

    for vehicle in sorted(rows):
        result = rows[vehicle]
        if (isinstance(result, Mapping) and result.get("status") == _BLOCKED_STATUS
                and isinstance(result.get("failure_receipt"), str)):
            vehicles[vehicle] = {"status": "BLOCKED", "reason": "UPSTREAM_BASELINE_BLOCKED"}
            continue
        try:
            if not isinstance(result, Mapping):
                raise QualificationError("vehicle result must be an object")
            baseline_records = result["baseline_records"]
            tuned_records = result["selected_records"]
            baseline = _qualify_role(root, vehicle, "baseline", baseline_records, summary_policy)
            tuned = _qualify_role(root, vehicle, "tuned", tuned_records, summary_policy)
            _validate_role_match(vehicle, baseline_records, tuned_records)
            vehicles[vehicle] = {"status": "PASS", "roles": {
                "baseline": baseline, "tuned": tuned,
            }}
            qualified += 1
        except (KeyError, QualificationError, TypeError, ValueError, OverflowError) as error:
            vehicles[vehicle] = {"status": "BLOCKED", "reason": str(error)}

    blocked_unqualified = any(row["status"] == "BLOCKED"
                              and row.get("reason") != "UPSTREAM_BASELINE_BLOCKED"
                              for row in vehicles.values())
    status = "PASS" if qualified and not blocked_unqualified else "BLOCKED"
    return {
        "schema": QUALIFICATION_SCHEMA,
        "status": status,
        "summary_sha256": summary_sha,
        "qualified_vehicle_count": qualified,
        "reconstruction_policy": {
            "method": "scipy.signal.resample_poly; kaiser beta 5; line boundary",
            "domain": "FINAL_DECODED_PCM_FLOAT",
            "factor_order": list(DEFAULT_FACTORS),
        },
        "vehicles": vehicles,
    }


def verify_qualification_receipt(root: Path, summary: Mapping[str, Any],
                                 receipt: Mapping[str, Any] | None) -> dict[str, Any]:
    """Require byte-canonical equality with fresh recomputation and current PASS."""
    if not isinstance(receipt, Mapping) or receipt.get("schema") != QUALIFICATION_SCHEMA:
        raise ValueError("independent qualification receipt missing or unsupported")
    fresh = build_qualification_receipt(root, summary)
    try:
        matches = _canonical(receipt) == _canonical(fresh)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("independent qualification receipt is malformed") from error
    if not matches:
        raise ValueError("independent qualification receipt does not match recomputed evidence")
    if fresh["status"] != "PASS":
        raise ValueError("independent qualification is BLOCKED")
    return fresh


__all__ = (
    "QUALIFICATION_FILENAME",
    "QUALIFICATION_SCHEMA",
    "QualificationError",
    "build_qualification_receipt",
    "numeric_ok",
    "verify_qualification_receipt",
)
