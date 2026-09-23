"""Render and verify a plain six-vehicle Stage AI-8 diagnostic preview.

This is diagnostic evidence only.  It does not claim validated-B or human review.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import io
import json
import subprocess
import tarfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from scipy.io import wavfile

from ..stage_ah.c63_pipeline import C63Engine, C63_SOURCE_VARIANT
from ..stage_ah.continuous_drive import build_continuous_trace, continuous_events
from ..stage_ah.engine import RemediationEngine
from ..stage_ah.fourcar_pipeline import peak_estimate_4x
from ..stage_ah.output_guard import LINKED_SOFT_CEILING_V1
from ..stage_ah.qualification import numeric_ok
from ..stage_ah.reconstruction_peak import reconstructed_peak_ok, reconstructed_peak_receipt
from ..stage_ah.reference_feedback_cli import _runtime_identity
from ..stage_ah.supra_pipeline import SupraEngine, SUPRA_SOURCE_VARIANT

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35", "c63_w204", "supra_jza80")
FOURCAR = frozenset(VEHICLES[:4])
SAMPLE_RATE_HZ = 48_000
DURATION_S = 30.0
SCENE_ID = "continuous_drive"
SCHEMA = "s12.stage_ai8.diagnostic_preview.v2"
_RENDERER_FIELDS = frozenset({
    "source_variant", "trace_sha256", "output_policy", "parent_peak",
    "candidate_raw_peak", "normalization_denominator", "normalization",
    "seed", "flags", "identity_layer_clip_count", "identity_layer_clip_error",
    "identity_layer_clip_error_rms", "post_identity_clip_count",
    "post_identity_clip_error", "post_identity_clip_error_rms",
})
_NORMALIZATION_FIELDS = frozenset({
    "output_policy", "normalization_denominator", "post_guard_ceiling_exceedance_samples",
    "emergency_clip_count", "legacy_ceiling_input_exceedance_samples",
    "pre_guard_exceedance_longest_run", "emergency_clip_error", "emergency_clip_error_rms",
    "legacy_transfer_pre_guard_peak", "pre_guard_peak", "soft_guard_delta_peak",
    "soft_guard_delta_rms", "post_guard_peak", "frame_count", "soft_guard_active_frames",
})
_PREVIEW_FIELDS = _RENDERER_FIELDS | frozenset({
    "vehicle", "scene_id", "sample_rate_hz", "sample_count", "final_pcm_sha256",
    "final_peak", "final_rms", "peak_estimate_4x", "reconstruction_peak",
    "evidence_label", "human_review", "validated_b", "diagnostic_status", "status",
})
_CLAIM_MARKERS = ("promot", "validated", "qualif", "human", "oem", "calibrat",
                  "profilefreeze", "release", "production")
_POSITIVE_CLAIMS = {"accepted", "approved", "calibrated", "confirmed", "match", "matched",
                    "pass", "passed", "promoted", "qualified", "ready", "true"}
_NEGATIVE_CLAIMS = {"blocked", "failed", "fail", "false", "missing", "no", "not",
                    "pending", "rejected", "unverified"}
_EVENT_CONTRACT = {
    "schema": "s12.stage_ai8.preview_event_contract.v1",
    "fourcar": {"shift_duration_s": 0.01, "afterfire_intensity": 0.2, "bov_duration_s": 0.16},
    "c63_supra": "continuous_event_mapping_native",
    "boundary": "SYNTHETIC_PREVIEW_ONLY_NOT_CALIBRATION",
}
_SOURCE_SCOPE = "tools/sound_sim/s12/acoustic_identity_v015"
_RUNTIME_IDENTITY_FIELDS = frozenset({
    "commit", "scope", "inventory_sha256", "source_files", "source_status",
})
_SUMMARY_FIELDS = frozenset({
    "schema", "status", "runtime_identity", "synthetic_orchestration_stub",
    "event_contract", "vehicles",
})
_VEHICLE_ROW_FIELDS = frozenset({"status", "report", "wav", "audio_available"})
_VEHICLE_STATUSES = frozenset({"DIAGNOSTIC_BASELINE", "FAILED_NUMERIC_GATE", "RENDER_FAILED"})
_FAILED_REPORT_FIELDS = frozenset({"schema", "status", "vehicle", "error_type", "error"})


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=4)
def _commit_source_files(commit: str) -> dict[str, str] | None:
    repository = Path(__file__).resolve().parents[5]
    try:
        archive = subprocess.check_output([
            "git", "-C", str(repository), "archive", "--format=tar", commit, _SOURCE_SCOPE,
        ], stderr=subprocess.DEVNULL)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
            return {member.name: hashlib.sha256(source.extractfile(member).read()).hexdigest()
                    for member in source.getmembers() if member.isfile()}
    except (OSError, subprocess.CalledProcessError, tarfile.TarError):
        return None


def _runtime_identity_valid(identity: Any) -> bool:
    if not isinstance(identity, dict) or set(identity) != _RUNTIME_IDENTITY_FIELDS:
        return False
    commit = identity["commit"]
    if (not isinstance(commit, str) or len(commit) not in (40, 64)
            or any(character.lower() not in "0123456789abcdef" for character in commit)):
        return False
    source_files = identity["source_files"]
    if (identity["scope"] != _SOURCE_SCOPE or identity["source_status"] != "SOURCE_CLEAN"
            or not isinstance(source_files, dict) or not source_files):
        return False
    for path, digest in source_files.items():
        if (not isinstance(path, str) or not path.startswith(_SOURCE_SCOPE + "/")
                or any(part in {"", ".", ".."} for part in path.split("/"))
                or not isinstance(digest, str) or len(digest) != 64
                or any(character.lower() not in "0123456789abcdef" for character in digest)):
            return False
    inventory = hashlib.sha256(
        json.dumps(source_files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if identity["inventory_sha256"] != inventory:
        return False
    # Bind the map to its historical commit, without requiring it to equal HEAD.
    return _commit_source_files(commit) == source_files


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def _claim_field(name: str) -> bool:
    tokens = "".join(character.lower() if character.isalnum() else " " for character in name).split()
    compact = "".join(tokens)
    return any(marker in compact for marker in _CLAIM_MARKERS) or (
        "b" in tokens and bool(set(tokens) & {"available", "qualified", "ready", "status"})
    )


def _positive_claim(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return bool(np.isfinite(value) and value > 0)
    if isinstance(value, str):
        tokens = "".join(character.lower() if character.isalnum() else " " for character in value).split()
        return bool(set(tokens) & _POSITIVE_CLAIMS) and not bool(set(tokens) & _NEGATIVE_CLAIMS)
    if isinstance(value, Mapping):
        return any(_positive_claim(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_positive_claim(item) for item in value)
    return False


def _positive_claim_field(value: Any, parent: str = "") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{parent}.{key}" if parent else str(key)
            if isinstance(key, str) and _claim_field(key) and _positive_claim(item):
                return path
            nested = _positive_claim_field(item, path)
            if nested:
                return nested
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            nested = _positive_claim_field(item, f"{parent}[{index}]")
            if nested:
                return nested
    return None


def _renderer_report(report: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        raise ValueError("renderer report must be an object")
    claim = _positive_claim_field(report)
    if claim:
        raise ValueError("renderer report contains unsupported positive claim field: " + claim)
    result = {key: copy.deepcopy(report[key]) for key in _RENDERER_FIELDS if key in report}
    if isinstance(result.get("normalization"), Mapping):
        result["normalization"] = {
            key: copy.deepcopy(value)
            for key, value in result["normalization"].items()
            if key in _NORMALIZATION_FIELDS
        }
    return result


def _preview_report_schema_valid(report: Mapping[str, Any]) -> bool:
    normalization = report.get("normalization")
    return (set(report).issubset(_PREVIEW_FIELDS)
            and (not isinstance(normalization, Mapping)
                 or set(normalization).issubset(_NORMALIZATION_FIELDS)))


def _validate_vehicles(vehicles: Sequence[str]) -> tuple[str, ...]:
    result = tuple(vehicles)
    if not result or len(set(result)) != len(result):
        raise ValueError("vehicles must be a nonempty unique list")
    for vehicle in result:
        if vehicle not in VEHICLES:
            raise ValueError(f"unsupported vehicle: {vehicle}")
    return result


def _default_renderer(vehicle: str) -> tuple[np.ndarray, dict[str, Any]]:
    trace = build_continuous_trace(vehicle)
    events = continuous_events()
    rpm, throttle = trace.rpm[:-1], trace.throttle[:-1]
    if vehicle in FOURCAR:
        events = _fourcar_events(events)
        engine = RemediationEngine(vehicle, variant="r1_baseline", seed=20260908,
                                   output_policy=LINKED_SOFT_CEILING_V1)
        pcm = engine.render_track(rpm, throttle, DURATION_S, **events)
        report = copy.deepcopy(engine.last_report)
    else:
        cls = C63Engine if vehicle == "c63_w204" else SupraEngine
        engine = cls(output_policy=LINKED_SOFT_CEILING_V1, seed=20260908,
                     scene_ids=(SCENE_ID,))
        pcm = engine.render_track(rpm, throttle, DURATION_S, **events)
        report = copy.deepcopy(engine.reports[-1])
    return pcm, report


def _fourcar_events(events: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, list[tuple[float, float]]]:
    """Adapt typed AI-6 preview events to the legacy four-car tuple contract."""
    # Reuse tested AH synthetic defaults; these are preview values, not fitted calibration.
    return {
        "shift_events": [(float(event["time_s"]), _EVENT_CONTRACT["fourcar"]["shift_duration_s"])
                         for event in events["shift_events"]],
        "afterfire_events": [(float(event["time_s"]), _EVENT_CONTRACT["fourcar"]["afterfire_intensity"])
                             for event in events["afterfire_events"]],
        "bov_events": [(float(event["time_s"]), _EVENT_CONTRACT["fourcar"]["bov_duration_s"])
                       for event in events["bov_events"]],
    }


def _prepare_report(vehicle: str, pcm: np.ndarray, report: Mapping[str, Any]) -> dict[str, Any]:
    array = np.asarray(pcm)
    expected_frames = int(SAMPLE_RATE_HZ * DURATION_S)
    if array.dtype != np.int16 or array.shape != (expected_frames, 2):
        raise ValueError("renderer must return exactly 1,440,000 stereo int16 frames")
    decoded = array.astype(np.float64) / 32767.0
    if not np.all(np.isfinite(decoded)):
        raise ValueError("renderer waveform must be finite")
    result = _renderer_report(report)
    result.update({
        "vehicle": vehicle,
        "scene_id": SCENE_ID,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "sample_count": int(len(array)),
        "final_pcm_sha256": hashlib.sha256(
            np.ascontiguousarray(array, dtype="<i2").tobytes()).hexdigest(),
        "final_peak": float(np.max(np.abs(decoded))),
        "final_rms": float(np.sqrt(np.mean(decoded * decoded))),
        "peak_estimate_4x": peak_estimate_4x(decoded),
        "reconstruction_peak": reconstructed_peak_receipt(decoded, sample_rate=SAMPLE_RATE_HZ),
    })
    result.setdefault("normalization_denominator", result.get("parent_peak"))
    result["evidence_label"] = "DIAGNOSTIC_BASELINE"
    result["human_review"] = "NOT_RUN"
    result["validated_b"] = False
    return result


def _index(rows: Mapping[str, Mapping[str, Any]]) -> str:
    cards = []
    for vehicle in VEHICLES:
        if vehicle not in rows:
            continue
        row = rows[vehicle]
        status = html.escape(str(row["status"]))
        if status == "DIAGNOSTIC_BASELINE":
            audio = f'<audio controls preload="none" src="{html.escape(str(row["wav"]))}"></audio>'
        elif status == "FAILED_NUMERIC_GATE":
            audio = "<span>unavailable: numeric gate failed</span>"
        else:
            audio = "<span>unavailable: render failed</span>"
        cards.append(f"<li><b>{html.escape(vehicle)}</b> — {status}<br>{audio}</li>")
    return ("<!doctype html><meta charset=utf-8><title>Stage AI-8 diagnostic baseline</title>"
            "<h1>DIAGNOSTIC_BASELINE</h1><p>Numeric diagnostics only; no validated-B or "
            "human-review claim.</p><ul>" + "".join(cards) + "</ul>\n")


def render_preview(output: Path | str, *, vehicles: Sequence[str] = VEHICLES,
                   renderer: Callable[[str], tuple[np.ndarray, Mapping[str, Any]]] | None = None,
                   runtime_identity_fn: Callable[[], Mapping[str, Any]] = _runtime_identity) -> dict[str, Any]:
    """Create a fresh external preview directory and continue after per-car failures."""
    selected = _validate_vehicles(vehicles)
    destination = Path(output).resolve()
    repository = Path(__file__).resolve().parents[5]
    if destination == repository or repository in destination.parents:
        raise ValueError("output must be an external directory outside the source repository")
    if destination.exists():
        raise FileExistsError(destination)
    identity = dict(runtime_identity_fn())
    if identity.get("source_status") != "SOURCE_CLEAN":
        raise ValueError("runtime source identity is not clean")
    destination.mkdir(parents=True)
    render = renderer or _default_renderer
    rows: dict[str, dict[str, Any]] = {}
    for index, vehicle in enumerate(selected, 1):
        print(f"[{index}/{len(selected)}] rendering {vehicle}", flush=True)
        report_path = destination / f"{vehicle}.report.json"
        try:
            pcm, raw_report = render(vehicle)
            report = _prepare_report(vehicle, pcm, raw_report)
            wav_path = destination / f"{vehicle}.wav"
            wavfile.write(wav_path, SAMPLE_RATE_HZ, np.asarray(pcm, dtype=np.int16))
            qualified = numeric_ok(report) and reconstructed_peak_ok(report["reconstruction_peak"])
            status = "DIAGNOSTIC_BASELINE" if qualified else "FAILED_NUMERIC_GATE"
            report["diagnostic_status"] = status
            report["status"] = status
            _write_json(report_path, report)
            rows[vehicle] = {"status": status, "report": report_path.name,
                             "wav": wav_path.name,
                             "audio_available": qualified}
        except Exception as error:  # Per-vehicle evidence and continuation are deliberate.
            evidence = {"schema": SCHEMA, "status": "RENDER_FAILED",
                        "vehicle": vehicle, "error_type": type(error).__name__,
                        "error": str(error)}
            _write_json(report_path, evidence)
            rows[vehicle] = {"status": "RENDER_FAILED", "report": report_path.name,
                             "audio_available": False}
    summary = {"schema": SCHEMA, "status": "DIAGNOSTIC_ONLY", "runtime_identity": identity,
               "synthetic_orchestration_stub": renderer is not None,
               "event_contract": copy.deepcopy(_EVENT_CONTRACT), "vehicles": rows}
    _write_json(destination / "summary.json", summary)
    (destination / "index.html").write_text(_index(rows), encoding="utf-8")
    final_identity = dict(runtime_identity_fn())
    if final_identity != identity:
        summary["status"] = "INVALID_RUNTIME_IDENTITY_DRIFT"
        summary["runtime_identity_end"] = final_identity
        _write_json(destination / "summary.json", summary)
        raise ValueError("runtime source identity changed during render")
    files = {path.name: _sha(path) for path in sorted(destination.iterdir()) if path.is_file()}
    _write_json(destination / "manifest.json", {"schema": SCHEMA, "files": files})
    return summary


def verify_preview(output: Path | str, *, expected_manifest_sha256: str | None = None) -> dict[str, Any]:
    raw_root = Path(output)
    if raw_root.is_symlink():
        raise ValueError("unsafe symlink output root")
    root = raw_root.resolve()
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("unsafe manifest path")
    manifest_sha = _sha(manifest_path)
    if expected_manifest_sha256 is not None and manifest_sha != expected_manifest_sha256:
        raise ValueError("manifest SHA mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("manifest schema mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("manifest file inventory missing")
    for name, expected in files.items():
        if Path(name).name != name or name == "manifest.json":
            raise ValueError("unsafe manifest path")
        path = root / name
        if path.is_symlink() or path.resolve().parent != root or not path.is_file() or _sha(path) != expected:
            raise ValueError(f"content drift: {name}")
    actual = {path.name for path in root.iterdir() if path.is_file() and path.name != "manifest.json"}
    if actual != set(files):
        raise ValueError("content drift: file inventory")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    if (not isinstance(summary, dict) or set(summary) != _SUMMARY_FIELDS
            or summary.get("schema") != SCHEMA or summary.get("status") != "DIAGNOSTIC_ONLY"
            or not _runtime_identity_valid(summary.get("runtime_identity"))
            or not isinstance(summary.get("synthetic_orchestration_stub"), bool)
            or summary.get("event_contract") != _EVENT_CONTRACT):
        raise ValueError("summary semantic mismatch")
    rows = summary.get("vehicles")
    if (not isinstance(rows, dict) or not rows
            or any(vehicle not in VEHICLES for vehicle in rows)):
        raise ValueError("summary semantic mismatch")
    for vehicle, row in rows.items():
        if not isinstance(row, dict) or not set(row).issubset(_VEHICLE_ROW_FIELDS):
            raise ValueError(f"summary semantic mismatch: {vehicle}")
        status = row.get("status")
        if (not isinstance(status, str) or status not in _VEHICLE_STATUSES
                or type(row.get("audio_available")) is not bool
                or row["audio_available"] != (status == "DIAGNOSTIC_BASELINE")):
            raise ValueError(f"summary semantic mismatch: {vehicle}")
        required = {"status", "report", "audio_available"}
        if status != "RENDER_FAILED":
            required.add("wav")
        if set(row) != required:
            raise ValueError(f"summary semantic mismatch: {vehicle}")
    if (root / "index.html").read_text(encoding="utf-8") != _index(rows):
        raise ValueError("index semantic drift")
    for vehicle, row in rows.items():
        if not isinstance(row, dict):
            raise ValueError(f"numeric gate drift: {vehicle}")
        report_name = f"{vehicle}.report.json"
        wav_name = f"{vehicle}.wav"
        if row.get("report") != report_name or report_name not in files:
            raise ValueError(f"unsafe report binding: {vehicle}")
        report = json.loads((root / report_name).read_text(encoding="utf-8"))
        if row["status"] == "RENDER_FAILED":
            if (wav_name in files or not isinstance(report, dict)
                    or set(report) != _FAILED_REPORT_FIELDS
                    or report.get("schema") != SCHEMA or report.get("vehicle") != vehicle
                    or report.get("status") != "RENDER_FAILED"
                    or not isinstance(report.get("error_type"), str) or not report["error_type"]
                    or not isinstance(report.get("error"), str) or not report["error"]):
                raise ValueError(f"failed report semantic mismatch: {vehicle}")
            continue
        if row.get("wav") != wav_name or wav_name not in files:
            raise ValueError(f"unsafe WAV binding: {vehicle}")
        rate, pcm = wavfile.read(root / wav_name)
        if rate != SAMPLE_RATE_HZ or pcm.dtype != np.int16:
            raise ValueError(f"numeric gate drift: {vehicle}")
        if not isinstance(report, dict) or not _preview_report_schema_valid(report):
            raise ValueError(f"report schema contains unsupported fields: {vehicle}")
        if (report.get("diagnostic_status") != row.get("status")
                or report.get("status") != row.get("status")
                or report.get("evidence_label") != "DIAGNOSTIC_BASELINE"
                or report.get("validated_b") is not False or report.get("human_review") != "NOT_RUN"):
            raise ValueError(f"numeric gate drift: {vehicle}")
        if pcm.shape != (int(SAMPLE_RATE_HZ * DURATION_S), 2):
            raise ValueError(f"numeric gate drift: {vehicle}")
        decoded = pcm.astype(np.float64) / 32767.0
        recomputed = reconstructed_peak_receipt(decoded, sample_rate=SAMPLE_RATE_HZ)
        recomputed_4x = peak_estimate_4x(decoded)
        recomputed_peak = float(np.max(np.abs(decoded)))
        recomputed_rms = float(np.sqrt(np.mean(decoded * decoded)))
        pcm_sha = hashlib.sha256(np.ascontiguousarray(pcm, dtype="<i2").tobytes()).hexdigest()
        checked = copy.deepcopy(report)
        checked.update(final_peak=recomputed_peak, final_rms=recomputed_rms,
                       peak_estimate_4x=recomputed_4x, reconstruction_peak=recomputed,
                       final_pcm_sha256=pcm_sha, sample_count=int(len(pcm)),
                       sample_rate_hz=rate)
        gate = numeric_ok(checked) and reconstructed_peak_ok(recomputed)
        expected = row.get("status") == "DIAGNOSTIC_BASELINE"
        expected_variant = ("r1_baseline" if vehicle in FOURCAR else
                            C63_SOURCE_VARIANT if vehicle == "c63_w204" else SUPRA_SOURCE_VARIANT)
        if (gate != expected or report.get("reconstruction_peak") != recomputed
                or report.get("peak_estimate_4x") != recomputed_4x
                or report.get("final_peak") != recomputed_peak
                or report.get("final_rms") != recomputed_rms
                or report.get("final_pcm_sha256") != pcm_sha
                or report.get("sample_count") != len(pcm)
                or report.get("sample_rate_hz") != SAMPLE_RATE_HZ
                or report.get("vehicle") != vehicle or report.get("scene_id") != SCENE_ID
                or report.get("output_policy") != LINKED_SOFT_CEILING_V1
                or report.get("source_variant") != expected_variant
                or row["audio_available"] != expected):
            raise ValueError(f"numeric gate drift: {vehicle}")
    return {"schema": SCHEMA, "status": "VERIFIED", "file_count": len(files)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render")
    render.add_argument("output", type=Path)
    render.add_argument("--vehicles", nargs="+", default=list(VEHICLES))
    verify = sub.add_parser("verify")
    verify.add_argument("output", type=Path)
    verify.add_argument("--expected-manifest-sha256")
    args = parser.parse_args(argv)
    result = (render_preview(args.output, vehicles=args.vehicles)
              if args.command == "render" else verify_preview(
                  args.output, expected_manifest_sha256=args.expected_manifest_sha256))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
