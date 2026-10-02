import importlib
import importlib.util

import numpy as np
import pytest


_MODULE_NAME = "experiment_s13_c63_anchor_resonance"
resonance = (
    importlib.import_module(_MODULE_NAME)
    if importlib.util.find_spec(_MODULE_NAME)
    else None
)


def require_module():
    assert resonance is not None, "S13.5 anchor-resonance diagnostic is not implemented"
    return resonance


def test_porcelain_z_parser_preserves_status_and_paths_without_truncation():
    module = require_module()
    payload = b" M Project/android/README.md\0?? docs/a file.md\0A  tools/x.py\0"

    rows = module.parse_porcelain_z(payload)

    assert rows == [
        {"status": " M", "path": "Project/android/README.md"},
        {"status": "??", "path": "docs/a file.md"},
        {"status": "A ", "path": "tools/x.py"},
    ]


@pytest.mark.parametrize(
    ("target_rpm", "expected_role", "expected_index"),
    [(5_200.0, "upper", 1), (5_500.0, "same", 1), (6_100.0, "lower", 1)],
)
def test_5500_anchor_path_role_is_deterministic(target_rpm, expected_role, expected_index):
    module = require_module()

    result = module.anchor_path_for_target((4_300.0, 5_500.0, 6_800.0), target_rpm, 5_500.0)

    assert result == {"role": expected_role, "anchor_index": expected_index}


def test_anchor_self_power_share_uses_the_selected_path_and_same_window():
    module = require_module()
    time = np.arange(4_800, dtype=np.float64) / 48_000
    lower = 0.1 * np.sin(2 * np.pi * 700 * time)
    upper = 0.9 * np.sin(2 * np.pi * 1_100 * time)
    lower_index = np.full(time.shape, 0, dtype=np.uint8)
    upper_index = np.full(time.shape, 1, dtype=np.uint8)
    weight = np.full(time.shape, 0.5, dtype=np.float64)
    gain = np.ones(time.shape, dtype=np.float64)

    share = module.anchor_self_power_share(
        lower, upper, lower_index, upper_index, anchor_index=1, band="1000-4000",
        rpm_weight=weight, shared_gain=gain,
    )

    assert share > 0.98


def test_anchor_self_power_share_uses_sample_weights_not_raw_path_power():
    module = require_module()
    time = np.arange(4_800, dtype=np.float64) / 48_000
    lower = np.sin(2 * np.pi * 1_100 * time)
    upper = 3.0 * np.sin(2 * np.pi * 1_100 * time)
    lower_index = np.zeros(time.shape, dtype=np.uint8)
    upper_index = np.ones(time.shape, dtype=np.uint8)
    weight = np.full(time.shape, 0.2, dtype=np.float64)
    gain = np.ones(time.shape, dtype=np.float64)

    share = module.anchor_self_power_share(
        lower, upper, lower_index, upper_index, anchor_index=1,
        rpm_weight=weight, shared_gain=gain,
    )

    assert share == pytest.approx(0.36, abs=0.03)


def test_fixed_condition_window_excludes_warmup_and_does_not_concatenate():
    module = require_module()
    windows = module.stable_condition_windows(
        total_frames=4 * 48_000,
        sample_rate_hz=48_000,
        warmup_seconds=1.0,
        end_guard_seconds=0.0,
        window_frames=4_800,
    )

    assert len(windows) == 30
    assert windows[0] == (48_000, 52_800)
    assert windows[-1] == (187_200, 192_000)
    assert all(end - start == 4_800 for start, end in windows)
    assert all(right[0] == left[1] for left, right in zip(windows, windows[1:]))


def test_support_gate_requires_5500_share_both_intervals_and_both_neighbor_transfers():
    module = require_module()
    share_windows = [
        {"interval": interval, "share_5500": 0.9}
        for interval in (4, 5)
        for _ in range(12)
    ]
    source = {
        "load_32": {"5200": {"band_db": 0.0}, "5500": {"band_db": 7.0}, "6100": {"band_db": 0.5}},
        "load_92": {"5200": {"band_db": 0.0}, "5500": {"band_db": 7.0}, "6100": {"band_db": 0.5}},
    }
    transfer = {
        "load_32": {"5200": {"difference_db": 7.0}, "5500": {"difference_db": 0.2}, "6100": {"difference_db": 7.0}},
        "load_92": {"5200": {"difference_db": 7.0}, "5500": {"difference_db": 0.2}, "6100": {"difference_db": 7.0}},
    }

    result = module.evaluate_resonance_gate(share_windows, source, transfer)

    assert result["status"] == "5500_STATIONARY_RESONANCE_TRANSFER_SUPPORTED"
    assert result["production_fix_implemented"] is False

    failed = module.evaluate_resonance_gate(share_windows[:10], source, transfer)
    assert failed["status"] == "NOT_SUPPORTED"

