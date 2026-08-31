from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.dashboard_contract import DashboardContractError, validate_dashboard_payload


def _payload() -> dict:
    pairs = []
    for index, vehicle_id in enumerate(("ferrari_458", "hellcat", "rx7_fd") * 3):
        pair_id = f"pair_{index:02d}"
        pairs.append({
            "pair_id": pair_id,
            "file_id": pair_id + "-reference-vs-candidate",
            "vehicle_id": vehicle_id,
            "scenario": "scenario_candidate_peak",
            "reference_class": "R3",
            "reference_sha256": "a" * 64,
            "candidate_sha256": "b" * 64,
            "integrity": {
                "reference": {"sha_status": "MATCH", "duration_s": 5.0},
                "candidate": {"sha_status": "MATCH", "duration_s": 5.0},
                "required_files": True,
            },
            "order": {"status": "ORDER_COMPARISON_NOT_QUALIFIED"},
        })
    return {"schema_version": "s12-professional-pair-metrics-v1", "status": "R2_PROFESSIONAL_COMPARISON_COMPLETE", "pair_count": 9, "pairs": pairs}


def test_dashboard_contract_accepts_nine_playable_sha_bound_pairs() -> None:
    result = validate_dashboard_payload(_payload())
    assert result["status"] == "PASS"
    assert result["pair_count"] == 9
    assert result["order_status"] == "ORDER_COMPARISON_NOT_QUALIFIED"


def test_dashboard_contract_rejects_zero_duration() -> None:
    payload = _payload()
    payload["pairs"][0]["integrity"]["reference"]["duration_s"] = 0.0
    with pytest.raises(DashboardContractError, match="duration"):
        validate_dashboard_payload(payload)


def test_dashboard_contract_rejects_sha_or_file_id_mismatch() -> None:
    payload = _payload()
    payload["pairs"][1]["integrity"]["candidate"]["sha_status"] = "MISMATCH"
    with pytest.raises(DashboardContractError, match="SHA"):
        validate_dashboard_payload(payload)
    payload = _payload()
    payload["pairs"][1]["file_id"] = "wrong"
    with pytest.raises(DashboardContractError, match="file_id"):
        validate_dashboard_payload(payload)


def test_dashboard_files_expose_chinese_professional_sections() -> None:
    root = Path(__file__).resolve().parents[4] / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"
    html = (root / "index.html").read_text(encoding="utf-8")
    js = (root / "dashboard.js").read_text(encoding="utf-8")
    css = (root / "dashboard.css").read_text(encoding="utf-8")
    for token in ("Professional MATLAB", "Professional MoSQITo", "Legacy Proxy", "参考播放器", "候选播放器", "频带", "spectrogram", "软件诊断是否符合听感"):
        assert token in html + js
    for token in ("canplaythrough", "duration", "sha_status", "Jovi_Guided_Feedback", "不能提交"):
        assert token in js
    assert "相似度百分比" not in html + js
    assert "--amber" in css and "--cyan" in css


def test_dashboard_uses_clickable_problem_chips_and_one_vehicle_level_submit() -> None:
    root = Path(__file__).resolve().parents[4] / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"
    js = (root / "dashboard.js").read_text(encoding="utf-8")
    assert "problem-chip" in js
    assert "提交全部车型反馈" in js
    assert "feedback_scope" in js
    assert "vehicle_id" in js
    assert "select multiple" not in js


def test_dashboard_exposes_chinese_focus_topics_and_scene_hint() -> None:
    root = Path(__file__).resolve().parents[4] / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"
    js = (root / "dashboard.js").read_text(encoding="utf-8")
    for token in ("topic-chip", "focus_topics", "怠速", "减速/收油", "换挡", "回火/爆音", "转速变化", "当前窗口主题"):
        assert token in js


def test_rx7_topic_dashboard_is_separate_and_fail_closed() -> None:
    root = Path(__file__).resolve().parents[4] / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"
    html = (root / "rx7_topic_r2.html").read_text(encoding="utf-8")
    js = (root / "rx7_topic_r2.js").read_text(encoding="utf-8")
    results = json.loads((root / "rx7_topic_r2_results.json").read_text(encoding="utf-8"))
    for token in ("RX-7 FD", "CC BY-NC-SA 4.0", "Professional MATLAB", "Professional MoSQITo", "ORDER_COMPARISON_NOT_QUALIFIED", "调整后候选"):
        assert token in html + js
    assert "audio" in html + js and "S12_RX7_TOPIC_R2_DATA" in js
    assert results["status"] == "RX7_R2_PROFESSIONAL_COMPARISON_COMPLETE"
    assert results["pair_count"] == 5 and results["clip_count"] == 10
    assert results["order_status"] == "ORDER_COMPARISON_NOT_QUALIFIED"
    assert results["candidate"]["source_modified"] is False


def test_unified_evidence_matrix_keeps_r3_proxy_separate_from_formal_tools() -> None:
    root = Path(__file__).resolve().parents[4] / "tasks" / "reports" / "runtime" / "S12_Professional_Comparison_Dashboard_v1"
    matrix = json.loads((root / "professional_evidence_matrix.json").read_text(encoding="utf-8"))
    assert matrix["status"] == "UNIFIED_PROFESSIONAL_EVIDENCE_MATRIX_READY"
    assert matrix["record_count"] == 33
    assert matrix["dashboard_exact_pair_count"] == 9
    assert matrix["stage_r3_record_count"] == 24
    assert set(matrix["tool_domains"]) == {"Professional MATLAB", "Professional MoSQITo", "Legacy Proxy", "Not Qualified"}
    exact = [row for row in matrix["records"] if row["evidence_family"] == "dashboard_exact_ab"]
    r3 = [row for row in matrix["records"] if row["evidence_family"] == "stage_r3_eight_vehicle_summary"]
    assert all(row["matlab_psychoacoustic_residual"] is not None for row in exact)
    assert all(row["matlab_psychoacoustic_residual"] is None and row["mosqito_psychoacoustic_residual"] is None for row in r3)
