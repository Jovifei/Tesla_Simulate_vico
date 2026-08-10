"""Stage-G candidate renderer layered on the unchanged Stage-C pipeline."""

from __future__ import annotations

from dataclasses import replace

from ..contracts import SourceRender, VehicleStateTrace
from ..render_realism_v10 import _RENDERERS, _render_stateful
from ..stage_f.candidate_profiles import StageFCandidateProfile
from ..stage_f.render_candidate import render_stage_f_candidate
from .candidate_profiles import ANCHOR_IDS, StageGCandidateProfile


def render_stage_g_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    candidate: StageGCandidateProfile | None = None,
) -> SourceRender:
    """Render a Stage-G candidate before the shared/frozen PTR boundary.

    ``candidate=None`` deliberately delegates to the exact Stage-C entry point;
    it is a byte-for-byte regression anchor.  Candidate overlays are applied by
    the already-tested Stage-F layer path, then diagnostics are normalized to a
    Stage-G contract without mutating the common layers.
    """
    if vehicle_id not in ANCHOR_IDS:
        raise ValueError(f"unsupported Stage-G vehicle_id: {vehicle_id!r}")
    trace.validate()
    if candidate is None:
        return _render_stateful(_RENDERERS[vehicle_id], vehicle_id, trace)
    if candidate.vehicle_id != vehicle_id:
        raise ValueError("candidate vehicle_id does not match render vehicle_id")
    # Stage-F's renderer is intentionally reused as a narrow compatibility
    # adapter.  The Stage-G loader enforces its own stronger base/schema rules;
    # the dataclass below is only an internal view consumed by the unchanged
    # pre-PTR implementation.
    stage_f_view = StageFCandidateProfile(candidate.payload, candidate.path)
    rendered = render_stage_f_candidate(vehicle_id, trace, stage_f_view)
    diagnostics = dict(rendered.diagnostics)
    usage = diagnostics.get("candidate_parameter_usage", {})
    requested = sorted(candidate.requested_parameters())
    consumed = sorted(set(usage.get("consumed", ())))
    diagnostics.update(
        {
            "stage_g_candidate_id": candidate.candidate_id,
            "stage_g_candidate_status": candidate.status,
            "candidate_parameter_usage": {
                "requested": requested,
                "consumed": consumed,
                "unused": sorted(set(requested) - set(consumed)),
            },
            "pipeline_order": (
                "independent_source", "idle_dynamics", "deterministic_afterfire", "low_frequency_body",
                "exhaust_rumble", "shift_dynamics", "transient_peak_shaping", "pre_ptr_equalization",
                "frozen_ptr", "fixed_whole_cycle_gain", "pcm24",
            ),
            "candidate_overlay_position": "before_pre_ptr_equalization",
            "post_frozen_ptr_added_energy": 0.0,
            "stage_g_scope": "C/synthetic; uncalibrated; not OEM reproduction",
        }
    )
    return replace(rendered, diagnostics=diagnostics).validate()


__all__ = ("render_stage_g_candidate",)
