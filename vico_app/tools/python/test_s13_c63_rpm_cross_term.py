import importlib
import importlib.util

import numpy as np
import pytest


_MODULE_NAME = "experiment_s13_c63_rpm_cross_term"
cross_term = (
    importlib.import_module(_MODULE_NAME)
    if importlib.util.find_spec(_MODULE_NAME)
    else None
)


def require_module():
    assert cross_term is not None, "S13.4 RPM cross-term analyzer is not implemented"
    return cross_term


def test_in_phase_equal_paths_include_the_factor_two_cross_term():
    module = require_module()
    time = np.arange(4_800, dtype=np.float64) / 48_000
    low = 0.1 * np.sin(2 * np.pi * 1_000 * time)
    high = low.copy()
    weight = np.full(time.shape, 0.5)
    gain = np.ones(time.shape)
    mix = (1 - weight) * low + weight * high

    result = module.analyze_window(low, high, weight, gain, mix, mix)

    assert result["bands"]["1000-4000"]["cross_term_db"] == pytest.approx(3.0103, abs=0.02)
    assert result["bands"]["1000-4000"]["coherent_db"] == pytest.approx(
        result["bands"]["1000-4000"]["no_cross_db"] + 3.0103, abs=0.02
    )


def test_opposite_phase_paths_produce_destructive_cross_term():
    module = require_module()
    time = np.arange(4_800, dtype=np.float64) / 48_000
    low = 0.1 * np.sin(2 * np.pi * 1_000 * time)
    high = -low
    weight = np.full(time.shape, 0.5)
    mix = (1 - weight) * low + weight * high

    result = module.analyze_window(low, high, weight, np.ones_like(weight), mix, mix)

    assert result["bands"]["1000-4000"]["cross_term_db"] < -40


@pytest.mark.parametrize("weight_value", [0.0, 1.0])
def test_endpoint_rpm_weights_have_zero_cross_term(weight_value):
    module = require_module()
    time = np.arange(4_800, dtype=np.float64) / 48_000
    low = 0.07 * np.sin(2 * np.pi * 700 * time)
    high = 0.04 * np.sin(2 * np.pi * 1_700 * time)
    weight = np.full(time.shape, weight_value)
    mix = (1 - weight) * low + weight * high

    result = module.analyze_window(low, high, weight, np.ones_like(weight), mix, mix)

    assert result["bands"]["200-1000"]["cross_term_db"] == pytest.approx(0.0, abs=1e-8)


def test_dynamic_weights_are_samplewise_and_independent_of_input_block_partition():
    module = require_module()
    total = 9_600
    time = np.arange(total, dtype=np.float64) / 48_000
    low = 0.08 * np.sin(2 * np.pi * 520 * time)
    high = 0.06 * np.sin(2 * np.pi * 1_420 * time + 0.3)
    weight = np.linspace(0.2, 0.8, total)
    gain = np.linspace(0.7, 1.0, total)
    mix = (1 - weight) * low * gain + weight * high * gain
    boundaries = [0, 137, 2_401, 6_003, total]
    fields = (low, high, weight, gain, mix)
    chunks = [
        tuple(field[start:end] for field in fields)
        for start, end in zip(boundaries, boundaries[1:])
    ]
    reassembled = tuple(np.concatenate([chunk[index] for chunk in chunks]) for index in range(5))

    whole = [module.analyze_window(*(field[start:start + 4_800] for field in fields[:4]),
                                   fields[4][start:start + 4_800],
                                   fields[4][start:start + 4_800])
             for start in (0, 4_800)]
    chunked = [module.analyze_window(*(field[start:start + 4_800] for field in reassembled[:4]),
                                     reassembled[4][start:start + 4_800],
                                     reassembled[4][start:start + 4_800])
               for start in (0, 4_800)]

    assert chunked == whole
    assert any(item["bands"]["1000-4000"]["cross_term_db"] != 0 for item in whole)


def test_inconsistent_mix_window_or_clipped_capture_is_rejected():
    module = require_module()
    time = np.arange(4_800, dtype=np.float64) / 48_000
    low = 0.04 * np.sin(2 * np.pi * 1_000 * time)
    high = 0.03 * np.sin(2 * np.pi * 1_300 * time)
    weight = np.full(time.shape, 0.5)
    gain = np.ones_like(weight)
    mix = (1 - weight) * low + weight * high

    with pytest.raises(ValueError, match="reconstruct"):
        module.analyze_window(low, high, weight, gain, mix + 0.01, mix)
    clipped = mix.copy()
    clipped[0] = 1.0
    with pytest.raises(ValueError, match="clipp"):
        module.analyze_window(low, high, weight, gain, clipped, mix)


def test_different_frame_windows_or_spectral_normalization_are_rejected(monkeypatch):
    module = require_module()
    time = np.arange(4_800, dtype=np.float64) / 48_000
    low = 0.04 * np.sin(2 * np.pi * 1_000 * time)
    high = 0.03 * np.sin(2 * np.pi * 1_300 * time)
    weight = np.full(time.shape, 0.5)
    gain = np.ones_like(weight)
    mix = (1 - weight) * low + weight * high

    with pytest.raises(ValueError, match="equal-sized"):
        module.analyze_window(low[:-1], high, weight, gain, mix, mix)
    feature = module.coverage.window_feature_db

    def mismatched_normalization(samples, sample_rate_hz):
        values = feature(samples, sample_rate_hz)
        values["1000-4000"] += 0.25
        return values

    monkeypatch.setattr(module.coverage, "window_feature_db", mismatched_normalization)
    with pytest.raises(ValueError, match="normalization"):
        module.analyze_window(low, high, weight, gain, mix, mix)


def test_mixed_window_requires_adjacent_anchors_and_eighty_percent_blended_frames():
    module = require_module()
    lower = np.zeros(4_800, dtype=np.uint8)
    upper = lower + 1
    weight = np.full(4_800, 0.5)

    qualified = module.classify_mixed_window(lower, upper, weight)
    weight[:1_000] = 0.1
    rejected = module.classify_mixed_window(lower, upper, weight)
    non_adjacent = module.classify_mixed_window(lower, lower + 2, np.full(4_800, 0.5))

    assert qualified["qualifies"]
    assert qualified["mixed_fraction"] == pytest.approx(1.0)
    assert not rejected["qualifies"]
    assert not non_adjacent["qualifies"]


def test_support_gate_requires_twenty_windows_two_intervals_and_all_registered_bands():
    module = require_module()
    window = {
        "qualifies": True,
        "rpm_interval_index": 1,
        "bands": {
            "200-1000": {
                "coherent_residual_db": 2.0, "cross_term_db": 0.1,
                "coherent_error_db": 2.0, "no_cross_error_db": 1.9,
            },
            "1000-4000": {
                "coherent_residual_db": 6.0, "cross_term_db": 1.5,
                "coherent_error_db": 6.0, "no_cross_error_db": 4.5,
            },
        },
    }
    windows = [{**window, "rpm_interval_index": index % 2} for index in range(20)]

    supported = module.evaluate_support_gate(windows)
    insufficient = module.evaluate_support_gate(windows[:19])
    single_interval = module.evaluate_support_gate([{**item, "rpm_interval_index": 0} for item in windows])
    lower_band_regression = module.evaluate_support_gate([
        {**item, "bands": {**item["bands"], "200-1000": {
            "coherent_residual_db": 2.0, "cross_term_db": 0.1,
            "coherent_error_db": 2.0, "no_cross_error_db": 2.1,
        }}}
        for item in windows
    ])

    assert supported["status"] == "RPM_CROSS_TERM_IS_A_MATERIAL_CONTRIBUTOR"
    assert insufficient["status"] == "INSUFFICIENT_MIXED_RPM_WINDOWS"
    assert single_interval["status"] == "INSUFFICIENT_MIXED_RPM_WINDOWS"
    assert lower_band_regression["status"] == "RPM_COHERENT_CROSS_TERM_NOT_SUPPORTED"

