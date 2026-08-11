"""Stage-K candidate and parent rendering entry points.

The ``None`` path is intentionally a direct delegation to the Stage-C
stateful renderer.  This gives every eight-vehicle regression a stable,
sample-for-sample anchor.  Explicit Stage-K candidates are rendered before
the shared Pre-PTR boundary; later vehicle-specific Stage-K source modules may
replace the small legacy adapter below without changing this public contract.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping

import numpy as np

from ..acoustic_layers import (
    apply_afterfire,
    apply_exhaust_rumble,
    apply_idle_dynamics,
    apply_low_frequency_body,
    apply_pre_ptr_equalization,
    apply_shift_dynamics,
)
from ..contracts import SourceRender, VehicleStateTrace
from ..render_realism_v10 import _RENDERERS, _render_stateful
from ..sources.lexus_high_rev_v10_source_v2 import render_lfa_v2
from ..sources.mercedes_na_v8_source_v2 import render_c63_w204_v2
from ..sources.nissan_twin_turbo_v6_source_v2 import render_gtr_r35_v2
from ..sources.supercharged_hemi_source import render_hellcat
from .candidate_profiles import (
    PARENT_MAPPING,
    SOURCE_KEYS,
    STAGE_K_VEHICLES,
    StageKCandidateProfile,
    load_stage_k_candidate,
)
from .source_level import OperatingLevelTrim, apply_source_operating_trim


_SAMPLE_RATE_HZ = 48000
_LEGACY_SOURCE_KEYS = {
    "hellcat": {"blower_gain_scale", "blower_boost_mix", "boost_attack_s", "boost_release_s"},
    "c63_w204": {"bank_phase_offset_deg", "pulse_width_scale", "bark_resonance_scale", "mechanical_texture_scale", "high_rpm_growth_scale"},
    "gtr_r35": {"pulse_width_scale", "bank_phase_offset_deg", "primary_spool_tau_s", "secondary_spool_tau_s", "boost_attack_s", "boost_release_s", "wastegate_gain_scale", "turbo_whistle_mix"},
    "lfa": {"pulse_width_scale", "phase_offset_deg", "order_family_mix", "intake_resonance_scale", "metallic_texture_scale", "high_rpm_growth_scale"},
}
_SOURCE_RENDERERS = {
    "hellcat": render_hellcat,
    "c63_w204": render_c63_w204_v2,
    "gtr_r35": render_gtr_r35_v2,
    "lfa": render_lfa_v2,
}


def render_stage_k_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    candidate: StageKCandidateProfile | None = None,
) -> SourceRender:
    """Render a Stage-K candidate before Pre-PTR EQ and frozen PTR.

    ``candidate=None`` supports all eight formal Stage-C vehicle IDs and is
    deliberately byte-identical to :func:`render_realism_v10._render_stateful`.
    Explicit candidates are limited to the four Stage-K repair vehicles.
    """

    if candidate is None:
        if vehicle_id not in _RENDERERS:
            raise ValueError(f"unsupported Stage-K vehicle_id: {vehicle_id!r}")
        trace.validate()
        return _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    if vehicle_id not in STAGE_K_VEHICLES:
        raise ValueError(f"unsupported Stage-K candidate vehicle_id: {vehicle_id!r}")
    if candidate.vehicle_id != vehicle_id:
        raise ValueError("Stage-K candidate vehicle_id does not match render vehicle_id")
    trace.validate()

    source_overrides = candidate.section_values("source")
    source, consumed_source = _render_source(vehicle_id, trace, source_overrides)
    requested = set(candidate.requested_parameters())
    read: set[str] = {f"source.{name}" for name in consumed_source}

    idle_overrides = candidate.section_values("idle")
    render = apply_idle_dynamics(source, vehicle_id, trace, _SAMPLE_RATE_HZ, overrides=idle_overrides or None)
    read.update(f"idle.{name}" for name in idle_overrides)
    read.update(_diagnostic_parameter_names(render.diagnostics, "idle"))

    render = apply_afterfire(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    afterfire_scale = candidate.parameter("afterfire", "gain_scale", 1.0)
    render = _scale_named(render, "afterfire", afterfire_scale)
    read.update(f"afterfire.{name}" for name in candidate.section_values("afterfire"))

    render = apply_low_frequency_body(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    render = apply_exhaust_rumble(render, vehicle_id, trace, _SAMPLE_RATE_HZ)

    shift_values = candidate.section_values("shift_or_transient")
    # Stage-K LFA and vehicle-specific transient implementations may replace
    # this common adapter.  The adapter only handles the two legacy named
    # shift stems and keeps the new energy pre-PTR.
    render = apply_shift_dynamics(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    render = _scale_named(render, "shift_impact", candidate.parameter("shift_or_transient", "impact_scale", 1.0))
    render = _scale_named(render, "shift_recovery_boom", candidate.parameter("shift_or_transient", "recovery_scale", 1.0))
    read.update(f"shift_or_transient.{name}" for name in shift_values)

    operating_values = candidate.section_values("operating_level")
    if operating_values:
        trim = OperatingLevelTrim(
            low_load_gain_db=candidate.parameter("operating_level", "low_load_gain_db"),
            high_load_gain_db=candidate.parameter("operating_level", "high_load_gain_db"),
            blend_load=(
                candidate.parameter("operating_level", "blend_load_low"),
                candidate.parameter("operating_level", "blend_load_high"),
            ),
            smoothing_s=candidate.parameter("operating_level", "smoothing_s"),
        )
        event_stems = {"afterfire", "shift_impact", "shift_recovery_boom", "bov", "blower_bypass_release"}
        continuous_stems = tuple(name for name in render.stems if name not in event_stems)
        if continuous_stems:
            render = apply_source_operating_trim(render, trace, stem_names=continuous_stems, trim=trim, sample_rate_hz=_SAMPLE_RATE_HZ)
        read.update(f"operating_level.{name}" for name in operating_values)

    equalized = apply_pre_ptr_equalization(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    diagnostics = dict(equalized.diagnostics)
    read_sorted = sorted(read)
    requested_sorted = sorted(requested)
    unused = sorted(requested - read)
    active = sorted(set(read_sorted) - set(unused))
    diagnostics.update(
        {
            "stage_k_candidate_id": candidate.candidate_id,
            "stage_k_candidate_status": candidate.status,
            "stage_k_parent_candidate_id": candidate.payload["parent_candidate_id"],
            "candidate_parameter_usage": {
                "requested": requested_sorted,
                "read": read_sorted,
                "configured": read_sorted,
                "active": active,
                "inactive": [],
                "unused": unused,
            },
            "pipeline_order": (
                "independent_source",
                "source_operating_trim",
                "idle_dynamics",
                "deterministic_afterfire",
                "low_frequency_body",
                "exhaust_rumble",
                "vehicle_shift_or_transient",
                "pre_ptr_equalization",
                "frozen_ptr",
                "edge_fade",
                "fixed_whole_cycle_gain",
                "pcm24",
            ),
            "candidate_overlay_position": "before_pre_ptr_equalization_and_frozen_ptr",
            "post_frozen_ptr_added_energy": 0.0,
            "stage_k_scope": "C/synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
        }
    )
    return replace(equalized, diagnostics=diagnostics).validate()


def render_stage_k_parent(vehicle_id: str, trace: VehicleStateTrace) -> SourceRender:
    """Render the explicitly bound Stage-I/Stage-J parent for diagnostics.

    This is intentionally separate from ``candidate=None``: the latter is the
    Stage-C regression anchor, while this function exposes the historical
    repair parent named by the Stage-K lineage contract.
    """

    if vehicle_id not in STAGE_K_VEHICLES:
        raise ValueError(f"unsupported Stage-K parent vehicle_id: {vehicle_id!r}")
    base = Path(__file__).resolve().parents[1]
    parent_path = base / PARENT_MAPPING[vehicle_id]["path"]
    if vehicle_id == "hellcat":
        from ..stage_i.candidate_profiles import load_stage_i_candidate
        from ..stage_i.render_candidate import render_stage_i_candidate

        return render_stage_i_candidate(vehicle_id, trace, load_stage_i_candidate(parent_path))
    from ..stage_j.candidate_profiles import load_stage_j_candidate
    from ..stage_j.render_candidate import render_stage_j_candidate

    return render_stage_j_candidate(vehicle_id, trace, load_stage_j_candidate(parent_path))


def _render_source(vehicle_id: str, trace: VehicleStateTrace, overrides: Mapping[str, float]) -> tuple[SourceRender, set[str]]:
    renderer = _SOURCE_RENDERERS[vehicle_id]
    supported = _LEGACY_SOURCE_KEYS[vehicle_id]
    legacy = {name: float(value) for name, value in overrides.items() if name in supported}
    source = renderer(trace, overrides=legacy)
    diagnostic = source.diagnostics
    consumed: set[str] = set()
    for key in ("candidate_parameter_usage", "override_usage"):
        value = diagnostic.get(key)
        if isinstance(value, Mapping):
            raw = value.get("read", value.get("consumed", value.get("requested", ())))
            if isinstance(raw, (list, tuple, set)):
                consumed.update(
                    str(name).split(".", 1)[-1]
                    for name in raw
                    if str(name).split(".", 1)[-1] in overrides
                )
    for key in ("active_overrides", "candidate_source_overrides"):
        value = diagnostic.get(key)
        if isinstance(value, Mapping):
            consumed.update(
                str(name).split(".", 1)[-1]
                for name in value
                if str(name).split(".", 1)[-1] in overrides
            )
    if not consumed:
        consumed.update(legacy)
    return source, consumed


def _diagnostic_parameter_names(diagnostics: Mapping[str, object], section: str) -> set[str]:
    value = diagnostics.get("candidate_parameter_usage")
    if not isinstance(value, Mapping):
        return set()
    raw = value.get("read", value.get("consumed", ()))
    if not isinstance(raw, (list, tuple, set)):
        return set()
    return {name if str(name).startswith(f"{section}.") else f"{section}.{name}" for name in raw}


def _scale_named(render: SourceRender, stem_name: str, scale: float) -> SourceRender:
    if stem_name not in render.stems or float(scale) == 1.0:
        return render
    old = np.asarray(render.stems[stem_name], dtype=np.float64)
    new = old * float(scale)
    stems = dict(render.stems)
    stems[stem_name] = new
    return SourceRender(pressure=np.asarray(render.pressure) + new - old, stems=stems, diagnostics=render.diagnostics).validate()


__all__ = ("render_stage_k_candidate", "render_stage_k_parent")
