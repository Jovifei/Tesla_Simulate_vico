import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[5]
PACKAGE = ROOT / "tools" / "sound_sim" / "s12" / "runtime_validation"
sys.path.insert(0, str(PACKAGE))

from cpp_equivalence import run_cpp_equivalence  # noqa: E402


BASE_SHA = "29b50961d9628f835e7172b797380ccb36a7f38d"


class CppGoldenEquivalenceTests(unittest.TestCase):
    def test_native_core_matches_all_python_golden_cases(self):
        zig = os.environ.get("APP1_ZIG")
        if not zig or not Path(zig).is_file():
            self.skipTest("Set APP1_ZIG to the approved Zig host compiler path.")
        with tempfile.TemporaryDirectory() as folder:
            report = run_cpp_equivalence(
                Path(folder),
                zig_path=Path(zig),
                source_revision=BASE_SHA,
                seed=20260924,
            )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["profile_count"], 2)
        self.assertEqual(report["case_count"], 10)
        self.assertEqual(report["state_samples"], 2000)
        self.assertEqual(report["native_profile_mismatches"], 0)
        self.assertLessEqual(report["max_virtual_rpm_abs_error"], 0.001)
        self.assertLessEqual(report["max_load_abs_error"], 0.000001)
        self.assertEqual(report["event_mismatches"], 0)
        self.assertLessEqual(report["max_pcm_sample_abs_error"], 0.00005)
        self.assertLessEqual(report["max_pcm_rms_abs_error"], 0.000005)


if __name__ == "__main__":
    unittest.main()
