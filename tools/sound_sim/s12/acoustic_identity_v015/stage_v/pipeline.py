"""Stage-V raw Parent/Candidate rendering with an isolated monitor path."""

from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any, Callable, Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..event_domain.audition_monitor import render_audition_monitor
from ..event_domain.block_renderer import render_event_domain
from ..event_domain.config_schema import load_config
from ..event_domain.diagnostics import measure_audio
from ..sources.flat_plane_v8_source import render_ferrari_458
from ..sources.rotary_turbo_source import render_rx7_fd
from ..sources.supercharged_hemi_source import render_hellcat
from .scenarios import build_stage_v_scenario_trace

SAMPLE_RATE_HZ = 48000
ANALYSIS_OUTPUT_SCALE = 0.25
ANALYSIS_OUTPUT_SCALES = {"hellcat_v1": 0.25, "ferrari_458_v1": 0.25, "rx7_fd_v1": 0.04}
_LEGACY_RENDERERS: dict[str, Callable[[VehicleStateTrace], SourceRender]] = {
    "hellcat_v1": render_hellcat,
    "ferrari_458_v1": render_ferrari_458,
    "rx7_fd_v1": render_rx7_fd,
}


@dataclass(frozen=True)
class StageVCaseRender:
    vehicle_id: str
    scenario_id: str
    trace: VehicleStateTrace
    parent: SourceRender
    candidate: SourceRender
    monitor_audio: np.ndarray
    monitor_gain_trace_db: np.ndarray
    monitor_gain_db: float
    monitor_peak_dbfs: float
    diagnostics: dict[str, Any]


def render_stage_v_case(vehicle_id: str, scenario_id: str, duration_s: float | None = None, candidate_overrides: Mapping[str, object] | None = None) -> StageVCaseRender:
    if vehicle_id not in _LEGACY_RENDERERS:
        raise ValueError(f"unsupported Stage-V vehicle: {vehicle_id!r}")
    trace = build_stage_v_scenario_trace(vehicle_id, scenario_id, duration_s)
    analysis_scale = float(ANALYSIS_OUTPUT_SCALES.get(vehicle_id, ANALYSIS_OUTPUT_SCALE))
    parent = _scale_render(_LEGACY_RENDERERS[vehicle_id](trace).validate(), analysis_scale)
    config = load_config(vehicle_id)
    candidate_trace = {
        "time_s": trace.time_s,
        "rpm": trace.rpm,
        "load": trace.load,
        "throttle": trace.throttle,
        "acceleration_mps2": trace.acceleration_mps2,
    }
    if candidate_overrides:
        config = _apply_overrides(config, candidate_overrides)
    candidate = _scale_render(render_event_domain(candidate_trace, config, sample_rate_hz=SAMPLE_RATE_HZ, block_size=960).validate(), analysis_scale)
    monitor = render_audition_monitor(candidate.pressure, SAMPLE_RATE_HZ)
    peak = float(np.max(np.abs(monitor.audio))) if monitor.audio.size else 0.0
    peak_dbfs = float(20.0 * np.log10(max(peak, 1.0e-12)))
    diagnostics = dict(candidate.diagnostics)
    diagnostics.update(
        {
            "vehicle_id": vehicle_id,
            "scenario_id": scenario_id,
            "source_model": "event_domain_v1",
            "legacy_parent_model": "legacy_v015",
            "parent_metrics": measure_audio(parent.pressure, SAMPLE_RATE_HZ),
            "candidate_metrics": measure_audio(candidate.pressure, SAMPLE_RATE_HZ),
            "monitor_metrics": measure_audio(monitor.audio, SAMPLE_RATE_HZ),
            "monitor_gain_db": monitor.max_gain_db,
            "monitor_peak_dbfs": peak_dbfs,
            "fixed_analysis_scale": analysis_scale,
        }
    )
    return StageVCaseRender(vehicle_id, scenario_id, trace, parent, candidate, monitor.audio, monitor.gain_trace_db, monitor.max_gain_db, peak_dbfs, diagnostics)


def _scale_render(render: SourceRender, scale: float) -> SourceRender:
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("analysis scale must be finite and positive")
    diagnostics = dict(render.diagnostics)
    diagnostics["fixed_analysis_scale"] = float(scale)
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) * scale,
        stems={name: np.asarray(stem, dtype=np.float64) * scale for name, stem in render.stems.items()},
        diagnostics=diagnostics,
    ).validate()


def _apply_overrides(config: dict[str, Any], overrides: Mapping[str, object]) -> dict[str, Any]:
    updated = copy.deepcopy(config)
    for path, value in overrides.items():
        node: Any = updated
        parts = str(path).split(".")
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                raise ValueError(f"unknown Stage-V candidate parameter: {path}")
            node = node[part]
        leaf = parts[-1]
        if leaf not in node or not isinstance(node[leaf], dict) or "value" not in node[leaf]:
            raise ValueError(f"Stage-V override is not a parameter: {path}")
        node[leaf]["value"] = copy.deepcopy(value)
    return updated


__all__ = ["ANALYSIS_OUTPUT_SCALE", "ANALYSIS_OUTPUT_SCALES", "SAMPLE_RATE_HZ", "StageVCaseRender", "render_stage_v_case"]
