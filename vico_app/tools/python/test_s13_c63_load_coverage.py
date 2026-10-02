import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

_EXPERIMENT_NAME = "experiment_s13_c63_load_coverage"
experiment = (
    importlib.import_module(_EXPERIMENT_NAME)
    if importlib.util.find_spec(_EXPERIMENT_NAME)
    else None
)


APP_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = Path(r"E:\Tesla_speed\prj\tools")
VEHICLE = "c63_w204_v6"
BANK_ROOT = APP_ROOT / "Project/android/app/src/main/assets/s12_v10" / VEHICLE
TRACE_PATH = BANK_ROOT / "common_input_trace.json"


def require_experiment_module():
    assert experiment is not None, "C63 load-coverage experiment module is not implemented"
    return experiment


def test_cli_help_parses_arguments_without_creating_output():
    script = Path(__file__).with_name("experiment_s13_c63_load_coverage.py")
    result = subprocess.run(
        [sys.executable, "-B", str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--output-root" in result.stdout


def test_c63_extrema_and_single_factor_variants_come_from_trace():
    module = require_experiment_module()
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    base_levels = sorted({float(loop["load"]) for loop in json.loads(
        (BANK_ROOT / "manifest.json").read_text(encoding="utf-8")
    )["loops"]})

    minimum, maximum = module.trace_load_bounds(trace["points"])
    variants = module.plan_load_variants(base_levels, minimum, maximum)

    assert (minimum, maximum) == (0.08, 0.98)
    assert variants == {
        "A": (0.32, 0.92),
        "B-low": (0.08, 0.32, 0.92),
        "B-high": (0.32, 0.92, 0.98),
        "B-both": (0.08, 0.32, 0.92, 0.98),
    }


def test_no_variant_is_generated_for_an_already_covered_edge():
    module = require_experiment_module()
    variants = module.plan_load_variants((0.08, 0.32, 0.92, 0.98), 0.08, 0.98)

    assert variants == {"A": (0.08, 0.32, 0.92, 0.98)}


def test_candidate_output_cannot_alias_or_nest_under_production_bank(tmp_path):
    module = require_experiment_module()
    candidate = tmp_path / "candidate"
    assert module.validate_candidate_root(candidate, BANK_ROOT) == candidate.resolve()

    with pytest.raises(ValueError, match="outside the production bank"):
        module.validate_candidate_root(BANK_ROOT, BANK_ROOT)
    with pytest.raises(ValueError, match="outside the production bank"):
        module.validate_candidate_root(BANK_ROOT / "candidate", BANK_ROOT)

    candidate.mkdir()
    (candidate / "unrelated.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="not empty"):
        module.validate_candidate_root(candidate, BANK_ROOT)


def test_fixed_gain_is_applied_once_and_never_reduced_to_hide_overload():
    module = require_experiment_module()
    source = np.array([0.1, -0.2], dtype=np.float32)
    scaled = module.apply_fixed_gain(source, 2.0, peak_limit_dbfs=-1.5)
    np.testing.assert_array_equal(scaled, source * np.float32(2.0))

    with pytest.raises(ValueError, match="fixed vehicle gain exceeds peak limit"):
        module.apply_fixed_gain(np.array([0.9], dtype=np.float32), 1.0, peak_limit_dbfs=-1.5)


def test_renderer_load_trajectory_reports_requested_clamped_and_smoothed_values():
    module = require_experiment_module()
    build = getattr(module, "build_renderer_load_trajectory", None)
    assert callable(build), "load analysis must expose the renderer's request/clamp/smoothing stages"
    points = [
        {"time_s": index / 50.0, "rpm": 1000.0, "load": 0.08 if index == 0 else 0.92,
         "throttle": 0.2, "acceleration_mps2": 0.0}
        for index in range(1501)
    ]

    requested, clamped, smoothed = build(
        points, 0.32, 0.92, total_frames=960, block_frames=960, sample_rate_hz=48000,
    )

    assert requested.shape == clamped.shape == smoothed.shape == (960,)
    assert requested[0] == 0.08
    assert clamped[0] == 0.32
    assert smoothed[0] == 0.32
    assert requested[-1] > 0.91
    assert smoothed[-1] < clamped[-1]


def test_load_window_classifier_keeps_separated_segments_and_events_separate():
    module = require_experiment_module()
    classify = getattr(module, "classify_load_windows", None)
    assert callable(classify), "window analysis must preserve contiguous load regions and event windows"
    requested = np.array([0.10] * 4 + [0.50] * 4 + [0.12] * 4 + [0.50] * 4)
    smoothed = requested.copy()
    windows = classify(
        requested, smoothed, [{"id": "shift_1", "kind": "shift", "start_frame": 4, "sample_count": 4}],
        sample_rate_hz=48000, window_frames=4, low_boundary=0.32, high_boundary=0.92,
        transition_guard_frames=0, event_guard_frames=0, start_guard_frames=0, stop_guard_frames=0,
    )

    assert [window["group"] for window in windows] == ["low", "event_shift", "low", "in_range"]
    assert [window["start_frame"] for window in windows if window["group"] == "low"] == [0, 8]
    assert all(not window["eligible"] for window in windows if window["group"].startswith("event_"))


def test_load_window_classifier_marks_smoothing_boundary_guard():
    module = require_experiment_module()
    classify = getattr(module, "classify_load_windows", None)
    assert callable(classify), "window analysis must mark load-boundary smoothing transitions"
    loads = np.array([0.10] * 4 + [0.50] * 8)
    windows = classify(
        loads, loads, [], sample_rate_hz=48000, window_frames=4,
        low_boundary=0.32, high_boundary=0.92,
        transition_guard_frames=1, event_guard_frames=0, start_guard_frames=0, stop_guard_frames=0,
    )

    assert windows[0]["exclusion_reason"] == "load_boundary_transition"
    assert windows[1]["exclusion_reason"] == "load_boundary_transition"
    assert windows[2]["eligible"]


def test_candidate_gate_requires_five_windows_one_db_median_gain_and_no_p90_regression():
    module = require_experiment_module()
    evaluate = getattr(module, "evaluate_coverage_gate", None)
    assert callable(evaluate), "load-edge selection must use the pre-registered evidence gate"
    baseline = {
        "stable_window_count": 10,
        "bands": {
            "200-1000": {"absolute_error_median_db": 4.0, "absolute_error_p90_db": 6.0},
            "1000-4000": {"absolute_error_median_db": 5.0, "absolute_error_p90_db": 7.0},
        },
    }
    improved = {
        "stable_window_count": 10,
        "bands": {
            "200-1000": {"absolute_error_median_db": 2.9, "absolute_error_p90_db": 5.8},
            "1000-4000": {"absolute_error_median_db": 3.9, "absolute_error_p90_db": 7.0},
        },
    }
    insufficient = {**improved, "stable_window_count": 4}
    p90_regression = {
        **improved,
        "bands": {
            **improved["bands"],
            "1000-4000": {"absolute_error_median_db": 3.9, "absolute_error_p90_db": 7.1},
        },
    }

    assert evaluate(baseline, improved, ("200-1000", "1000-4000"))["status"] == "PASS"
    assert evaluate(baseline, insufficient, ("200-1000",))["status"] == "INSUFFICIENT_STABLE_WINDOWS"
    assert evaluate(baseline, p90_regression, ("200-1000", "1000-4000"))["status"] == "FAIL"


def test_window_spectral_features_separate_low_and_high_frequency_tones():
    module = require_experiment_module()
    measure = getattr(module, "window_feature_db", None)
    assert callable(measure), "window analysis must report frequency-band energy"
    sample_rate = 48000
    time = np.arange(4800) / sample_rate
    low = 0.1 * np.sin(2.0 * np.pi * 100.0 * time)
    high = 0.1 * np.sin(2.0 * np.pi * 5000.0 * time)

    low_features = measure(low, sample_rate)
    high_features = measure(high, sample_rate)

    assert low_features["20-200"] > low_features["4000-12000"] + 20.0
    assert high_features["4000-12000"] > high_features["20-200"] + 20.0


def test_real_c63_generation_preserves_every_old_bank_asset(tmp_path):
    module = require_experiment_module()
    before = module.bank_sha256_inventory(BANK_ROOT)
    output_root = tmp_path / "c63-s13-load-candidates"

    result = module.generate_c63_load_candidates(
        app_root=APP_ROOT,
        source_root=SOURCE_ROOT,
        output_root=output_root,
    )

    after = module.bank_sha256_inventory(BANK_ROOT)
    assert before == after
    assert result["vehicle_key"] == VEHICLE
    assert result["fixed_vehicle_gain"] == json.loads(
        (BANK_ROOT / "manifest.json").read_text(encoding="utf-8")
    )["fixed_vehicle_gain"]
    assert result["variants"]["A"]["load_levels"] == [0.32, 0.92]
    assert result["variants"]["B-low"]["load_levels"] == [0.08, 0.32, 0.92]
    assert result["variants"]["B-high"]["load_levels"] == [0.32, 0.92, 0.98]
    assert result["variants"]["B-both"]["load_levels"] == [0.08, 0.32, 0.92, 0.98]
    assert result["base_asset_sha256"] == before
    assert len(result["candidate_asset_sha256"]) == 16
    assert all(Path(path).is_file() for path in result["candidate_asset_paths"])
    assert output_root.is_dir()
