"""Stage-I Hellcat candidate renderer before the frozen PTR boundary."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..acoustic_layers import (
    apply_afterfire,
    apply_exhaust_rumble,
    apply_low_frequency_body,
    apply_pre_ptr_equalization,
    apply_shift_dynamics,
)
from ..acoustic_layers.idle_dynamics import apply_idle_dynamics
from ..contracts import SourceRender, VehicleStateTrace
from ..render_realism_v10 import _RENDERERS, _render_stateful
from ..sources.supercharged_hemi_source import render_hellcat
from ..sources.supercharger_whine_v3 import render_supercharger_whine_v3
from ..stage_f.candidate_profiles import StageFCandidateProfile
from ..stage_f.render_candidate import _apply_named_transient_shaper
from .candidate_profiles import StageICandidateProfile


_PIPELINE = (
    "independent_source",
    "idle_dynamics",
    "deterministic_afterfire",
    "low_frequency_body",
    "exhaust_rumble",
    "shift_dynamics",
    "transient_peak_shaping",
    "pre_ptr_equalization",
    "frozen_ptr",
    "fixed_whole_cycle_gain",
    "pcm24",
)


def render_stage_i_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    candidate: StageICandidateProfile | None = None,
) -> SourceRender:
    if vehicle_id not in ("ferrari_458", "hellcat", "rx7_fd"):
        raise ValueError(f"unsupported Stage-I vehicle_id: {vehicle_id!r}")
    trace.validate()
    if candidate is None:
        return _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    if vehicle_id != "hellcat" or candidate.vehicle_id != vehicle_id:
        raise ValueError("Stage-I candidate vehicle_id does not match renderer")

    render = _render_stage_i_source(trace, candidate)
    source_usage = render.diagnostics["candidate_parameter_usage"]
    read = {f"source.{name}" for name in source_usage["read"]}
    active = {f"source.{name}" for name in source_usage["active"]}
    idle_values = candidate.section_values("idle")
    render = apply_idle_dynamics(
        render,
        vehicle_id,
        trace,
        48000,
        overrides=idle_values,
    )
    read.update(f"idle.{name}" for name in idle_values)
    idle_activity = {
        "variation": _stem_has_energy(render, "idle_combustion_variation"),
        "jitter_ms": _stem_has_energy(render, "idle_combustion_variation"),
        "mechanical_texture": _stem_has_energy(render, "idle_accessory"),
    }
    active.update(f"idle.{name}" for name in idle_values if idle_activity.get(name, False))

    afterfire_values = candidate.section_values("afterfire")
    render = apply_afterfire(render, vehicle_id, trace, 48000)
    afterfire_event_active = (
        int(render.diagnostics.get("afterfire_event_count", 0)) > 0
        and _stem_has_energy(render, "afterfire")
    )
    render, afterfire_affected = _scale_named_with_activity(
        render,
        "afterfire",
        candidate.parameter("afterfire", "gain_scale", 1.0),
        event_active=afterfire_event_active,
    )
    read.update(f"afterfire.{name}" for name in afterfire_values)
    if afterfire_affected:
        active.update(f"afterfire.{name}" for name in afterfire_values)

    render = apply_low_frequency_body(render, vehicle_id, trace, 48000)
    render = apply_exhaust_rumble(render, vehicle_id, trace, 48000)
    shift_values = candidate.section_values("shift")
    render = apply_shift_dynamics(render, vehicle_id, trace, 48000)
    shift_event_active = int(render.diagnostics.get("shift_event_count", 0)) > 0
    render, impact_affected = _scale_named_with_activity(
        render,
        "shift_impact",
        candidate.parameter("shift", "impact_scale", 1.0),
        event_active=shift_event_active,
    )
    render, recovery_affected = _scale_named_with_activity(
        render,
        "shift_recovery_boom",
        candidate.parameter("shift", "recovery_scale", 1.0),
        event_active=shift_event_active,
    )
    read.update(f"shift.{name}" for name in shift_values)
    shift_activity = {
        "impact_scale": impact_affected,
        "recovery_scale": recovery_affected,
    }
    active.update(
        f"shift.{name}" for name in shift_values if shift_activity.get(name, False)
    )

    stage_f_view = StageFCandidateProfile(candidate.payload, candidate.path)
    before_shaping = np.asarray(render.pressure, dtype=np.float64)
    render, _ = _apply_named_transient_shaper(render, stage_f_view)
    if candidate.payload["loudness"]["transient_peak_shaper"]["enabled"]:
        shaper_names = {
            f"loudness.transient_peak_shaper.{name}"
            for name in ("attack_ms", "release_ms", "max_reduction_db")
        }
        read.update(shaper_names)
        if not np.array_equal(before_shaping, render.pressure):
            active.update(shaper_names)
    equalized = apply_pre_ptr_equalization(render, vehicle_id, trace, 48000)

    requested = sorted(candidate.requested_parameters())
    read_sorted = sorted(read)
    active_sorted = sorted(active & read)
    inactive_sorted = sorted(read - active)
    diagnostics = dict(equalized.diagnostics)
    diagnostics.update(
        {
            "stage_i_candidate_id": candidate.candidate_id,
            "stage_i_candidate_status": candidate.status,
            "candidate_parameter_usage": {
                "requested": requested,
                "read": read_sorted,
                "configured": read_sorted,
                "active": active_sorted,
                "inactive": inactive_sorted,
                "consumed": read_sorted,
                "unused": sorted(set(requested) - set(read_sorted)),
            },
            "pipeline_order": _PIPELINE,
            "candidate_overlay_position": "before_pre_ptr_equalization",
            "post_frozen_ptr_added_energy": 0.0,
            "stage_i_scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        }
    )
    return replace(equalized, diagnostics=diagnostics).validate()


def _render_stage_i_source(
    trace: VehicleStateTrace, candidate: StageICandidateProfile
) -> SourceRender:
    sample_rate_hz = 48000
    baseline = render_hellcat(trace, sample_rate_hz)
    count = baseline.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    engine_phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    overrides = candidate.section_values("source")
    whine = render_supercharger_whine_v3(
        rpm,
        load,
        throttle,
        engine_phase,
        sample_rate_hz,
        overrides,
    )
    old_blower = np.asarray(baseline.stems["blower"], dtype=np.float64)
    new_blower = np.asarray(whine.stems["blower"], dtype=np.float64)
    stems = dict(baseline.stems)
    stems.update(whine.stems)
    stems["blower"] = new_blower
    diagnostics = dict(baseline.diagnostics)
    diagnostics.update(whine.diagnostics)
    diagnostics.update(
        {
            "stage_i_source_model": "supercharger_whine_v3",
            "candidate_source_overrides": dict(overrides),
        }
    )
    return SourceRender(
        pressure=baseline.pressure + new_blower - old_blower,
        stems=stems,
        diagnostics=diagnostics,
    ).validate()


def _scale_named(render: SourceRender, name: str, scale: float) -> SourceRender:
    if name not in render.stems or float(scale) == 1.0:
        return render
    old = np.asarray(render.stems[name], dtype=np.float64)
    new = old * float(scale)
    stems = dict(render.stems)
    stems[name] = new
    return SourceRender(
        pressure=render.pressure + new - old,
        stems=stems,
        diagnostics=render.diagnostics,
    ).validate()


def _scale_named_with_activity(
    render: SourceRender,
    name: str,
    scale: float,
    *,
    event_active: bool,
) -> tuple[SourceRender, bool]:
    before = np.asarray(render.stems[name], dtype=np.float64) if name in render.stems else None
    scaled = _scale_named(render, name, scale)
    affected = bool(
        event_active
        and before is not None
        and name in scaled.stems
        and not np.array_equal(before, np.asarray(scaled.stems[name], dtype=np.float64))
    )
    return scaled, affected


def _stem_has_energy(render: SourceRender, name: str) -> bool:
    if name not in render.stems:
        return False
    return bool(
        np.any(np.abs(np.asarray(render.stems[name], dtype=np.float64)) > 1.0e-12)
    )


__all__ = ("render_stage_i_candidate",)
