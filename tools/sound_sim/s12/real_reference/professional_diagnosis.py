"""Plain-language R2 diagnosis and bounded candidate specifications."""
from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .professional_clip_analysis import load_exact_anchor_pairs
from .professional_receipts import merge_professional_receipts


def _mean_band(pairs: Sequence[Mapping[str, Any]], band: str) -> float:
    values = [float(pair["legacy_proxy"]["bands"][band]["delta"]) for pair in pairs if pair.get("legacy_proxy", {}).get("bands", {}).get(band)]
    return sum(values) / len(values) if values else 0.0


def _mean_professional_delta(pairs: Sequence[Mapping[str, Any]], domain: str, metric: str) -> float | None:
    values = [pair.get(domain, {}).get("delta", {}).get(metric) for pair in pairs]
    values = [float(value) for value in values if isinstance(value, (int, float))]
    return sum(values) / len(values) if values else None


def _item(text: str, basis: str, values: Mapping[str, Any], uncertainty: str) -> dict[str, Any]:
    return {
        "diagnosis_zh": text,
        "basis": basis,
        "observed_values": dict(values),
        "uncertainty": uncertainty,
        "not_a_similarity_score": True,
    }


def build_plain_language_diagnosis(pair_metrics: Mapping[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for pair in pair_metrics.get("pairs", []):
        grouped[str(pair.get("vehicle_id"))].append(pair)
    vehicles: list[dict[str, Any]] = []
    for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
        pairs = grouped.get(vehicle_id, [])
        items: list[dict[str, Any]] = []
        b = lambda name: _mean_band(pairs, name)
        roughness_matlab = _mean_professional_delta(pairs, "matlab", "roughness_asper")
        roughness_mosqito = _mean_professional_delta(pairs, "mosqito", "roughness_asper")
        if vehicle_id == "ferrari_458":
            if b("120_250") + b("250_400") < -0.12:
                items.append(_item("120–400Hz主体不足，主体声压和攻击感偏弱。", "Legacy Proxy 频带能量", {"120_250_delta": b("120_250"), "250_400_delta": b("250_400")}, "R3来源/麦位/AGC/工况不确定"))
            if b("1000_4000") > 0.20:
                items.append(_item("1–4kHz相对偏高，候选可能更集中、更像窄带中高频。", "Legacy Proxy 频带能量", {"1000_4000_delta": b("1000_4000")}, "不是绝对 SPL；仅作相对方向"))
            if b("4000_5500") < -0.003 or b("5500_12000") < -0.002:
                items.append(_item("4kHz以上真实 metallic 层偏弱，需检查高阶包络和金属质感。", "Legacy Proxy 高频频带", {"4000_5500_delta": b("4000_5500"), "5500_12000_delta": b("5500_12000")}, "公开视频压缩和麦位未知"))
            if roughness_matlab is not None and roughness_matlab < -0.02:
                items.append(_item("MATLAB 粗糙度差值偏低，机械粗糙度和动态生命感可能偏弱。", "Professional MATLAB roughness_asper", {"delta": roughness_matlab}, "数字域相对值，不是绝对声学标定"))
        elif vehicle_id == "hellcat":
            if b("20_60") + b("60_120") > 0.10:
                items.append(_item("20–120Hz相对偏多，声音容易闷或低频堆积。", "Legacy Proxy 频带能量", {"20_60_delta": b("20_60"), "60_120_delta": b("60_120")}, "R3来源与排气状态未知"))
            if b("120_250") + b("250_400") < -0.10:
                items.append(_item("120–400Hz不足，V8压力和加速攻击感可能不够。", "Legacy Proxy 频带能量", {"120_250_delta": b("120_250"), "250_400_delta": b("250_400")}, "无 RPM/load 同步，不能做阶次判断"))
            if b("400_1000") > 0.06:
                items.append(_item("400–1000Hz偏多，可能产生箱体感或中频拥挤。", "Legacy Proxy 频带能量", {"400_1000_delta": b("400_1000")}, "仅相对频带方向"))
            if roughness_matlab is not None:
                items.append(_item("MATLAB 粗糙度差值已列出，需由 Jovi 判断是自然机械纹理还是伪影。", "Professional MATLAB roughness_asper", {"delta": roughness_matlab}, "MoSQITo/ MATLAB 指标单位不同，不直接合并"))
        elif vehicle_id == "rx7_fd":
            if b("120_250") > 0.20:
                items.append(_item("120–250Hz单峰过强，当前更像窄带嗡鸣而不是宽频转子+涡轮。", "Legacy Proxy 频带能量", {"120_250_delta": b("120_250")}, "RX-7sim配置/麦位/压缩状态不确定"))
            if b("60_120") < -0.05 and b("400_1000") + b("1000_4000") < -0.15:
                items.append(_item("60–120Hz与400Hz–4kHz不足，宽频转子/涡轮层可能不完整。", "Legacy Proxy 频带能量", {"60_120_delta": b("60_120"), "400_1000_delta": b("400_1000"), "1000_4000_delta": b("1000_4000")}, "无同步状态，不能作 Order 结论"))
            if roughness_mosqito is not None:
                items.append(_item("MoSQITo 粗糙度差值已列出，需 Jovi 判断机械纹理是否自然。", "Professional MoSQITo roughness_asper", {"delta": roughness_mosqito}, "MoSQITo 当前不提供 fluctuation_vacil"))
        vehicles.append({
            "vehicle_id": vehicle_id,
            "pair_count": len(pairs),
            "items": items,
            "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
            "reference_class": "R3",
            "human_confirmation_required": True,
        })
    return {
        "schema_version": "s12-professional-plain-language-diagnosis-v1",
        "overall_status": "R2_DIAGNOSTIC_ONLY_NO_TOTAL_SIMILARITY",
        "total_similarity_percent": None,
        "vehicles": vehicles,
        "software_domains": ["Professional MATLAB", "Professional MoSQITo", "Legacy Proxy"],
        "limitations_zh": [
            "参考音频为 R3 页面试听片段，不是 R1 原始录音。",
            "没有同步 RPM/load/throttle/gear/shift，因此 Order 不资格。",
            "数字域指标不是绝对 SPL，不能输出一个总相似度百分比。",
            "Jovi 只需确认诊断是否符合听感，不需要判断具体频率。",
        ],
    }


_ANCHOR_CONFIG = {
    "ferrari_458": {
        "parameter_group": "metallic_high_order_envelope_mid_band",
        "axes": {"metallic_envelope_db": (-3.0, -1.0, 1.0, 3.0), "mid_band_balance_db": (-3.0, -1.0, 1.0, 3.0), "texture_mix": (0.0, 0.33, 0.66, 1.0)},
    },
    "hellcat": {
        "parameter_group": "pressure_attack_blower_intake_balance",
        "axes": {"pressure_attack_db": (-3.0, -1.0, 1.0, 3.0), "blower_intake_balance": (-0.25, -0.08, 0.08, 0.25), "mid_band_pressure_db": (-3.0, -1.0, 1.0, 3.0)},
    },
    "rx7_fd": {
        "parameter_group": "rotary_housing_turbo_distribution",
        "axes": {"housing_peak_db": (-3.0, -1.0, 1.0, 3.0), "turbo_band_balance_db": (-3.0, -1.0, 1.0, 3.0), "broadband_mix": (0.0, 0.33, 0.66, 1.0)},
    },
}


def build_r2_diagnostic_plan(pair_metrics: Mapping[str, Any]) -> dict[str, Any]:
    anchors: list[dict[str, Any]] = []
    for vehicle_id, config in _ANCHOR_CONFIG.items():
        names = list(config["axes"])
        values = list(config["axes"].values())
        specs = []
        for index, combination in enumerate(itertools.product(*values), start=1):
            specs.append({
                "candidate_id": f"{vehicle_id}_r2_diag_{index:02d}",
                "parameter_group": config["parameter_group"],
                "parameter_values": dict(zip(names, combination)),
                "bounded": True,
                "rendered": False,
                "source_modified": False,
            })
        anchors.append({
            "vehicle_id": vehicle_id,
            "parameter_group": config["parameter_group"],
            "candidate_spec_count": len(specs),
            "candidate_specs": specs,
            "hard_gates_required": ["Track-P unchanged", "finite PCM", "clipping=0", "wrong-condition events=0", "state regression", "non-target SHA unchanged", "package integrity"],
            "soft_objective": ["R2 frequency residual", "MATLAB psychoacoustic residual", "MoSQITo residual", "parameter change penalty", "artifact penalty"],
            "order_timing_modification": "FORBIDDEN_WITHOUT_RPM_TRACE",
        })
    return {
        "schema_version": "s12-r2-diagnostic-parameter-plan-v1",
        "status": "R2_DIAGNOSTIC_CANDIDATE_READY",
        "review_status": "WAITING_FOR_JOVI_GUIDED_REVIEW",
        "anchors": anchors,
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "profile_update": "FORBIDDEN",
        "source_modification": "FORBIDDEN_UNTIL_JOVI_GUIDED_REVIEW",
    }


def build_bounded_candidate_results(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "s12-r2-diagnostic-candidate-results-v1",
        "status": "WAITING_FOR_JOVI_GUIDED_REVIEW",
        "candidate_execution": "SPECIFICATIONS_ONLY_NOT_RENDERED",
        "objective_before_after_claim": "NOT_CLAIMED",
        "anchors": [
            {
                "vehicle_id": anchor["vehicle_id"],
                "parameter_group": anchor["parameter_group"],
                "candidate_spec_count": anchor["candidate_spec_count"],
                "evaluated_count": 0,
                "objective_before": None,
                "objective_after": None,
                "hard_gate_status": "NOT_RUN_NO_SOURCE_MODIFICATION",
                "candidate_specs": anchor["candidate_specs"],
            }
            for anchor in plan.get("anchors", [])
        ],
        "automatic_tuning_eligible": False,
        "profile_candidate_ready": False,
        "profile_update": "FORBIDDEN",
    }


def build_professional_pair_metrics(pairs: Sequence[Mapping[str, Any]], matlab: Mapping[str, Any], mosqito: Mapping[str, Any], proxy: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return merge_professional_receipts(pairs, matlab, mosqito, proxy)


def write_diagnosis_outputs(pair_metrics: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnosis = build_plain_language_diagnosis(pair_metrics)
    plan = build_r2_diagnostic_plan(pair_metrics)
    results = build_bounded_candidate_results(plan)
    paths = {
        "diagnosis": output_dir / "professional_plain_language_diagnosis.json",
        "plan": output_dir / "r2_diagnostic_parameter_plan.json",
        "results": output_dir / "r2_diagnostic_candidate_results.json",
    }
    for key, payload in (("diagnosis", diagnosis), ("plan", plan), ("results", results)):
        paths[key].write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return paths


__all__ = ["build_bounded_candidate_results", "build_plain_language_diagnosis", "build_professional_pair_metrics", "build_r2_diagnostic_plan", "write_diagnosis_outputs"]
