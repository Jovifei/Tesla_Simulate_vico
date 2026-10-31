import hashlib
import json
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parent


class ApprovedContract(unittest.TestCase):
    def setUp(self):
        path = LAB / "EXPERIMENT_CONTRACT.json"
        self.assertTrue(path.is_file(), "approved experiment contract must exist")
        self.contract = json.loads(path.read_text(encoding="utf-8"))

    def test_native_b_input_and_frozen_baseline_identity(self):
        ref = self.contract["reference"]
        self.assertEqual(ref["capture_mat_sha256"], "bdefffc0f7b6d5071d8f359c6169c5c13ba46ea7294fb4ea788e503121beb919")
        self.assertEqual(ref["pcm_sha256"], "1a56b2f54ce3149a15d184c80257f1a838ddee83fd0ff193318d791b4dc396ef")
        self.assertEqual((ref["frames"], ref["columns"]), (4500, 9))
        with Path(ref["capture_mat"]).open("rb") as source:
            self.assertEqual(hashlib.file_digest(source, "sha256").hexdigest(), ref["capture_mat_sha256"])

    def test_fixed_experiment_controls(self):
        c = self.contract
        self.assertEqual(c["source_columns"], ["combustion_L", "combustion_R", "other_L", "other_R", "cycle_phase", "rpm", "load", "cut", "sample_time"])
        self.assertEqual(c["renderer_gain"], 0.1)
        self.assertEqual(c["network"], {"admittances": [1, 1, 2], "delays_samples": [48, 72], "losses": [0.99, 0.99], "reflections": [0.3, 0.3], "downstream_reflection": 0})
        self.assertEqual(c["calibration"], {"rpm": 2200, "load": 0.35, "throttle": 0.32, "duration_s": 6, "window_s": [1, 5], "status": "NOT_CALIBRATED"})
        self.assertEqual(c["cold_repeat"], "NEW_MATLAB_PROCESS_REQUIRED")
        self.assertEqual(c["mechanical_mix"], "POST_FROZEN_PRE_RENDERER_SUM")


if __name__ == "__main__":
    unittest.main()
