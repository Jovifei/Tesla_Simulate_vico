"""Stage-E renderer with reachable candidate overlays before the frozen boundary."""

from __future__ import annotations

from dataclasses import replace
import numpy as np

from ..acoustic_layers import apply_afterfire, apply_exhaust_rumble, apply_low_frequency_body, apply_pre_ptr_equalization, apply_shift_dynamics
from ..acoustic_layers.idle_dynamics import apply_idle_dynamics
from ..acoustic_layers.transient_peak_shaping import apply_transient_peak_shaping
from ..contracts import SourceRender, VehicleStateTrace
from ..render_realism_v10 import _RENDERERS, _render_stateful
from ..sources.flat_plane_v8_source import render_ferrari_458
from ..sources.supercharged_hemi_source import render_hellcat
from ..sources.rotary_turbo_source import render_rx7_fd
from .candidate_profiles import StageECandidateProfile

_ANCHORS = ("ferrari_458", "hellcat", "rx7_fd")
_SOURCE_RENDERERS = {"ferrari_458": render_ferrari_458, "hellcat": render_hellcat, "rx7_fd": render_rx7_fd}


def render_stage_e_candidate(vehicle_id: str, trace: VehicleStateTrace, candidate: StageECandidateProfile | None = None) -> SourceRender:
    if vehicle_id not in _ANCHORS:
        raise ValueError(f"unsupported Stage-E vehicle_id: {vehicle_id!r}")
    trace.validate()
    if candidate is None:
        return _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    if candidate.vehicle_id != vehicle_id:
        raise ValueError("candidate vehicle_id does not match render vehicle_id")
    renderer = _SOURCE_RENDERERS[vehicle_id]
    source = renderer(trace, overrides=candidate.section_values("source"))
    idle = apply_idle_dynamics(source, vehicle_id, trace, 48000, overrides=candidate.section_values("idle"))
    afterfire = apply_afterfire(idle, vehicle_id, trace, 48000)
    afterfire = _scale_named(afterfire, "afterfire", candidate.parameter("afterfire", "gain_scale", 1.0))
    body = apply_low_frequency_body(afterfire, vehicle_id, trace, 48000)
    rumble = apply_exhaust_rumble(body, vehicle_id, trace, 48000)
    shifted = apply_shift_dynamics(rumble, vehicle_id, trace, 48000)
    shifted = _scale_named(shifted, "shift_impact", candidate.parameter("shift", "impact_scale", 1.0))
    shifted = _scale_named(shifted, "shift_recovery_boom", candidate.parameter("shift", "recovery_scale", 1.0))
    shaped = apply_transient_peak_shaping(shifted, vehicle_id, trace, candidate, 48000)
    equalized = apply_pre_ptr_equalization(shaped, vehicle_id, trace, 48000)
    diagnostics = dict(equalized.diagnostics)
    diagnostics.update({
        "stage_e_candidate_id": candidate.candidate_id,
        "stage_e_candidate_status": "Candidate",
        "candidate_parameter_usage": {f"{section}.{name}": True for section in ("source", "idle", "afterfire", "shift") for name in candidate.payload.get(section, {})},
        "pipeline_order": ("independent_source", "idle_dynamics", "deterministic_afterfire", "low_frequency_body", "exhaust_rumble", "shift_dynamics", "transient_peak_shaping", "pre_ptr_equalization", "frozen_ptr", "fixed_whole_cycle_gain", "pcm24"),
        "stage_e_overlay_position": "before_pre_ptr_equalization_and_frozen_ptr",
    })
    return replace(equalized, diagnostics=diagnostics).validate()


def _scale_named(render: SourceRender, name: str, scale: float) -> SourceRender:
    if name not in render.stems or float(scale) == 1.0:
        return render
    old = np.asarray(render.stems[name], dtype=np.float64)
    new = old * float(scale)
    stems = dict(render.stems)
    stems[name] = new
    return SourceRender(pressure=np.asarray(render.pressure) + new - old, stems=stems, diagnostics=render.diagnostics).validate()
