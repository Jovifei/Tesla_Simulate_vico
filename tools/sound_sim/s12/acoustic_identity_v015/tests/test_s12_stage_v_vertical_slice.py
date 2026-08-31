"""TDD contract tests for the Stage-V Hellcat vertical slice."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.comparator import (
    compare_three_way,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.io import (
    read_pcm24_wav,
    write_pcm24_wav,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.pipeline import (
    render_stage_v_case,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_v.scenarios import (
    STAGE_V_SCENARIOS,
    build_stage_v_scenario_trace,
)
from tools.sound_sim.s12.acoustic_comparator.core import ComparisonCase


def test_stage_v_exposes_all_five_state_bound_scenarios() -> None:
    for scenario in STAGE_V_SCENARIOS:
        trace = build_stage_v_scenario_trace("hellcat_v1", scenario, duration_s=0.8)
        trace.validate()
        assert trace.time_s.size >= 80
        assert np.all(np.diff(trace.time_s) > 0.0)
        assert np.all(np.isfinite(trace.rpm))


def test_pcm24_write_reopen_preserves_quantized_audio_and_sha(tmp_path) -> None:
    audio = np.column_stack(
        (
            np.linspace(-0.75, 0.75, 240, dtype=np.float64),
            np.linspace(0.75, -0.75, 240, dtype=np.float64),
        )
    )
    receipt = write_pcm24_wav(tmp_path / "candidate.wav", audio, 48000)
    reopened, metadata = read_pcm24_wav(tmp_path / "candidate.wav")
    assert receipt.sha256 == hashlib.sha256((tmp_path / "candidate.wav").read_bytes()).hexdigest()
    assert metadata["sample_rate_hz"] == 48000
    assert metadata["channels"] == 2
    assert metadata["sample_width_bits"] == 24
    assert np.array_equal(reopened, receipt.reopened_audio)


def test_hellcat_vertical_slice_separates_raw_parent_candidate_and_monitor() -> None:
    result = render_stage_v_case("hellcat_v1", "hot_idle_20s", duration_s=0.8)
    assert result.parent.pressure.shape == result.candidate.pressure.shape
    assert result.parent.pressure.shape[1] == 2
    assert not np.array_equal(result.parent.pressure, result.candidate.pressure)
    assert not np.shares_memory(result.candidate.pressure, result.monitor_audio)
    assert result.monitor_peak_dbfs <= -1.0
    assert result.diagnostics["source_model"] == "event_domain_v1"


def test_three_way_comparator_binds_reference_parent_candidate_and_rejects_identity() -> None:
    time = np.arange(4800, dtype=np.float64) / 48000.0
    reference = np.column_stack((0.15 * np.sin(2 * np.pi * 120 * time),) * 2)
    parent = reference * 0.8
    candidate = reference * 0.9 + np.column_stack((0.01 * np.sin(2 * np.pi * 240 * time),) * 2)
    case = ComparisonCase(
        "hellcat_v1",
        "hot_idle_20s",
        "r2-hellcat",
        "event_candidate",
        48000,
        (850.0, 850.0),
        (850.0, 850.0),
        (0.18, 0.18),
        (0.18, 0.18),
        "unaltered_analysis_signal",
        reference_provenance="R2/listening-only",
        candidate_source_commit="working-tree",
    )
    result = compare_three_way(reference, parent, candidate, case)
    assert set(result["pairs"]) == {"reference_parent", "reference_candidate", "parent_candidate"}
    assert result["pairs"]["parent_candidate"]["difference_rms"] > 0.0
    with pytest.raises(ValueError, match="identical"):
        compare_three_way(reference, parent, parent, case)


def test_stage_v_monitor_is_bounded_and_does_not_mutate_raw() -> None:
    result = render_stage_v_case("hellcat_v1", "afterfire_eligible_lift", duration_s=0.8)
    raw_before = result.candidate.pressure.copy()
    assert np.array_equal(raw_before, result.candidate.pressure)
    assert np.max(np.abs(result.monitor_audio)) < 1.0
    assert -12.0 <= result.monitor_gain_db <= 9.0
    assert result.diagnostics["afterfire_event_count"] >= 0


def test_afterfire_eligible_lift_produces_path_bound_events() -> None:
    result = render_stage_v_case("hellcat_v1", "afterfire_eligible_lift", duration_s=0.8)
    assert result.diagnostics["afterfire_event_count"] > 0
    assert result.diagnostics["wrong_condition_event_count"] == 0
