"""Real reader rejection tests over synthetic wire fixtures, never reference qualification."""
from dataclasses import replace
import hashlib
import math
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

import numpy as np

from fixtures.n2.render_fixture import replace_metadata, rewrite_row, write_fixture
from n2_reference_export import BRANCHES, CHANNELS, compare_partitions, measure, read_export


class ReferenceExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.shared.cleanup)
        cls.source = Path(cls.shared.name) / "source"
        write_fixture(cls.source)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "export"
        shutil.copytree(self.source, self.root)

    def test_loads_every_file_and_recomputes_measurements(self):
        actual = read_export(self.root)
        self.assertEqual(15, len(actual.payload_sha256))
        self.assertEqual(set(BRANCHES), set(actual.branches))
        self.assertEqual(1, actual.trajectory_segments)
        for branch in actual.branches.values():
            self.assertEqual((24000,), branch["pcm"].shape)
            self.assertEqual((24000, 9), branch["taps"].shape)
            self.assertEqual(set(CHANNELS), set(branch["stem_measurements"]))
            self.assertGreater(branch["measurement"]["rms"], 0)

    def test_float32_promoted_before_squaring(self):
        result = measure(np.array([1e20, -1e20], dtype=np.float32))
        self.assertTrue(result["energy_finite"])
        self.assertAlmostEqual(result["rms"] / 1e20, 1, places=6)
        self.assertEqual(0, measure(np.zeros(3))["rms"])
        for x in ([], [math.nan], [math.inf], [1e308], np.ones((2, 2))):
            with self.subTest(x=str(x)), self.assertRaises(ValueError):
                measure(x)

    def test_missing_payload_is_not_complete(self):
        (self.root / "se_event_off.taps.f64le").unlink()
        with self.assertRaises((ValueError, OSError)):
            read_export(self.root)

    def test_truncated_manifest_is_rejected(self):
        path = self.root / "manifest.tsv"
        path.write_text("\n".join(path.read_text().splitlines()[:-1]))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            read_export(self.root)

    def test_duplicate_payload_and_arbitrary_path_are_rejected(self):
        for name in ("t_event_on.pcm.f32le", "../private.pcm.f32le"):
            with self.subTest(name=name):
                rewrite_row(self.root, "s_event_on.pcm.f32le", file=name)
                with self.assertRaisesRegex(ValueError, "unknown or duplicate"):
                    read_export(self.root)
                shutil.copyfile(self.source / "manifest.tsv", self.root / "manifest.tsv")

    def test_manifest_schema_and_branch_identity_are_rejected(self):
        for changes in ({"candidate": "C63_HY1"}, {"mode": "E"}, {"events_audible": "false"},
                        {"bytes": "1"}, {"raw_arrivals": "NaN"}, {"pending_frames": "12289"}):
            with self.subTest(changes=changes):
                rewrite_row(self.root, "t_event_on.pcm.f32le", **changes)
                with self.assertRaises(ValueError):
                    read_export(self.root)
                shutil.copyfile(self.source / "manifest.tsv", self.root / "manifest.tsv")

    def test_tampered_payload_fails_hash(self):
        path = self.root / "s_event_on.pcm.f32le"
        payload = bytearray(path.read_bytes()); payload[0] ^= 1
        path.write_bytes(payload)
        with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
            read_export(self.root)

    def test_nonfinite_payload_rejected_even_with_updated_hash(self):
        for name, fmt in (("t_event_on.pcm.f32le", "<f"), ("t_event_on.taps.f64le", "<d")):
            with self.subTest(name=name):
                path = self.root / name
                payload = bytearray(path.read_bytes())
                struct.pack_into(fmt, payload, 0, math.nan)
                path.write_bytes(payload)
                rewrite_row(self.root, name, sha256=hashlib.sha256(payload).hexdigest())
                with self.assertRaisesRegex(ValueError, "nonfinite payload"):
                    read_export(self.root)
                shutil.copyfile(self.source / name, path)
                shutil.copyfile(self.source / "manifest.tsv", self.root / "manifest.tsv")

    def test_reported_metrics_cannot_substitute_for_actual_pcm(self):
        for key, value in (("rms", .00001), ("peak", .00001), ("impulse_frames", 1)):
            for suffix in (".pcm.f32le", ".taps.f64le"):
                rewrite_row(self.root, "t_event_on" + suffix, **{key: value, "raw_arrivals": 1})
            with self.subTest(key=key), self.assertRaises(ValueError):
                read_export(self.root)
            shutil.copyfile(self.source / "manifest.tsv", self.root / "manifest.tsv")

    def test_artifact_and_trajectory_bindings_are_checked(self):
        for name in ("profile.bin", "baseline.bin", "trajectory.bin"):
            with self.subTest(name=name):
                path = self.root / name
                path.write_bytes(path.read_bytes() + b"tamper")
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    read_export(self.root)
                shutil.copyfile(self.source / name, path)

    def test_resealed_malformed_baseline_and_trajectory_are_rejected(self):
        for name, metadata in (("baseline.bin", "baseline_artifact_sha256"), ("trajectory.bin", "fixture_sha256")):
            with self.subTest(name=name):
                path = self.root / name
                payload = bytearray(path.read_bytes()); payload[0] ^= 1
                path.write_bytes(payload)
                replace_metadata(self.root, metadata, hashlib.sha256(payload).hexdigest())
                if name == "baseline.bin":
                    replace_metadata(self.root, "baseline_identity", hashlib.sha256(payload).hexdigest())
                with self.assertRaises(ValueError):
                    read_export(self.root)
                shutil.copyfile(self.source / name, path)
                shutil.copyfile(self.source / "manifest.tsv", self.root / "manifest.tsv")

    def test_symlink_payload_and_output_root_rejected(self):
        path = self.root / "s_event_on.pcm.f32le"
        path.unlink()
        try:
            path.symlink_to(self.source / path.name)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows symbolic-link privilege unavailable")
            raise
        with self.assertRaisesRegex(ValueError, "non-regular"):
            read_export(self.root)
        link = Path(self.tmp.name) / "link"
        link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "regular directory"):
            read_export(link)

    def test_equivalent_schedules_clipped_at_trajectory_boundaries_rejected(self):
        before = read_export(self.root)
        before = replace(before, segment_frames=(200,) * 120)
        after = replace(before, metadata={**before.metadata, "partitions": "333,297"})
        with self.assertRaisesRegex(ValueError, "different realized"):
            compare_partitions(before, after)
        # Index advances on clipped blocks and is not reset per segment.
        first = replace(before, segment_frames=(500, 500), metadata={**before.metadata, "partitions": "333,297"})
        second = replace(first, metadata={**first.metadata, "partitions": "333,333"})
        # Both consume 333,167 per segment in this particular trajectory.
        with self.assertRaisesRegex(ValueError, "different realized"):
            compare_partitions(first, second)
        first = replace(first, segment_frames=(200, 500))
        second = replace(second, segment_frames=(200, 500))
        # After the 200-frame segment, 333,297 next requests 297, unlike 333,333.
        self.assertTrue(compare_partitions(first, second))

    def test_partition_identity_and_schedule_comparison(self):
        before = read_export(self.root)
        with self.assertRaisesRegex(ValueError, "different realized block schedules"):
            compare_partitions(before, before)
        for schedule in ("960,960", "4800", "4800,4800"):
            # The fixture has one 24000-frame segment. 960 duplicates have the
            # same realized blocks; 4800 schedules differ from the original.
            replace_metadata(self.root, "partitions", schedule)
            loaded = read_export(self.root)
            if schedule == "960,960":
                with self.assertRaisesRegex(ValueError, "different realized"):
                    compare_partitions(before, loaded)
            else:
                self.assertTrue(compare_partitions(before, loaded))
        replace_metadata(self.root, "partitions", "333,297")
        after = read_export(self.root)
        self.assertTrue(compare_partitions(before, after))
        after.payload_sha256["t_event_on.pcm.f32le"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "payload mismatch"):
            compare_partitions(before, after)
        after.metadata["fixture_id"] = "changed"
        with self.assertRaisesRegex(ValueError, "input identity"):
            compare_partitions(before, after)


@unittest.skipUnless(os.environ.get("VICO_N2_RENDER_EXPORT"), "opt-in actual JVM export directory not supplied")
class ActualJvmExportTest(unittest.TestCase):
    def test_actual_renderer_pcm_and_tap_artifacts(self):
        root = Path(os.environ["VICO_N2_RENDER_EXPORT"])
        block = read_export(root / "block960")
        split = read_export(root / "split333_297")
        self.assertTrue(compare_partitions(block, split))
        self.assertEqual(140160, int(block.metadata["frames"]))
        self.assertEqual(20, block.branches["e_event_on"]["impulse_frames"])
        self.assertEqual(23, block.branches["e_event_on"]["raw_arrivals_reported"])
        for mode in ("e", "se"):
            self.assertFalse(np.array_equal(block.branches[mode + "_event_on"]["pcm"],
                                           block.branches[mode + "_event_off"]["pcm"]))


if __name__ == "__main__":
    unittest.main()
