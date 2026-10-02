import importlib
import importlib.util

import numpy as np
import pytest


_MODULE_NAME = "experiment_s13_c63_rpm_guard_bank"
guard = importlib.import_module(_MODULE_NAME) if importlib.util.find_spec(_MODULE_NAME) else None


def require_module():
    assert guard is not None, "S13.5 RPM guard candidate module is not implemented"
    return guard


def test_candidate_is_exactly_the_registered_local_guard_grid():
    module = require_module()

    assert module.CANDIDATE_RPMS == (5_400, 5_600)
    assert module.HOLDOUT_RPMS == (5_450, 5_550)
    assert module.LOADS == (0.32, 0.92)
    assert set(module.CANDIDATE_RPMS).isdisjoint(module.HOLDOUT_RPMS)


def test_inventory_digest_is_order_independent_and_content_bound():
    module = require_module()

    first = module._canonical_inventory_sha({"b.wav": "2", "a.wav": "1"})
    reordered = module._canonical_inventory_sha({"a.wav": "1", "b.wav": "2"})
    changed = module._canonical_inventory_sha({"a.wav": "1", "b.wav": "3"})

    assert first == reordered
    assert first != changed


def test_error_summary_reports_absolute_window_error():
    module = require_module()

    summary = module._error_summary([0.0, 1.0, 2.0, 4.0])

    assert summary["count"] == 4
    assert summary["median_db"] == pytest.approx(1.5)
    assert summary["p90_db"] == pytest.approx(3.4)


def test_candidate_root_rejects_repository_and_production_overlap(tmp_path, monkeypatch):
    module = require_module()
    allowed = tmp_path / "download"
    app = tmp_path / "app"
    production = app / "assets" / "c63"
    monkeypatch.setattr(module, "ALLOWED_OUTPUT_ROOT", allowed)
    allowed.mkdir()
    app.mkdir()
    production.mkdir(parents=True)

    with pytest.raises(ValueError, match="outside the Vico repository"):
        module._require_external_root(app / "candidate", app, production)
    other_app = tmp_path / "other-app"
    other_app.mkdir()
    with pytest.raises(ValueError, match="outside the production bank"):
        module._require_external_root(production / "nested", other_app, production)


def test_source_candidate_frame_contract_is_fixed():
    module = require_module()

    assert module.SAMPLE_RATE_HZ == 48_000
    assert module.CONDITION_FRAMES == 192_000
    assert module.WINDOW_FRAMES == 4_800
    assert module.TOTAL_FRAMES == 1_440_000


def test_error_gate_does_not_count_unchanged_windows_as_strict_improvement():
    module = require_module()

    result = module.evaluate_error_gate(
        [0.0, 0.0, 1.0, 1.0], [10.0] * 4, [10.0, 10.0, 9.0, 9.0],
        minimum_median_improvement_db=0.5, minimum_strict_improvement_fraction=0.6,
    )

    assert result["strict_improved_fraction"] == pytest.approx(0.5)
    assert result["pass"] is False


def test_error_gate_compares_absolute_error_p90_directly():
    module = require_module()

    result = module.evaluate_error_gate(
        [4.0, -20.0, 4.0, 4.0], [10.0, 10.0, 10.0, 10.0], [6.0, 30.0, 6.0, 6.0],
        minimum_median_improvement_db=1.0, minimum_strict_improvement_fraction=0.6,
    )

    assert result["improvement"]["median_db"] == pytest.approx(4.0)
    assert result["p90_not_worse"] is False
    assert result["pass"] is False


def test_protection_gate_rejects_a_single_low_band_regression():
    module = require_module()

    result = module.evaluate_protection_gate([{
        "scope": "fixed:rpm_6100_load_92", "band": "20-200",
        "A": {"median_db": 2.9, "p90_db": 3.0, "count": 30},
        "B": {"median_db": 3.0, "p90_db": 4.47, "count": 30},
    }])

    assert result["pass"] is False
    assert result["rows"][0]["p90_regression_db"] > 0.5
