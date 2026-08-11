"""Build the explicit, louder Stage-J three-vehicle review package."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np

from ..acoustic_analysis import compute_order_map, write_order_map, write_spectrogram
from ..contracts import SourceRender
from ..loudness_manager import manage_bundle_loudness, measure_loudness
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _health, _pcm24_roundtrip, _read_pcm24_wav, _write_pcm24_wav
from .candidate_profiles import STAGE_J_VEHICLES, load_stage_j_candidate
from .perceptual_metrics import compute_stage_j_perceptual_metrics
from .reference_distance import compute_stage_j_reference_distance
from .render_candidate import render_stage_j_candidate

SAMPLE_RATE_HZ = 48000
REVIEW_GAIN_LINEAR = 1.25
REVIEW_GAIN_DB = 20.0 * float(np.log10(REVIEW_GAIN_LINEAR))
PEAK_LIMIT_DBFS = -1.5
_PEAK_LIMIT_LINEAR = 10.0 ** (PEAK_LIMIT_DBFS / 20.0)


def build_stage_j_named_review(
    output_root: str | Path,
    *,
    duration_s: float = 60.0,
    requested_review_gain_linear: float = REVIEW_GAIN_LINEAR,
) -> dict[str, object]:
    """Render formal PCM plus a common louder review copy for each selected car."""
    if not np.isfinite(duration_s) or duration_s < 1.0:
        raise ValueError("duration_s must be finite and >= 1.0")
    if not np.isfinite(requested_review_gain_linear) or requested_review_gain_linear <= 0.0:
        raise ValueError("review gain must be finite and > 0")
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    feedback_path = root / "Jovi_Stage_J_Named_Feedback.csv"
    if not feedback_path.exists():
        _write_feedback_template(feedback_path)
    readme = root / "00_OPEN_ME_FIRST.md"
    manifest: dict[str, object] = {
        "package_id": "S12_Stage_J_Named_Review_v1",
        "status": "PARTIAL / AUTOMATED_GATE_FAIL",
        "named_review_status": "WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW",
        "duration_s": float(duration_s),
        "vehicle_ids": list(STAGE_J_VEHICLES),
        "requested_review_gain_linear": float(requested_review_gain_linear),
        "requested_review_gain_db": REVIEW_GAIN_DB if requested_review_gain_linear == REVIEW_GAIN_LINEAR else float(20.0 * np.log10(requested_review_gain_linear)),
        "review_policy": "common linear gain on baseline/candidate pair; attenuation-only headroom cap; no compressor/limiter/EQ/AGC",
        "provenance": "C/synthetic; uncalibrated; not OEM reproduction",
        "vehicles": {},
    }
    feedback_rows: list[dict[str, str]] = []
    for vehicle_id in STAGE_J_VEHICLES:
        vehicle_root = root / vehicle_id
        vehicle_root.mkdir(parents=True, exist_ok=True)
        trace = build_drive_cycle_trace(vehicle_id, duration_s)
        candidate = load_stage_j_candidate(_candidate_path(vehicle_id))
        baseline_render = render_stage_j_candidate(vehicle_id, trace, None)
        candidate_render = render_stage_j_candidate(vehicle_id, trace, candidate)
        baseline_formal, baseline_managed = _finalize_formal(baseline_render)
        candidate_formal, candidate_managed = _finalize_formal(candidate_render)
        common_gain = _common_review_gain(baseline_formal, candidate_formal, float(requested_review_gain_linear))
        baseline_review = _pcm24_roundtrip(baseline_formal * common_gain)
        candidate_review = _pcm24_roundtrip(candidate_formal * common_gain)
        baseline_path = _write_pcm24_wav(vehicle_root / f"{vehicle_id}_StageC_Baseline_Review_60s.wav", baseline_review)
        candidate_path = _write_pcm24_wav(vehicle_root / f"{vehicle_id}_StageJ_Candidate_v1_Review_60s.wav", candidate_review)
        identity_path = _write_pcm24_wav(vehicle_root / f"{vehicle_id}_StageJ_Identity_12s.wav", candidate_review[: min(candidate_review.shape[0], 12 * SAMPLE_RATE_HZ + 1)])
        diagnostic_path = _write_pcm24_wav(vehicle_root / f"{vehicle_id}_StageJ_Shift_Lift_Diagnostic_12s.wav", candidate_review[min(8 * SAMPLE_RATE_HZ, candidate_review.shape[0] - 1): min(20 * SAMPLE_RATE_HZ + 1, candidate_review.shape[0])])
        write_spectrogram(vehicle_root / "spectrogram.png", candidate_review, SAMPLE_RATE_HZ)
        write_order_map(vehicle_root / "order_map.png", compute_order_map(candidate_review, trace, SAMPLE_RATE_HZ))
        baseline_metrics = _metrics(baseline_render, baseline_review, trace, baseline_managed, common_gain)
        candidate_metrics = _metrics(candidate_render, candidate_review, trace, candidate_managed, common_gain)
        metric_payload = {
            "vehicle_id": vehicle_id,
            "candidate_id": candidate.candidate_id,
            "trace": {"duration_s": float(trace.time_s[-1]), "samples": int(trace.time_s.size), "timeline": "0-8 idle; 8-26 acceleration + 3 shifts; 26-36 full pull; 36-46 lift/afterfire; 46-52 coast; 52-60 idle return"},
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            "review_loudness": {"requested_gain_linear": float(requested_review_gain_linear), "requested_gain_db": float(20.0 * np.log10(requested_review_gain_linear)), "applied_gain_linear": common_gain, "applied_gain_db": float(20.0 * np.log10(common_gain)), "headroom_limited": bool(common_gain < requested_review_gain_linear), "pair_common": True},
            "candidate_parameter_usage": candidate_render.diagnostics.get("candidate_parameter_usage"),
            "provenance": "C/synthetic; uncalibrated; not OEM reproduction",
        }
        metrics_path = vehicle_root / "stage_j_metrics.json"
        metrics_path.write_text(json.dumps(metric_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        target_path = _target_path(vehicle_id)
        if duration_s >= 46.0:
            reference = compute_stage_j_reference_distance(vehicle_id, baseline_path, candidate_path, target_path)
        else:
            reference = {"automatic_status": "NOT_PERFORMED_SHORT_TEST", "states": {}}
        (vehicle_root / "reference_distance.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        health_baseline = _health(_read_pcm24_wav(baseline_path))
        health_candidate = _health(_read_pcm24_wav(candidate_path))
        manifest["vehicles"][vehicle_id] = {
            "baseline_review_wav": str(baseline_path),
            "candidate_review_wav": str(candidate_path),
            "identity_stem_wav": str(identity_path),
            "shift_lift_diagnostic_wav": str(diagnostic_path),
            "metrics_json": str(metrics_path),
            "reference_distance_json": str(vehicle_root / "reference_distance.json"),
            "health": {"baseline": health_baseline, "candidate": health_candidate},
            "review_loudness": metric_payload["review_loudness"],
            "reference_status": reference.get("automatic_status"),
        }
        feedback_rows.append({"file_id": f"{vehicle_id}_StageJ_Candidate_v1_Review_60s", "vehicle_id": vehicle_id, "identity_1_5": "", "low_frequency_weight_1_5": "", "high_frequency_harshness_1_5": "", "artifact_freedom_1_5": "", "keep_or_change": "", "notes": ""})
    manifest["automatic_status"] = "PASS" if all(value.get("reference_status") == "PASS" for value in manifest["vehicles"].values()) else "PARTIAL / AUTOMATED_GATE_FAIL"
    manifest["qualified_for_profile_freeze"] = False
    readme.write_text(_open_me_first(root, manifest), encoding="utf-8")
    _write_feedback_template(feedback_path, feedback_rows)
    # Freeze every packaged input before creating the archive.  Mutating the
    # manifest after ZIP creation would make the archive and its evidence
    # disagree, so ZIP metadata is returned to the caller/report only.
    manifest.pop("sha256", None)
    manifest.pop("zip_path", None)
    manifest.pop("zip_sha256", None)
    (root / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (root / "SHA256SUMS.txt").write_text(_sha_sums(root), encoding="utf-8")
    zip_path = root / "S12_Stage_J_Named_Review.zip"
    _zip_tree(root, zip_path)
    manifest["zip_path"] = str(zip_path)
    manifest["zip_sha256"] = _sha256(zip_path)
    return manifest


def _candidate_path(vehicle_id: str) -> Path:
    return Path(__file__).resolve().parents[1] / "targets" / "stage_j_candidates" / f"{vehicle_id}_candidate_v1.json"


def _target_path(vehicle_id: str) -> Path:
    return Path(__file__).resolve().parents[1] / "reference_database" / f"{vehicle_id}_reference_targets.json"


def _finalize_formal(render: SourceRender) -> tuple[np.ndarray, object]:
    ptr_audio = _edge_fade(_apply_frozen_ptr(render.pressure))
    managed = manage_bundle_loudness({"cycle": ptr_audio}, SAMPLE_RATE_HZ, target_lufs=-16.0, peak_limit_dbfs=-1.5)
    return _pcm24_roundtrip(managed.segments["cycle"]), managed


def _common_review_gain(baseline: np.ndarray, candidate: np.ndarray, requested: float) -> float:
    peak = max(float(np.max(np.abs(baseline))), float(np.max(np.abs(candidate))))
    if peak <= 0.0:
        return requested
    return float(min(requested, _PEAK_LIMIT_LINEAR / peak))


def _metrics(render: SourceRender, final_audio: np.ndarray, trace, managed, applied_gain: float) -> dict[str, object]:
    metrics = compute_stage_j_perceptual_metrics(render, trace, SAMPLE_RATE_HZ)
    loudness = measure_loudness(final_audio, SAMPLE_RATE_HZ)
    return {"source": metrics, "final_pcm": {"integrated_lufs": loudness.integrated_lufs, "rms_dbfs": loudness.rms_dbfs, "peak_dbfs": loudness.peak_dbfs, "crest_factor_db": loudness.crest_factor_db, "clipping_count": loudness.clipping_count}, "formal_gain_db": float(managed.gain_db), "review_gain_linear": applied_gain, "health": _health(final_audio)}


def _open_me_first(root: Path, manifest: dict[str, object]) -> str:
    lines = ["# S12 Stage J 三车型具名试听包", "", "状态：`WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW`；自动参考距离若未达门限会同时标记 `PARTIAL / AUTOMATED_GATE_FAIL`。", "", "试听规则：先听每车 StageC_Baseline 与 StageJ_Candidate，再听 12 秒身份片段和 shift/lift 诊断。审核副本按同一对文件施加共同线性增益，目标是比正式 -16 LUFS 版本更容易听见；没有压缩、限幅、EQ 或分段 AGC。", "", "时间线（60 秒）：0–8 idle；8–26 acceleration + 3 shifts；26–36 full pull；36–46 lift/afterfire；46–52 coast；52–60 idle return。", ""]
    for vehicle_id, value in manifest["vehicles"].items():
        lines.extend([f"## {vehicle_id}", "", f"- Stage C baseline：`{value['baseline_review_wav']}`", f"- Stage J candidate：`{value['candidate_review_wav']}`", f"- 12 秒身份片段：`{value['identity_stem_wav']}`", f"- shift/lift 诊断：`{value['shift_lift_diagnostic_wav']}`", ""])
    lines.extend(["## 请重点记录", "", "- C63：低负载 lumpy cross-plane bark、机械纹理、加速时事件化中频。", "- GT-R：V6 事件列、双涡轮建立、随负载变化的涡轮啸叫、收油 wastegate/BOV。", "- LFA：5/10/15 阶随 RPM 移动、高转进气、金属纹理，不能像固定正弦。", "", "所有文件均为 C/synthetic、uncalibrated、not OEM reproduction。请填写同目录 `Jovi_Stage_J_Named_Feedback.csv`，不要将自动指标当作真实感结论。", ""])
    return "\n".join(lines)


def _write_feedback_template(path: Path, rows: list[dict[str, str]] | None = None) -> None:
    fields = ["file_id", "vehicle_id", "identity_1_5", "low_frequency_weight_1_5", "high_frequency_harshness_1_5", "artifact_freedom_1_5", "keep_or_change", "notes"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows or []:
            writer.writerow(row)


def _write_manifest(root: Path, manifest: dict[str, object]) -> str:
    path = root / "artifact_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return _sha256(path)


def _zip_tree(root: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path != zip_path:
                archive.write(path, path.relative_to(root).as_posix())


def _sha_sums(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in {"SHA256SUMS.txt", "S12_Stage_J_Named_Review.zip"}:
            lines.append(f"{_sha256(path)}  {path.relative_to(root).as_posix()}")
    return "\n".join(lines) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ("REVIEW_GAIN_LINEAR", "REVIEW_GAIN_DB", "build_stage_j_named_review")
