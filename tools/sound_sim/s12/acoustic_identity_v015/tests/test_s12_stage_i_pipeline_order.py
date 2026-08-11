from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import (
    build_drive_cycle_trace,
)


_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE = _ROOT / "targets" / "stage_i_candidates" / "Hellcat_candidate_v6.json"


def _trace(duration_s: float = 0.5) -> VehicleStateTrace:
    count = int(duration_s * 48000) + 1
    time_s = np.arange(count, dtype=np.float64) / 48000.0
    phase = time_s / duration_s
    return VehicleStateTrace(
        time_s,
        900.0 + 5000.0 * phase,
        0.15 + 0.8 * phase,
        0.15 + 0.83 * phase,
        np.zeros(count),
    ).validate()


def test_stage_i_candidate_usage_distinguishes_read_from_active_on_monotonic_trace() -> None:
    profiles = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles"
    )
    renderer = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.render_candidate"
    )
    candidate = profiles.load_stage_i_candidate(_CANDIDATE)
    render = renderer.render_stage_i_candidate("hellcat", _trace(), candidate)
    assert render.diagnostics["pipeline_order"] == (
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
    usage = render.diagnostics["candidate_parameter_usage"]
    assert usage["requested"] == usage["read"]
    assert usage["consumed"] == usage["read"]
    assert set(usage["requested"]) == set(usage["active"]) | set(usage["inactive"])
    assert set(usage["active"]).isdisjoint(usage["inactive"])
    assert "afterfire.gain_scale" in usage["inactive"]
    assert "shift.impact_scale" in usage["inactive"]
    assert "shift.recovery_scale" in usage["inactive"]
    assert "afterfire.gain_scale" not in usage["active"]
    assert "shift.impact_scale" not in usage["active"]
    assert "shift.recovery_scale" not in usage["active"]
    assert usage["unused"] == []
    assert render.diagnostics["candidate_overlay_position"] == "before_pre_ptr_equalization"
    assert render.diagnostics["post_frozen_ptr_added_energy"] == 0.0


def test_full_drive_cycle_only_marks_event_scales_active_when_they_change_audio() -> None:
    profiles = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.candidate_profiles"
    )
    renderer = importlib.import_module(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_i.render_candidate"
    )
    candidate = profiles.load_stage_i_candidate(_CANDIDATE)
    neutral = (
        candidate.with_parameter("afterfire", "gain_scale", 1.0)
        .with_parameter("shift", "impact_scale", 1.0)
        .with_parameter("shift", "recovery_scale", 1.0)
    )
    trace = build_drive_cycle_trace("hellcat", duration_s=6.0)

    neutral_render = renderer.render_stage_i_candidate("hellcat", trace, neutral)
    assert neutral_render.diagnostics["afterfire_event_count"] > 0
    assert neutral_render.diagnostics["shift_event_count"] > 0
    neutral_usage = neutral_render.diagnostics["candidate_parameter_usage"]
    assert {
        "afterfire.gain_scale",
        "shift.impact_scale",
        "shift.recovery_scale",
    } <= set(neutral_usage["inactive"])
    assert not {
        "afterfire.gain_scale",
        "shift.impact_scale",
        "shift.recovery_scale",
    } & set(neutral_usage["active"])

    affected = (
        candidate.with_parameter("afterfire", "gain_scale", 1.1)
        .with_parameter("shift", "impact_scale", 0.9)
        .with_parameter("shift", "recovery_scale", 0.95)
    )
    affected_render = renderer.render_stage_i_candidate("hellcat", trace, affected)
    affected_usage = affected_render.diagnostics["candidate_parameter_usage"]
    assert {
        "afterfire.gain_scale",
        "shift.impact_scale",
        "shift.recovery_scale",
    } <= set(affected_usage["active"])
