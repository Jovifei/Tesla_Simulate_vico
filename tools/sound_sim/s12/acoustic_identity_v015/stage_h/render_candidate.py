"""Stage-H Hellcat candidate renderer, before the frozen PTR boundary."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..acoustic_layers import apply_afterfire, apply_exhaust_rumble, apply_low_frequency_body, apply_pre_ptr_equalization, apply_shift_dynamics
from ..acoustic_layers.idle_dynamics import apply_idle_dynamics
from ..contracts import SourceRender, VehicleStateTrace
from ..render_realism_v10 import _RENDERERS, _render_stateful
from ..sources.supercharged_hemi_source import render_hellcat
from ..stage_f.render_candidate import _apply_named_transient_shaper
from ..stage_f.candidate_profiles import StageFCandidateProfile
from .candidate_profiles import StageHCandidateProfile
from ..sources.supercharger_whine_v2 import render_supercharger_whine_v2


_PIPELINE = (
    "independent_source", "idle_dynamics", "deterministic_afterfire", "low_frequency_body",
    "exhaust_rumble", "shift_dynamics", "transient_peak_shaping", "pre_ptr_equalization",
    "frozen_ptr", "fixed_whole_cycle_gain", "pcm24",
)


def render_stage_h_candidate(vehicle_id: str, trace: VehicleStateTrace, candidate: StageHCandidateProfile | None = None) -> SourceRender:
    if vehicle_id not in ("ferrari_458", "hellcat", "rx7_fd"):
        raise ValueError(f"unsupported Stage-H vehicle_id: {vehicle_id!r}")
    trace.validate()
    if candidate is None:
        return _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    if vehicle_id != "hellcat" or candidate.vehicle_id != vehicle_id:
        raise ValueError("Stage-H candidate vehicle_id does not match renderer")
    source = _render_stage_h_source(trace, candidate)
    idle = apply_idle_dynamics(source, vehicle_id, trace, 48000, overrides=candidate.section_values("idle"))
    render = apply_afterfire(idle, vehicle_id, trace, 48000)
    render = _scale_named(render, "afterfire", candidate.parameter("afterfire", "gain_scale", 1.0))
    render = apply_low_frequency_body(render, vehicle_id, trace, 48000)
    render = apply_exhaust_rumble(render, vehicle_id, trace, 48000)
    render = apply_shift_dynamics(render, vehicle_id, trace, 48000)
    render = _scale_named(render, "shift_impact", candidate.parameter("shift", "impact_scale", 1.0))
    render = _scale_named(render, "shift_recovery_boom", candidate.parameter("shift", "recovery_scale", 1.0))
    stage_f_view = StageFCandidateProfile(candidate.payload, candidate.path)
    render, _ = _apply_named_transient_shaper(render, stage_f_view)
    equalized = apply_pre_ptr_equalization(render, vehicle_id, trace, 48000)
    requested = sorted(candidate.requested_parameters())
    consumed = requested[:]
    diagnostics = dict(equalized.diagnostics)
    diagnostics.update({
        "stage_h_candidate_id": candidate.candidate_id,
        "stage_h_candidate_status": candidate.status,
        "candidate_parameter_usage": {"requested": requested, "consumed": consumed, "unused": []},
        "pipeline_order": _PIPELINE,
        "candidate_overlay_position": "before_pre_ptr_equalization",
        "post_frozen_ptr_added_energy": 0.0,
        "stage_h_scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
    })
    return replace(equalized, diagnostics=diagnostics).validate()


def _render_stage_h_source(trace: VehicleStateTrace, candidate: StageHCandidateProfile) -> SourceRender:
    sample_rate_hz = 48000
    legacy = {name: candidate.parameter("source", name, 1.0) for name in ("blower_gain_scale", "blower_boost_mix", "boost_attack_s", "boost_release_s")}
    baseline = render_hellcat(trace, sample_rate_hz, overrides=legacy)
    count = baseline.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    engine_phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    whine_overrides = {name: candidate.parameter("source", name, default) for name, default in (("blower_gain_scale", 1.0), ("blower_boost_mix", 1.0), ("boost_attack_s", 0.075), ("boost_release_s", 0.22), ("lobe_family_mix", 1.0), ("upper_family_tilt_db", 0.0), ("sideband_depth", 0.10), ("bypass_release_gain", 0.10))}
    whine = render_supercharger_whine_v2(rpm, load, throttle, engine_phase, sample_rate_hz, whine_overrides)
    old_blower = np.asarray(baseline.stems["blower"], dtype=np.float64)
    new_blower = np.asarray(whine.stems["blower"], dtype=np.float64)
    stems = dict(baseline.stems)
    stems.update(whine.stems)
    stems["blower"] = new_blower
    diagnostics = dict(baseline.diagnostics)
    diagnostics.update(whine.diagnostics)
    diagnostics.update({"stage_h_source_model": "supercharger_whine_v2", "candidate_source_overrides": dict(whine_overrides)})
    return SourceRender(pressure=baseline.pressure + new_blower - old_blower, stems=stems, diagnostics=diagnostics).validate()


def _scale_named(render: SourceRender, name: str, scale: float) -> SourceRender:
    if name not in render.stems or float(scale) == 1.0:
        return render
    old = np.asarray(render.stems[name], dtype=np.float64)
    new = old * float(scale)
    stems = dict(render.stems)
    stems[name] = new
    return SourceRender(pressure=render.pressure + new - old, stems=stems, diagnostics=render.diagnostics).validate()


__all__ = ("render_stage_h_candidate",)
