from __future__ import annotations

from tools.sound_sim.s12.real_reference.run_exact_mosqito_metrics import build_receipt_from_rows


def test_mosqito_receipt_builder_preserves_18_clip_tool_provenance() -> None:
    rows = [
        {
            "pair_id": "hellcat_01",
            "side": "reference",
            "input_sha256": "a" * 64,
            "metrics": {"loudness_sone": 1.0},
        },
        {
            "pair_id": "hellcat_01",
            "side": "candidate",
            "input_sha256": "b" * 64,
            "metrics": {"loudness_sone": 2.0},
        },
    ]
    receipt = build_receipt_from_rows(rows, "manifest-sha")
    assert receipt["status"] == "EXECUTED_ON_EXACT_CLIPS"
    assert receipt["tool"] == "MoSQITo"
    assert receipt["results"] == rows
    assert receipt["order_status"] == "ORDER_COMPARISON_NOT_QUALIFIED"
