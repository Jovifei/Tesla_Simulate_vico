"""Stage-F candidate renderer; all overlays remain before the frozen PTR."""

from __future__ import annotations

from dataclasses import replace
import math
import numpy as np

from ..acoustic_layers import apply_afterfire, apply_exhaust_rumble, apply_low_frequency_body, apply_pre_ptr_equalization, apply_shift_dynamics
from ..acoustic_layers.idle_dynamics import apply_idle_dynamics
from ..contracts import SourceRender, VehicleStateTrace
from ..render_realism_v10 import _RENDERERS, _render_stateful
from ..sources.flat_plane_v8_source import render_ferrari_458
from ..sources.supercharged_hemi_source import render_hellcat
from ..sources.rotary_turbo_source import render_rx7_fd
from .candidate_profiles import StageFCandidateProfile

_ANCHORS = ("ferrari_458", "hellcat", "rx7_fd")
_SOURCE_RENDERERS = {"ferrari_458": render_ferrari_458, "hellcat": render_hellcat, "rx7_fd": render_rx7_fd}


def render_stage_f_candidate(vehicle_id: str, trace: VehicleStateTrace, candidate: StageFCandidateProfile | None = None) -> SourceRender:
    if vehicle_id not in _ANCHORS:
        raise ValueError(f"unsupported Stage-F vehicle_id: {vehicle_id!r}")
    trace.validate()
    if candidate is None:
        return _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    if candidate.vehicle_id != vehicle_id:
        raise ValueError("candidate vehicle_id does not match render vehicle_id")
    source = _SOURCE_RENDERERS[vehicle_id](trace, overrides=candidate.section_values("source"))
    idle = apply_idle_dynamics(source, vehicle_id, trace, 48000, overrides=candidate.section_values("idle"))
    render = apply_afterfire(idle, vehicle_id, trace, 48000)
    consumed = list(f"source.{name}" for name in source.diagnostics.get("candidate_source_overrides", {}))
    consumed.extend(f"idle.{name}" for name in idle.diagnostics.get("candidate_idle_overrides", {}))
    afterfire_scale = candidate.parameter("afterfire", "gain_scale", 1.0)
    render = _scale_named(render, "afterfire", afterfire_scale)
    if "gain_scale" in candidate.payload.get("afterfire", {}):
        consumed.append("afterfire.gain_scale")
    render = apply_low_frequency_body(render, vehicle_id, trace, 48000)
    render = apply_exhaust_rumble(render, vehicle_id, trace, 48000)
    render = apply_shift_dynamics(render, vehicle_id, trace, 48000)
    for name in ("impact_scale", "recovery_scale"):
        stem = "shift_impact" if name == "impact_scale" else "shift_recovery_boom"
        render = _scale_named(render, stem, candidate.parameter("shift", name, 1.0))
        if name in candidate.payload.get("shift", {}):
            consumed.append(f"shift.{name}")
    render, shaper_consumed = _apply_named_transient_shaper(render, candidate)
    consumed.extend(shaper_consumed)
    equalized = apply_pre_ptr_equalization(render, vehicle_id, trace, 48000)
    requested = list(candidate.requested_parameters())
    diagnostics = dict(equalized.diagnostics)
    diagnostics.update({
        "stage_f_candidate_id": candidate.candidate_id,
        "stage_f_candidate_status": candidate.status,
        "candidate_parameter_usage": {"requested": requested, "consumed": sorted(set(consumed)), "unused": sorted(set(requested) - set(consumed))},
        "pipeline_order": ("independent_source", "idle_dynamics", "deterministic_afterfire", "low_frequency_body", "exhaust_rumble", "shift_dynamics", "transient_peak_shaping", "pre_ptr_equalization", "frozen_ptr", "fixed_whole_cycle_gain", "pcm24"),
        "stage_f_overlay_position": "before_pre_ptr_equalization_and_frozen_ptr",
    })
    return replace(equalized, diagnostics=diagnostics).validate()


def _scale_named(render: SourceRender, name: str, scale: float) -> SourceRender:
    if name not in render.stems or float(scale) == 1.0:
        return render
    old = np.asarray(render.stems[name], dtype=np.float64)
    new = old * float(scale)
    stems = dict(render.stems); stems[name] = new
    return SourceRender(pressure=np.asarray(render.pressure) + new - old, stems=stems, diagnostics=render.diagnostics).validate()


def _apply_named_transient_shaper(render: SourceRender, candidate: StageFCandidateProfile) -> tuple[SourceRender, list[str]]:
    shaper = candidate.payload["loudness"]["transient_peak_shaper"]
    if not shaper["enabled"]:
        return render, []
    attack_ms = candidate.parameter("loudness", "attack_ms", 1.0)
    release_ms = candidate.parameter("loudness", "release_ms", 40.0)
    reduction_db = candidate.parameter("loudness", "max_reduction_db", 0.0)
    consumed = [f"loudness.transient_peak_shaper.{name}" for name in ("attack_ms", "release_ms", "max_reduction_db")]
    result = render
    for stem_name in ("shift_impact", "shift_recovery_boom", "afterfire", "blower_attack"):
        result = _shape_stem(result, stem_name, attack_ms, release_ms, reduction_db, 48000)
    return result, consumed


def _shape_stem(render: SourceRender, name: str, attack_ms: float, release_ms: float, max_reduction_db: float, sample_rate_hz: int) -> SourceRender:
    if name not in render.stems:
        return render
    stem = np.asarray(render.stems[name], dtype=np.float64)
    magnitude = np.max(np.abs(stem), axis=1)
    envelope = np.zeros_like(magnitude)
    attack_alpha = 1.0 - math.exp(-1.0 / max(attack_ms * 0.001 * sample_rate_hz, 1.0))
    release_alpha = 1.0 - math.exp(-1.0 / max(release_ms * 0.001 * sample_rate_hz, 1.0))
    for index in range(1, magnitude.size):
        alpha = attack_alpha if magnitude[index] >= envelope[index - 1] else release_alpha
        envelope[index] = envelope[index - 1] + alpha * (magnitude[index] - envelope[index - 1])
    threshold = max(float(np.percentile(envelope, 75.0)), 1e-12)
    excess = np.clip(envelope / threshold - 1.0, 0.0, 1.0)
    floor = 10.0 ** (-max_reduction_db / 20.0)
    replacement = stem * (1.0 - excess * (1.0 - floor))[:, None]
    stems = dict(render.stems); stems[name] = replacement
    return SourceRender(pressure=render.pressure + replacement - stem, stems=stems, diagnostics=render.diagnostics).validate()
