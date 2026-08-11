"""Stage-J candidate renderer with three independent source models."""

from __future__ import annotations

from dataclasses import replace
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
from .candidate_profiles import STAGE_J_VEHICLES, StageJCandidateProfile


_SOURCE_RENDERERS = {
    "c63_w204": render_c63_w204_v2,
    "gtr_r35": render_gtr_r35_v2,
    "lfa": render_lfa_v2,
}
_SAMPLE_RATE_HZ = 48000


def render_stage_j_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    candidate: StageJCandidateProfile | None = None,
) -> SourceRender:
    """Render one Stage-J candidate before the shared frozen PTR boundary.

    The ``None`` path delegates directly to Stage C and is intentionally kept
    as the bit-identical regression anchor.  Candidate overlays are applied to
    the independent source and named pre-PTR layers only.
    """
    if vehicle_id not in STAGE_J_VEHICLES:
        raise ValueError(f"unsupported Stage-J vehicle_id: {vehicle_id!r}")
    trace.validate()
    if candidate is None:
        return _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    if candidate.vehicle_id != vehicle_id:
        raise ValueError("candidate vehicle_id does not match render vehicle_id")
    source = _SOURCE_RENDERERS[vehicle_id](trace, overrides=candidate.section_values("source"))
    render = apply_idle_dynamics(source, vehicle_id, trace, _SAMPLE_RATE_HZ, overrides=candidate.section_values("idle"))
    render = apply_afterfire(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    render = _scale_named(render, "afterfire", candidate.parameter("afterfire", "gain_scale", 1.0))
    render = apply_low_frequency_body(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    render = apply_exhaust_rumble(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    render = apply_shift_dynamics(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    render = _scale_named(render, "shift_impact", candidate.parameter("shift", "impact_scale", 1.0))
    render = _scale_named(render, "shift_recovery_boom", candidate.parameter("shift", "recovery_scale", 1.0))
    equalized = apply_pre_ptr_equalization(render, vehicle_id, trace, _SAMPLE_RATE_HZ)
    requested = list(candidate.requested_parameters())
    source_usage = source.diagnostics.get("candidate_parameter_usage", source.diagnostics.get("override_usage", {}))
    source_names: set[str] = set()
    if isinstance(source_usage, Mapping):
        raw_names = source_usage.get("read", source_usage.get("consumed", source_usage.get("requested", ())))
        if isinstance(raw_names, (list, tuple, set)):
            source_names.update(f"source.{name}" if not str(name).startswith("source.") else str(name) for name in raw_names)
    raw_overrides = source.diagnostics.get("candidate_source_overrides", source.diagnostics.get("active_overrides", {}))
    if isinstance(raw_overrides, Mapping):
        source_names.update(f"source.{name}" for name in raw_overrides)
    read = sorted(source_names | {name for name in requested if name.startswith("idle.") or name.startswith("afterfire.") or name.startswith("shift.")})
    diagnostics = dict(equalized.diagnostics)
    diagnostics.update(
        {
            "stage_j_candidate_id": candidate.candidate_id,
            "stage_j_candidate_status": candidate.status,
            "candidate_parameter_usage": {
                "requested": sorted(requested),
                "read": read,
                "configured": read,
                "active": read,
                "inactive": [],
                "consumed": read,
                "unused": sorted(set(requested) - set(read)),
            },
            "pipeline_order": (
                "independent_source", "idle_dynamics", "deterministic_afterfire", "low_frequency_body",
                "exhaust_rumble", "shift_dynamics", "pre_ptr_equalization", "frozen_ptr",
                "fixed_whole_cycle_gain", "pcm24",
            ),
            "candidate_overlay_position": "before_pre_ptr_equalization_and_frozen_ptr",
            "post_frozen_ptr_added_energy": 0.0,
            "stage_j_scope": "C/synthetic; uncalibrated; not OEM reproduction",
        }
    )
    return replace(equalized, diagnostics=diagnostics).validate()


def _scale_named(render: SourceRender, stem_name: str, scale: float) -> SourceRender:
    if stem_name not in render.stems or float(scale) == 1.0:
        return render
    old = np.asarray(render.stems[stem_name], dtype=np.float64)
    new = old * float(scale)
    stems = dict(render.stems)
    stems[stem_name] = new
    return SourceRender(pressure=np.asarray(render.pressure) + new - old, stems=stems, diagnostics=render.diagnostics).validate()


__all__ = ("render_stage_j_candidate",)
