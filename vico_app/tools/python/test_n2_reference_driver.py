"""Tests of actual manifest helpers. They do not claim that the helper renders PCM."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from n2_reference_driver import calibrate, export_fixture


class ReferenceDriverTest(unittest.TestCase):
    def test_export_writes_bound_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "export"
            manifest = export_fixture(output, b"synthetic trajectory", b"binary fixture", [1, 2, 3])
            actual = json.loads((output / "manifest.json").read_text())
            self.assertEqual(hashlib.sha256(b"synthetic trajectory").hexdigest(), actual["fixture_sha256"])
            self.assertEqual(hashlib.sha256(b"binary fixture").hexdigest(), actual["artifact_sha256"])
            self.assertEqual(3, actual["states"])
            self.assertEqual([333, 297, 960], actual["partitions"])
            self.assertEqual(["T", "S", "E_ON", "E_OFF", "SE_ON", "SE_OFF"], actual["modes"])
            self.assertEqual(manifest["artifact_sha256"], actual["artifact_sha256"])
            self.assertEqual(["manifest.json"], [p.name for p in output.iterdir()])

    def test_calibration_helper_valid_input_and_nonpositive_denominator(self):
        self.assertEqual(2., calibrate(2., 4.))
        for value in (0., -1.):
            with self.assertRaises(ValueError):
                calibrate(value, 4.)


if __name__ == "__main__":
    unittest.main()
