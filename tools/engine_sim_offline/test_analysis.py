"""Synthetic checks only; never runs a physical trial or changes measurements."""
import importlib.util
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_captures as analysis


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fs = 8000
        cls.time = np.arange(60 * cls.fs) / cls.fs
        cls.am = (1 + .4 * np.sin(2 * np.pi * 1.8 * cls.time)) * np.sin(2 * np.pi * 997 * cls.time)

    def test_known_am_frequency_and_modulation(self):
        result, _ = analysis.envelope_metrics(self.am, self.fs, 10)
        self.assertAlmostEqual(result["slow_peak_hz"], 1.8, delta=.051)
        self.assertGreater(result["target_fraction_of_slow"], .98)
        self.assertAlmostEqual(result["cv"], .4 / math.sqrt(2), delta=.004)

    def test_absolute_power_is_not_normalized(self):
        a, _ = analysis.envelope_metrics(self.am, self.fs, 20)
        b, _ = analysis.envelope_metrics(self.am * 3, self.fs, 20)
        self.assertAlmostEqual(b["target_power"] / a["target_power"], 9, places=8)
        self.assertAlmostEqual(b["target_power_over_mean_squared"], a["target_power_over_mean_squared"], places=10)

    def test_fractional_lag_is_not_rounded_to_grid(self):
        t = np.arange(6000) / 100
        x = np.sin(2 * np.pi * 1.8 * t)
        exact = analysis.fractional_lag_acf(x, 100, 1 / 1.8)
        rounded = analysis.fractional_lag_acf(x, 100, .56)
        self.assertGreater(exact, .999999)
        self.assertGreater(exact - rounded, .001)

    def test_fractional_peak_recovers_noninteger_period(self):
        period = .553846153846
        t = np.arange(6000) / 100
        result, _ = analysis.acf_metrics(np.sin(2 * np.pi * t / period), 100)
        self.assertAlmostEqual(result["peak_lag_s"], period, delta=.0001)
        self.assertGreater(result["peak_correlation"], .99999)

    def test_e2_keeps_cycle_crop_period_and_only_modifies_seam(self):
        fs = 1000
        t = np.arange(12 * fs) / fs
        source = np.sin(2 * np.pi * 63 * t) * (1 + .1 * np.sin(2 * np.pi * 1.7 * t))
        st = np.arange(.0099, 12, .01)
        cycles = st * 910 / 120 + .23
        state = {"t_s": st, "rpm": np.full(st.size, 910.),
                 "integrated_cycles": cycles - cycles[0],
                 "cycle_angle_rad": np.mod(cycles, 1) * 4 * np.pi}
        output, loop, receipt = analysis.make_e2(source, fs, state, 12, "low")
        self.assertGreaterEqual(receipt["start_cycle_time_s"], 5)
        self.assertEqual(receipt["complete_720_cycles"], 4)
        n = len(loop)
        np.testing.assert_array_equal(output[:n], output[n:2*n])
        lo = receipt["crop_start_frame"]
        hi = receipt["crop_end_frame"]
        fade = receipt["crossfade_frames"]
        np.testing.assert_array_equal(loop[fade:-fade], source[lo:hi][fade:-fade])
        self.assertEqual(receipt["effective_period_frames"], hi - lo)
        with self.assertRaises(ValueError):
            analysis.make_e2(source, fs, state, 12, "main")

    def test_listening_uses_one_gain_with_explicit_peak_constraint(self):
        spike = np.zeros(10000)
        spike[5000] = 1
        receipt = analysis.listening_gain([spike], .1, .85)
        self.assertTrue(receipt["peak_constraint_active"])
        self.assertAlmostEqual(receipt["gain"], .85)
        self.assertAlmostEqual(receipt["achieved_peak"], .85)
        self.assertLess(receipt["achieved_pooled_rms"], .1)

    def test_nonfinite_is_invalid_not_repaired(self):
        values = np.array([0., 1., np.nan, np.inf])
        health = analysis.signal_health(values)
        self.assertEqual(health["nonfinite_count"], 2)
        self.assertFalse(health["valid"])

    def test_missing_rotation_evidence_cannot_be_a_coarse_pass(self):
        result = analysis.validate_physical_sidecar(None)
        self.assertTrue(result["errors"])
        self.assertTrue(result["status"].startswith("NOT_EVALUATED"))

    def test_nonnegative_omega_or_zero_lit_dwell_fails_closed(self):
        valid = {"cw_all_capture": True, "min_omega_rad_s": -100,
                 "max_omega_rad_s": -90, "lit_cylinder_steps": 100}
        for broken in ({**valid, "max_omega_rad_s": 0},
                       {**valid, "min_omega_rad_s": 90, "max_omega_rad_s": 100},
                       {**valid, "cw_all_capture": False},
                       {**valid, "lit_cylinder_steps": 0}):
            with self.subTest(broken=broken):
                result = analysis.validate_physical_sidecar(broken)
                self.assertEqual(result["status"], "INVALID_PHYSICAL_MODEL")
                self.assertTrue(result["errors"])

    def test_valid_sidecar_is_only_coarse_direction_and_lit_evidence(self):
        result = analysis.validate_physical_sidecar(
            {"cw_all_capture": True, "min_omega_rad_s": -100,
             "max_omega_rad_s": -90, "lit_cylinder_steps": 100})
        self.assertFalse(result["errors"])
        self.assertEqual(result["status"], "COARSE_DIRECTION_AND_ACTIVE_LIT_ONLY_NOT_CALIBRATED")

    def test_js_mapping_and_syntax_without_rendering(self):
        script = HERE / "render_vico_trace.mjs"
        subprocess.run(["node", "--check", str(script)], check=True, capture_output=True, text=True)
        expression = f"""import {{mapLoadProxy}} from {script.as_uri()!r};
            if(mapLoadProxy(0,101325)!==.05)throw Error('low clamp');
            if(mapLoadProxy(50662.5,101325)!==.5)throw Error('MAP ratio');
            if(mapLoadProxy(500000,101325)!==1)throw Error('high clamp');
            let bad=false;try{{mapLoadProxy(1,0)}}catch{{bad=true}};
            if(!bad)throw Error('invalid ambient accepted');"""
        subprocess.run(["node", "--input-type=module", "-e", expression], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
