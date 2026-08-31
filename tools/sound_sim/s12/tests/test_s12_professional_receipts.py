from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.professional_clip_analysis import load_exact_anchor_pairs
from tools.sound_sim.s12.real_reference.professional_receipts import (
    ProfessionalReceiptError,
    validate_mosqito_receipt,
    validate_matlab_receipt,
)
from tools.sound_sim.s12.tests.test_s12_anchor_ab_validate import _make_package


MATLAB_TOOLCHAIN = [
    "acousticLoudness",
    "acousticSharpness",
    "acousticRoughness",
    "acousticFluctuation",
    "acousticToneToNoiseRatio",
    "acousticProminenceRatio",
]


def _receipt(pairs: list[dict], tool: str, *, candidate_only: bool = False) -> dict:
    rows = []
    for pair in pairs:
        sides = ("candidate",) if candidate_only else ("reference", "candidate")
        for side in sides:
            rows.append({
                "pair_id": pair["pair_id"],
                "side": side,
                "vehicle_id": pair["vehicle_id"],
                "sample_rate_hz": 48_000,
                "window": {"start_s": 0.0, "duration_s": 5.0},
                "input_sha256": pair[f"{side}_sha256"],
                "metrics": {
                    "loudness_sone": 1.0,
                    "sharpness_acum": 1.0,
                    "roughness_asper": 1.0,
                    "fluctuation_vacil": 1.0,
                    "tone_to_noise_ratio_db": 1.0,
                    "tone_to_noise_frequency_hz": 1000.0,
                    "prominence_ratio_db": 1.0,
                    "prominence_frequency_hz": 1000.0,
                },
                "units": {"loudness_sone": "sone", "sharpness_acum": "acum", "roughness_asper": "asper", "fluctuation_vacil": "vacil"},
            })
    if tool == "MATLAB Audio Toolbox":
        return {
            "schema_version": "s12-professional-matlab-exact-clip-receipt-v1",
            "status": "EXECUTED_ON_EXACT_CLIPS",
            "matlab_release": "R2026a",
            "toolchain": MATLAB_TOOLCHAIN,
            "analysis_signal": "unaltered digital-domain; not calibrated SPL",
            "results": rows,
            "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        }
    return {
        "schema_version": "s12-professional-mosqito-exact-clip-receipt-v1",
        "status": "EXECUTED_ON_EXACT_CLIPS",
        "tool": "MoSQITo",
        "mosqito_version": "1.2.1",
        "results": rows,
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
    }


def test_matlab_receipt_requires_reference_and_candidate_for_all_pairs(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    pairs = load_exact_anchor_pairs(package / "anchor_ab_zh_manifest.json")
    receipt = _receipt(pairs, "MATLAB Audio Toolbox")
    result = validate_matlab_receipt(receipt, pairs)
    assert result["status"] == "VALIDATED_EXACT_CLIPS"
    assert result["clip_count"] == 18
    assert result["tool_domain"] == "Professional MATLAB"


def test_matlab_receipt_rejects_candidate_only(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    pairs = load_exact_anchor_pairs(package / "anchor_ab_zh_manifest.json")
    with pytest.raises(ProfessionalReceiptError, match="reference and candidate"):
        validate_matlab_receipt(_receipt(pairs, "MATLAB Audio Toolbox", candidate_only=True), pairs)


def test_matlab_receipt_rejects_proxy_claim(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    pairs = load_exact_anchor_pairs(package / "anchor_ab_zh_manifest.json")
    receipt = _receipt(pairs, "MATLAB Audio Toolbox")
    receipt["toolchain"] = ["Legacy Proxy"]
    with pytest.raises(ProfessionalReceiptError, match="toolchain"):
        validate_matlab_receipt(receipt, pairs)


def test_mosqito_receipt_requires_version_and_all_18_clips(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    pairs = load_exact_anchor_pairs(package / "anchor_ab_zh_manifest.json")
    result = validate_mosqito_receipt(_receipt(pairs, "MoSQITo"), pairs)
    assert result["status"] == "VALIDATED_EXACT_CLIPS"
    assert result["clip_count"] == 18
    assert result["tool_domain"] == "Professional MoSQITo"
