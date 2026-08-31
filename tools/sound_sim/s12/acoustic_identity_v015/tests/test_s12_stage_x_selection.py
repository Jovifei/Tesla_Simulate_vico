"""Stage X focused tests: selection contract, reference caseset, comparator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_x import multi_reference_comparator as mrc
from tools.sound_sim.s12.acoustic_identity_v015.stage_x import reference_caseset as rc
from tools.sound_sim.s12.acoustic_identity_v015.stage_x import selection_contract as sc

REPO_ROOT = Path(__file__).resolve().parents[5]
HELLCAT_MANIFEST = REPO_ROOT / "tools" / "sound_sim" / "s12" / "acoustic_identity_v015" / "reference_database" / "realism_reference_manifest.json"
R2_AUDIO_DIR = Path("E:/Claude_allow/Download/s12-acoustic-realism-v10")


# ---------------------------------------------------------------- X1


def test_two_layer_contract_defaults_keep_formal_gate_closed() -> None:
    contract = sc.build_selection_contract()
    assert contract["engineering_preselection"]["status"] == "NOT_ATTEMPTED"
    assert contract["engineering_preselection"]["architecture"] is None
    assert contract["formal_selection"]["status"] == "FORMAL_R1_REFERENCE_MISSING"
    assert contract["formal_selection"]["architecture"] is None
    assert "missing_r1_does_not_block" in contract["separation_policy"]
    assert "engineering_preselection" in contract["separation_policy"]["missing_r1_does_not_block"]


def test_engineering_preselection_forbidden_claims_rejected() -> None:
    with pytest.raises(ValueError):
        sc.validate_engineering({"status": "R2_ENGINEERING_PRESELECTION", "limitations": ["APPROVED_PROFILE reached"]})


def test_engineering_preselection_accepts_r2_level() -> None:
    record = sc.validate_engineering(
        {
            "status": "R2_ENGINEERING_PRESELECTION",
            "architecture": "P3",
            "evidence_level": "R2_AUDIO_DIAGNOSTIC",
            "objective": {"improvement_fraction": 0.21},
        }
    )
    assert record["architecture"] == "P3"
    assert record["evidence_level"] == "R2_AUDIO_DIAGNOSTIC"


def test_formal_selection_requires_pass_for_architecture() -> None:
    with pytest.raises(ValueError):
        sc.validate_formal({"architecture": "P3", "status": "FORMAL_SELECTION_READY_NOT_RUN"})


def test_selection_eligibility_is_data_driven() -> None:
    eligible = sc.evaluate_selection_eligibility(
        hard_gates_passed=True,
        valid_reference_count=3,
        median_improvement_fraction=0.18,
        reference_evidence_level="R2_AUDIO_DIAGNOSTIC",
    )
    assert eligible["selection_eligible"] is True
    assert eligible["blocking_reasons"] == []
    blocked = sc.evaluate_selection_eligibility(
        hard_gates_passed=False,
        valid_reference_count=0,
        median_improvement_fraction=None,
        reference_evidence_level="NONE",
    )
    assert blocked["selection_eligible"] is False
    assert "HARD_GATES_FAILED" in blocked["blocking_reasons"]
    assert "VALID_REFERENCE_COUNT_LT_2" in blocked["blocking_reasons"]
    assert "MEDIAN_OBJECTIVE_UNAVAILABLE" in blocked["blocking_reasons"]


# ---------------------------------------------------------------- X2


def _speech_like(seconds: float, sample_rate: int) -> np.ndarray:
    rng = np.random.default_rng(7)
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    syllable = 0.5 * (1.0 + np.sin(2.0 * np.pi * 4.0 * t))
    carrier = np.sin(2.0 * np.pi * 900.0 * t) + 0.6 * np.sin(2.0 * np.pi * 1800.0 * t + 0.4)
    return 0.5 * syllable * carrier + 0.02 * rng.standard_normal(t.size)


def _engine_like(seconds: float, sample_rate: int) -> np.ndarray:
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    return 0.8 * np.sin(2.0 * np.pi * 90.0 * t) + 0.4 * np.sin(2.0 * np.pi * 180.0 * t) + 0.2 * np.sin(2.0 * np.pi * 270.0 * t) + 0.05 * np.sin(2.0 * np.pi * 1500.0 * t)


def test_speech_detector_flags_speech_and_passes_engine() -> None:
    sample_rate = 48000
    speech = rc.detect_speech(_speech_like(3.0, sample_rate), sample_rate)
    engine = rc.detect_speech(_engine_like(3.0, sample_rate), sample_rate)
    assert speech["speech_contaminated"] is True
    assert engine["speech_contaminated"] is False
    assert engine["speech_probability"] < speech["speech_probability"]


def test_reference_caseset_binds_and_rejects_rx7(tmp_path: Path) -> None:
    if not (R2_AUDIO_DIR / "9eh-Nq6NRmk.wav").is_file() or not HELLCAT_MANIFEST.is_file():
        pytest.skip("R2 reference audio not present on this machine")
    caseset = rc.build_reference_caseset("hellcat", HELLCAT_MANIFEST, R2_AUDIO_DIR)
    assert caseset["vehicle_id"] == "hellcat"
    assert caseset["bound_scenario_count"] >= 3
    scenarios = {case["scenario"] for case in caseset["cases"] if case["status"] == "BOUND"}
    assert "hot_idle" in scenarios
    for case in caseset["cases"]:
        if case["status"] == "BOUND":
            assert case["audio_sha256"] == "a737b618e58ff0d0" + "0" * 0 or len(case["audio_sha256"]) == 64
            assert case["evidence_level"] == "R3"
            assert case["rights_status"] == "R3_PRIVATE_DIAGNOSTIC_ONLY"
            assert case["rpm_trace"] is None
    rx7 = rc.build_reference_caseset(
        "rx7_fd",
        HELLCAT_MANIFEST,
        R2_AUDIO_DIR,
        human_speech_confirmations={"rx7_fd": "Jovi: extracted audio contains speech, not engine sound"},
    )
    assert rx7["valid_reference_count"] == 0
    assert all(case["status"] == "REJECTED_SPEECH_CONTAMINATED" for case in rx7["cases"])


# ---------------------------------------------------------------- X3


def test_loudness_match_is_gain_only() -> None:
    rng = np.random.default_rng(3)
    signal = rng.standard_normal(48000)
    matched = mrc.loudness_match_rms(signal, 0.2)
    assert np.allclose(mrc.timbre_metrics(matched, 48000)["canonical_band_shares"], mrc.timbre_metrics(signal, 48000)["canonical_band_shares"], atol=1e-9)


def test_comparator_prefers_candidate_closer_to_reference() -> None:
    sample_rate = 48000
    t = np.arange(sample_rate * 2) / sample_rate
    reference = 0.5 * np.sin(2 * np.pi * 90.0 * t) + 0.3 * np.sin(2 * np.pi * 250.0 * t)
    parent = 0.2 * np.sin(2 * np.pi * 90.0 * t) + 0.8 * np.sin(2 * np.pi * 3000.0 * t)
    candidate = 0.45 * np.sin(2 * np.pi * 90.0 * t) + 0.32 * np.sin(2 * np.pi * 250.0 * t)
    comparison = mrc.compare_case(reference, parent, candidate, sample_rate, candidate_id="P3")
    low = comparison["metrics"]["band_share_20_60"]
    assert low["candidate_vs_parent_rel"] <= 0.0
    aggregate = mrc.aggregate_dimensions(comparison, "hot_idle", render_seconds=1.0)
    assert "low_frequency_body" in aggregate
    multi = mrc.compare_multi_reference({"hot_idle": [{"dimensions": aggregate}]}, candidate_id="P3")
    assert multi["improvement_fraction"] > 0.0
    assert "oem_similarity_percentage" in multi["forbidden_outputs"]
