"""Analyze an externally-held Stage-Q source intake without copying raw media.

The intake is deliberately fail-closed: public video derivatives remain R3
when a licence receipt, exact stock/exhaust proof, and synchronized vehicle
state are missing.  This module only writes JSON/Markdown-derived evidence to
the approved external download root.  It never writes audio into Git and it
never updates a vehicle profile or starts MATLAB.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.sound_sim.s12.acoustic_comparator.core import ComparisonCase, compare_signals
from tools.sound_sim.s12.acoustic_comparator.psychoacoustics import proxy_metrics
from tools.sound_sim.s12.acoustic_comparator.spectral import spectrum_features
from tools.sound_sim.s12.acoustic_comparator.transients import transient_shape
from tools.sound_sim.s12.real_reference.stage_r_execute import read_unaltered_pcm_wav


SCHEMA_VERSION = "s12-stage-q-download-analysis-v1"
ALLOWED_DOWNLOAD_ROOT = Path(r"E:\Claude_allow\Download")
SYNTHETIC_CANDIDATE_RELATIVE = {
    "aventador_lp700": "tools/sound_sim/s12/acoustic_identity_v015/docs/aventador_lp700_ab.wav",
    "c63_w204": "tools/sound_sim/s12/acoustic_identity_v015/docs/c63_w204_ab.wav",
    "ferrari_458": "tools/sound_sim/s12/acoustic_identity_v015/docs/ferrari_458_ab.wav",
    "gtr_r35": "tools/sound_sim/s12/acoustic_identity_v015/docs/gtr_r35_ab.wav",
    "hellcat": "tools/sound_sim/s12/acoustic_identity_v015/docs/hellcat_ab.wav",
    "lfa": "tools/sound_sim/s12/acoustic_identity_v015/docs/lfa_ab.wav",
    "rx7_fd": "tools/sound_sim/s12/acoustic_identity_v015/docs/rx7_fd_ab.wav",
    "supra_jza80": "tools/sound_sim/s12/acoustic_identity_v015/docs/supra_jza80_ab.wav",
}

VISUAL_REVIEW = {
    "hellcat": {
        "vehicle_identity": "SUPPORTS_CHALLENGER_OR_CHARGER_HELLCAT_FAMILY",
        "notes": "三条画面均可见 Dodge 车身；第二条可见道路/仪表，第三条明确出现 Stock 与 Mid Muffler Delete 对照文字。",
    },
    "ferrari_458": {
        "vehicle_identity": "SUPPORTS_FERRARI_458_FAMILY",
        "notes": "三条画面可见 458 车身、方向盘或发动机；第三条有活动/赛道环境。",
    },
    "aventador_lp700": {
        "vehicle_identity": "SUPPORTS_AVENTADOR_FAMILY",
        "notes": "测功机、赛道飞行通过和 Roadster 启动画面均可见 Aventador；LP700/具体排气配置未由画面独立证明。",
    },
    "lfa": {
        "vehicle_identity": "SUPPORTS_LEXUS_LFA_FAMILY",
        "notes": "三条画面可见 LFA；第二、三条显示 Nürburgring/赛道编号等变体风险，不能当作普通原厂 LFA。",
    },
    "rx7_fd": {
        "vehicle_identity": "SUPPORTS_RX7_FD_OR_FD_FAMILY",
        "notes": "三条画面可见 RX-7/FD 车身或节目演示；改装/代际/排气状态未被画面独立确认。",
    },
    "c63_w204": {
        "vehicle_identity": "SUPPORTS_C63_AMG_W204_FAMILY",
        "notes": "三条画面可见 C63/AMG 车身；第三条是 Black Series 变体，第二条含漂移/赛道情境。",
    },
    "gtr_r35": {
        "vehicle_identity": "SUPPORTS_NISSAN_GT_R_R35_FAMILY",
        "notes": "三条画面可见 R35/GT-R；第二条标识为 NISMO，第三条为 Launch Control，精确年份/排气未完全确认。",
    },
    "supra_jza80": {
        "vehicle_identity": "SUPPORTS_SUPRA_JZA80_FAMILY",
        "notes": "三条画面可见 A80/2JZ Supra；第一条测功机，第二条 Mostly Stock，第三条标题为 Stock，但均没有可审计原厂排气凭证。",
    },
}

SELECTION_VARIANT_RISK = {
    "hellcat_03": "STOCK_VS_MID_MUFFLER_DELETE_MIXED_SCENARIO",
    "ferrari_03": "EVENT_OR_TRACK_CONTEXT",
    "aventador_01": "DYNO_FLAMES_OR_OVERRUN_CONTEXT",
    "aventador_03": "ROADSTER_VARIANT",
    "lfa_02": "NURBURGRING_EDITION_VARIANT_RISK",
    "lfa_03": "NURBURGRING_EDITION_OR_TRACK_VARIANT_RISK",
    "rx7_01": "PERIOD_TELEVISION_OR_VARIANT_UNCERTAINTY",
    "rx7_03": "TECHNICAL_SEQUENTIAL_TURBO_DEMO_UNKNOWN_CONFIGURATION",
    "c63_02": "DRIFT_OR_TRACK_CONTEXT",
    "c63_03": "BLACK_SERIES_VARIANT_RISK",
    "gtr_02": "NISMO_VARIANT_RISK",
    "gtr_03": "LAUNCH_CONTROL_CONTEXT",
    "supra_01": "DYNO_CONTEXT",
    "supra_02": "MOSTLY_STOCK_CLAIM_NOT_INDEPENDENTLY_VERIFIED",
    "supra_03": "STOCK_TITLE_CLAIM_NOT_INDEPENDENTLY_VERIFIED",
}


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_external_root(path: Path) -> Path:
    resolved = path.resolve()
    root = ALLOWED_DOWNLOAD_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"output must remain under {root}: {resolved}")
    return resolved


def _mono(signal: np.ndarray) -> np.ndarray:
    if signal.ndim == 1:
        return signal.astype(np.float64, copy=False)
    return signal.mean(axis=1, dtype=np.float64)


def _energy_windows(mono: np.ndarray, sample_rate_hz: int) -> dict[str, tuple[float, float]]:
    duration = mono.size / float(sample_rate_hz)
    if duration <= 0.0:
        raise ValueError("empty audio")
    width = min(5.0, max(2.0, duration))
    head = (0.0, min(width, duration))
    tail = (max(0.0, duration - width), duration)
    frame = max(1, int(round(sample_rate_hz * 0.25)))
    starts = np.arange(0, max(1, mono.size - frame + 1), frame, dtype=np.int64)
    if starts.size == 0:
        starts = np.array([0], dtype=np.int64)
    rms = np.asarray([np.sqrt(np.mean(np.square(mono[start : min(start + frame, mono.size)]))) for start in starts])
    peak_start = int(starts[int(np.argmax(rms))])
    max_start = max(0.0, duration - width)
    peak_center = (peak_start + frame / 2.0) / sample_rate_hz
    candidate_start = min(max(0.0, peak_center - width / 2.0), max_start)
    peak = (candidate_start, min(duration, candidate_start + width))
    return {"context_head": head, "scenario_candidate_peak": peak, "context_tail": tail}


def _segment_features(segment: np.ndarray, sample_rate_hz: int) -> dict[str, Any]:
    if segment.size < max(64, sample_rate_hz // 20):
        raise ValueError("segment is too short for feature extraction")
    spectral, _, _ = spectrum_features(segment, sample_rate_hz)
    psycho = proxy_metrics(segment, sample_rate_hz, spectral["centroid_hz"])
    return {
        "samples": int(segment.size),
        "duration_s": float(segment.size / sample_rate_hz),
        "spectral": spectral,
        "psychoacoustic_proxies": psycho,
        "transient_shape": transient_shape(segment, sample_rate_hz),
    }


def _resample(signal: np.ndarray, source_rate_hz: int, target_rate_hz: int) -> np.ndarray:
    if source_rate_hz == target_rate_hz:
        return signal
    if signal.size < 2:
        return signal
    output_size = max(2, int(round(signal.shape[0] * target_rate_hz / source_rate_hz)))
    source_x = np.arange(signal.shape[0], dtype=np.float64)
    target_x = np.linspace(0.0, signal.shape[0] - 1.0, output_size)
    if signal.ndim == 1:
        return np.interp(target_x, source_x, signal).astype(np.float64)
    return np.column_stack([np.interp(target_x, source_x, signal[:, channel]) for channel in range(signal.shape[1])])


def _comparator_summary(
    record: Mapping[str, Any],
    reference_segment: np.ndarray,
    reference_rate_hz: int,
    candidate: np.ndarray,
    candidate_path: Path,
) -> dict[str, Any]:
    target_rate_hz = 48_000
    reference = _resample(reference_segment, reference_rate_hz, target_rate_hz)
    case = ComparisonCase(
        vehicle_id=str(record["vehicle_id"]),
        scenario=str(record["scenario"]),
        reference_id=str(record["recording_id"]),
        candidate_id=f"{record['vehicle_id']}_ab_candidate",
        sample_rate_hz=target_rate_hz,
        reference_rpm=(0.0, 0.0),
        candidate_rpm=(0.0, 0.0),
        reference_load=(0.0, 0.0),
        candidate_load=(0.0, 0.0),
        analysis_domain="unaltered_analysis_signal",
        reference_kind="external_recording",
        reference_provenance=(
            f"external_path_alias={record['wav_path']};"
            f"source_url={record['source_url']};wav_sha256={record['wav_sha256']}"
        ),
        candidate_source_commit="working-tree-s12-stage-q-real-reference-calibration",
        microphone_setup_uncertainty="UNKNOWN_PUBLIC_VIDEO_CAPTURE",
    )
    result = compare_signals(reference, candidate, case, candidate_domain="unaltered_analysis_signal")
    spectral = result.get("spectral", {})
    psycho = result.get("psychoacoustics", {})
    bands = result.get("bands", {})
    return {
        "selection_id": record["selection_id"],
        "vehicle_id": record["vehicle_id"],
        "scenario": record["scenario"],
        "reference_segment": "scenario_candidate_peak",
        "reference_wav_path": record["wav_path"],
        "reference_wav_sha256": record["wav_sha256"],
        "candidate_wav_path": str(candidate_path),
        "candidate_sample_rate_hz": target_rate_hz,
        "reference_resampled_for_comparison": reference_rate_hz != target_rate_hz,
        "qualification": "R3_DIAGNOSTIC_ONLY",
        "identity_score_available": False,
        "automatic_tuning_eligible": False,
        "recommendation_status": "WITHHELD_UNTIL_LAWFUL_REFERENCE_STATE_AND_JOVI_AB_FEEDBACK",
        "spectral_log_distance": spectral.get("log_distance"),
        "centroid_delta_hz": spectral.get("centroid_delta_hz"),
        "rolloff_delta_hz": spectral.get("rolloff_delta_hz"),
        "contrast_delta_db": spectral.get("contrast_delta_db"),
        "loudness_delta_db": (result.get("loudness") or {}).get("delta_db"),
        "band_deltas": {name: values.get("delta") for name, values in bands.items()},
        "psychoacoustic_deltas": {
            name: psycho.get(name)
            for name in (
                "sharpness_proxy_delta",
                "roughness_proxy_delta",
                "fluctuation_proxy_delta",
                "tonality_proxy_delta",
            )
        },
        "alignment": result.get("alignment"),
        "order": {
            "status": "not_evaluated_without_rpm_trace",
            "rpm_compatible": False,
            "reference_rpm": [0.0, 0.0],
            "candidate_rpm": [0.0, 0.0],
        },
        "uncertainty": {
            "legal_permission": "UNVERIFIED",
            "stock_exhaust_confirmation": "UNVERIFIED",
            "synchronized_rpm_load_gear": "MISSING",
            "microphone_and_agc": "UNKNOWN",
            "source_is_lossy_video_derivative": True,
            "segment_confidence": "LOW",
        },
    }


def _summary_stats(values: list[float]) -> dict[str, float | None]:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=np.float64)
    if finite.size == 0:
        return {"median": None, "q25": None, "q75": None, "min": None, "max": None}
    return {
        "median": float(np.median(finite)),
        "q25": float(np.quantile(finite, 0.25)),
        "q75": float(np.quantile(finite, 0.75)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
    }


def _parameter_diagnostics(comparisons: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for item in comparisons:
        grouped.setdefault(str(item["vehicle_id"]), []).append(item)
    recommendations: list[dict[str, Any]] = []
    for vehicle_id, items in sorted(grouped.items()):
        band_stats = {
            band: _summary_stats([float(item["band_deltas"].get(band) or 0.0) for item in items])
            for band in next(iter(items))["band_deltas"]
        }
        largest_band = max(
            band_stats,
            key=lambda band: abs(float(band_stats[band]["median"] or 0.0)),
        )
        largest_delta = float(band_stats[largest_band]["median"] or 0.0)
        if largest_delta > 0.0:
            direction = "本地候选在该频段相对公开录音偏高；仅在 Jovi 人耳确认后考虑降低"
        elif largest_delta < 0.0:
            direction = "本地候选在该频段相对公开录音偏低；仅在 Jovi 人耳确认后考虑增加"
        else:
            direction = "该频段没有稳定方向；不提出增益动作"
        recommendations.append(
            {
                "vehicle_id": vehicle_id,
                "status": "DIAGNOSTIC_SUGGESTION_ONLY",
                "action": "WITHHELD_NO_AUTO_TUNING",
                "evidence_level": "R3",
                "largest_spread_band": largest_band,
                "directional_note_zh": direction,
                "band_delta_summary": band_stats,
                "centroid_delta_hz": _summary_stats([float(item["centroid_delta_hz"] or 0.0) for item in items]),
                "loudness_delta_db": _summary_stats([float(item["loudness_delta_db"] or 0.0) for item in items]),
                "uncertainty": {
                    "confidence": "LOW",
                    "between_source_variation": "SEE_Q25_Q75_AND_MIN_MAX",
                    "legal_permission": "UNVERIFIED",
                    "stock_exhaust_confirmation": "UNVERIFIED",
                    "rpm_load_gear_sync": "MISSING",
                    "microphone_agc": "UNKNOWN",
                    "requires_jovi_human_ab": True,
                },
                "profile_update": "FORBIDDEN",
            }
        )
    return recommendations


def analyze(manifest_path: Path, output_root: Path, repo_root: Path) -> dict[str, Any]:
    output_root = _require_external_root(output_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 24:
        raise ValueError("combined manifest must contain exactly 24 records")
    candidate_cache: dict[str, tuple[np.ndarray, int, Path]] = {}
    for vehicle_id, relative in SYNTHETIC_CANDIDATE_RELATIVE.items():
        path = (repo_root / relative).resolve()
        signal, rate, _ = read_unaltered_pcm_wav(path)
        candidate_cache[vehicle_id] = (signal, rate, path)

    features_root = output_root / "derived_features_v1"
    features_root.mkdir(parents=True, exist_ok=True)
    segments: list[dict[str, Any]] = []
    feature_records: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        wav_path = Path(str(record["wav_path"]))
        if not wav_path.is_file():
            raise FileNotFoundError(wav_path)
        actual_sha = _sha256(wav_path)
        if actual_sha != str(record["wav_sha256"]):
            raise ValueError(f"WAV SHA-256 mismatch for {record['selection_id']}")
        signal, sample_rate_hz, header = read_unaltered_pcm_wav(wav_path)
        mono = _mono(signal)
        windows = _energy_windows(mono, sample_rate_hz)
        source_segments: list[dict[str, Any]] = []
        segment_feature_map: dict[str, Any] = {}
        for segment_name, (start_s, end_s) in windows.items():
            start = int(round(start_s * sample_rate_hz))
            end = max(start + 1, int(round(end_s * sample_rate_hz)))
            end = min(end, mono.size)
            segment = mono[start:end]
            feature = _segment_features(segment, sample_rate_hz)
            segment_record = {
                "selection_id": record["selection_id"],
                "vehicle_id": record["vehicle_id"],
                "recording_id": record["recording_id"],
                "segment_id": f"{record['selection_id']}::{segment_name}",
                "segment_name": segment_name,
                "scenario_label": record["scenario"],
                "start_s": float(start / sample_rate_hz),
                "end_s": float(end / sample_rate_hz),
                "status": "PROVISIONAL_NO_SYNC_STATE",
                "source": "energy_peak_heuristic_plus_catalog_scenario",
                "confidence": "LOW",
                "usable_for_order_or_tuning": False,
            }
            segments.append(segment_record)
            source_segments.append(segment_record)
            segment_feature_map[segment_name] = feature
        feature_payload = {
            "schema_version": SCHEMA_VERSION,
            "selection_id": record["selection_id"],
            "vehicle_id": record["vehicle_id"],
            "recording_id": record["recording_id"],
            "scenario": record["scenario"],
            "source_url": record["source_url"],
            "source_page_url": record["source_page_url"],
            "external_wav_path_alias": str(wav_path),
            "wav_sha256": actual_sha,
            "video_sha256": record["video_sha256"],
            "analysis_domain": "relative_recording_features_only_unaltered_pcm",
            "pcm_header": header,
            "classification": "R3",
            "evidence_level": record["evidence"]["level"],
            "visual_review": {
                **VISUAL_REVIEW.get(str(record["vehicle_id"]), {}),
                "selection_variant_risk": SELECTION_VARIANT_RISK.get(str(record["selection_id"])),
                "vehicle_identity_status": "VISUAL_IDENTITY_SUPPORT_ONLY",
                "stock_exhaust_status": "NOT_CONFIRMED",
                "review_method": "contact_sheet_visual_inspection_2026-08-22",
            },
            "segments": source_segments,
            "features": segment_feature_map,
            "state_trace": {
                "rpm": "MISSING",
                "load_throttle": "MISSING",
                "gear_shift": "MISSING",
                "microphone_position": "UNKNOWN",
                "recording_device_agc": "UNKNOWN",
            },
            "raw_media_policy": "external_only_not_in_git",
        }
        feature_path = features_root / f"{record['selection_id']}.json"
        _write_json(feature_path, feature_payload)
        feature_records.append(
            {
                "selection_id": record["selection_id"],
                "vehicle_id": record["vehicle_id"],
                "external_wav_path_alias": str(wav_path),
                "wav_sha256": actual_sha,
                "video_sha256": record["video_sha256"],
                "derived_feature_path": str(feature_path),
                "classification": "R3",
                "scenario_segment_status": "PROVISIONAL_NO_SYNC_STATE",
            }
        )
        candidate_signal, candidate_rate, candidate_path = candidate_cache[str(record["vehicle_id"])]
        peak = windows["scenario_candidate_peak"]
        start = int(round(peak[0] * sample_rate_hz))
        end = min(mono.size, max(start + 1, int(round(peak[1] * sample_rate_hz))))
        comparisons.append(
            _comparator_summary(record, mono[start:end], sample_rate_hz, candidate_signal, candidate_path)
        )
        print(f"[{index}/24] processed {record['selection_id']}")

    segments_path = output_root / "scenario_segments_v1.json"
    _write_json(
        segments_path,
        {
            "schema_version": SCHEMA_VERSION,
            "status": "PROVISIONAL_NO_SYNC_STATE",
            "usable_for_order_or_tuning": False,
            "records": segments,
        },
    )
    comparison_path = output_root / "comparator_diagnostics_v1.json"
    _write_json(
        comparison_path,
        {
            "schema_version": SCHEMA_VERSION,
            "status": "COMPLETE_DIAGNOSTIC_ONLY_R3",
            "raw_media_policy": "external_only_not_in_git",
            "identity_score_available": False,
            "automatic_tuning_eligible": False,
            "records": comparisons,
        },
    )
    recommendation_path = output_root / "parameter_diagnostics_v1.json"
    recommendations = _parameter_diagnostics(comparisons)
    _write_json(
        recommendation_path,
        {
            "schema_version": SCHEMA_VERSION,
            "status": "WITHHELD_NO_AUTO_TUNING",
            "recommendations": recommendations,
        },
    )
    ab_path = output_root / "human_ab_package_v1.json"
    _write_json(
        ab_path,
        {
            "schema_version": SCHEMA_VERSION,
            "language": "zh-CN",
            "status": "WAITING_FOR_JOVI_LISTENING",
            "instructions": [
                "使用相同播放音量进行 A/B；不要把视频标题或车标当作原厂证明。",
                "分别记录低频主体、中频机械感、高频刺耳/空气感、瞬态攻击和回火；没有主观记录就不推进参数建议。",
                "此包只引用外部 WAV 路径和仓库内合成候选，不复制任何原始版权音频。",
            ],
            "trials": [
                {
                    "trial_id": item["selection_id"],
                    "vehicle_id": item["vehicle_id"],
                    "reference_wav_path_alias": item["reference_wav_path"],
                    "reference_wav_sha256": item["reference_wav_sha256"],
                    "reference_segment": item["reference_segment"],
                    "candidate_wav_path": item["candidate_wav_path"],
                    "feedback": None,
                }
                for item in comparisons
            ],
        },
    )
    analysis_manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "COMPLETE_DIAGNOSTIC_ONLY_R3",
        "source_library_archive_sha256": manifest.get("source_library_archive_sha256"),
        "source_library_archive_path": manifest.get("source_library_archive_path"),
        "selected_source_count": len(feature_records),
        "selected_per_vehicle": {vehicle: sum(row["vehicle_id"] == vehicle for row in feature_records) for vehicle in sorted(SYNTHETIC_CANDIDATE_RELATIVE)},
        "classification_counts": {"R1": 0, "R2": 0, "R3": len(feature_records)},
        "raw_media_policy": "external_only_not_in_git",
        "feature_records": feature_records,
        "outputs": {
            "scenario_segments": str(segments_path),
            "comparator_diagnostics": str(comparison_path),
            "parameter_diagnostics": str(recommendation_path),
            "human_ab_package": str(ab_path),
        },
        "blocked_gates": [
            "legal_permission_or_licence_receipt",
            "exact_stock_exhaust_confirmation",
            "synchronized_rpm_trace",
            "load_throttle_trace",
            "gear_shift_trace",
            "microphone_position_and_recording_agc_contract",
            "Jovi_human_A_B_feedback",
        ],
    }
    manifest_output = output_root / "source_analysis_manifest_v1.json"
    _write_json(manifest_output, analysis_manifest)
    return analysis_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="combined URL intake manifest")
    parser.add_argument("--output-root", type=Path, required=True, help="approved external output root")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="repository root containing synthetic candidates")
    args = parser.parse_args()
    result = analyze(args.manifest.resolve(), args.output_root.resolve(), args.repo_root.resolve())
    print(json.dumps({"status": result["status"], "selected_source_count": result["selected_source_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
