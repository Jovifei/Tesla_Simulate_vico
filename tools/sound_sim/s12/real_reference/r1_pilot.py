"""Hellcat-first R1 pilot acquisition, rights, SHA and time-sync preflight."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from .raw_audio_intake import (
    RawReferenceContractError,
    _audio_metadata,
    _validate_state,
    ingest_raw_reference_specs,
)


class R1PilotValidationError(ValueError):
    """Raised when a pilot input violates an R1 contract."""


REQUIRED_RIGHTS_USES = {"local_analysis", "derived_features", "comparison", "human_audition", "bounded_tuning"}
_SHA_LINE = re.compile(r"^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(root: Path, value: str | Path, label: str) -> Path:
    root = Path(root).resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise R1PilotValidationError(f"{label} escapes pilot recording root: {candidate}") from exc
    return resolved


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise R1PilotValidationError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise R1PilotValidationError(f"{label} must be a JSON object")
    return value


def validate_rights_scope(recording_root: Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    """Require explicit algorithm-development scope; ordinary SFX is insufficient."""

    root = Path(recording_root).resolve()
    rights_value = spec.get("rights_path") or "rights.json"
    rights_path = _inside(root, str(rights_value), "rights_path")
    if not rights_path.is_file():
        raise R1PilotValidationError(f"rights file missing: {rights_path}")
    if rights_path.suffix.lower() == ".pdf":
        return {
            "schema_version": "s12.stage_q.r1-rights-validation.v1",
            "name": "rights_scope",
            "status": "MANUAL_REVIEW_REQUIRED",
            "r1_rights_ready": False,
            "rights_path": str(rights_path),
            "rights_sha256": _sha256(rights_path),
            "reason": "PDF 权利文件缺少机器可审计用途字段；必须人工确认本地分析、派生特征、Comparator、A/B 和有界调音范围。",
        }
    rights = _read_json(rights_path, "rights.json")
    allowed = rights.get("allowed_uses")
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise R1PilotValidationError("rights.json allowed_uses is missing")
    missing = sorted(REQUIRED_RIGHTS_USES - {item.strip() for item in allowed})
    if missing:
        raise R1PilotValidationError("rights.json allowed_uses missing: " + ", ".join(missing))
    if rights.get("permission_status") != "CONFIRMED":
        raise R1PilotValidationError("rights.json permission_status must be CONFIRMED")
    if rights.get("raw_media_git_policy") != "EXTERNAL_ONLY":
        raise R1PilotValidationError("rights.json raw_media_git_policy must be EXTERNAL_ONLY")
    source_holder = rights.get("source_holder")
    license_identifier = rights.get("license_identifier")
    if not isinstance(source_holder, str) or not source_holder.strip() or not isinstance(license_identifier, str) or not license_identifier.strip():
        raise R1PilotValidationError("rights.json source_holder and license_identifier are required")
    return {
        "schema_version": "s12.stage_q.r1-rights-validation.v1",
        "name": "rights_scope",
        "status": "PASS",
        "r1_rights_ready": True,
        "rights_path": str(rights_path),
        "rights_sha256": _sha256(rights_path),
        "source_holder": source_holder,
        "license_identifier": license_identifier,
        "allowed_uses": sorted(allowed),
        "raw_media_git_policy": rights["raw_media_git_policy"],
        "raw_redistribution": rights.get("raw_redistribution"),
    }


def validate_sha256_manifest(recording_root: Path, required_files: Sequence[str]) -> dict[str, Any]:
    """Validate sha256.txt for every required delivery file."""

    root = Path(recording_root).resolve()
    sha_path = root / "sha256.txt"
    if not sha_path.is_file():
        raise R1PilotValidationError(f"sha256.txt missing: {sha_path}")
    declared: dict[str, str] = {}
    for line_number, raw_line in enumerate(sha_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _SHA_LINE.match(line)
        if not match:
            raise R1PilotValidationError(f"invalid SHA-256 line {line_number}: {raw_line}")
        digest, relative = match.groups()
        relative_path = relative.replace("\\", "/")
        if relative_path in declared:
            raise R1PilotValidationError(f"duplicate SHA-256 entry: {relative_path}")
        declared[relative_path] = digest.lower()
    checked: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for relative in required_files:
        normalized = str(relative).replace("\\", "/")
        path = _inside(root, normalized, "sha256 required file")
        if not path.is_file():
            missing.append(normalized)
            continue
        if normalized not in declared:
            raise R1PilotValidationError(f"SHA-256 entry missing: {normalized}")
        actual = _sha256(path)
        expected = declared[normalized]
        if actual != expected:
            raise R1PilotValidationError(f"SHA-256 mismatch for {normalized}: {actual} != {expected}")
        checked[normalized] = {"declared": expected, "actual": actual}
    if missing:
        raise R1PilotValidationError("required delivery files missing: " + ", ".join(missing))
    return {
        "schema_version": "s12.stage_q.r1-sha-validation.v1",
        "name": "sha256",
        "status": "PASS",
        "sha256_path": str(sha_path),
        "sha256_sha256": _sha256(sha_path),
        "checked_files": checked,
    }


def validate_state_sync(recording_root: Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    """Validate timestamped state traces with no guessing or extrapolation."""

    root = Path(recording_root).resolve()
    raw_audio = spec.get("audio_path")
    if not isinstance(raw_audio, str) or not raw_audio.strip():
        raise R1PilotValidationError("spec.audio_path is required")
    audio_path = _inside(root, raw_audio, "audio_path")
    if not audio_path.is_file():
        raise R1PilotValidationError(f"raw audio missing: {audio_path}")
    try:
        audio = _audio_metadata(audio_path)
        bindings = _validate_state(spec.get("state") or {}, root=root, audio=audio)
    except (OSError, RawReferenceContractError) as exc:
        raise R1PilotValidationError(str(exc)) from exc
    return {
        "schema_version": "s12.stage_q.r1-state-sync-validation.v1",
        "name": "state_sync",
        "status": "PASS",
        "synchronization": bindings["synchronization"],
        "audio": audio,
        "time_window": bindings["time_window"],
        "units": bindings["units"],
        "shift_source": bindings["shift_source"],
        "trace_paths": {key: bindings[key] for key in ("rpm_trace_path", "load_throttle_trace_path", "gear_shift_trace_path")},
        "raw_trace_sha256": bindings["raw_trace_sha256"],
        "row_counts": bindings["row_counts"],
        "no_extrapolation": True,
    }


def _gate_error(name: str, error: str) -> dict[str, Any]:
    return {"name": name, "status": "FAIL", "error": error}


def _gate_missing(name: str, missing: Sequence[str]) -> dict[str, Any]:
    return {"name": name, "status": "MISSING", "missing": list(missing)}


def _required_delivery_files(spec: Mapping[str, Any]) -> list[str]:
    state = spec.get("state") if isinstance(spec.get("state"), Mapping) else {}
    trace_root = str(state.get("trace_root") or "").replace("\\", "/").strip("/")
    paths = [str(spec.get("audio_path") or ""), str(spec.get("rights_path") or "rights.json"), "spec.json"]
    for key in ("rpm_trace_path", "load_throttle_trace_path", "gear_shift_trace_path"):
        value = str(state.get(key) or "")
        paths.append(f"{trace_root}/{value}" if trace_root else value)
    return [path.replace("\\", "/") for path in paths if path]


def run_r1_pilot_preflight(pilot_root: Path, recording_id: str, output_dir: Path | None = None) -> dict[str, Any]:
    """Run all pilot gates and write metadata-only preflight receipts."""

    pilot_root = Path(pilot_root).resolve()
    recording_root = _inside(pilot_root, recording_id, "recording_id")
    output_dir = Path(output_dir).resolve() if output_dir is not None else Path.cwd() / "r1-pilot-preflight"
    output_dir.mkdir(parents=True, exist_ok=True)
    missing_files: list[str] = []
    if not recording_root.is_dir():
        missing_files = ["spec.json", "rights.json or rights.pdf", "sha256.txt", "raw/raw_audio.wav or raw/raw_audio.flac", "state/rpm.csv", "state/load_throttle.csv", "state/gear_shift.csv"]
        result = {
            "schema_version": "s12.stage_q.r1-pilot-preflight.v1",
            "status": "WAITING_FOR_R1_PILOT_DELIVERY",
            "recording_id": recording_id,
            "vehicle_id": "hellcat",
            "recording_root": str(recording_root),
            "missing_files": missing_files,
            "gates": [_gate_missing("delivery", missing_files)],
            "r1_pilot_ready": False,
            "automatic_tuning_eligible": False,
            "order_hard_gate_eligible": False,
            "profile_candidate_ready": False,
        }
        _write_preflight_outputs(output_dir, result, _gate_missing("rights_scope", ["rights.json or rights.pdf"]), _gate_missing("state_sync", ["raw audio and state traces"]))
        return result
    spec_path = recording_root / "spec.json"
    if not spec_path.is_file():
        result = {
            "schema_version": "s12.stage_q.r1-pilot-preflight.v1",
            "status": "WAITING_FOR_R1_PILOT_DELIVERY",
            "recording_id": recording_id,
            "recording_root": str(recording_root),
            "missing_files": ["spec.json"],
            "gates": [_gate_missing("delivery", ["spec.json"])],
            "r1_pilot_ready": False,
            "automatic_tuning_eligible": False,
            "order_hard_gate_eligible": False,
            "profile_candidate_ready": False,
        }
        _write_preflight_outputs(output_dir, result, _gate_missing("rights_scope", ["spec.json"]), _gate_missing("state_sync", ["spec.json"]))
        return result
    spec = _read_json(spec_path, "spec.json")
    gates: list[dict[str, Any]] = []
    try:
        rights = validate_rights_scope(recording_root, spec)
    except R1PilotValidationError as exc:
        rights = _gate_error("rights_scope", str(exc))
    gates.append(rights)
    required = _required_delivery_files(spec)
    try:
        sha = validate_sha256_manifest(recording_root, required)
    except R1PilotValidationError as exc:
        sha = _gate_error("sha256", str(exc))
    gates.append(sha)
    try:
        state_sync = validate_state_sync(recording_root, spec)
    except R1PilotValidationError as exc:
        state_sync = _gate_error("state_sync", str(exc))
    gates.append(state_sync)
    raw_intake: dict[str, Any]
    if all(gate.get("status") == "PASS" for gate in (rights, sha, state_sync)):
        intake_spec = dict(spec)
        intake_spec["license_status"] = "CONFIRMED"
        intake_spec["rights_evidence"] = rights.get("rights_path")
        try:
            with tempfile.TemporaryDirectory(prefix="s12-r1-pilot-intake-") as temp_dir:
                intake = ingest_raw_reference_specs([intake_spec], output_root=Path(temp_dir), allowed_root=recording_root)
            record = intake["records"][0]
            raw_intake = {
                "name": "raw_audio_intake",
                "status": "PASS" if intake["status"] == "R1_REFERENCE_PACKAGE_READY" and record.get("evidence", {}).get("r1_eligible") else "FAIL",
                "r1_eligible": bool(record.get("evidence", {}).get("r1_eligible")),
                "reason": record.get("evidence", {}).get("reason"),
            }
        except (OSError, RawReferenceContractError, ValueError) as exc:
            raw_intake = _gate_error("raw_audio_intake", str(exc))
    else:
        raw_intake = {"name": "raw_audio_intake", "status": "BLOCKED_UPSTREAM_GATES"}
    gates.append(raw_intake)
    ready = all(gate.get("status") == "PASS" for gate in gates)
    status = "R1_PILOT_READY" if ready else "R1_PILOT_PREFLIGHT_FAILED"
    result = {
        "schema_version": "s12.stage_q.r1-pilot-preflight.v1",
        "status": status,
        "recording_id": recording_id,
        "vehicle_id": spec.get("vehicle_id"),
        "scenario": spec.get("scenario"),
        "recording_root": str(recording_root),
        "gates": gates,
        "r1_pilot_ready": ready,
        "automatic_tuning_eligible": False,
        "order_hard_gate_eligible": False,
        "profile_candidate_ready": False,
        "next_step": "Stage Q canonical merge then MATLAB/Comparator only after Jovi review" if ready else "补齐失败 gate 后重新运行预检",
    }
    _write_preflight_outputs(output_dir, result, rights, state_sync)
    return result


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _write_preflight_outputs(output_dir: Path, result: Mapping[str, Any], rights: Mapping[str, Any], state_sync: Mapping[str, Any]) -> None:
    _write_json(output_dir / "r1_pilot_preflight.json", result)
    _write_json(output_dir / "rights_scope_validation.json", rights)
    _write_json(output_dir / "state_sync_validation.json", state_sync)


def write_r1_pilot_outputs(pilot_root: Path, recording_id: str, output_dir: Path) -> dict[str, Path]:
    """Write the complete metadata-only pilot package and its waiting report."""

    output_dir = Path(output_dir).resolve()
    result = run_r1_pilot_preflight(pilot_root, recording_id, output_dir)
    ready = bool(result.get("r1_pilot_ready"))
    comparison = {
        "schema_version": "s12.stage_r.r1-pilot-comparison-results.v1",
        "status": "PENDING_STAGE_Q_CANONICAL_MERGE" if ready else "NOT_RUN_WAITING_FOR_R1_PILOT",
        "recording_id": recording_id,
        "cases": [],
        "matlab_order_status": "PENDING_STAGE_Q_CANONICAL_MERGE" if ready else "NOT_RUN_WAITING_FOR_R1_PILOT",
        "matlab_psychoacoustic_status": "NOT_RUN",
        "comparator_status": "NOT_RUN",
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "reason": "没有真实 R1 试点文件；不调用 MATLAB、Comparator 或调音。" if not ready else "预检通过后仍需 Stage Q canonical merge、MATLAB/MoSQITo 和 Comparator 收据。",
    }
    recommendations = {
        "schema_version": "s12.stage_r.r1-pilot-parameter-recommendations.v1",
        "status": "WITHHELD_MISSING_R1_PILOT" if not ready else "WITHHELD_NOT_YET_COMPARED",
        "recording_id": recording_id,
        "recommendations": [],
        "parameter_changes": 0,
        "automatic_tuning_eligible": False,
        "profile_update": "FORBIDDEN",
        "profile_candidate_ready": False,
    }
    feedback_gate = {
        "schema_version": "s12.stage_s.r1-pilot-feedback-gate.v1",
        "status": "WAITING_FOR_R1_PILOT_DELIVERY" if not ready else "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "feedback_rows": 0,
        "parameter_changes": 0,
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
    }
    comparison_path = output_dir / "comparison_results.json"
    recommendations_path = output_dir / "parameter_recommendations.json"
    feedback_path = output_dir / "feedback_gate.json"
    _write_json(comparison_path, comparison)
    _write_json(recommendations_path, recommendations)
    _write_json(feedback_path, feedback_gate)
    gates = result.get("gates") or []
    gate_lines = [f"- `{gate.get('name')}`：`{gate.get('status')}`" for gate in gates if isinstance(gate, Mapping)]
    report_path = output_dir / "S12_R1_Pilot_Acquisition_Report.md"
    report_path.write_text(
        "\n".join([
            "# S12 R1 Pilot Acquisition Report",
            "",
            f"状态：`{result.get('status')}`",
            "",
            f"试点记录：`{recording_id}`；车型：`{result.get('vehicle_id') or '待交付'}`。",
            "",
            "## 当前门禁",
            "",
            *gate_lines,
            "",
            "## 保护边界",
            "",
            "原始 WAV/FLAC、视频、PCM 和状态 CSV/JSON 只允许留在 E:\\Claude_allow\\Download 外部目录；本报告只写路径、SHA、授权范围和验证结果，不复制原始媒体。",
            "",
            "没有通过 rights、SHA、时间同步和 raw_audio_intake 四个门之前，不运行 MATLAB rpmordermap/ordertrack/orderspectrum，不运行 Comparator，不生成数值参数建议，不修改声源。",
            "",
            "## 收到真实文件后的顺序",
            "",
            "raw_audio_intake → Stage Q canonical merge → 状态窗口绑定 → MATLAB 阶次/心理声学 → Comparator 差异报告 → 中文 A/B → 一车一问题一参数组有界调音 → 回归 → 第二轮 A/B。",
            "",
        ]),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "report": report_path,
        "preflight": output_dir / "r1_pilot_preflight.json",
        "rights": output_dir / "rights_scope_validation.json",
        "state": output_dir / "state_sync_validation.json",
        "comparison": comparison_path,
        "recommendations": recommendations_path,
        "feedback_gate": feedback_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S12 Hellcat-first R1 pilot rights/SHA/time-sync preflight")
    parser.add_argument("--pilot-root", type=Path, default=Path(r"E:\Claude_allow\Download\s12-r1-pilot"))
    parser.add_argument("--recording-id", default="hellcat_full_pull_01")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = write_r1_pilot_outputs(args.pilot_root, args.recording_id, args.output_dir)
    result = json.loads(paths["preflight"].read_text(encoding="utf-8"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "R1_PILOT_READY" else 2


__all__ = [
    "R1PilotValidationError",
    "REQUIRED_RIGHTS_USES",
    "run_r1_pilot_preflight",
    "write_r1_pilot_outputs",
    "validate_rights_scope",
    "validate_sha256_manifest",
    "validate_state_sync",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
