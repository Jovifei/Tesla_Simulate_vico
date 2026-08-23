from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from tools.sound_sim.s12.real_reference.professional_clip_analysis import (
    ExactClipValidationError,
    analyze_proxy_pair,
    load_exact_anchor_pairs,
    validate_exact_clip_pair,
)
from tools.sound_sim.s12.tests.test_s12_anchor_ab_validate import _make_package


def test_load_exact_anchor_pairs_preserves_nine_page_trials(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    pairs = load_exact_anchor_pairs(package / "anchor_ab_zh_manifest.json")
    assert len(pairs) == 9
    assert {pair["vehicle_id"] for pair in pairs} == {"ferrari_458", "hellcat", "rx7_fd"}
    assert all(pair["reference_class"] == "R3" for pair in pairs)
    assert all(pair["order"]["status"] == "ORDER_COMPARISON_NOT_QUALIFIED" for pair in pairs)


def test_exact_pair_requires_both_audio_files_and_sha(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    pair = load_exact_anchor_pairs(package / "anchor_ab_zh_manifest.json")[0]
    pair["window"]["duration_s"] = 0.001
    result = validate_exact_clip_pair(pair)
    assert result["status"] == "PASS"
    assert result["reference"]["sha_status"] == "MATCH"
    assert result["candidate"]["sha_status"] == "MATCH"
    assert result["reference"]["duration_s"] == pytest.approx(0.002)
    assert result["candidate"]["duration_s"] == pytest.approx(0.002)


def test_exact_pair_rejects_zero_duration_audio(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    pair = load_exact_anchor_pairs(package / "anchor_ab_zh_manifest.json")[0]
    zero = Path(pair["reference_path"])
    with wave.open(str(zero), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8_000)
        handle.writeframes(b"")
    with pytest.raises(ExactClipValidationError, match="duration"):
        validate_exact_clip_pair(pair)


def test_proxy_pair_has_eight_bands_spectrogram_and_transient_fields(tmp_path: Path) -> None:
    package = _make_package(tmp_path)
    pair = load_exact_anchor_pairs(package / "anchor_ab_zh_manifest.json")[0]
    pair["window"]["duration_s"] = 0.001
    result = analyze_proxy_pair(pair)
    assert result["tool_domains"] == ["Legacy Proxy"]
    assert set(result["legacy_proxy"]["bands"]) == {"20_60", "60_120", "120_250", "250_400", "400_1000", "1000_4000", "4000_5500", "5500_12000"}
    assert result["spectrogram_residual"]["status"] == "COMPUTED_LEGACY_PROXY"
    assert "attack_s" in result["legacy_proxy"]["transient"]
    assert "crest_factor" in result["legacy_proxy"]["transient"]
    assert result["order"]["status"] == "ORDER_COMPARISON_NOT_QUALIFIED"
