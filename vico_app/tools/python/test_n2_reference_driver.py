"""Measured diagnostic regression and CLI tests, with no acceptance/budget evaluation."""
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from build_c63_hybrid_targets import features
from fixtures.n2.render_fixture import replace_metadata, rewrite_row, write_fixture
from n2_hard_gate import metric_reasons
from n2_reference_driver import band_power, inspect_exports, main, protected_comparison

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


class ReferenceDriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.shared.cleanup)
        cls.source = Path(cls.shared.name) / "source"
        write_fixture(cls.source)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.export = self.root / "export"
        shutil.copytree(self.source, self.export)

    def test_welch_matches_existing_absolute_feature_definition(self):
        rng = np.random.default_rng(19)
        x = rng.normal(0, .1, 48000)
        np.testing.assert_allclose(band_power(x), features(x)["absolute_band_power"], rtol=1e-15, atol=0)

    def test_known_gain_deltas_and_no_sample_normalization(self):
        time = np.arange(48000) / 48000
        x = .1 * np.sin(2*np.pi*100*time) + .03 * np.sin(2*np.pi*900*time)
        candidate = x * 2
        before = x.copy()
        result = protected_comparison(x, candidate, x, candidate)
        for key in ("low_max_db", "mid_max_rise_db", "source_rms_change_db"):
            self.assertAlmostEqual(20*math.log10(2), result[key], places=10)
        np.testing.assert_array_equal(before, x)
        quieter = protected_comparison(x, x/2, x, x/2)
        self.assertGreater(quieter["low_max_db"], 0)
        self.assertLess(quieter["mid_max_rise_db"], 0)
        self.assertLess(quieter["source_rms_change_db"], 0)

    def test_protected_metrics_reject_unusable_windows(self):
        for x in (np.zeros(48000), np.ones(100), np.full(48000, math.nan), np.full(48000, 1e308)):
            with self.subTest(size=len(x)), self.assertRaises(ValueError):
                band_power(x)
        x = np.sin(np.arange(48000))
        with self.assertRaises(ValueError):
            protected_comparison(x, x, np.zeros(48000), x)
        with self.assertRaises(ValueError):
            protected_comparison(x, x[:-1], x, x)

    def test_measured_receipt_remains_non_accepting(self):
        result = inspect_exports(self.export)
        self.assertEqual("MEASURED_DIAGNOSTIC_ONLY_NOT_QUALIFICATION", result["status"])
        self.assertEqual(144000, result["evidence"]["sample_count"])
        self.assertIsNone(result["partition_invariant"])
        self.assertFalse(result["objective_evaluated"])
        self.assertFalse(result["budget_reserved"])
        self.assertEqual("NOT_PRODUCED", result["qualification"]["reference_result_v2"])
        self.assertNotIn("reservation", result)
        self.assertNotIn("provenance_groups", result["continuous"])
        self.assertNotIn("feasible", result)
        self.assertIn("snapshot_replay", metric_reasons(result))
        self.assertIn("provenance_groups_missing", metric_reasons(result))
        self.assertEqual(0, result["event_observations"]["E"]["on_minus_off_pcm"]["rms"])
        self.assertEqual(15, len(result["source_receipts"]["payload_sha256"]))
        self.assertAlmostEqual(20*math.log10(1.02), result["continuous"]["source_rms_change_db"], places=11)
        json.dumps(result, allow_nan=False)

    def test_window_validation(self):
        for start, stop in ((-1, None), (0, 23999), (0, 24001), (24000, 0), (True, None)):
            with self.subTest(start=start, stop=stop), self.assertRaises(ValueError):
                inspect_exports(self.export, start_frame=start, stop_frame=stop)

    def test_actual_partition_comparison_is_required_for_true(self):
        other = self.root / "other"
        shutil.copytree(self.export, other)
        replace_metadata(other, "partitions", "333,297")
        result = inspect_exports(self.export, other)
        self.assertIs(result["partition_invariant"], True)
        self.assertNotEqual(result["source_receipts"]["manifest_sha256"],
                            result["source_receipts"]["comparison_manifest_sha256"])

    def test_resealed_changed_non_bark_stem_is_rejected(self):
        path = self.export / "s_event_on.taps.f64le"
        taps = np.frombuffer(path.read_bytes(), dtype="<f8").copy().reshape(-1, 9)
        taps[:, 0] *= 2
        payload = taps.tobytes(); path.write_bytes(payload)
        rewrite_row(self.export, path.name, sha256=hashlib.sha256(payload).hexdigest())
        with self.assertRaisesRegex(ValueError, "non-bark"):
            inspect_exports(self.export)

    def test_shared_event_branches_cannot_hide_non_event_corruption(self):
        for column in (0, 1, 2, 3, 5, 6, 7):
            with self.subTest(column=column):
                for branch in ("e_event_on", "e_event_off", "se_event_on", "se_event_off"):
                    path = self.export / (branch + ".taps.f64le")
                    taps = np.frombuffer(path.read_bytes(), dtype="<f8").copy().reshape(-1, 9)
                    taps[:, column] += .01
                    payload = taps.tobytes(); path.write_bytes(payload)
                    rewrite_row(self.export, path.name, sha256=hashlib.sha256(payload).hexdigest())
                with self.assertRaisesRegex(ValueError, "event replacement changed"):
                    inspect_exports(self.export)
                for branch in ("e_event_on", "e_event_off", "se_event_on", "se_event_off"):
                    name = branch + ".taps.f64le"
                    shutil.copyfile(self.source / name, self.export / name)
                shutil.copyfile(self.source / "manifest.tsv", self.export / "manifest.tsv")

    def test_resealed_event_off_stem_is_rejected(self):
        for branch, column in (("e_event_off", 4), ("se_event_off", 0)):
            with self.subTest(branch=branch):
                path = self.export / (branch + ".taps.f64le")
                taps = np.frombuffer(path.read_bytes(), dtype="<f8").copy().reshape(-1, 9)
                taps[:, column] += .01
                payload = taps.tobytes(); path.write_bytes(payload)
                rewrite_row(self.export, path.name, sha256=hashlib.sha256(payload).hexdigest())
                with self.assertRaisesRegex(ValueError, "event-off"):
                    inspect_exports(self.export)
                shutil.copyfile(self.source / path.name, path)
                shutil.copyfile(self.source / "manifest.tsv", self.export / "manifest.tsv")

    def test_cli_direct_module_and_exclusive_output(self):
        for mode in ("script", "module"):
            output = self.root / (mode + ".json")
            command = [sys.executable, str(HERE / "n2_reference_driver.py")] if mode == "script" else [
                sys.executable, "-m", "vico_app.tools.python.n2_reference_driver"]
            command += ["--export", str(self.export), "--out", str(output)]
            run = subprocess.run(command, cwd=REPO, text=True, capture_output=True, timeout=30)
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
            before = output.read_bytes()
            self.assertEqual(hashlib.sha256(before).hexdigest(), json.loads(run.stdout)["output_sha256"])
            retry = subprocess.run(command, cwd=REPO, text=True, capture_output=True, timeout=30)
            self.assertEqual(2, retry.returncode, retry.stdout + retry.stderr)
            self.assertEqual(before, output.read_bytes())
        self.assertFalse(any("budget" in path.name for path in self.root.iterdir()))

    def test_cli_rejected_input_never_writes_success_receipt(self):
        output = self.root / "output.json"
        (self.export / "e_event_on.pcm.f32le").unlink()
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            code = main(["--export", str(self.export), "--out", str(output)])
        self.assertEqual(2, code)
        self.assertEqual("REJECTED", json.loads(stream.getvalue())["status"])
        self.assertFalse(output.exists())

    def test_cli_dangling_output_symlink_is_not_overwritten(self):
        output = self.root / "output.json"
        target = self.root / "absent.json"
        output.symlink_to(target)
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["--export", str(self.export), "--out", str(output)])
        self.assertEqual(2, code)
        self.assertTrue(output.is_symlink())
        self.assertFalse(target.exists())


@unittest.skipUnless(os.environ.get("VICO_N2_RENDER_EXPORT"), "opt-in actual JVM export directory not supplied")
class ActualJvmMetricsTest(unittest.TestCase):
    def test_measures_actual_kotlin_exports_without_acceptance(self):
        root = Path(os.environ["VICO_N2_RENDER_EXPORT"])
        report = inspect_exports(root / "block960", root / "split333_297")
        self.assertIs(report["partition_invariant"], True)
        self.assertEqual(840960, report["evidence"]["sample_count"])
        self.assertGreater(report["event_observations"]["E"]["on_minus_off_pcm"]["rms"], 0)
        self.assertEqual("NOT_RUN", report["qualification"]["event_distance"])
        self.assertGreater(report["continuous"]["source_rms_change_db"], 1)
        self.assertNotIn("feasible", report)


if __name__ == "__main__":
    unittest.main()
