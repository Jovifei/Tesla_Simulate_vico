"""Build and validate the Stage AA Hellcat v3 audition package."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

from ..stage_v.io import read_pcm24_wav, write_json, write_pcm24_wav
from ..stage_x.multi_reference_comparator import loudness_match_rms, raw_dynamic_metrics, timbre_metrics
from ..stage_z.method_ablation import render_final_scene, render_parent_scene
from .candidates import render_candidate
from .energy_budget import _band_metrics
from .reference_contract import build_reference_diagnostic_contract


REPO_ROOT = Path(__file__).resolve().parents[5]
V1_ROOT = Path("E:/Tesla_speed/review_packages/s12-stage-y-hellcat-layers-v1")
V2_ROOT = Path("E:/Tesla_speed/review_packages/s12-stage-y-hellcat-layers-v2")
SCENES = (
    ("hot_idle", "hot_idle_20s"),
    ("steady_1200", "steady_1200rpm"),
    ("steady_2000", "steady_2000rpm"),
    ("steady_3000", "steady_3000rpm"),
    ("tip_in", "throttle_tip_in"),
    ("full_load", "full_load_acceleration"),
    ("gear_shift", "gear_shift"),
    ("lift", "high_rpm_lift"),
    ("afterfire", "afterfire_eligible"),
    ("idle_return", "idle_return"),
    ("complete_cycle", "complete_cycle_60s"),
)
OUTPUT = Path("tasks/reports/runtime/s12-stage-aa/package_v3_manifest.json")
OBJECTIVE = Path("tasks/reports/runtime/s12-stage-aa/objective_before_after_v3.json")
RECEIPT = Path("tasks/reports/runtime/s12-stage-aa/receipts/aa6-v3-package.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metrics(audio: np.ndarray) -> dict[str, Any]:
    dynamic = raw_dynamic_metrics(audio, 48000)
    timbre = timbre_metrics(audio, 48000)
    return {
        **{key: float(value) for key, value in dynamic.items() if key != "note"},
        "spectral_centroid_hz": float(timbre["spectral_centroid_hz"]),
        "spectral_flux": float(timbre["spectral_flux"]),
        "roughness_proxy": float(timbre["roughness_proxy"]),
        "sharpness_proxy": float(timbre["sharpness_proxy"]),
        "tonality_proxy": float(timbre["tonality_proxy"]),
        "persistent_tone_ratio": float(timbre["persistent_tone_ratio"]),
        "narrowband_whine_proxy": float(timbre["narrowband_whine_proxy"]),
        "low_frequency_body_share": float(sum(_band_metrics(audio)[name]["power_share"] for name in ("20_80_hz", "120_250_hz", "250_400_hz"))),
    }


def _write_audio(root: Path, relative: str, audio: np.ndarray) -> str:
    path = root / relative
    receipt = write_pcm24_wav(path, np.asarray(audio, dtype=np.float64), 48000)
    return receipt.sha256


def _html_timbre(rows: list[dict[str, Any]]) -> str:
    blocks = []
    for row in rows:
        blocks.append(f"<section><h2>{row['label']}</h2><p>Reference Diagnostic: {row['reference_status']}</p><audio controls preload='none' src='{row['parent_timbre_path']}'></audio><audio controls preload='none' src='{row['stage_z_timbre_path']}'></audio><audio controls preload='none' src='{row['aa_timbre_path']}'></audio><p>顺序：Parent / Stage-Z / AA candidate；三者为共享 RMS 的 Timbre Review 派生试听。</p></section>")
    return "<!doctype html><meta charset='utf-8'><title>Hellcat Timbre Review</title><h1>Hellcat Timbre Review</h1><p>这是响度受控的相对音色比较；不是 Dynamic Review，也不是 R1/OEM 资格。</p>" + "".join(blocks)


def _html_dynamic(rows: list[dict[str, Any]]) -> str:
    blocks = []
    for row in rows:
        blocks.append(f"<section><h2>{row['label']}</h2><audio controls preload='none' src='{row['blind_b_path']}'></audio><audio controls preload='none' src='{row['blind_c_path']}'></audio><p>顺序：B / C。保持原始相对响度，不做逐段匹配。</p></section>")
    return "<!doctype html><meta charset='utf-8'><title>Hellcat Dynamic Review</title><h1>Hellcat Dynamic Review</h1><p>这是保持 idle→WOT、tip-in、shift、lift、afterfire、idle-return 相对动态的盲化 B/C 试听。</p>" + "".join(blocks)


def _html_answers(rows: list[dict[str, Any]]) -> str:
    lines = ["<!doctype html><meta charset='utf-8'><title>答案 manifest</title><h1>Dynamic Review 答案</h1><p>B = Stage-Z Final；C = AA-C3。此页用于复核，不要先看。</p><ul>"]
    lines.extend(f"<li>{row['label']}: B=Stage-Z Final, C=AA-C3</li>" for row in rows)
    lines.append("</ul>")
    return "".join(lines)


def _guide() -> str:
    return """# S12 Stage AA Hellcat v3 中文试听说明

## Timbre Review

先听 `timbre_review.html`。Parent、Stage-Z、AA candidate 使用共享 RMS 派生试听，只比较频谱包络、低频 body、roughness、sharpness、tonality 与机械纹理。

## Dynamic Review

再听 `dynamic_review.html`。B/C 默认盲化，不做逐段响度匹配；保留 idle→tip-in→WOT→shift→lift→idle return 的相对动态。不要把音量大小直接当成真实感。

Reference Diagnostic 只登记 canonical R2/R3 元数据；本包不复制外部音频。R1、OEM、Profile Freeze 与产品 Runtime 仍未通过。
"""


def build_stage_aa_package(root: Path, *, duration_s: float = 4.0, hot_idle_duration_s: float = 20.0, main_head: str = "unknown", tested_head: str = "unknown") -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    reference = build_reference_diagnostic_contract()
    write_json(root / "reference_diagnostic.json", reference)
    objective_rows: list[dict[str, Any]] = []
    page_rows: list[dict[str, Any]] = []
    for index, (label, trace_scene) in enumerate(SCENES, start=1):
        scene_duration = hot_idle_duration_s if label == "hot_idle" else duration_s
        print(f"[AA6 {index}/{len(SCENES)}] render {label}", flush=True)
        parent, _parent_raw, parent_monitor = render_parent_scene(trace_scene, scene_duration)
        stage_z_raw, _stage_z_raw2, stage_z_monitor, _diag, _elapsed, _memory = render_final_scene(trace_scene, scene_duration)
        aa = render_candidate("AA-C3", label, scene_duration)
        parent_raw_path = f"overall/{label}/parent.wav"
        stage_z_raw_path = f"overall/{label}/stage_z_final_raw.wav"
        stage_z_monitor_path = f"overall/{label}/stage_z_final_monitor.wav"
        aa_raw_path = f"overall/{label}/aa_c3_raw.wav"
        aa_monitor_path = f"overall/{label}/aa_c3_monitor.wav"
        parent_sha = _write_audio(root, parent_raw_path, parent)
        stage_z_sha = _write_audio(root, stage_z_raw_path, stage_z_raw)
        stage_z_monitor_sha = _write_audio(root, stage_z_monitor_path, stage_z_monitor)
        aa_sha = _write_audio(root, aa_raw_path, aa.raw_pcm)
        aa_monitor_sha = _write_audio(root, aa_monitor_path, aa.monitor_pcm)
        target_rms = min(float(np.sqrt(np.mean(np.square(x)))) for x in (parent, stage_z_raw, aa.raw_pcm) if np.any(x))
        parent_timbre_path = f"timbre_review/{label}/parent.wav"
        stage_z_timbre_path = f"timbre_review/{label}/stage_z.wav"
        aa_timbre_path = f"timbre_review/{label}/aa.wav"
        _write_audio(root, parent_timbre_path, loudness_match_rms(parent, target_rms))
        _write_audio(root, stage_z_timbre_path, loudness_match_rms(stage_z_raw, target_rms))
        _write_audio(root, aa_timbre_path, loudness_match_rms(aa.raw_pcm, target_rms))
        blind_b = f"dynamic_review/{label}/B.wav"
        blind_c = f"dynamic_review/{label}/C.wav"
        _write_audio(root, blind_b, stage_z_raw)
        _write_audio(root, blind_c, aa.raw_pcm)
        parent_metrics = _metrics(parent)
        stage_z_metrics = _metrics(stage_z_raw)
        aa_metrics = _metrics(aa.raw_pcm)
        objective_rows.append({"scene": label, "duration_s": scene_duration, "parent": parent_metrics, "stage_z_final": stage_z_metrics, "aa_c3": aa_metrics, "delta_stage_z_to_aa": {key: aa_metrics[key] - stage_z_metrics[key] for key in stage_z_metrics if isinstance(stage_z_metrics[key], (int, float))}})
        page_rows.append({"label": label, "reference_status": "R2/R3 diagnostic only; no embedded audio", "parent_timbre_path": parent_timbre_path, "stage_z_timbre_path": stage_z_timbre_path, "aa_timbre_path": aa_timbre_path, "blind_b_path": blind_b, "blind_c_path": blind_c, "parent_sha256": parent_sha, "stage_z_sha256": stage_z_sha, "stage_z_monitor_sha256": stage_z_monitor_sha, "aa_sha256": aa_sha, "aa_monitor_sha256": aa_monitor_sha})
    objective = {"schema": "s12.stage_aa.objective_before_after_v3", "status": "DIAGNOSTIC_ONLY", "comparison": "Parent vs Stage-Z Final vs AA-C3", "reference_status": "R1_MISSING_R2_R3_DIAGNOSTIC_ONLY", "rows": objective_rows, "human_status": "WAITING_FOR_JOVI_AUDITION", "oem_or_profile_claim": False}
    write_json(root / "objective_before_after_v3.json", objective)
    (root / "timbre_review.html").write_text(_html_timbre(page_rows), encoding="utf-8", newline="\n")
    (root / "dynamic_review.html").write_text(_html_dynamic(page_rows), encoding="utf-8", newline="\n")
    (root / "answers_manifest.html").write_text(_html_answers(page_rows), encoding="utf-8", newline="\n")
    (root / "AUDITION_GUIDE_ZH.md").write_text(_guide(), encoding="utf-8", newline="\n")
    excluded = {"package_manifest.json", "sha256_manifest.json"}
    file_hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in excluded:
            file_hashes[str(path.relative_to(root)).replace("\\", "/")] = _sha256(path)
    write_json(root / "sha256_manifest.json", {"schema": "s12.stage_aa.package_sha256_manifest.v1", "files": file_hashes})
    v1_manifest = V1_ROOT / "package_manifest.json"
    v2_manifest = V2_ROOT / "package_manifest.json"
    manifest = {
        "schema": "s12.stage_aa.audition_package.v3",
        "status": "WAITING_FOR_JOVI_AUDITION",
        "vehicle": "hellcat",
        "base_main_head": main_head,
        "tested_head": tested_head,
        "selected_candidate": "AA-C3",
        "scenes": [label for label, _ in SCENES],
        "scene_durations_s": {label: (hot_idle_duration_s if label == "hot_idle" else duration_s) for label, _ in SCENES},
        "overall_objects": ["parent", "stage_z_final_raw", "stage_z_final_monitor", "aa_c3_raw", "aa_c3_monitor"],
        "reference_diagnostic": "reference_diagnostic.json",
        "objective": "objective_before_after_v3.json",
        "sha256_manifest": "sha256_manifest.json",
        "pages": ["timbre_review.html", "dynamic_review.html", "answers_manifest.html"],
        "v1_manifest_sha256": _sha256(v1_manifest) if v1_manifest.is_file() else None,
        "v2_manifest_sha256": _sha256(v2_manifest) if v2_manifest.is_file() else None,
        "parent_final_sha_different": any(row["parent_sha256"] != row["stage_z_sha256"] for row in page_rows),
        "stage_z_aa_sha_different": any(row["stage_z_sha256"] != row["aa_sha256"] for row in page_rows),
        "boundaries": {"copied_third_party_audio": False, "copied_third_party_source": False, "copied_model_weight": False, "master_gain_repair": False, "ptr_radiation_track_p": "UNCHANGED", "r1_reference": "MISSING", "human_audition": "WAITING_FOR_JOVI"},
    }
    write_json(root / "package_manifest.json", manifest)
    return manifest


def validate_stage_aa_package(root: Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / "package_manifest.json"
    if not manifest_path.is_file():
        return ["package_manifest.json:missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "s12.stage_aa.audition_package.v3":
            errors.append("manifest:schema")
        if len(manifest.get("scenes", [])) != 11:
            errors.append("manifest:scene_count")
        for required in ("reference_diagnostic.json", "objective_before_after_v3.json", "sha256_manifest.json", "timbre_review.html", "dynamic_review.html", "answers_manifest.html", "AUDITION_GUIDE_ZH.md"):
            if not (root / required).is_file():
                errors.append(f"missing:{required}")
        sha_payload = json.loads((root / "sha256_manifest.json").read_text(encoding="utf-8"))
        for relative, expected in sha_payload.get("files", {}).items():
            path = root / relative
            if not path.is_file() or _sha256(path) != expected:
                errors.append(f"sha:{relative}")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"manifest_json:{exc.__class__.__name__}")
    dynamic = (root / "dynamic_review.html").read_text(encoding="utf-8") if (root / "dynamic_review.html").is_file() else ""
    if "Stage-Z" in dynamic or "AA-C3" in dynamic:
        errors.append("dynamic_page:blind_label_leak")
    answers = (root / "answers_manifest.html").read_text(encoding="utf-8") if (root / "answers_manifest.html").is_file() else ""
    if "Stage-Z" not in answers or "AA-C3" not in answers:
        errors.append("answers_page:mapping_missing")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".cpp", ".cc", ".h", ".hpp", ".rs", ".mr", ".mp3", ".ogg", ".flac"}:
            errors.append(f"third_party_or_external_file:{path.relative_to(root)}")
        if path.suffix.lower() == ".wav":
            try:
                audio, metadata = read_pcm24_wav(path)
                if metadata["channels"] != 2 or metadata["sample_rate_hz"] != 48000 or metadata["sample_width_bits"] != 24 or not np.all(np.isfinite(audio)) or metadata["clipping"]:
                    errors.append(f"wav_contract:{path.relative_to(root)}")
            except (OSError, ValueError) as exc:
                errors.append(f"wav_read:{path.relative_to(root)}:{exc.__class__.__name__}")
    return sorted(set(errors))


def publish_stage_aa_package(*, root: Path, main_head: str, tested_head: str, duration_s: float = 4.0, hot_idle_duration_s: float = 20.0, log_path: str | None = None, command: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    manifest = build_stage_aa_package(root, duration_s=duration_s, hot_idle_duration_s=hot_idle_duration_s, main_head=main_head, tested_head=tested_head)
    errors = validate_stage_aa_package(root)
    ended = datetime.now(timezone.utc)
    receipt = {"schema": "s12.stage_aa.v3_package_receipt.v1", "status": "PASS" if not errors else "FAIL", "main_head": main_head, "tested_head": tested_head, "package_root": str(root), "manifest_sha256": _sha256(Path(root) / "package_manifest.json"), "sha_manifest_sha256": _sha256(Path(root) / "sha256_manifest.json"), "scene_count": len(manifest["scenes"]), "wav_count": len(list(Path(root).rglob("*.wav"))), "validation_errors": errors, "command": command or [], "started_at_utc": started.isoformat().replace("+00:00", "Z"), "ended_at_utc": ended.isoformat().replace("+00:00", "Z"), "exit_code": 0 if not errors else 1, "log_path": log_path, "log_sha256": _sha256(Path(log_path)) if log_path and Path(log_path).is_file() else None}
    write_json(repo_root / RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--main-head", required=True)
    parser.add_argument("--tested-head", required=True)
    parser.add_argument("--duration-s", type=float, default=4.0)
    parser.add_argument("--hot-idle-duration-s", type=float, default=20.0)
    parser.add_argument("--log-path")
    args = parser.parse_args()
    receipt = publish_stage_aa_package(root=Path(args.package_root), main_head=args.main_head, tested_head=args.tested_head, duration_s=args.duration_s, hot_idle_duration_s=args.hot_idle_duration_s, log_path=args.log_path, command=sys.argv)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_stage_aa_package", "validate_stage_aa_package", "publish_stage_aa_package"]
