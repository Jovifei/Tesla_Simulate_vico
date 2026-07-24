import pathlib
import sys
import unittest
import json
import tempfile
import wave


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "s12" / "acoustic_demo"
sys.path.insert(0, str(DEMO_ROOT))

from engine_operating_points.library import load_operating_point_library  # noqa: E402
from s12_acoustic_audition import PressureTrace  # noqa: E402
from sound_renderer.s12_product_renderer import renderer_profile_from_library, render_product_wav  # noqa: E402
from audio_parameter_package.package import build_audio_parameter_package, validate_audio_parameter_package  # noqa: E402


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


class ProductRendererAndPackageTests(unittest.TestCase):
    def test_renderer_writes_portable_48khz_24bit_stereo_metadata(self):
        library = load_operating_point_library()
        trace = PressureTrace.uniform(
            "renderer-fixture", [0.0, 0.12, -0.12, 0.06] * 120,
            48000, 50.0, "engine_exhaust_port", ("synthetic",),
        )
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root)
            metadata = render_product_wav(
                trace, folder / "fixture.wav", folder / "fixture.json",
                renderer_profile_from_library(library),
            )
            with wave.open(str(folder / "fixture.wav"), "rb") as audio:
                self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()), (48000, 2, 3))
            self.assertEqual(metadata["sample_rate"], 48000)
            self.assertEqual(metadata["gain_db"], -3.0)
            self.assertEqual(metadata["source_hash"], trace.source_identity_sha256)
            self.assertTrue(metadata["synthetic"])
            self.assertEqual(json.loads((folder / "fixture.json").read_text(encoding="utf-8")), metadata)

    def test_renderer_rejects_uncontracted_sample_rate(self):
        library = load_operating_point_library()
        trace = PressureTrace.uniform(
            "wrong-rate", [0.0, 0.1, -0.1, 0.0], 44100, 50.0,
            "engine_exhaust_port", ("synthetic",),
        )
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                render_product_wav(trace, pathlib.Path(root) / "bad.wav", pathlib.Path(root) / "bad.json", renderer_profile_from_library(library))

    def test_audio_parameter_package_is_versioned_json_with_a_hash(self):
        library = load_operating_point_library()
        package = build_audio_parameter_package(library, renderer_profile_from_library(library), "test-commit")
        validate_audio_parameter_package(package)
        self.assertEqual(package["version"], "AudioParameterPackage v0.1")
        self.assertEqual(package["source_commit"], "test-commit")
        self.assertEqual(package["engine_id"], "synthetic_four_cylinder_four_stroke")
        self.assertTrue(package["synthetic"])
        self.assertEqual(json.loads(json.dumps(package, sort_keys=True)), package)


if __name__ == "__main__":
    unittest.main()
