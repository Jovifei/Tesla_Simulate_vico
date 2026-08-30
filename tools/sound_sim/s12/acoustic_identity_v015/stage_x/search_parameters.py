"""Stage X Hellcat parameter definitions and reachability harness.

Each search parameter maps to an event-domain config mutation. A parameter
is REACHABLE only when the renderer consumes it (diagnostics/parameter
consumption), the rendered WAV changes (SHA), a target metric moves, and
non-target movement stays bounded. Unreachable parameters are excluded
from the search and reported as PARAMETER_NOT_REACHABLE.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from ..event_domain.config_schema import load_config, parameter, unwrap
from ..stage_v.io import write_json
from .multi_reference_comparator import raw_dynamic_metrics, timbre_metrics

REACHABILITY_SCHEMA = "s12.stage_x.parameter_reachability.v1"
PARAMETER_NOT_REACHABLE = "PARAMETER_NOT_REACHABLE"
PARAMETER_REACHABLE = "PARAMETER_REACHABLE"


@dataclass(frozen=True)
class SearchParameter:
    name: str
    baseline: float
    delta: float
    apply: Callable[[dict[str, Any], float], None]
    target_metrics: tuple[str, ...]
    guard_metrics: tuple[str, ...] = ()
    unit: str = "normalized"
    note: str = ""
    architecture: str = "P2H"
    scenes: tuple[tuple[str, float], ...] = (("hot_idle_20s", 2.0), ("full_load_acceleration", 2.0))
    stem: str = "post_ptr"


def _set_parameter(config: dict[str, Any], path: str, value: Any) -> None:
    """Set an existing parameter node's value, preserving provenance keys."""
    node: Any = config
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]]["value"] = value


def _scale_spread(config: dict[str, Any], key: str, spread: float) -> None:
    values = np.asarray(unwrap(config, key), dtype=np.float64)
    mean = float(np.mean(values))
    if np.allclose(values, mean):
        pattern = np.array([1.0 if index % 2 == 0 else -1.0 for index in range(values.size)], dtype=np.float64)
        values = mean * (1.0 + 0.22 * pattern)
    _set_parameter(config, key, list(mean + (values - mean) * spread))


def _band_120_400(audio: np.ndarray, sample_rate: int) -> float:
    metrics = timbre_metrics(audio, sample_rate)
    shares = metrics["fine_band_shares"]
    return shares[2] + shares[3]  # 120-250 + 250-400


def _low_band(audio: np.ndarray, sample_rate: int) -> float:
    return timbre_metrics(audio, sample_rate)["fine_band_shares"][0] + timbre_metrics(audio, sample_rate)["fine_band_shares"][1]


def _mid_band(audio: np.ndarray, sample_rate: int) -> float:
    return timbre_metrics(audio, sample_rate)["fine_band_shares"][4] + timbre_metrics(audio, sample_rate)["fine_band_shares"][5]


def _high_band(audio: np.ndarray, sample_rate: int) -> float:
    return timbre_metrics(audio, sample_rate)["fine_band_shares"][6] + timbre_metrics(audio, sample_rate)["fine_band_shares"][7]


METRIC_FUNCS: dict[str, Callable[[np.ndarray, int], float]] = {
    "low_band_share": _low_band,
    "band_120_400": _band_120_400,
    "mid_band_share": _mid_band,
    "high_band_share": _high_band,
    "tonality": lambda audio, sr: timbre_metrics(audio, sr)["tonality_proxy"],
    "sharpness": lambda audio, sr: timbre_metrics(audio, sr)["sharpness_proxy"],
    "roughness": lambda audio, sr: timbre_metrics(audio, sr)["roughness_proxy"],
    "flux": lambda audio, sr: timbre_metrics(audio, sr)["spectral_flux"],
    "centroid": lambda audio, sr: timbre_metrics(audio, sr)["spectral_centroid_hz"],
    "crest": lambda audio, sr: raw_dynamic_metrics(audio, sr)["crest_db"],
    "dynamic_range": lambda audio, sr: raw_dynamic_metrics(audio, sr)["dynamic_range_db"],
    "transient_density": lambda audio, sr: raw_dynamic_metrics(audio, sr)["transient_event_density_per_s"],
}


def _fixed(value: float, unit: str, source: str) -> dict[str, Any]:
    return parameter(value, unit, "search_override", source=source, verification_state="synthetic_assumption")


def hellcat_search_parameters() -> list[SearchParameter]:
    """The 27 contract parameters mapped onto event-domain config mutations."""
    return [
        SearchParameter("combustion_event_energy", 0.60, 0.18, lambda c, v: _set_parameter(c, "combustion_event.event_energy", v), ("crest", "transient_density", "low_band_share"), ("centroid",), unit="normalized_pressure", note="per-event pressure energy"),
        SearchParameter("combustion_rise_time", 0.0035, 0.0012, lambda c, v: _set_parameter(c, "combustion_event.rise_time_s", v), ("band_120_400", "sharpness"), ("low_band_share",), unit="s"),
        SearchParameter("combustion_decay_time", 0.030, 0.008, lambda c, v: _set_parameter(c, "combustion_event.decay_time_s", v), ("low_band_share", "dynamic_range"), ("tonality",), unit="s"),
        SearchParameter("cycle_variation", 0.08, 0.03, lambda c, v: _set_parameter(c, "cycle_variation", v), ("roughness", "flux"), ("centroid",), unit="normalized"),
        SearchParameter("crank_inertia", 0.34, 0.10, lambda c, v: _set_parameter(c, "crank_inertia", v), ("flux", "dynamic_range"), (), unit="kg_m2", scenes=(("hot_idle_20s", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("idle_governor", 0.22, 0.07, lambda c, v: _set_parameter(c, "idle_governor", v), ("flux", "dynamic_range"), (), unit="normalized_torque", scenes=(("hot_idle_20s", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("primary_length_spread", 1.0, 0.25, lambda c, v: _scale_spread(c, "per_path_primary_length_m", v), ("band_120_400", "roughness"), (), unit="spread_scale"),
        SearchParameter("primary_attenuation_spread", 1.0, 0.25, lambda c, v: _scale_spread(c, "per_path_attenuation", v), ("mid_band_share", "roughness"), (), unit="spread_scale", scenes=(("full_load_acceleration", 2.0),)),
        SearchParameter("waveguide_reflection", 1.0, 1.0, lambda c, v: c.setdefault("exhaust_waveguide", {}).update({"reflection_mode": _fixed("open" if v < 1.0 else "closed", "label", "stage x search reflection mode")}), ("band_120_400", "dynamic_range"), (), unit="mode_scale", note="open vs closed junction reflection", architecture="P2H", scenes=(("full_load_acceleration", 2.0), ("gear_shift", 1.5))),
        SearchParameter("waveguide_loss", 0.08, 0.03, lambda c, v: c.setdefault("exhaust_waveguide", {}).update({"loss_per_meter": _fixed(v, "ratio", "stage x search waveguide loss")}), ("high_band_share", "mid_band_share"), (), unit="per_m"),
        SearchParameter("collector_loss", 0.92, 0.06, lambda c, v: _set_parameter(c, "collector_loss", v), ("mid_band_share", "high_band_share"), (), unit="ratio"),
        SearchParameter("attack_mix_120_400", 0.0, 0.20, lambda c, v: c.setdefault("attack_shaping", {}).update({"band_120_400_mix": _fixed(v, "gain", "stage x attack shaping")}), ("band_120_400",), ("low_band_share",), unit="gain"),
        SearchParameter("timbre_map_order_weights", 1.0, 0.30, lambda c, v: c.setdefault("timbre_mixes", {}).update({"order_weights": _fixed([v, v, 1.0, 1.0], "vector", "stage x order weights")}), ("sharpness", "tonality"), (), unit="vector_scale", architecture="P3", scenes=(("full_load_acceleration", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("blower_sideband_mix", 1.0, 0.30, lambda c, v: c.setdefault("timbre_mixes", {}).update({"sideband_mix": _fixed(v, "gain", "stage x sideband mix")}), ("tonality", "sharpness"), ("low_band_share",), unit="gain", architecture="P3", scenes=(("full_load_acceleration", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("blower_broadband_mix", 1.0, 0.30, lambda c, v: c.setdefault("timbre_mixes", {}).update({"broadband_mix": _fixed(v, "gain", "stage x broadband mix")}), ("roughness", "flux"), ("tonality",), unit="gain", architecture="P3", scenes=(("full_load_acceleration", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("blower_casing_mix", 1.0, 0.30, lambda c, v: c.setdefault("timbre_mixes", {}).update({"casing_mix": _fixed(v, "gain", "stage x casing mix")}), ("tonality",), ("low_band_share",), unit="gain", architecture="P3", scenes=(("full_load_acceleration", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("intake_mix", 0.18, 0.06, lambda c, v: _set_parameter(c, "intake_model", v), ("mid_band_share", "flux"), (), unit="normalized_gain"),
        SearchParameter("boost_attack", 0.0, 0.08, lambda c, v: c.setdefault("timbre_mixes", {}).update({"boost_attack_s": _fixed(v, "s", "stage x boost attack")}), ("flux", "dynamic_range"), (), unit="s", architecture="P3", scenes=(("full_load_acceleration", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("boost_release", 0.0, 0.20, lambda c, v: c.setdefault("timbre_mixes", {}).update({"boost_release_s": _fixed(v, "s", "stage x boost release")}), ("flux",), (), unit="s", architecture="P3", scenes=(("full_load_acceleration", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("bypass_threshold", 0.20, 0.08, lambda c, v: c.setdefault("timbre_mixes", {}).update({"bypass_threshold": _fixed(v, "throttle", "stage x bypass threshold")}), ("tonality", "sharpness"), (), unit="throttle", architecture="P3", scenes=(("full_load_acceleration", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("afterfire_reservoir_rate", 0.72, 0.20, lambda c, v: c["afterfire"].update({"fuel_reservoir_rate": _fixed(v, "normalized", "stage x reservoir rate")}), ("transient_density",), (), unit="normalized", architecture="P3", scenes=(("high_rpm_lift", 2.5), ("afterfire_eligible", 2.5))),

        SearchParameter("afterfire_ignition_delay", 0.004, 0.0015, lambda c, v: _set_parameter(c, "afterfire.ignition_delay_s", v), ("transient_density",), (), unit="s", architecture="P3", scenes=(("high_rpm_lift", 2.5), ("afterfire_eligible", 2.5))),

        SearchParameter("afterfire_location_mix", 0.0, 1.0, lambda c, v: _set_parameter(c, "afterfire.event_location", "bank_collector" if v >= 1.0 else "primary"), ("transient_density", "crest"), (), unit="mode", note="primary vs bank collector routing", architecture="P3", scenes=(("high_rpm_lift", 2.5), ("afterfire_eligible", 2.5))),

        SearchParameter("afterfire_energy", 0.06, 0.02, lambda c, v: _set_parameter(c, "afterfire.gain", v), ("transient_density", "crest"), (), unit="normalized_gain", architecture="P3", scenes=(("high_rpm_lift", 2.5), ("afterfire_eligible", 2.5))),

        SearchParameter("monitor_attack", 0.12, 0.05, lambda c, v: c.setdefault("monitor_policy", {}).update({"attack_s": _fixed(v, "s", "stage x monitor attack")}), ("dynamic_range",), (), unit="s", stem="monitor", scenes=(("hot_idle_20s", 2.0),)),

        SearchParameter("monitor_release", 1.20, 0.40, lambda c, v: c.setdefault("monitor_policy", {}).update({"release_s": _fixed(v, "s", "stage x monitor release")}), ("dynamic_range", "crest"), (), unit="s", stem="monitor", scenes=(("hot_idle_20s", 2.0),)),

        SearchParameter("monitor_max_makeup", 9.0, 3.0, lambda c, v: c.setdefault("monitor_policy", {}).update({"max_makeup_db": _fixed(v, "dB", "stage x monitor makeup")}), ("dynamic_range", "crest"), ("low_band_share",), unit="dB", stem="monitor", scenes=(("hot_idle_20s", 2.0),)),

    ]


def apply_parameters(base_config: dict[str, Any], overrides: dict[str, float], parameters: list[SearchParameter]) -> dict[str, Any]:
    """Deep-copy the base config and apply named search overrides."""
    config = copy.deepcopy(base_config)
    by_name = {item.name: item for item in parameters}
    for name, value in overrides.items():
        if name not in by_name:
            raise KeyError(f"unknown search parameter: {name}")
        by_name[name].apply(config, float(value))
    return config


def _render_config_pcm(config: dict[str, Any], architecture: str, traces: list[Any]) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Render post-PTR and engine-monitor stems for each trace (P1 falls back)."""
    from ..stage_w.bakeoff import _render_architecture, build_hellcat_bakeoff_trace  # noqa: F401
    from ..stage_w.persistent_engine import PersistentEventDomainEngine

    settings = {"P2": {"path_model": "delay_lpf_v1", "forced_induction_model": "harmonic_v1"}, "P2H": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"}, "P3": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"}, "P5": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"}}[architecture]
    blocks: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for trace in traces:
        engine = PersistentEventDomainEngine(copy.deepcopy(config), 48000, 960, ptr_enabled=True, **settings)
        result = engine.process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
        post = result.post_ptr_raw if result.post_ptr_raw is not None else result.raw_pcm
        blocks.append((result.raw_pcm, post, result.monitor_pcm))
    return blocks


def run_parameter_reachability(
    output_root,
    traces: list[Any],
    metric_stem: str = "post_ptr",
    *,
    architecture: str = "P2H",
    tolerance: float = 0.02,
) -> dict[str, Any]:
    """Render baseline and +/- delta per parameter; classify reachability.

    A parameter is reachable when: both directions render finite audio, the
    post-PCM WAV-equivalent bytes differ from baseline, at least one target
    metric moves by more than tolerance, and guard metrics stay within a
    bounded factor (5x the target movement). Consumption is proven by the
    config actually mutating the render, not by a declared flag.
    """
    from ..stage_w.bakeoff import _render_architecture  # local import avoids cycles in docs

    root = output_root
    root.mkdir(parents=True, exist_ok=True)
    base_config = load_config("hellcat_v1")
    parameters = hellcat_search_parameters()

    def _stem_blocks(blocks: list[tuple[np.ndarray, np.ndarray, np.ndarray]], stem: str) -> list[np.ndarray]:
        index = {"raw": 0, "post_ptr": 1, "monitor": 2}[stem]
        return [block[index] for block in blocks]

    results = []
    from ..stage_w.bakeoff import build_hellcat_bakeoff_trace as build_scene_trace
    for item in parameters:
        record: dict[str, Any] = {
            "parameter": item.name,
            "baseline": item.baseline,
            "delta": item.delta,
            "unit": item.unit,
            "target_metrics": list(item.target_metrics),
            "note": item.note,
            "probe_architecture": item.architecture,
            "probe_scenes": [scene for scene, _ in item.scenes],
            "probe_stem": item.stem,
        }
        movement: dict[str, float] = {}
        sha_changed = False
        finite_ok = True
        item_traces = [build_scene_trace(scene, duration) for scene, duration in item.scenes]
        item_baseline = _render_config_pcm(base_config, item.architecture, item_traces)
        item_baseline = _stem_blocks(item_baseline, item.stem)
        baseline_bytes = b"".join(block.tobytes() for block in item_baseline)
        item_baseline_metrics = _pcm_metrics(item_baseline)
        for direction, sign in (("minus", -1.0), ("plus", 1.0)):
            value = item.baseline + sign * item.delta
            config = copy.deepcopy(base_config)
            item.apply(config, value)
            try:
                pcm_blocks = _render_config_pcm(config, item.architecture, item_traces)
                pcm_blocks = _stem_blocks(pcm_blocks, item.stem)
            except Exception as error:  # noqa: BLE001 - reachability must classify, not crash
                record[f"{direction}_error"] = str(error)
                finite_ok = False
                continue
            if not all(np.all(np.isfinite(block)) for block in pcm_blocks):
                finite_ok = False
                continue
            variant_bytes = b"".join(block.tobytes() for block in pcm_blocks)
            if hashlib.sha256(variant_bytes).hexdigest() != hashlib.sha256(baseline_bytes).hexdigest():
                sha_changed = True
            variant_metrics = _pcm_metrics(pcm_blocks)
            for metric, value_pair in variant_metrics.items():
                base_value = item_baseline_metrics[metric]
                change = abs(value_pair - base_value) / max(abs(base_value), 1e-9)
                movement[metric] = max(movement.get(metric, 0.0), change)
        target_movement = max((movement.get(name, 0.0) for name in item.target_metrics), default=0.0)
        guard_violation = any(
            movement.get(name, 0.0) > max(5.0 * target_movement, 0.5) for name in item.guard_metrics
        )
        if not finite_ok:
            status = PARAMETER_NOT_REACHABLE
            reason = "render failed or non-finite PCM"
        elif not sha_changed:
            status = PARAMETER_NOT_REACHABLE
            reason = "rendered PCM identical to baseline"
        elif target_movement <= tolerance:
            status = PARAMETER_NOT_REACHABLE
            reason = f"target metric movement {target_movement:.4f} <= tolerance {tolerance}"
        elif guard_violation:
            status = PARAMETER_NOT_REACHABLE
            reason = "guard metric moved out of bounds"
        else:
            status = PARAMETER_REACHABLE
            reason = f"target movement {target_movement:.4f}"
        record.update({"status": status, "reason": reason, "metric_movement": {name: float(value) for name, value in sorted(movement.items())}})
        results.append(record)
    summary = {
        "schema": REACHABILITY_SCHEMA,
        "architecture": architecture,
        "protocol": "per-parameter targeted probe: architecture + scenes + stem declared on each SearchParameter",
        "metric_stem": metric_stem,
        "parameter_count": len(results),
        "reachable_count": sum(1 for item in results if item["status"] == PARAMETER_REACHABLE),
        "unreachable": [item["parameter"] for item in results if item["status"] != PARAMETER_REACHABLE],
        "results": results,
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    write_json(root / "parameter_reachability.json", summary)
    return summary


def _pcm_metrics(blocks: list[np.ndarray]) -> dict[str, float]:
    """Metric vector over the concatenated scene set (post-PCM domain)."""
    concat = np.concatenate([block.mean(axis=1) for block in blocks]) if blocks else np.zeros(1)
    sample_rate = 48000
    metrics = raw_dynamic_metrics(concat, sample_rate)
    timbre = timbre_metrics(concat, sample_rate)
    return {
        "crest": metrics["crest_db"],
        "dynamic_range": metrics["dynamic_range_db"],
        "transient_density": metrics["transient_event_density_per_s"],
        "low_band_share": timbre["fine_band_shares"][0] + timbre["fine_band_shares"][1],
        "band_120_400": timbre["fine_band_shares"][2] + timbre["fine_band_shares"][3],
        "mid_band_share": timbre["fine_band_shares"][4] + timbre["fine_band_shares"][5],
        "high_band_share": timbre["fine_band_shares"][6] + timbre["fine_band_shares"][7],
        "tonality": timbre["tonality_proxy"],
        "sharpness": timbre["sharpness_proxy"],
        "roughness": timbre["roughness_proxy"],
        "flux": timbre["spectral_flux"],
        "centroid": timbre["spectral_centroid_hz"],
    }


__all__ = [
    "METRIC_FUNCS",
    "PARAMETER_NOT_REACHABLE",
    "PARAMETER_REACHABLE",
    "REACHABILITY_SCHEMA",
    "SearchParameter",
    "apply_parameters",
    "hellcat_search_parameters",
    "run_parameter_reachability",
]
