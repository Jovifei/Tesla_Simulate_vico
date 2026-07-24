import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "s12" / "acoustic_demo"
sys.path.insert(0, str(DEMO_ROOT))

from engine_operating_points.library import load_operating_point_library  # noqa: E402


class EngineOperatingPointLibraryTests(unittest.TestCase):
    def test_library_has_documented_grid_provenance_and_canonical_hash(self):
        library = load_operating_point_library()
        self.assertEqual(library.rpm_grid, (800.0, 1500.0, 2500.0, 4000.0, 6000.0))
        self.assertEqual(library.load_grid, (0.0, 0.25, 0.5, 0.75, 1.0))
        self.assertEqual(library.source_level, "C")
        self.assertEqual(library.library_hash, library.canonical_hash())
        self.assertTrue(all(entry["source_level"] == "C" and entry["source"] == "synthetic" for entry in library.provenance_entries))

    def test_library_returns_exact_and_bilinear_continuous_parameters(self):
        library = load_operating_point_library()
        exact = library.evaluate(2500.0, 0.5)
        self.assertEqual(exact.rpm, 2500.0)
        self.assertEqual(exact.load, 0.5)
        self.assertAlmostEqual(exact.excitation_gain, 1.0)
        midpoint = library.evaluate(2000.0, 0.625)
        self.assertAlmostEqual(midpoint.excitation_gain, 1.0075)
        left = library.evaluate(2500.0 - 1.0e-6, 0.5)
        right = library.evaluate(2500.0 + 1.0e-6, 0.5)
        self.assertLess(abs(left.excitation_gain - right.excitation_gain), 1.0e-5)

    def test_library_rejects_out_of_range_inputs(self):
        library = load_operating_point_library()
        with self.assertRaises(ValueError):
            library.evaluate(799.0, 0.5)
        with self.assertRaises(ValueError):
            library.evaluate(2500.0, 1.01)


if __name__ == "__main__":
    unittest.main()
