"""Stage AI-4A true-peak diagnostics only; no audio repair or threshold change."""
from __future__ import annotations

import json

import numpy as np
import pytest
from scipy.io import wavfile

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_pipeline import peak_estimate_4x
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.true_peak_diagnostics import (
    analyze_true_peak, analyze_wav,
)


def intersample_signal(frames=4096):
    sr = 48_000
    t = np.arange(frames) / sr
    # Continuous amplitude > 1, but this phase/frequency samples below 1.0.
    mono = 1.02 * np.sin(2*np.pi*4000*t + np.deg2rad(12.0))
    return np.column_stack([mono, 0.85*mono])


def test_detects_intersample_overshoot_without_modifying_input():
    audio = intersample_signal()
    saved = audio.copy()
    result = analyze_true_peak(audio)
    np.testing.assert_array_equal(audio, saved)
    assert result["sample_peak"] < 1.0
    assert result["worst_peak"] > 1.0
    assert result["classification"] == "INTERSAMPLE_OVERSHOOT_BLOCKED"
    assert result["factors"]["4"]["exceedance_count"] > 0
    assert result["audio_modified"] is False


def test_existing_four_x_gate_is_reproduced_exactly():
    audio = intersample_signal()
    old = peak_estimate_4x(audio)
    new = analyze_true_peak(audio)
    assert new["factors"]["4"]["peak"] == pytest.approx(old["peak"], rel=0, abs=1e-14)
    assert new["factors"]["4"]["factor"] == 4


def test_safe_signal_stays_safe_and_reports_local_spectrum():
    t = np.arange(4800) / 48_000
    audio = np.column_stack([.4*np.sin(2*np.pi*950*t), .3*np.sin(2*np.pi*950*t+.2)])
    result = analyze_true_peak(audio)
    assert result["classification"] == "WITHIN_THRESHOLD"
    assert result["worst_peak"] < 1.0
    assert result["local_spectrum"]["top_bins_hz"]
    assert result["local_spectrum"]["centroid_hz"] > 0


def test_wav_binding_and_hash_mismatch_fail_closed(tmp_path):
    audio = np.clip(intersample_signal(), -.99, .99)
    pcm = (audio*32767).astype(np.int16)
    path = tmp_path/"rx7.wav"
    wavfile.write(path, 48000, pcm)
    first = analyze_wav(path)
    assert first["wav_sha256"]
    again = analyze_wav(path, expected_sha256=first["wav_sha256"])
    assert again["wav_sha256"] == first["wav_sha256"]
    with pytest.raises(ValueError, match="SHA mismatch"):
        analyze_wav(path, expected_sha256="0"*64)


@pytest.mark.parametrize("bad", [
    np.zeros(16),
    np.array([np.nan]*128),
    np.ones((128, 3)),
    np.ones(128, dtype=np.complex128),
])
def test_invalid_audio_is_rejected(bad):
    with pytest.raises(ValueError):
        analyze_true_peak(bad)


@pytest.mark.parametrize("rate", [True, 0, 7999])
def test_invalid_sample_rate_rejected(rate):
    with pytest.raises(ValueError):
        analyze_true_peak(np.zeros((128,2)), sample_rate=rate)


def test_json_serializable_no_nan():
    result = analyze_true_peak(intersample_signal())
    text = json.dumps(result, allow_nan=False)
    assert "INTERSAMPLE_OVERSHOOT_BLOCKED" in text
