from __future__ import annotations

import json
from pathlib import Path

from tools.sound_sim.s12.acoustic_identity_v015.stage_aa.semantic_closeout import (
    build_method_adoption_matrix_v3,
    build_scorecard_v2,
    load_metric_significance_contract,
)


ROOT = Path(__file__).resolve().parents[5]


def _scorecard_rows() -> list[dict]:
    payload = json.loads((ROOT / "tasks/reports/runtime/s12-stage-z/method_ablation_scorecard.json").read_text(encoding="utf-8"))
    return payload["rows"]


def test_metric_contract_has_independent_units_and_significance_floors() -> None:
    contract = load_metric_significance_contract()
    assert contract["schema"] == "s12.stage_aa.metric_significance_contract.v1"
    for name in ("spectral_centroid_hz", "spectral_flux", "roughness_proxy", "sharpness_proxy", "dynamic_range_db", "rms_dbfs"):
        item = contract["metrics"][name]
        assert item["unit"]
        assert item["absolute_floor"] > 0
        assert item["relative_floor"] > 0
        assert item["reason"] and item["estimation_method"]


def test_scorecard_v2_separates_causal_from_engineering_significance() -> None:
    payload = build_scorecard_v2(_scorecard_rows())
    assert payload["schema"] == "s12.stage_aa.method_ablation_scorecard.v2"
    assert len(payload["rows"]) == 12
    assert all("status" not in row for row in payload["rows"])
    assert all(row["deprecated_status"] == "PROVEN_CONTRIBUTION" for row in payload["rows"])
    collector = next(row for row in payload["rows"] if row["method_id"] == "engine_sim_collector_network")
    assert collector["causal_status"] == "CAUSAL_EFFECT_DETECTED"
    assert collector["engineering_significance_status"] == "BELOW_ENGINEERING_SIGNIFICANCE"
    assert collector["quality_direction_status"] == "REFERENCE_UNAVAILABLE"
    event = next(row for row in payload["rows"] if row["method_id"] == "engine_sim_event_pressure")
    assert event["engineering_significance_status"] == "MEANINGFUL_ENGINEERING_EFFECT"


def test_matrix_v3_keeps_adoption_separate_from_acoustic_significance() -> None:
    matrix = json.loads((ROOT / "docs/research/engine-audio-ecosystem/method_adoption_matrix_v2.json").read_text(encoding="utf-8"))
    scorecard = build_scorecard_v2(_scorecard_rows())
    result = build_method_adoption_matrix_v3(matrix, scorecard, base_main_head="209378bcb9a0c1a352ffd56ca1c765ecce01f81d")
    assert result["schema"] == "s12.stage_aa.method_adoption_matrix.v3"
    assert len(result["rows"]) == len(matrix["rows"])
    row = next(item for item in result["rows"] if item["method_id"] == "engine_sim_collector_network")
    assert row["adoption_status"] == "IMPLEMENTED_CLEAN_ROOM"
    assert row["acoustic_evidence"]["engineering_significance_status"] == "BELOW_ENGINEERING_SIGNIFICANCE"
