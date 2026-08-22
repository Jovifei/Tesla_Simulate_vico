"""Build an external, Chinese R2 A/B audition package.

The package contains only loudness-matched presentation copies.  It keeps the
unaltered source WAV outside Git and binds each audition file to the original
source SHA-256.  It is a listening hand-off, not a tuning or Profile update.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import wave
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.sound_sim.s12.acoustic_comparator.listening import loudness_matched_audition
from tools.sound_sim.s12.real_reference.stage_r_execute import read_unaltered_pcm_wav


ALLOWED_DOWNLOAD_ROOT = Path(r"E:\Claude_allow\Download")
SCHEMA_VERSION = "s12-stage-s-r2-ab-package-v1"
DIMENSIONS = (
    "vehicle_identity",
    "realism",
    "low_frequency_weight",
    "mechanical_character",
    "idle_life",
    "acceleration_aggression",
    "shift_realism",
    "afterfire_naturalness",
    "synthetic_artifact_freedom",
    "preference",
)
DIMENSION_LABELS_ZH = {
    "vehicle_identity": "车型身份",
    "realism": "真实感",
    "low_frequency_weight": "低频重量",
    "mechanical_character": "机械感",
    "idle_life": "怠速生命感",
    "acceleration_aggression": "加速攻击性",
    "shift_realism": "换挡真实感",
    "afterfire_naturalness": "回火自然度",
    "synthetic_artifact_freedom": "合成器感/伪影少",
    "preference": "偏好",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_pcm16(path: Path, signal: np.ndarray, sample_rate_hz: int) -> None:
    value = np.asarray(signal, dtype=np.float64)
    if value.ndim == 1:
        value = value[:, None]
    if value.ndim != 2 or value.shape[1] not in {1, 2}:
        raise ValueError("audition WAV must be mono or stereo")
    pcm = np.rint(np.clip(value, -1.0, 1.0 - 1.0 / (1 << 15)) * ((1 << 15) - 1)).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(int(value.shape[1]))
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate_hz))
        handle.writeframes(pcm.tobytes())


def _make_audition(source: Path, destination: Path) -> dict[str, Any]:
    signal, rate, header = read_unaltered_pcm_wav(source)
    audition, level = loudness_matched_audition(signal)
    _write_pcm16(destination, audition, rate)
    return {
        "source_path_alias": str(source),
        "source_sha256": str(header["sha256"]),
        "audition_path": str(destination),
        "audition_sha256": _sha256(destination),
        "sample_rate_hz": int(rate),
        "channels": int(header["channels"]),
        "frames": int(header["frames"]),
        "level": level,
        "analysis_signal": "unaltered_source_wav",
        "audition_signal": "loudness_matched_audition_signal_separate",
    }


def _under_download(path: Path) -> Path:
    resolved = path.resolve()
    root = ALLOWED_DOWNLOAD_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"output must stay under {root}: {resolved}")
    return resolved


def _write_csv(path: Path, cases: list[Mapping[str, Any]], package_sha256: str) -> None:
    columns = [
        "package_manifest_sha256",
        "test_id",
        "case_id",
        "vehicle_id",
        "scenario",
        "reference_sha256",
        "candidate_sha256",
        "listener_id",
        "playback_device",
        "windows_volume",
        "playback_endpoint",
        "system_audio_effects",
        *DIMENSIONS,
        "notes_zh",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "package_manifest_sha256": package_sha256,
                    "test_id": "s12-stage-s-r2-ab-20260822",
                    "case_id": case["case_id"],
                    "vehicle_id": case["vehicle_id"],
                    "scenario": case["scenario"],
                    "reference_sha256": case["reference"]["source_sha256"],
                    "candidate_sha256": case["candidate"]["source_sha256"],
                    "notes_zh": "请由 Jovi 填写；空白行不能导入为反馈。",
                }
            )


def build_package(manifest_path: Path, candidate_spec_path: Path, output_root: Path) -> dict[str, Any]:
    output_root = _under_download(output_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite populated package: {output_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate_spec = json.loads(candidate_spec_path.read_text(encoding="utf-8"))
    candidates = {str(row["recording_id"]): dict(row) for row in candidate_spec["cases"]}
    output_root.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    for recording in manifest.get("recordings", []):
        recording_id = str(recording.get("recording_id"))
        candidate = candidates.get(recording_id)
        if candidate is None:
            continue
        reference_path = Path(str(recording["external_path"]))
        candidate_path = Path(str(candidate["candidate_path"]))
        if not reference_path.is_file() or not candidate_path.is_file():
            raise FileNotFoundError(f"missing R2 A/B source for {recording_id}")
        expected_reference_sha = str(recording["sha256"])
        actual_reference_sha = _sha256(reference_path)
        if actual_reference_sha != expected_reference_sha:
            raise ValueError(f"reference SHA-256 mismatch for {recording_id}")
        expected_candidate_sha = str(candidate.get("candidate_sha256") or _sha256(candidate_path))
        actual_candidate_sha = _sha256(candidate_path)
        if actual_candidate_sha != expected_candidate_sha:
            raise ValueError(f"candidate SHA-256 mismatch for {recording_id}")
        case_id = recording_id.removeprefix("web_")
        ref_dest = output_root / "audio" / case_id / "reference_audition.wav"
        candidate_dest = output_root / "audio" / case_id / "candidate_audition.wav"
        reference_receipt = _make_audition(reference_path, ref_dest)
        candidate_receipt = _make_audition(candidate_path, candidate_dest)
        cases.append(
            {
                "case_id": case_id,
                "recording_id": recording_id,
                "reference_id": recording["reference_id"],
                "vehicle_id": recording["vehicle_id"],
                "scenario": recording["scenario"],
                "scenario_identity": recording.get("scenario_identity"),
                "license": recording["provenance"]["license"],
                "source_url": recording["provenance"]["source_url"],
                "reference": reference_receipt,
                "candidate": {
                    **candidate,
                    "source_sha256": actual_candidate_sha,
                    "audition": candidate_receipt,
                },
                "qualification": "R2_LIMITED_COMPARISON_ONLY",
                "order_hard_gate": False,
                "automatic_tuning_eligible": False,
                "feedback_status": "WAITING_FOR_JOVI",
            }
        )
    if not cases:
        raise ValueError("candidate spec selected no R2 manifest records")
    study = {
        "schema_version": SCHEMA_VERSION,
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "language": "zh-CN",
        "test_id": "s12-stage-s-r2-ab-20260822",
        "study_type": "paired_A_B",
        "source_policy": "raw_source_wav_stays_external; only audition copies are materialized in this external package",
        "analysis_policy": "do_not_use_audition_copy_for_metrics",
        "instructions_zh": [
            "每个案例先听 A（真实参考）再听 B（本地 synthetic 候选），保持同一播放设备和系统音量。",
            "不要把视频标题、车标或网页描述当作原厂排气证明；当前是 R2 相对比较。",
            "请记录车型身份、真实感、低频重量、机械感、加速攻击性、合成器伪影和偏好。没有 SHA 绑定的记录不导入。",
        ],
        "dimensions": [{"id": key, "label_zh": DIMENSION_LABELS_ZH[key], "scale": [0, 25, 50, 75, 100]} for key in DIMENSIONS],
        "cases": cases,
        "missing_anchor_cases": [
            {
                "vehicle_id": "rx7_fd",
                "status": "NOT_INCLUDED_R3_ONLY",
                "reason": "当前只有 CC BY-SA 旋转机械演示，不是 RX-7 FD 整车参考；不会把它当作 R2。",
            }
        ],
    }
    study_path = output_root / "study_manifest.json"
    study_path.write_text(json.dumps(study, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    study_sha = _sha256(study_path)
    binding = {
        "schema_version": SCHEMA_VERSION,
        "status": "WAITING_FOR_JOVI_HUMAN_FEEDBACK",
        "test_id": study["test_id"],
        "study_manifest_sha256": study_sha,
        "required_binding": [
            "study_manifest_sha256",
            "test_id",
            "case_id",
            "reference_sha256",
            "candidate_sha256",
            "listener_id",
            "playback_device",
            "windows_volume",
            "playback_endpoint",
            "system_audio_effects",
            *DIMENSIONS,
        ],
        "cases": {case["case_id"]: {"vehicle_id": case["vehicle_id"], "scenario": case["scenario"], "reference_sha256": case["reference"]["source_sha256"], "candidate_sha256": case["candidate"]["source_sha256"]} for case in cases},
    }
    binding_path = output_root / "feedback_binding.json"
    binding_path.write_text(json.dumps(binding, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    template_path = output_root / "feedback_template.csv"
    _write_csv(template_path, cases, study_sha)
    readme = output_root / "README_中文.md"
    readme.write_text(
        "# S12 R2 中文 A/B 听审包\n\n"
        "状态：`WAITING_FOR_JOVI_HUMAN_FEEDBACK`。本包只有外部 R2 合法参考的响度匹配试听副本；未校准 WAV 仍只用于分析，不能用试听副本计算指标。\n\n"
        "1. 依次播放 `audio/<case_id>/reference_audition.wav`（A）和 `candidate_audition.wav`（B）。\n"
        "2. 固定播放设备、Windows 音量、输出端点和系统音效；不要使用增强、EQ 或自动增益。\n"
        "3. 把反馈写入 `feedback_template.csv`，每一行必须填 listener_id、设备、音量、端点、系统音效和全部中文维度。\n"
        "4. 反馈必须保留 `study_manifest_sha256`、案例 ID、参考 SHA 和候选 SHA；空白模板不是真人反馈。\n\n"
        "Ferrari/Hellcat/Supra 是 R2 有限参考；RX-7 FD 当前未进入正式 A/B，因为现有 CC 音频不是整车 FD 录音。\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": study["status"],
        "study_manifest": str(study_path),
        "study_manifest_sha256": study_sha,
        "feedback_binding": str(binding_path),
        "feedback_template": str(template_path),
        "case_count": len(cases),
        "cases": [case["case_id"] for case in cases],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成仓库外中文 R2 A/B 听审包")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate-spec", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = build_package(args.manifest.resolve(), args.candidate_spec.resolve(), args.output_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
