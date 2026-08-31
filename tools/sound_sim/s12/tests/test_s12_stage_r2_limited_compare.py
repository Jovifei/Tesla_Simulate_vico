from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_comparator.core import ComparisonCase
from tools.sound_sim.s12.real_reference.limited import compare_r2_signals
from tools.sound_sim.s12.real_reference.qualification import ReferenceQualificationError


def _case() -> ComparisonCase:
    return ComparisonCase(
        vehicle_id="ferrari_458",
        scenario="acceleration",
        reference_id="q:ferrari_r2",
        candidate_id="candidate:test",
        sample_rate_hz=48_000,
        reference_rpm=(0.0, 0.0),
        candidate_rpm=(0.0, 0.0),
        reference_load=(0.0, 1.0),
        candidate_load=(0.0, 1.0),
        analysis_domain="unaltered_analysis_signal",
        reference_kind="external_recording",
        reference_provenance="authorised R2 test fixture",
    )


def test_r2_comparison_preserves_relative_only_boundary() -> None:
    t = np.arange(16_384) / 48_000.0
    reference = np.sin(2 * np.pi * 240 * t)
    candidate = np.sin(2 * np.pi * 260 * t)
    record = {
        "recording_id": "ferrari_r2",
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "file_present": True,
        "sha256": "a" * 64,
        "provenance": {"legal_permission": "CONFIRMED"},
    }
    result = compare_r2_signals(reference, candidate, _case(), record, candidate_scenario="acceleration")
    assert result["reference_qualification"]["level"] == "R2"
    assert result["uncertainty"]["digital_domain_relative_only"] is True
    assert result["uncertainty"]["identity_score_available"] is False
    assert result["order"]["used_for_gate"] is False
    assert result["recommendation_status"].startswith("WITHHELD")


def test_r2_comparison_rejects_unverified_record() -> None:
    record = {
        "recording_id": "ferrari_r2_missing_rights",
        "vehicle_id": "ferrari_458",
        "scenario": "acceleration",
        "file_present": True,
        "sha256": "a" * 64,
        "provenance": {"legal_permission": "UNVERIFIED"},
    }
    with pytest.raises(ReferenceQualificationError, match="not R2-eligible"):
        compare_r2_signals(np.zeros(32), np.zeros(32), _case(), record)
