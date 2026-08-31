"""Stage-D candidate overlay rendered strictly before the frozen PTR boundary."""

from __future__ import annotations

from dataclasses import replace
import math

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..acoustic_layers.transient_peak_shaping import apply_transient_peak_shaping
from ..render_realism_v10 import _RENDERERS, _render_stateful
from .candidate_profiles import StageDCandidateProfile


def render_stage_d_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    candidate: StageDCandidateProfile | None = None,
) -> SourceRender:
    if vehicle_id not in ("ferrari_458", "hellcat", "rx7_fd"):
        raise ValueError(f"unsupported Stage-D vehicle_id: {vehicle_id!r}")
    trace.validate()
    base = _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    if candidate is None:
        return base
    if candidate.vehicle_id != vehicle_id:
        raise ValueError("candidate vehicle_id does not match render vehicle_id")
    if vehicle_id == "ferrari_458":
        rendered = _apply_ferrari(base, trace, candidate)
    elif vehicle_id == "hellcat":
        rendered = _apply_hellcat(base, trace, candidate)
    else:
        rendered = _apply_rx7(base, trace, candidate)
    diagnostics = dict(rendered.diagnostics)
    diagnostics["stage_d_candidate_id"] = candidate.candidate_id
    diagnostics["stage_d_candidate_status"] = "Candidate"
    diagnostics["stage_d_overlay_position"] = "before_frozen_ptr"
    return replace(rendered, diagnostics=diagnostics).validate()


def _apply_ferrari(render: SourceRender, trace: VehicleStateTrace, candidate: StageDCandidateProfile) -> SourceRender:
    result = render
    idle_mask = trace.rpm <= 1300.0
    variation = candidate.parameter("idle", "variation", 0.24)
    jitter_ms = candidate.parameter("idle", "jitter_ms", 0.45)
    mechanical = candidate.parameter("idle", "mechanical_texture", 0.18)
    t = trace.time_s - trace.time_s[0]
    idle_mod = 1.0 + idle_mask * ((variation - 0.24) * 0.28 * np.sin(2.0 * np.pi * (2.7 + jitter_ms) * t))
    result = _scale_stem(result, "idle_combustion_variation", idle_mod)
    result = _scale_stem(result, "idle_crank", 1.0 + idle_mask * max(0.0, mechanical - 0.18) * 0.8)
    result = _scale_stem(result, "idle_valvetrain", 1.0 + idle_mask * max(0.0, mechanical - 0.18) * 0.5)
    pulse_scale = candidate.parameter("source", "pulse_width_scale", 1.0)
    if "pressure_pulse" in result.stems:
        pulse = result.stems["pressure_pulse"]
        sharpened = np.tanh(pulse * pulse_scale) / max(math.tanh(max(pulse_scale, 1e-9)), 1e-9)
        result = _replace_stem(result, "pressure_pulse", sharpened)
    mid_gain = candidate.parameter("source", "metallic_mid_gain_scale", 1.0)
    upper_gain = candidate.parameter("source", "metallic_upper_gain_scale", 1.0)
    growth = candidate.parameter("source", "high_rpm_growth_scale", 1.0)
    drive = np.clip((trace.rpm - 1300.0) / (9000.0 - 1300.0), 0.0, 1.0)
    result = _scale_stem(result, "metallic", 1.0 + drive[:, None] * ((mid_gain - 1.0) + (upper_gain - 1.0) * growth))
    return result


def _apply_hellcat(render: SourceRender, trace: VehicleStateTrace, candidate: StageDCandidateProfile) -> SourceRender:
    result = render
    blower_gain = candidate.parameter("source", "blower_gain_scale", 1.0)
    for stem_name in ("blower", "intake", "mechanical"):
        result = _scale_stem(result, stem_name, blower_gain if stem_name == "blower" else 1.0)
    afterfire_gain = candidate.parameter("afterfire", "gain_scale", 1.0)
    result = _scale_stem(result, "afterfire", afterfire_gain)
    result = _scale_stem(result, "shift_impact", candidate.parameter("shift", "impact_scale", 1.0))
    result = _scale_stem(result, "shift_recovery_boom", candidate.parameter("shift", "recovery_scale", 1.0))
    return apply_transient_peak_shaping(result, "hellcat", trace, candidate, 48000)


def _apply_rx7(render: SourceRender, trace: VehicleStateTrace, candidate: StageDCandidateProfile) -> SourceRender:
    result = render
    rotary_scale = candidate.parameter("source", "rotary_pulse_width_scale", 1.0)
    phase_offset = candidate.parameter("source", "rotary_phase_offset_deg", 0.0)
    if "rotary" in result.stems:
        rotary = result.stems["rotary"]
        t = trace.time_s - trace.time_s[0]
        modulation = 1.0 + 0.03 * math.sin(math.radians(phase_offset)) * np.sin(2.0 * np.pi * np.maximum(trace.rpm, 1.0) / 60.0 * t)
        result = _replace_stem(result, "rotary", rotary * rotary_scale * modulation[:, None])
    result = _scale_stem(result, "turbo", candidate.parameter("source", "turbo_gain_scale", 1.0))
    result = _scale_stem(result, "turbine", candidate.parameter("source", "secondary_spool_tau_s", 0.31) / 0.31)
    result = _scale_stem(result, "blow_off", candidate.parameter("source", "blow_off_gain_scale", 1.0))
    return result


def _scale_stem(render: SourceRender, name: str, scale: float | np.ndarray) -> SourceRender:
    if name not in render.stems:
        return render
    factor = np.asarray(scale, dtype=np.float64)
    if factor.ndim == 1:
        factor = factor[:, None]
    return _replace_stem(render, name, render.stems[name] * factor)


def _replace_stem(render: SourceRender, name: str, value: np.ndarray) -> SourceRender:
    old = np.asarray(render.stems[name], dtype=np.float64)
    new = np.asarray(value, dtype=np.float64)
    stems = dict(render.stems)
    stems[name] = new
    return SourceRender(pressure=render.pressure + new - old, stems=stems, diagnostics=render.diagnostics).validate()
