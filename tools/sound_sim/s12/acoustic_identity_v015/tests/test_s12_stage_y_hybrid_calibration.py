"""Tests for Stage Y data-derived timbre, residual and transfer tooling."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_y.cycle_residual_bank import (
    CycleResidualBank,
    CycleResidualRecord,
    build_cycle_residual_bank,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.finalist_validation import (
    FinalistEvidence,
    REQUIRED_PSYCHOACOUSTIC_METRICS,
    evaluate_finalists,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.harmonic_timbre_extractor import extract_harmonic_timbre_map
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.hybrid_source import HybridSourceMixer
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.transfer_response_id import (
    CausalFirFilter,
    apply_fir,
    identify_fir_response,
)


def test_synchronized_timbre_extractor_recovers_known_fourth_order() -> None:
    sample_rate = 12000
    duration_s = 4.0
    t = np.arange(int(sample_rate * duration_s), dtype=np.float64) / sample_rate
    rpm = 1800.0
    crank_phase = 2.0 * np.pi * rpm / 60.0 * t
    audio = 0.85 * np.sin(4.0 * crank_phase) + 0.08 * np.sin(2.0 * crank_phase)
    state_times = np.array([0.0, duration_s])
    result = extract_harmonic_timbre_map(
        audio,
        sample_rate,
        state_times_s=state_times,
        rpm_trace=np.array([rpm, rpm]),
        load_trace=np.array([0.55, 0.55]),
        boost_trace=np.array([0.0, 0.0]),
        rpm_axis=(rpm,),
        load_axis=(0.55,),
        boost_axis=(0.0,),
        order_axis=(2.0, 4.0, 6.0),
        frame_size=1024,
        hop_size=256,
    )
    assert result.dominant_order() == 4.0
    assert int(np.sum(result.observation_count)) > 0
    payload = result.to_dict()
    assert payload["raw_audio_embedded"] is False
    assert payload["metadata"]["synchronized_state_required"] is True


def test_cycle_residual_bank_is_rights_gated_and_phase_locked() -> None:
    sample_rate = 8000
    duration_s = 2.0
    t = np.arange(int(sample_rate * duration_s), dtype=np.float64) / sample_rate
    rpm = np.full(t.size, 1200.0)
    load = np.full(t.size, 0.42)
    phase = 2.0 * np.pi * rpm[0] / 60.0 * t
    audio = 0.7 * np.sin(phase) + 0.12 * np.sin(11.0 * phase + 0.3)
    source_sha = hashlib.sha256(np.ascontiguousarray(audio).tobytes()).hexdigest()
    with pytest.raises(PermissionError):
        build_cycle_residual_bank(
            audio,
            phase_rad=phase,
            rpm=rpm,
            load=load,
            state_labels="steady",
            source_sha256=source_sha,
            rights_status="UNVERIFIED",
        )
    bank = build_cycle_residual_bank(
        audio,
        phase_rad=phase,
        rpm=rpm,
        load=load,
        state_labels="steady",
        source_sha256=source_sha,
        rights_status="PROJECT_OWNED",
        phase_samples=256,
        remove_low_order_count=4,
    )
    rendered = bank.render(phase[:1000], rpm[:1000], load[:1000], "steady")
    assert rendered.shape == (1000,)
    assert np.all(np.isfinite(rendered))
    assert float(np.std(rendered)) > 0.001
    manifest = bank.to_manifest()
    assert manifest["record_count"] > 1
    assert manifest["raw_audio_embedded"] is False
    assert manifest["runtime_default_enabled"] is False


def test_fir_identification_recovers_known_causal_response_and_streaming_equivalence() -> None:
    rng = np.random.default_rng(20260830)
    source = rng.standard_normal(12000) * 0.15
    true_taps = np.array([0.72, -0.18, 0.09, 0.04], dtype=np.float64)
    target = apply_fir(source, true_taps)
    result = identify_fir_response(
        source,
        target,
        12000,
        tap_count=12,
        regularization=1e-8,
        training_fraction=0.75,
        provenance={"fixture": True},
    )
    assert result.fit_nrmse < 0.02
    assert result.validation_nrmse < 0.03
    assert np.allclose(result.taps[:4], true_taps, atol=0.02)
    one_shot = apply_fir(source, result.taps)
    streaming = CausalFirFilter(result.taps)
    blocks = [streaming.process(source[index : index + 256]) for index in range(0, source.size, 256)]
    assert np.allclose(np.concatenate(blocks), one_shot, atol=1e-10)
    assert result.to_dict()["stable_by_construction"] is True


def _psycho_receipt(tool: str, candidate_sha: str, error: float) -> dict:
    return {
        "tool": tool,
        "fixture": False,
        "candidate_sha256": candidate_sha,
        "reference_sha256": "b" * 64,
        "metrics": {
            name: {"reference": 1.0, "candidate": 1.0 + error, "absolute_error": error}
            for name in REQUIRED_PSYCHOACOUSTIC_METRICS
        },
    }


def _order_receipt(candidate_sha: str, error_db: float) -> dict:
    return {
        "order_metric_status": "QUALIFIED_WITH_SYNCHRONIZED_RPM",
        "fixture": False,
        "candidate_sha256": candidate_sha,
        "rpm_trace_sha256": "c" * 64,
        "order_ridges": [
            {"order": 4.0, "reference_db": -12.0, "candidate_db": -12.0 + error_db, "absolute_error_db": error_db}
        ],
    }


def test_professional_finalist_gate_ranks_real_sha_bound_receipts_without_freezing_profile() -> None:
    first_sha = "1" * 64
    second_sha = "2" * 64
    result = evaluate_finalists(
        [
            FinalistEvidence(
                "candidate-a",
                first_sha,
                0.18,
                _psycho_receipt("MATLAB_R2026a", first_sha, 0.08),
                _psycho_receipt("MoSQITo_1.2.1", first_sha, 0.07),
                _order_receipt(first_sha, 1.2),
            ),
            FinalistEvidence(
                "candidate-b",
                second_sha,
                0.20,
                _psycho_receipt("MATLAB_R2026a", second_sha, 0.18),
                _psycho_receipt("MoSQITo_1.2.1", second_sha, 0.19),
                _order_receipt(second_sha, 2.8),
            ),
        ],
        maximum_psychoacoustic_median_error=0.15,
        maximum_order_median_error_db=2.0,
    )
    assert result["preferred_for_human_review"] == "candidate-a"
    assert result["profile_freeze_ready"] is False
    assert result["formal_selection"] is None


def test_hybrid_source_is_optional_bounded_and_snapshot_deterministic() -> None:
    phase_samples = 128
    wave = 0.03 * np.sin(np.linspace(0.0, 2.0 * np.pi, phase_samples, endpoint=False) * 9.0)
    record = CycleResidualRecord(1000.0, 0.2, "idle", wave, "d" * 64, 0, "PROJECT_OWNED")
    bank = CycleResidualBank([record])
    mixer = HybridSourceMixer(bank, residual_gain=1.5, stereo_width=0.2, peak_guard=0.95)
    count = 960
    phase = np.linspace(0.0, 8.0 * np.pi, count, endpoint=False)
    event = np.zeros((count, 2), dtype=np.float64)
    state = mixer.snapshot()
    first = mixer.process(event, phase_rad=phase, rpm=1000.0, load=0.2, state="idle")
    mixer.restore(state)
    second = mixer.process(event, phase_rad=phase, rpm=1000.0, load=0.2, state="idle")
    assert np.array_equal(first.audio, second.audio)
    assert first.diagnostics["residual_enabled"] is True
    assert first.diagnostics["clipping_samples"] == 0
    assert first.diagnostics["frozen_ptr_modified"] is False


def test_hybrid_source_without_bank_is_exact_event_passthrough_below_guard() -> None:
    event = np.full((128, 2), 0.1, dtype=np.float64)
    phase = np.linspace(0.0, 2.0 * np.pi, 128, endpoint=False)
    result = HybridSourceMixer(None, residual_gain=0.0).process(
        event,
        phase_rad=phase,
        rpm=1200.0,
        load=0.3,
        state="steady",
    )
    assert np.array_equal(result.audio, event)
    assert result.diagnostics["residual_enabled"] is False
