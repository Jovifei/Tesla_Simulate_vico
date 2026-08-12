"""Stage-L L1 parent isolation and primitive contributor assembly."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..sources.supercharged_hemi_source import render_hellcat
from ..sources.supercharger_whine_v4 import render_supercharger_whine_v4
from ..stage_k.candidate_profiles import load_stage_k_candidate
from ..stage_k.render_candidate import render_stage_k_candidate
from ..tuning.state_band_shaper import _inject_state_spectral_targets
from .candidate_profiles import PARENT_CANDIDATE_PATH, StageLCandidateProfile
from .crank_clock import build_hellcat_crank_clock


_SAMPLE_RATE_HZ = 48000
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_HEMI_CONTRIBUTORS = ("exhaust_left_bank", "exhaust_right_bank", "mechanical", "intake")
_BLOWER_CONTRIBUTORS = (
    "blower_shaft", "blower_rotor_family", "blower_gear_casing", "blower_sidebands",
    "blower_intake_voicing", "blower_bypass_release",
)
_CONTRIBUTORS = _HEMI_CONTRIBUTORS + _BLOWER_CONTRIBUTORS
_AGGREGATES = ("exhaust", "blower")


def render_stage_l_parent(trace: VehicleStateTrace) -> SourceRender:
    """Render the exact hash-bound Stage-K Hellcat v7 parent."""
    trace.validate()
    parent = load_stage_k_candidate(_PACKAGE_ROOT / PARENT_CANDIDATE_PATH)
    return render_stage_k_candidate("hellcat", trace, parent)


def render_stage_l_candidate(trace: VehicleStateTrace, candidate: StageLCandidateProfile) -> SourceRender:
    """Assemble the L1 source contract; L2-L4 controls remain explicit unused stubs."""
    trace.validate()
    if not isinstance(candidate, StageLCandidateProfile):
        raise TypeError("candidate must be a validated StageLCandidateProfile")
    if candidate.vehicle_id != "hellcat":
        raise ValueError("Stage-L candidate vehicle_id must be hellcat")
    clock = build_hellcat_crank_clock(trace, _SAMPLE_RATE_HZ)
    legacy = render_hellcat(trace, sample_rate_hz=_SAMPLE_RATE_HZ, apply_state_shaping=False)
    count = legacy.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / _SAMPLE_RATE_HZ
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    stage_k_parent = load_stage_k_candidate(_PACKAGE_ROOT / PARENT_CANDIDATE_PATH)
    blower_overrides = {
        name: float(record["value"])
        for name, record in stage_k_parent.payload["source"].items()
    }
    blower = render_supercharger_whine_v4(
        rpm, load, throttle, clock.engine_phase_cycles, _SAMPLE_RATE_HZ, overrides=blower_overrides,
    )
    stems = {name: np.asarray(legacy.stems[name], dtype=np.float64) for name in _HEMI_CONTRIBUTORS}
    stems.update({name: np.asarray(blower.stems[name], dtype=np.float64) for name in _BLOWER_CONTRIBUTORS})
    contract = {"contributors": list(_CONTRIBUTORS), "diagnostic_aggregates": list(_AGGREGATES)}
    diagnostics = dict(legacy.diagnostics)
    diagnostics.update(blower.diagnostics)
    diagnostics["pressure_stem_contract"] = contract
    pressure = sum((stems[name] for name in _CONTRIBUTORS), np.zeros_like(legacy.pressure))
    raw = SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()
    shaped = _inject_state_spectral_targets(raw, "hellcat", trace, sample_rate_hz=_SAMPLE_RATE_HZ)
    shaped_stems = {name: np.asarray(shaped.stems[name], dtype=np.float64) for name in _CONTRIBUTORS}
    shaped_stems["exhaust"] = shaped_stems["exhaust_left_bank"] + shaped_stems["exhaust_right_bank"]
    shaped_stems["blower"] = sum(
        (shaped_stems[name] for name in _BLOWER_CONTRIBUTORS), np.zeros_like(shaped.pressure)
    )
    shaped_pressure = sum(
        (shaped_stems[name] for name in _CONTRIBUTORS), np.zeros_like(shaped.pressure)
    )
    requested = sorted(candidate.requested_parameters())
    final_diagnostics = dict(shaped.diagnostics)
    final_diagnostics.update(
        {
            "pressure_stem_contract": contract,
            "stage_l_candidate_id": candidate.candidate_id,
            "stage_l_candidate_status": candidate.status,
            "stage_l_parent_candidate_id": candidate.payload["parent_candidate_id"],
            "stage_l_phase": "L1_CONTRACT_ONLY",
            "candidate_parameter_usage": {
                "requested": requested, "read": [], "configured": [], "active": [],
                "inactive": [], "unused": requested,
            },
            "crank_clock_firing_order": tuple(candidate.payload["crank_clock"]["firing_order"]),
            "crank_clock_event_count": len(clock.event_sample_indices),
            "pipeline_order": (
                "shared_hellcat_crank_clock", "cross_plane_combustion_blowdown_source",
                "twin_screw_intake_case_source", "state_spectral_targets_once",
                "source_operating_trim", "idle_dynamics", "deterministic_afterfire",
                "frozen_common_low_frequency_body", "frozen_exhaust_rumble",
                "hellcat_shift_load_transient", "hellcat_named_peak_budget",
                "frozen_common_pre_ptr_equalization", "frozen_ptr", "edge_fade",
                "fixed_whole_cycle_gain", "pcm24",
            ),
            "implemented_pipeline_stop": "state_spectral_targets_once",
            "post_frozen_ptr_added_energy": 0.0,
            "stage_l_scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        }
    )
    return SourceRender(shaped_pressure, shaped_stems, final_diagnostics).validate()


__all__ = ("render_stage_l_candidate", "render_stage_l_parent")
