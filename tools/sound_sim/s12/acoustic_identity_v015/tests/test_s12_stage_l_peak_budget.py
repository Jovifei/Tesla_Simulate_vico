"""Stage-L L4 named transient peak-budget contracts."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import load_stage_l_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.hellcat_peak_budget import (
    apply_hellcat_named_peak_budget,
    make_stage_l_formal_copy,
    make_stage_l_comfort_copy,
)


_SR = 8_000
_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE = load_stage_l_candidate(
    _ROOT / "targets" / "stage_l_candidates" / "Hellcat_candidate_v8.json"
)
_NAMED = ("afterfire", "hellcat_shift_reengagement", "hellcat_sc_drive_transient", "hellcat_tip_in_blowdown")
_STEADY = ("hemi_exhaust_left", "sc_intake_radiated", "exhaust_rumble")


def _fixture() -> tuple[SourceRender, VehicleStateTrace]:
    count = _SR + 1
    time_s = np.arange(count, dtype=np.float64) / _SR
    trace = VehicleStateTrace(
        time_s, np.full(count, 3_200.0), np.full(count, 0.8),
        np.full(count, 0.85), np.zeros(count),
    ).validate()
    steady = np.column_stack((0.08 * np.sin(2 * np.pi * 90 * time_s), 0.07 * np.sin(2 * np.pi * 90 * time_s)))
    stems = {name: (index + 1) * 0.2 * steady for index, name in enumerate(_STEADY)}
    for index, name in enumerate(_NAMED):
        event = np.zeros_like(steady)
        event[1000 + 500 * index, :] = 0.9 - 0.1 * index
        stems[name] = event
    contributors = list(_STEADY + _NAMED)
    pressure = sum((stems[name] for name in contributors), np.zeros_like(steady))
    render = SourceRender(
        pressure, stems,
        {"pressure_stem_contract": {"contributors": contributors, "diagnostic_aggregates": []}},
    ).validate()
    return render, trace


def test_peak_budget_changes_only_four_named_stems_and_rewrites_exact_delta() -> None:
    before, trace = _fixture()
    result = apply_hellcat_named_peak_budget(before, trace, _CANDIDATE, _SR)
    for name in _STEADY:
        assert np.array_equal(result.stems[name], before.stems[name])
    assert all(np.linalg.norm(result.stems[name]) <= np.linalg.norm(before.stems[name]) for name in _NAMED)
    expected_delta = sum(
        (result.stems[name] - before.stems[name] for name in _NAMED),
        np.zeros_like(before.pressure),
    )
    np.testing.assert_allclose(result.pressure - before.pressure, expected_delta, atol=1e-12, rtol=0.0)
    assert result.diagnostics["peak_budget_named_stems"] == _NAMED
    assert result.diagnostics["whole_pressure_processed"] is False
    assert result.diagnostics["compressor_or_limiter_used"] is False
    evidence = result.diagnostics["peak_budget_stem_evidence"]
    assert set(evidence) == set(_NAMED)
    for name in _NAMED:
        assert evidence[name]["before_peak"] == np.max(np.abs(before.stems[name]))
        assert evidence[name]["after_peak"] == np.max(np.abs(result.stems[name]))
        assert evidence[name]["gain"] == result.diagnostics["peak_budget_stem_gains"][name]
        assert evidence[name]["status"] in {"REDUCED_ISOLATED_PEAK", "HEADROOM_ALREADY_SATISFIED", "INACTIVE_ZERO"}
    assert any(evidence[name]["gain"] < 1.0 for name in _NAMED)


def test_comfort_copy_is_static_gain_with_peak_safe_headroom_cap() -> None:
    audio = np.full((_SR, 2), 0.85, dtype=np.float64)
    copy, evidence = make_stage_l_comfort_copy(audio, requested_gain_db=1.9382, peak_limit_dbfs=-1.5)
    assert evidence["requested_gain_db"] == 1.9382
    assert evidence["actual_gain_db"] <= 1.9382
    assert evidence["headroom_limited"] is True
    assert evidence["static_whole_copy_gain_only"] is True
    assert np.max(np.abs(copy)) <= 10.0 ** (-1.5 / 20.0) + 1e-12
    assert evidence["compressor_or_limiter_used"] is False


def test_formal_copy_is_bit_identical_and_uses_no_dynamic_processor() -> None:
    audio = np.linspace(-0.4, 0.4, _SR * 2, dtype=np.float64).reshape(_SR, 2)
    formal, evidence = make_stage_l_formal_copy(audio)
    assert np.array_equal(formal, audio)
    assert evidence == {
        "gain_db": 0.0,
        "static_whole_copy_gain_only": True,
        "compressor_or_limiter_used": False,
        "per_section_agc_used": False,
    }


def test_named_budget_reduces_isolated_peak_without_reducing_steady_lufs_proxy() -> None:
    before, trace = _fixture()
    result = apply_hellcat_named_peak_budget(before, trace, _CANDIDATE, _SR)
    before_steady = sum((before.stems[name] for name in _STEADY), np.zeros_like(before.pressure))
    after_steady = sum((result.stems[name] for name in _STEADY), np.zeros_like(result.pressure))
    assert np.array_equal(after_steady, before_steady)
    assert np.max(np.abs(result.pressure)) <= np.max(np.abs(before.pressure))


def test_final_pcm_probe_enforces_peak_clipping_and_loudness_delta() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
        render_stage_l_l4_final_pcm_probe,
    )

    count = 48_001
    time_s = np.arange(count, dtype=np.float64) / 48_000.0
    trace = VehicleStateTrace(
        time_s, np.linspace(1_600.0, 3_800.0, count), np.full(count, 0.90),
        np.full(count, 0.94), np.ones(count),
    ).validate()
    evidence = render_stage_l_l4_final_pcm_probe(trace, _CANDIDATE)
    assert evidence["finite"] is True
    assert evidence["candidate_peak_dbfs"] <= -1.5 + 1e-6
    assert evidence["candidate_clipping_count"] == 0
    assert evidence["candidate_lufs"] >= evidence["parent_lufs"] - 0.5
    assert evidence["formal_compressor_or_limiter_used"] is False
    assert evidence["l4_before_pre_ptr_equalization"] is True
    assert evidence["l4_shift_event_count"] == 3
    assert evidence["l4_tip_in_nonzero"] is True
    assert evidence["l4_afterfire_event_count"] > 0
    assert evidence["l4_named_nonzero_stems"] == list(_NAMED)
    production_budget = evidence["l4_peak_budget_stem_evidence"]
    assert set(production_budget) == set(_NAMED)
    assert any(row["gain"] < 1.0 for row in production_budget.values())
    order = evidence["pipeline_order"]
    assert order.index("hellcat_shift_load_transient") < order.index("frozen_common_low_frequency_body")
    assert order.index("hellcat_named_peak_budget") < order.index("frozen_common_pre_ptr_equalization")


def test_source_diagnostics_and_final_probe_share_one_pipeline_order() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
        _STAGE_L_PIPELINE_ORDER,
        render_stage_l_candidate,
        render_stage_l_l4_final_pcm_probe,
    )

    count = 16_001
    time_s = np.arange(count, dtype=np.float64) / 8_000.0
    trace = VehicleStateTrace(
        time_s, np.linspace(1_500.0, 4_000.0, count), np.full(count, 0.82),
        np.full(count, 0.88), np.ones(count),
    ).validate()
    source = render_stage_l_candidate(trace, _CANDIDATE)
    probe = render_stage_l_l4_final_pcm_probe(trace, _CANDIDATE)
    assert tuple(source.diagnostics["final_pipeline_order"]) == _STAGE_L_PIPELINE_ORDER
    assert tuple(source.diagnostics["pipeline_order"]) == _STAGE_L_PIPELINE_ORDER
    assert tuple(probe["pipeline_order"]) == _STAGE_L_PIPELINE_ORDER
    prefix = tuple(source.diagnostics["executed_pipeline_prefix"])
    assert prefix == _STAGE_L_PIPELINE_ORDER[:2]
    order = _STAGE_L_PIPELINE_ORDER
    assert order.index("hellcat_shift_load_transient") < order.index("hellcat_named_peak_budget")
    assert order.index("hellcat_named_peak_budget") < order.index("frozen_common_low_frequency_body")
    assert order.index("frozen_common_low_frequency_body") < order.index("frozen_exhaust_rumble")
    assert order.index("frozen_exhaust_rumble") < order.index("frozen_common_pre_ptr_equalization")
    assert order.index("frozen_common_pre_ptr_equalization") < order.index("frozen_ptr")
