"""Stage AI-5 reconstructed-peak qualification.

Synthetic waveforms validate the gate itself. They are not vehicle-fidelity
evidence and do not authorize a sound change.
"""
from __future__ import annotations

import copy

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reconstruction_peak import (
    DEFAULT_FACTORS,
    reconstructed_peak_ok,
    reconstructed_peak_receipt,
)


FOUR_X_BLIND_SPOT = np.array([
    [0.575237664059, -0.589608332237],
    [0.731863379758, 0.326017770083],
    [0.852349233806, -0.545495167886],
    [-0.502438076346, -0.081669497849],
    [-0.660339073466, -0.865313964125],
    [-0.278412751054, 0.472018061502],
    [0.731291863699, -0.501337777496],
    [0.835290939563, -0.791032098956],
], dtype=np.float64)


def test_multirate_gate_detects_case_4x_alone_would_miss():
    receipt = reconstructed_peak_receipt(FOUR_X_BLIND_SPOT)
    assert receipt["factors"]["4"]["peak"] < 1.0
    assert receipt["factors"]["8"]["peak"] > 1.0
    assert receipt["factors"]["16"]["peak"] > 1.0
    assert receipt["status"] == "BLOCKED_RECONSTRUCTED_PEAK"
    assert not reconstructed_peak_ok(receipt)


def test_safe_signal_passes_all_declared_factors_and_input_is_unchanged():
    t = np.arange(4096, dtype=np.float64) / 48_000.0
    audio = np.column_stack([
        0.45 * np.sin(2 * np.pi * 187 * t),
        0.38 * np.sin(2 * np.pi * 389 * t + 0.4),
    ])
    saved = audio.copy()
    receipt = reconstructed_peak_receipt(audio)
    np.testing.assert_array_equal(audio, saved)
    assert tuple(receipt["factor_order"]) == DEFAULT_FACTORS
    assert receipt["status"] == "PASS"
    assert reconstructed_peak_ok(receipt)


@pytest.mark.parametrize("mutation", [
    lambda r: r.pop("factors"),
    lambda r: r["factors"].pop("16"),
    lambda r: r.__setitem__("status", "PASS") or r["factors"]["8"].__setitem__("peak", 1.02),
    lambda r: r.__setitem__("threshold", 1.01),
    lambda r: r["factors"]["4"].__setitem__("exceedance_count", 1),
    lambda r: r.__setitem__("worst_peak", float("nan")),
])
def test_qualification_fails_closed_on_missing_or_inconsistent_receipt(mutation):
    audio = np.zeros((1024, 2), dtype=np.float64)
    audio[:, 0] = 0.2
    receipt = reconstructed_peak_receipt(audio)
    broken = copy.deepcopy(receipt)
    mutation(broken)
    assert not reconstructed_peak_ok(broken)


@pytest.mark.parametrize("audio", [
    np.ones((1, 2)),
    np.ones((64, 3)),
    np.full((64, 2), np.nan),
    np.full((64, 2), 1.1),
])
def test_invalid_audio_is_rejected(audio):
    with pytest.raises(ValueError):
        reconstructed_peak_receipt(audio)


def _numeric_record(receipt):
    return {
        "normalization": {
            "output_policy": "linked_soft_ceiling_v1",
            "normalization_denominator": 0.8,
            "legacy_ceiling_input_exceedance_samples": 0,
            "legacy_transfer_pre_guard_peak": 0.9,
            "pre_guard_exceedance_longest_run": 0,
            "pre_guard_peak": 0.9,
            "frame_count": 8,
            "soft_guard_active_frames": 0,
            "soft_guard_delta_peak": 0.0,
            "soft_guard_delta_rms": 0.0,
            "post_guard_peak": 0.9,
            "post_guard_ceiling_exceedance_samples": 0,
            "emergency_clip_count": 0,
            "emergency_clip_error": 0.0,
            "emergency_clip_error_rms": 0.0,
        },
        "identity_layer_clip_count": 0,
        "post_identity_clip_count": 0,
        "identity_layer_clip_error": 0.0,
        "post_identity_clip_error": 0.0,
        "parent_peak": 0.8,
        "candidate_raw_peak": 0.9,
        "output_policy": "linked_soft_ceiling_v1",
        "final_rms": 0.2,
        "final_peak": 0.9,
        "peak_estimate_4x": {"peak": 0.995},
        "reconstruction_peak": receipt,
        "normalization_denominator": 0.8,
    }


def test_reference_feedback_numeric_gate_uses_multirate_receipt():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback_cli import numeric_ok

    blind = reconstructed_peak_receipt(FOUR_X_BLIND_SPOT)
    assert blind["factors"]["4"]["peak"] < 1.0
    assert blind["factors"]["8"]["peak"] > 1.0
    assert not numeric_ok(_numeric_record(blind))

    safe = reconstructed_peak_receipt(FOUR_X_BLIND_SPOT * 0.8)
    assert reconstructed_peak_ok(safe)
    assert numeric_ok(_numeric_record(safe))


def test_numeric_gate_fails_closed_when_multirate_receipt_is_missing():
    from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback_cli import numeric_ok

    safe = reconstructed_peak_receipt(FOUR_X_BLIND_SPOT * 0.8)
    record = _numeric_record(safe)
    record.pop("reconstruction_peak")
    assert not numeric_ok(record)
