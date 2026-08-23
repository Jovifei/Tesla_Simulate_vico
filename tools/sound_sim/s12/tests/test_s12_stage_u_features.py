from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.real_reference.stage_u_features import (
    FeatureContractError,
    bounded_dtw,
    extract_raw_feature_summary,
    openl3_capability,
    select_common_audio_feature_columns,
)
from tools.sound_sim.s12.real_reference.stage_u_timbral_runner import run as run_timbral


FS = 48_000


def _tone(frequency_hz: float, duration_s: float = 2.0) -> np.ndarray:
    time_s = np.arange(round(FS * duration_s), dtype=np.float64) / FS
    return np.sin(2.0 * np.pi * frequency_hz * time_s)


def test_identical_feature_trajectory_has_near_zero_bounded_dtw() -> None:
    features = np.column_stack((np.linspace(0.0, 1.0, 40), np.linspace(1.0, 0.0, 40)))
    result = bounded_dtw(features, features, {"scenario": "full_pull", "rpm_window": [3000, 6000]}, {"scenario": "full_pull", "rpm_window": [3100, 5900]})
    assert result["distance"] == pytest.approx(0.0, abs=1e-12)


def test_cross_scenario_dtw_is_rejected() -> None:
    features = np.ones((8, 2))
    with pytest.raises(FeatureContractError, match="scenario"):
        bounded_dtw(features, features, {"scenario": "idle", "rpm_window": [900, 1000]}, {"scenario": "full_pull", "rpm_window": [4000, 7000]})


def test_gain_changes_loudness_not_timbre_summary() -> None:
    reference = _tone(600.0) + 0.15 * _tone(3200.0)
    quieter = reference * 10.0 ** (-6.0 / 20.0)
    first = extract_raw_feature_summary(reference, FS)
    second = extract_raw_feature_summary(quieter, FS)
    assert second["rms_dbfs"] - first["rms_dbfs"] == pytest.approx(-6.0, abs=0.05)
    assert second["brightness_proxy"] == pytest.approx(first["brightness_proxy"], rel=1e-4)
    assert second["spectral_centroid_hz"] == pytest.approx(first["spectral_centroid_hz"], rel=1e-4)


def test_high_frequency_content_raises_brightness_and_lowpass_reduces_it() -> None:
    low = _tone(240.0)
    bright = low + 0.7 * _tone(5500.0)
    first = extract_raw_feature_summary(low, FS)
    second = extract_raw_feature_summary(bright, FS)
    assert second["brightness_proxy"] > first["brightness_proxy"]
    assert second["spectral_centroid_hz"] > first["spectral_centroid_hz"]


def test_70hz_am_raises_modulation_roughness_proxy() -> None:
    time_s = np.arange(2 * FS, dtype=np.float64) / FS
    carrier = np.sin(2.0 * np.pi * 800.0 * time_s)
    modulated = (1.0 + 0.8 * np.sin(2.0 * np.pi * 70.0 * time_s)) * carrier
    assert extract_raw_feature_summary(modulated, FS)["roughness_70hz_proxy"] > extract_raw_feature_summary(carrier, FS)["roughness_70hz_proxy"]


def test_openl3_unavailable_is_explicit_optional_research_metric() -> None:
    status = openl3_capability("ModuleNotFoundError: imp")
    assert status["classification"] == "OPTIONAL_RESEARCH_METRIC"
    assert status["hard_gate"] is False
    assert status["status"] == "PROJECT_UNMAINTAINED_NOT_AVAILABLE"


def test_timbral_runner_reports_unmaintained_runtime_failure_as_optional(tmp_path) -> None:
    path = tmp_path / "reference.wav"
    path.write_bytes(b"placeholder")
    result = run_timbral(path, extractor=lambda *_args, **_kwargs: (_ for _ in ()).throw(TypeError("legacy librosa API")))
    assert result["classification"] == "OPTIONAL_RESEARCH_METRIC"
    assert result["hard_gate"] is False
    assert result["status"] == "PROJECT_UNMAINTAINED_NOT_AVAILABLE"


def test_common_audio_feature_columns_exclude_sample_rate_dependent_bark_erb_bins() -> None:
    features = np.arange(24, dtype=float).reshape(3, 8)
    info = {"barkSpectrum": [1, 2], "erbSpectrum": [3], "mfcc": [4, 5], "gtcc": [6], "spectralFlux": 7, "pitch": 8}
    selected, columns = select_common_audio_feature_columns(features, info)
    assert columns == [4, 5, 6, 7, 8]
    assert np.array_equal(selected, features[:, [3, 4, 5, 6, 7]])
