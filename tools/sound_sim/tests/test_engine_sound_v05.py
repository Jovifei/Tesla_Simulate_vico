import pathlib
import sys
import unittest
import json
import hashlib
import tempfile
import wave
import subprocess
from dataclasses import replace
from copy import deepcopy


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "s12" / "acoustic_demo"
sys.path.insert(0, str(DEMO_ROOT))

from engine_operating_points.library import load_operating_point_library  # noqa: E402
from s12_acoustic_audition import PressureTrace  # noqa: E402
from sound_renderer.s12_product_renderer import renderer_profile_from_library, render_product_wav  # noqa: E402
from audio_parameter_package.package import build_audio_parameter_package, validate_audio_parameter_package  # noqa: E402
from engine_product_excitation import build_product_demo_states, generate_product_excitation, project_order_amplitude  # noqa: E402
from frozen_ptr_contract import EXPECTED_RADIATION_PACKAGE_SHA256, verify_frozen_radiation_package  # noqa: E402


SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def rehash_package(package):
    content = dict(package)
    content.pop("hash", None)
    package["hash"] = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


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
            self.assertEqual(metadata["gain_db"], -10.0)
            self.assertEqual(metadata["source_hash"], trace.source_identity_sha256)
            self.assertEqual(metadata["post_ptr_processing_contract"], "output_format_only_no_order_eq_limiter_or_synthesis")
            self.assertIn("dc_removal", metadata["processing"])
            self.assertTrue(metadata["synthetic"])
            self.assertEqual(json.loads((folder / "fixture.json").read_text(encoding="utf-8")), metadata)

    def test_renderer_resamples_uncontracted_uniform_input_to_48khz(self):
        library = load_operating_point_library()
        trace = PressureTrace.uniform(
            "wrong-rate", [0.0, 0.1, -0.1, 0.0], 44100, 50.0,
            "engine_exhaust_port", ("synthetic",),
        )
        with tempfile.TemporaryDirectory() as root:
            metadata = render_product_wav(trace, pathlib.Path(root) / "resampled.wav", pathlib.Path(root) / "resampled.json", renderer_profile_from_library(library))
            with wave.open(str(pathlib.Path(root) / "resampled.wav"), "rb") as audio:
                self.assertEqual(audio.getframerate(), 48000)
            self.assertEqual(metadata["resampled_from_hz"], 44100)
            self.assertIn("linear_resampling", metadata["processing"])

    def test_audio_parameter_package_is_versioned_json_with_a_hash(self):
        library = load_operating_point_library()
        package = build_audio_parameter_package(library, renderer_profile_from_library(library), SOURCE_COMMIT)
        validate_audio_parameter_package(package)
        self.assertEqual(package["version"], "AudioParameterPackage v0.1")
        self.assertEqual(package["source_commit"], SOURCE_COMMIT)
        self.assertEqual(package["engine_id"], "synthetic_four_cylinder_four_stroke")
        self.assertTrue(package["synthetic"])
        self.assertEqual(package["provenance"]["source_level"], "C")
        self.assertEqual(package["provenance"]["source"], "synthetic")
        self.assertEqual(json.loads(json.dumps(package, sort_keys=True)), package)

    def test_audio_parameter_package_pins_frozen_radiation_content(self):
        library = load_operating_point_library()
        package = build_audio_parameter_package(library, renderer_profile_from_library(library), SOURCE_COMMIT)
        ptr = verify_frozen_radiation_package()
        self.assertEqual(ptr["radiation_package_sha256"], EXPECTED_RADIATION_PACKAGE_SHA256)
        self.assertEqual(package["ptr_profile"]["radiation_package_sha256"], EXPECTED_RADIATION_PACKAGE_SHA256)
        self.assertEqual(package["ptr_profile"]["radiation_source_commit"], "4afe65a67ed21822422f1eb6dbf43fdd627072d3")

    def test_audio_parameter_package_rejects_nonportable_values_and_bad_commit(self):
        library = load_operating_point_library()
        package = build_audio_parameter_package(library, renderer_profile_from_library(library), SOURCE_COMMIT)
        nonfinite = deepcopy(package)
        nonfinite["renderer_profile"]["gain_db"] = float("nan")
        invalid_bool = deepcopy(package)
        invalid_bool["synthetic"] = "true"
        invalid_commit = deepcopy(package)
        invalid_commit["source_commit"] = "not-a-git-sha"
        for invalid in (nonfinite, invalid_bool, invalid_commit):
            rehash_package(invalid)
            with self.assertRaises(ValueError):
                validate_audio_parameter_package(invalid)


class ProductVerticalSliceTests(unittest.TestCase):
    def test_product_excitation_maps_rpm_load_and_acceleration_before_ptr(self):
        library = load_operating_point_library()
        states = build_product_demo_states(library)
        idle = generate_product_excitation(states["idle"], library)
        cruise = generate_product_excitation(states["cruise"], library)
        self.assertAlmostEqual(idle.firing_frequency_hz, 800.0 / 60.0)
        self.assertAlmostEqual(cruise.firing_frequency_hz, 2000.0 / 60.0)
        quiet = replace(states["cruise"], case_id="quiet", acceleration=tuple(0.0 for _ in states["cruise"].acceleration))
        active = replace(states["cruise"], case_id="active", acceleration=tuple(6.0 for _ in states["cruise"].acceleration))
        self.assertNotEqual(generate_product_excitation(quiet, library).pressure_pa, generate_product_excitation(active, library).pressure_pa)

    def test_load_changes_pre_ptr_harmonic_balance(self):
        library = load_operating_point_library()
        state = build_product_demo_states(library)["cruise"]
        low = replace(state, case_id="low", load=tuple(0.05 for _ in state.load), throttle=tuple(0.05 for _ in state.throttle))
        high = replace(state, case_id="high", load=tuple(1.0 for _ in state.load), throttle=tuple(1.0 for _ in state.throttle))
        low_trace = generate_product_excitation(low, library)
        high_trace = generate_product_excitation(high, library)
        self.assertGreater(
            project_order_amplitude(high_trace, high, 3.0) / project_order_amplitude(high_trace, high, 1.0),
            project_order_amplitude(low_trace, low, 3.0) / project_order_amplitude(low_trace, low, 1.0),
        )

    def test_v05_demo_writes_portable_deterministic_product_bundle(self):
        from s12_engine_sound_v05 import run_v05_demo

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            left = run_v05_demo(pathlib.Path(first))
            right = run_v05_demo(pathlib.Path(second))
            self.assertEqual(left.manifest_path.read_bytes(), right.manifest_path.read_bytes())
            self.assertEqual(left.sha256_path.read_bytes(), right.sha256_path.read_bytes())
            root = pathlib.Path(first) / "v05_demo"
            required = {"idle.wav", "cruise.wav", "acceleration.wav", "high_load.wav", "lift.wav", "vehicle_state.json", "audio_parameter_package.json", "manifest.json", "SHA256.txt"}
            self.assertTrue(required <= {path.name for path in root.iterdir()})
            package = json.loads((root / "audio_parameter_package.json").read_text(encoding="utf-8"))
            validate_audio_parameter_package(package)
            expected_commit = subprocess.check_output(["git", "-C", str(ROOT.parents[1]), "rev-parse", "HEAD"], text=True).strip()
            self.assertEqual(package["source_commit"], expected_commit)

    def test_v05_demo_rejects_a_caller_supplied_commit_that_is_not_head(self):
        from s12_engine_sound_v05 import run_v05_demo

        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                run_v05_demo(pathlib.Path(root), SOURCE_COMMIT)

    def test_future_dsp_interface_is_documented_without_realtime_implementation(self):
        document = (DEMO_ROOT / "Realtime_DSP_Interface_v01.md").read_text(encoding="utf-8")
        for token in ("rpm", "speed", "acceleration", "load", "timestamp", "PCM frame", "latency budget", "Android", "ESP32", "CAN", "I2S"):
            self.assertIn(token, document)
        self.assertIn("not implemented", document)


if __name__ == "__main__":
    unittest.main()
