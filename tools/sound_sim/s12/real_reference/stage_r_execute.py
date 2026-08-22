"""Fail-closed Stage-R execution entry points for qualified references.

R2 can produce only relative digital-domain evidence.  R1 produces an
execution plan for the already-validated MATLAB/Stage-N toolchain and refuses
to run if the synchronized state contract is incomplete.  Neither path
creates tuning recommendations or profile changes by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.sound_sim.s12.acoustic_comparator.core import ComparisonCase

from .limited import compare_r2_signals
from .qualification import ReferenceQualificationError, require_r1_reference, qualify_r2_reference


MATLAB_R1_FUNCTIONS = (
    "rpmordermap",
    "ordertrack",
    "orderspectrum",
    "rpmfreqmap",
    "acousticLoudness",
    "acousticSharpness",
    "acousticRoughness",
    "acousticFluctuation",
    "acousticToneToNoiseRatio",
    "acousticProminenceRatio",
)


class StageRExecutionContractError(ValueError):
    """Raised when a Stage-R execution input is incomplete or unsafe."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_unaltered_pcm_wav(path: Path) -> tuple[np.ndarray, int, dict[str, Any]]:
    """Read PCM WAV without gain/EQ/AGC and fold channels only in the comparator."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"WAV file not found: {path}")
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        sample_rate_hz = stream.getframerate()
        frames = stream.getnframes()
        if stream.getcomptype() != "NONE":
            raise StageRExecutionContractError("compressed WAV is not allowed for analysis")
        raw = stream.readframes(frames)
    if channels < 1 or width not in {1, 2, 3, 4} or sample_rate_hz <= 0:
        raise StageRExecutionContractError("unsupported PCM WAV layout")
    expected_bytes = frames * channels * width
    if len(raw) != expected_bytes:
        raise StageRExecutionContractError(
            f"PCM WAV frame data is truncated: expected={expected_bytes}, actual={len(raw)}"
        )
    values = np.frombuffer(raw, dtype=np.uint8)
    if width == 1:
        decoded = (values.astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        decoded = np.frombuffer(raw, dtype="<i2").astype(np.float64) / (1 << 15)
    elif width == 3:
        packed = values.reshape(-1, 3)
        decoded = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
        decoded = np.where(decoded & 0x800000, decoded - (1 << 24), decoded).astype(np.float64) / (1 << 23)
    else:
        decoded = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (1 << 31)
    signal = decoded.reshape(-1, channels)
    if signal.size == 0 or not np.isfinite(signal).all():
        raise StageRExecutionContractError("PCM WAV is empty or non-finite")
    return signal, sample_rate_hz, {
        "channels": channels,
        "sample_width_bits": width * 8,
        "sample_rate_hz": sample_rate_hz,
        "frames": int(frames),
        "sha256": _sha256(path),
    }


def _reference_path(record: Mapping[str, Any]) -> Path:
    path = Path(str(record.get("external_path", "")))
    if not path.is_file():
        raise StageRExecutionContractError(f"reference external_path is not readable: {path}")
    expected = record.get("sha256")
    if expected and _sha256(path) != expected:
        raise StageRExecutionContractError(f"reference SHA-256 mismatch: {path}")
    return path


def _r2_case(record: Mapping[str, Any], candidate_meta: Mapping[str, Any], sample_rate_hz: int) -> ComparisonCase:
    vehicle_id = str(record.get("vehicle_id", ""))
    scenario = str(record.get("scenario") or record.get("scenario_hint") or "")
    if not vehicle_id or not scenario:
        raise StageRExecutionContractError("R2 reference must identify vehicle and scenario")
    missing = [name for name in ("vehicle_id", "scenario", "candidate_id") if not candidate_meta.get(name)]
    if missing:
        raise StageRExecutionContractError("R2 candidate metadata missing: " + ", ".join(missing))
    candidate_scenario = str(candidate_meta["scenario"])
    if candidate_scenario != scenario:
        raise StageRExecutionContractError("candidate/reference scenario mismatch")
    if str(candidate_meta["vehicle_id"]) != vehicle_id:
        raise StageRExecutionContractError("candidate/reference vehicle mismatch")
    return ComparisonCase(
        vehicle_id=vehicle_id,
        scenario=scenario,
        reference_id=str(record.get("reference_id") or record.get("recording_id")),
        candidate_id=str(candidate_meta["candidate_id"]),
        sample_rate_hz=sample_rate_hz,
        reference_rpm=(0.0, 0.0),
        candidate_rpm=(0.0, 0.0),
        reference_load=(0.0, 0.0),
        candidate_load=(0.0, 0.0),
        analysis_domain="unaltered_analysis_signal",
        reference_kind="external_recording",
        reference_provenance=f"authorised R2 reference {record.get('recording_id')}",
        candidate_source_commit=str(candidate_meta.get("source_commit") or "unspecified"),
        channel_policy="recorded_channels_folded_to_mono_for_comparison",
        microphone_setup_uncertainty="R2 capture metadata incomplete; relative-only",
        loudness_match_policy="analysis_unaltered_audition_separate",
    )


def run_r2_limited_comparison(
    reference_record: Mapping[str, Any],
    candidate_path: Path,
    *,
    candidate_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the permitted R2 relative comparison for one external reference."""

    gate = qualify_r2_reference(dict(reference_record))
    if not gate["eligible"]:
        raise ReferenceQualificationError(
            f"reference {reference_record.get('recording_id', '<unknown>')} is not R2-eligible: "
            + ", ".join(gate["missing"])
        )
    candidate_meta = dict(candidate_meta or {})
    reference_path = _reference_path(reference_record)
    reference, reference_rate, reference_header = read_unaltered_pcm_wav(reference_path)
    candidate, candidate_rate, candidate_header = read_unaltered_pcm_wav(Path(candidate_path))
    if reference_rate != candidate_rate:
        raise StageRExecutionContractError(
            f"sample-rate mismatch: reference={reference_rate}, candidate={candidate_rate}; resampling is not implicit"
        )
    case = _r2_case(reference_record, candidate_meta, reference_rate)
    result = compare_r2_signals(
        reference,
        candidate,
        case,
        dict(reference_record),
        candidate_scenario=case.scenario,
    )
    result.update(
        {
            "status": "R2_LIMITED_COMPARISON_COMPLETE",
            "comparison_scope": "relative_digital_domain_only",
            "reference_header": reference_header,
            "candidate_header": candidate_header,
            "reference_id": case.reference_id,
            "candidate_id": case.candidate_id,
            "automatic_tuning_eligible": False,
            "parameter_recommendations": [],
            "difference_report": {
                "vehicle_id": case.vehicle_id,
                "scenario": case.scenario,
                "spectral_residual": result.get("spectral", {}),
                "band_residual": result.get("bands", {}),
                "loudness_residual": result.get("loudness", {}),
                "psychoacoustic_residual": result.get("psychoacoustics", {}),
                "transient_residual": result.get("transients", {}),
                "order_residual": result.get("order", {}).get("comparison"),
                "reference_uncertainty": "R2/no synchronized RPM-state; relative only",
                "human_score": None,
            },
        }
    )
    return result


def build_r1_execution_plan(
    reference_record: Mapping[str, Any],
    candidate_meta: Mapping[str, Any],
) -> dict[str, Any]:
    """Prepare, but do not execute, a full R1 MATLAB/Stage-N comparison."""

    gate = require_r1_reference(dict(reference_record))
    reference_path = _reference_path(reference_record)
    required = ("vehicle_id", "scenario", "candidate_id", "candidate_sha256", "state_trace_sha256", "rpm_trace_path", "load_throttle_trace_path", "gear_shift_trace_path")
    missing = [name for name in required if not candidate_meta.get(name)]
    if missing:
        raise StageRExecutionContractError("R1 candidate metadata missing: " + ", ".join(missing))
    if str(candidate_meta["vehicle_id"]) != str(reference_record.get("vehicle_id")):
        raise StageRExecutionContractError("R1 candidate/reference vehicle mismatch")
    if str(candidate_meta["scenario"]) != str(reference_record.get("scenario") or reference_record.get("scenario_hint")):
        raise StageRExecutionContractError("R1 candidate/reference scenario mismatch")
    return {
        "status": "READY_FOR_R1_MATLAB_EXECUTION",
        "qualification": gate,
        "reference": {
            "reference_id": reference_record.get("reference_id") or reference_record.get("recording_id"),
            "external_path": str(reference_path),
            "sha256": reference_record.get("sha256"),
        },
        "candidate": dict(candidate_meta),
        "alignment_contract": {
            "dimensions": ["vehicle", "scenario", "rpm_range", "load_throttle", "gear_shift", "time_window", "sample_rate", "channel_policy"],
            "analysis_signal": "unaltered_analysis_signal",
            "audition_signal": "loudness_matched_audition_signal_separate",
            "estimated_rpm_allowed": False,
        },
        "matlab_required_functions": list(MATLAB_R1_FUNCTIONS),
        "required_receipts": ["matlab_order_session_receipt", "matlab_psychoacoustic_session_receipt", "mosqito_project_receipt"],
        "order_hard_gate": True,
        "automatic_tuning_authority": "WITHHELD_UNTIL_STAGE_S_HUMAN_FEEDBACK_AND_HARD_GATES",
    }


def write_r2_outputs(result: Mapping[str, Any], out_dir: Path) -> dict[str, Path]:
    """Write a Chinese R2 result/report without creating recommendation files."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "stage_r_r2_limited_result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report_path = out_dir / "S12_Stage_R_R2_Limited_Difference_Report.md"
    report_path.write_text(
        "\n".join(
            [
                "# S12 Stage R2 有限真实声浪差异报告",
                "",
                "状态：`R2_LIMITED_COMPARISON_COMPLETE`",
                "",
                "本报告只表示已授权 R2 参考与本地候选在未增益分析信号上的相对数字域差异。没有同步 RPM/state，因此不输出阶次硬门、不输出 OEM 绝对门限，也不生成参数建议。",
                "",
                f"车型：`{result.get('case', {}).get('vehicle_id')}`；工况：`{result.get('case', {}).get('scenario')}`。",
                "",
                "## 差异结果",
                "",
                "```json",
                json.dumps(result.get("difference_report", {}), indent=2, ensure_ascii=False, sort_keys=True),
                "```",
                "",
                "试听必须使用独立的响度匹配副本；本结果中的分析信号没有使用响度匹配副本。R2 结果仍需 Jovi 中文听审后才能进入任何后续判断。",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    return {"result": result_path, "report": report_path}


def _load_manifest_record(path: Path, recording_id: str) -> dict[str, Any]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    for record in manifest.get("recordings", []):
        if record.get("recording_id") == recording_id or record.get("reference_id") == recording_id:
            return dict(record)
    raise StageRExecutionContractError(f"recording_id not found in manifest: {recording_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="执行受资格门约束的 S12 Stage R R2 比较或生成 R1 MATLAB 执行计划")
    parser.add_argument("--mode", choices=("r2", "r1-plan"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--candidate-wav", type=Path)
    parser.add_argument("--candidate-meta", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    record = _load_manifest_record(args.manifest, args.recording_id)
    meta = json.loads(args.candidate_meta.read_text(encoding="utf-8")) if args.candidate_meta else {}
    if args.mode == "r2":
        if args.candidate_wav is None:
            raise SystemExit("--candidate-wav is required for --mode r2")
        result = run_r2_limited_comparison(record, args.candidate_wav, candidate_meta=meta)
        write_r2_outputs(result, args.output)
    else:
        plan = build_r1_execution_plan(record, meta)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through CLI smoke tests
    raise SystemExit(main())


__all__ = [
    "MATLAB_R1_FUNCTIONS",
    "StageRExecutionContractError",
    "build_r1_execution_plan",
    "read_unaltered_pcm_wav",
    "run_r2_limited_comparison",
    "write_r2_outputs",
]
