"""S12 Phase 2 - idle realism direction regression tests.

Validates that the upgraded idle_dynamics v2 preserves the vehicle identity
direction measured from Phase 1 real recordings:
  crest factor:   Hellcat > Ferrari > RX-7   (sharp V8 pulses vs smooth rotary)
  spectral centroid: Ferrari > Hellcat > RX-7 (metallic NA vs low-freq mechanical/rotary)
"""

from __future__ import annotations

import unittest

import numpy as np

from acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from acoustic_identity_v015.acoustic_layers.idle_dynamics import apply_idle_dynamics

_SR = 48000
_N = int(_SR * 3.0)
_VEHICLES = ["ferrari_458", "hellcat", "rx7_fd"]


class TestIdleRealismV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        t = np.arange(_N) / _SR
        cls.trace = VehicleStateTrace(
            time_s=t,
            rpm=np.full(_N, 850.0),
            load=np.full(_N, 0.10),
            throttle=np.full(_N, 0.05),
            acceleration_mps2=np.zeros(_N),
        )
        cls.results: dict[str, SourceRender] = {}
        for vid in _VEHICLES:
            render = SourceRender(pressure=np.zeros((_N, 2)), stems={"base": np.zeros((_N, 2))}, diagnostics={})
            cls.results[vid] = apply_idle_dynamics(render, vid, cls.trace, _SR)

    def _crest(self, vid: str) -> float:
        sig = self.results[vid].pressure.mean(axis=1)
        rms = float(np.sqrt(np.mean(np.square(sig))) or 1e-15)
        return float(np.max(np.abs(sig)) / rms)

    def _centroid(self, vid: str) -> float:
        sig = self.results[vid].pressure.mean(axis=1)
        spec = np.square(np.abs(np.fft.rfft(sig * np.hanning(sig.size))))
        freqs = np.fft.rfftfreq(sig.size, 1.0 / _SR)
        total = float(spec.sum()) or 1e-15
        return float(np.sum(freqs * spec) / total)

    def test_all_vehicles_rendered(self) -> None:
        for vid in _VEHICLES:
            self.assertIn(vid, self.results)
            self.assertTrue(np.all(np.isfinite(self.results[vid].pressure)))

    def test_crest_direction_hellcat_gt_ferrari(self) -> None:
        self.assertGreater(self._crest("hellcat"), self._crest("ferrari_458"), "Hellcat idle crest should exceed Ferrari (sharp V8 pulses)")

    def test_crest_direction_ferrari_gt_rx7(self) -> None:
        self.assertGreater(self._crest("ferrari_458"), self._crest("rx7_fd"), "Ferrari idle crest should exceed RX-7 (piston pulses vs smooth rotary)")

    def test_centroid_direction_ferrari_gt_hellcat(self) -> None:
        self.assertGreater(self._centroid("ferrari_458"), self._centroid("hellcat"), "Ferrari idle centroid should exceed Hellcat (metallic NA V8)")

    def test_centroid_direction_hellcat_gt_rx7(self) -> None:
        self.assertGreater(self._centroid("hellcat"), self._centroid("rx7_fd"), "Hellcat idle centroid should exceed RX-7 (mechanical V8 vs low-freq rotary)")

    def test_cycle_amplitude_std_nonzero_for_all(self) -> None:
        for vid in _VEHICLES:
            std = self.results[vid].diagnostics.get("idle_cycle_amplitude_std", 0.0)
            self.assertGreater(std, 0.0, f"{vid} idle cycle variation must be non-zero")

    def test_cycle_amplitude_std_hellcat_strongest(self) -> None:
        stds = {v: self.results[v].diagnostics["idle_cycle_amplitude_std"] for v in _VEHICLES}
        self.assertGreater(stds["hellcat"], stds["rx7_fd"], "Hellcat idle variation should be stronger than RX-7 (rotary is smoother)")

    def test_v2_model_identifier(self) -> None:
        for vid in _VEHICLES:
            self.assertEqual(self.results[vid].diagnostics["idle_dynamics_model"], "multi_freq_cycle_variation_broadband_mechanical_v2")

    def test_crest_target_reference_recorded(self) -> None:
        for vid in _VEHICLES:
            self.assertIn("idle_crest_target_reference", self.results[vid].diagnostics)
            self.assertGreater(self.results[vid].diagnostics["idle_crest_target_reference"], 0.0)

    def test_mechanical_texture_weight_recorded(self) -> None:
        for vid in _VEHICLES:
            self.assertIn("idle_mechanical_texture_weight", self.results[vid].diagnostics)

    def test_finite_stems_present(self) -> None:
        for vid in _VEHICLES:
            for stem in ("idle_combustion_variation", "idle_accessory", "idle_valvetrain", "idle_crank"):
                self.assertIn(stem, self.results[vid].stems, f"{vid} missing stem {stem}")
                self.assertTrue(np.all(np.isfinite(self.results[vid].stems[stem])))


if __name__ == "__main__":
    unittest.main()
