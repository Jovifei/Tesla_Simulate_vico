"""Synthetic known-target tests. These are NOT real-car acoustic evidence."""
from dataclasses import replace
import hashlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.reference_feedback import (
    ReferenceCase, Rendered, SearchConfig, SR, audio_sha, feature_distance,
    optimize_reference_feedback, pcm_float, spectral_features, validate_parameters,
)


def tone(mix, *, phase=0.0):
    t = np.arange(SR // 3) / SR
    return 0.16 * np.sin(2*np.pi*180*t + phase) + mix * 0.16 * np.sin(2*np.pi*1700*t + phase)


def cases(train=1.8, validation=1.8):
    return [ReferenceCase("train", "steady", "source-a", "a"*64, "train", tone(train),
                          (0.0, 1/3), True, "synthetic known same-RPM steady target"),
            ReferenceCase("validation", "steady", "source-b", "b"*64, "validation",
                          tone(validation, phase=0.2), (0.0, 1/3), True,
                          "independent synthetic phase realization; not real recording")]


def renderer(p, scene):
    return Rendered(tone(p["mix"]), True, {})


def fit(refs=None, **kwargs):
    return optimize_reference_feedback({"mix": 1.0}, {"mix": (0.5, 2.0)},
                                       cases() if refs is None else refs, renderer, **kwargs)


def test_loop_measures_rerenders_and_improves():
    result = fit()
    assert result["status"] == "RELATIVE_IMPROVEMENT_VALIDATED"
    assert result["selected_train_loss"] < result["baseline_train_loss"]
    assert result["selected_parameters"]["mix"] > 1.0
    assert result["trial_count"] > 2
    assert any(row["decision"] == "TRAIN_ACCEPTED" for row in result["history"])
    assert result["validation_used_for_search"] is False
    assert result["promotable"] is False
    assert result["human_status"] == "NOT_EVALUATED"


def test_holdout_rejection_restores_baseline():
    result = fit(cases(validation=0.6))
    assert result["status"] == "VALIDATION_REJECTED_ROLLED_BACK"
    assert result["selected_parameters"] == {"mix": 1.0}
    assert result["parameter_delta"]["mix"] == 0
    assert result["proposed_train_loss"] < result["baseline_train_loss"]


def test_no_effect_not_claimed_improvement():
    result = optimize_reference_feedback({"mix": 1.0}, {"mix": (0.5, 2.0)}, cases(),
                                        lambda p, s: Rendered(tone(1), True, {}))
    assert result["status"] == "NO_IMPROVEMENT"
    assert result["selected_parameters"] == {"mix": 1.0}


def test_rejected_numeric_trial_never_published():
    result = optimize_reference_feedback({"mix": 1.0}, {"mix": (0.5, 2.0)}, cases(),
        lambda p, s: Rendered(tone(p["mix"]), p["mix"] <= 1, {}))
    assert result["selected_parameters"]["mix"] == 1
    assert any(row["decision"] == "INVALID_TRIAL_REJECTED" for row in result["history"])


def test_deterministic_budget_and_bounds():
    config = SearchConfig(max_trials=5)
    a, b = fit(config=config), fit(config=config)
    assert a == b
    assert a["trial_count"] <= 5
    assert all(0.5 <= r["parameters"]["mix"] <= 2 for r in a["history"])


@pytest.mark.parametrize("field,value", [("source_id", "source-a"), ("source_sha256", "a"*64)])
def test_no_source_leakage(field, value):
    refs = cases()
    refs[1] = replace(refs[1], **{field: value})
    with pytest.raises(ValueError, match="leakage"):
        fit(refs)


def test_identical_clip_on_fake_independent_source_rejected():
    refs = cases()
    refs[1] = replace(refs[1], audio=refs[0].audio.copy())
    with pytest.raises(ValueError, match="leakage"):
        fit(refs)


@pytest.mark.parametrize("bad", [[], [cases()[0]], [replace(cases()[0], comparable=False), cases()[1]]])
def test_missing_or_unreviewed_data_is_not_zero_error(bad):
    with pytest.raises(ValueError):
        fit(bad)


@pytest.mark.parametrize("audio", [np.zeros(4096), np.full(4096, np.nan), np.ones(4096)*0.3,
                                    np.ones(4096)*2, np.ones(16), np.ones(128, dtype=complex)])
def test_invalid_audio_rejected(audio):
    with pytest.raises(ValueError):
        spectral_features(audio)


def test_analysis_gain_invariance_without_pcm_mutation():
    original = tone(1)
    saved = original.copy()
    assert feature_distance(spectral_features(original), spectral_features(original * 0.2)) < 1e-12
    np.testing.assert_array_equal(original, saved)
    assert audio_sha(original) != audio_sha(original * 0.2)


def test_stereo_antiphase_is_not_silence():
    a = tone(1)
    assert np.all(np.isfinite(spectral_features(np.column_stack([a, -a]))))


def test_parameter_whitelist_and_type_rejection():
    for values in ({"mix": True}, {"mix": np.nan}, {"gain": 1.0}, {"mix": 2.1}):
        with pytest.raises(ValueError):
            validate_parameters(values, {"mix": (0.5, 2.0)})


def test_dtype_normalization():
    np.testing.assert_allclose(pcm_float(np.zeros(64, dtype=np.uint8))[:, 0], -1)
    np.testing.assert_allclose(pcm_float(np.full(64, 16384, dtype=np.int16))[:, 0], 0.5)


def test_fixed_candidate_window_not_silently_truncated():
    refs = cases()
    refs[0] = replace(refs[0], candidate_window_s=(0, 2))
    with pytest.raises(ValueError, match="outside scene"):
        fit(refs)


@pytest.mark.parametrize("config", [SearchConfig(max_trials=0), SearchConfig(rounds=True),
                                    SearchConfig(regression_fraction=np.nan), SearchConfig(max_trials=1000)])
def test_invalid_search_limits(config):
    with pytest.raises(ValueError):
        fit(config=config)
