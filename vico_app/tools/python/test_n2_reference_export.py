"""Execute the current manifest-only export API, without asserting renderer qualification."""
import hashlib
import unittest

from n2_reference_export import calibrated_source_scale, export_manifest


class ReferenceExportTest(unittest.TestCase):
    def test_manifest_hashes_each_actual_input(self):
        manifest = export_manifest([b"first", b"second"], b"artifact", "profile-id", "calibration-id")
        self.assertEqual([hashlib.sha256(x).hexdigest() for x in (b"first", b"second")], manifest["fixtures"])
        self.assertEqual(hashlib.sha256(b"artifact").hexdigest(), manifest["artifact"])
        self.assertEqual("profile-id", manifest["profile"])
        self.assertEqual("calibration-id", manifest["calibration"])
        self.assertEqual(("T", "S", "E_ON", "E_OFF", "SE_ON", "SE_OFF"), manifest["modes"])
        self.assertEqual((333, 297, 960), manifest["partitions"])
        self.assertIs(False, manifest["objective"])
        self.assertIs(False, manifest["held_out"])

    def test_manifest_changes_when_fixture_or_artifact_changes(self):
        before = export_manifest([b"first"], b"artifact", "p", "c")
        after = export_manifest([b"changed"], b"modified", "p", "c")
        self.assertNotEqual(before["fixtures"], after["fixtures"])
        self.assertNotEqual(before["artifact"], after["artifact"])

    def test_scale_helper_executes_and_rejects_nonpositive_unit(self):
        self.assertEqual(2., calibrated_source_scale(2., 4.))
        for unit in (0., -1.):
            with self.assertRaises(ValueError):
                calibrated_source_scale(unit, 4.)


if __name__ == "__main__":
    unittest.main()
