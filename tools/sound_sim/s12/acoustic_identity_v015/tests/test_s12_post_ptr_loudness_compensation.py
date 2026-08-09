"""Unit tests for the Track S post-PTR per-state loudness compensation layer.

The Track S source EQ (`_inject_state_spectral_targets`) is source-energy
preserving but redistributes band energy; the frozen PTR low-cut then turns
that redistribution into a per-state POST-PTR loudness spread (2.11 -> 12.19 dB
across the fixed-load rpm probes). This layer restores the pre-shaping post-PTR
loudness with a single per-clip scalar make-up gain, so:

  * band shares stay EXACTLY invariant (a scalar cannot move a ratio), hence the
    per-state band-share targets are untouched;
  * the source pressure is never touched (the source-level RMS gate is intact);
  * the frozen PTR is not modified.
"""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

_V015 = Path(__file__).resolve().parents[1]
if str(_V015.parent) not in sys.path:
    sys.path.insert(0, str(_V015.parent))

from acoustic_identity_v015.loudness_manager import measure_loudness  # noqa: E402
from acoustic_identity_v015.tuning.loudness_compensation import (  # noqa: E402
    apply_post_ptr_compensation,
    post_ptr_makeup_gain_db,
)

_SR = 48000


def _tone(freq_hz: float, amplitude: float, seconds: float = 0.6) -> np.ndarray:
    count = int(round(seconds * _SR))
    t = np.arange(count, dtype=np.float64) / _SR
    mono = amplitude * np.sin(2.0 * np.pi * freq_hz * t)
    return np.column_stack((mono, 0.8 * mono))


def _band_shares(audio: np.ndarray) -> np.ndarray:
    mono = np.asarray(audio, dtype=np.float64).mean(axis=1)
    power = np.square(np.abs(np.fft.rfft(mono * np.hanning(mono.size))))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / _SR)
    edges = [(20, 250), (250, 1000), (1000, 4000), (4000, 12000)]
    bands = np.array([float(power[(freqs >= lo) & (freqs <= hi)].sum()) for lo, hi in edges])
    return bands / (float(power.sum()) or 1e-30)


class PostPtrCompensationTests(unittest.TestCase):
    def test_makeup_gain_lifts_shaped_to_reference_loudness(self) -> None:
        reference = _tone(1500.0, 0.30)
        shaped = _tone(1500.0, 0.10)  # ~ -9.5 dB quieter
        _, gain_db = apply_post_ptr_compensation(shaped, reference, _SR)
        compensated, _ = apply_post_ptr_compensation(shaped, reference, _SR)
        self.assertGreater(gain_db, 0.0)
        self.assertAlmostEqual(
            measure_loudness(compensated).integrated_lufs,
            measure_loudness(reference).integrated_lufs,
            delta=0.25,
        )

    def test_scalar_gain_leaves_band_shares_invariant(self) -> None:
        reference = _tone(300.0, 0.20) + _tone(2000.0, 0.20)
        shaped = _tone(300.0, 0.05) + _tone(2000.0, 0.05)
        compensated, _ = apply_post_ptr_compensation(shaped, reference, _SR)
        np.testing.assert_allclose(_band_shares(compensated), _band_shares(shaped), atol=1e-9)

    def test_identity_reference_is_a_no_op(self) -> None:
        signal = _tone(1200.0, 0.2)
        compensated, gain_db = apply_post_ptr_compensation(signal, signal, _SR)
        self.assertAlmostEqual(gain_db, 0.0, delta=1e-6)
        np.testing.assert_allclose(compensated, signal, atol=1e-12)

    def test_gain_is_clamped_to_the_bound(self) -> None:
        reference = _tone(1500.0, 0.9)
        shaped = _tone(1500.0, 0.0005)  # would need ~ +65 dB
        gain_db = post_ptr_makeup_gain_db(shaped, reference, _SR, max_gain_db=12.0)
        self.assertAlmostEqual(gain_db, 12.0, delta=1e-9)

    def test_nonfinite_or_silent_inputs_are_no_ops(self) -> None:
        signal = _tone(1000.0, 0.2)
        silent = np.zeros_like(signal)
        self.assertEqual(post_ptr_makeup_gain_db(signal, silent, _SR), 0.0)
        self.assertEqual(post_ptr_makeup_gain_db(silent, signal, _SR), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
