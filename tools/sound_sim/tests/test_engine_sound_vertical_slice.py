import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
import wave


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "s12" / "acoustic_demo"
sys.path.insert(0, str(DEMO_ROOT))

from engine_order_model import order_frequencies_hz  # noqa: E402
from s12_engine_sound_design import load_order_profile  # noqa: E402
from s12_engine_source import (  # noqa: E402
    EngineSourceConfig,
    synthesize_four_stroke_profile,
    synthesize_four_stroke_trajectory,
)
from vehicle_state import (  # noqa: E402
    VehicleStateSeries,
    build_default_vehicle_state_cases,
    load_vehicle_state_bundle,
    write_vehicle_state_bundle,
)


class EngineSoundVerticalSliceTests(unittest.TestCase):
    def test_vehicle_state_cases_are_continuous_and_round_trip(self):
        cases = build_default_vehicle_state_cases()
        self.assertEqual(
            set(cases), {"idle", "cruise", "acceleration", "lift", "high_load"}
        )
        for state in cases.values():
            state.validate()
            self.assertEqual(state.sample_rate_hz, 48000)
            self.assertEqual(len(state.timestamp), len(state.rpm))
            self.assertEqual(state.load, state.throttle)

        self.assertGreaterEqual(min(cases["idle"].rpm), 800.0)
        self.assertLessEqual(max(cases["idle"].rpm), 1200.0)
        self.assertGreaterEqual(min(cases["cruise"].rpm), 1500.0)
        self.assertLessEqual(max(cases["cruise"].rpm), 3000.0)
        self.assertEqual(cases["acceleration"].rpm[0], 1000.0)
        self.assertEqual(cases["acceleration"].rpm[-1], 6000.0)
        self.assertGreater(cases["lift"].rpm[0], cases["lift"].rpm[-1])

        with tempfile.TemporaryDirectory() as root:
            path = write_vehicle_state_bundle(pathlib.Path(root) / "vehicle_state.json", cases)
            payload = json.loads(path.read_text(encoding="utf-8"))
            required_fields = {"timestamp", "rpm", "speed", "acceleration", "load", "throttle"}
            self.assertTrue(required_fields <= set(payload))
            self.assertEqual(payload["case_id"], "acceleration")
            self.assertEqual(payload["rpm"], list(cases["acceleration"].rpm))
            self.assertEqual(load_vehicle_state_bundle(path), cases)

    def test_synthetic_order_model_tracks_rpm(self):
        frequencies = order_frequencies_hz(3000.0, load_order_profile())
        self.assertEqual(frequencies["fundamental"], 50.0)
        self.assertEqual(frequencies["firing"], 100.0)
        self.assertEqual(frequencies["third"], 150.0)

    def test_existing_synthetic_source_supports_v03_idle_and_zero_load_mapping(self):
        trace = synthesize_four_stroke_profile(
            (
                EngineSourceConfig(1000.0, 0.0),
                EngineSourceConfig(1000.0, 0.0),
            ),
            480,
            "linear",
        )
        self.assertEqual(trace.sample_rate_hz, 48000)
        self.assertTrue(all(abs(value) <= 1.5 for value in trace.pressure_pa))

    def test_non_linear_vehicle_state_schedule_preserves_every_rpm_and_load_sample(self):
        frame_count = 480
        timestamp = tuple(index / 48000.0 for index in range(frame_count))
        rpm = tuple(1000.0 + 5000.0 * (index / (frame_count - 1)) ** 2 for index in range(frame_count))
        load = tuple(0.25 + 0.70 * (index / (frame_count - 1)) ** 2 for index in range(frame_count))
        speed = tuple(value * 0.01 for value in rpm)
        acceleration = ((speed[1] - speed[0]) * 48000.0,) + tuple(
            (current - previous) * 48000.0
            for previous, current in zip(speed, speed[1:])
        )
        state = VehicleStateSeries("nonlinear", timestamp, rpm, speed, acceleration, load, load)
        state.validate()
        self.assertEqual(list(state.to_order_schedule().samples()), list(zip(rpm, load)))
        source = synthesize_four_stroke_trajectory(state.source_config(), state.rpm, state.load)
        self.assertEqual(len(source.pressure_pa), frame_count)
        self.assertIn("profile_mode=vehicle_state", source.provenance)

    def test_vertical_slice_writes_deterministic_controlled_artifacts(self):
        from s12_engine_sound_vertical_slice import run_vertical_slice

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            left = run_vertical_slice(pathlib.Path(first))
            right = run_vertical_slice(pathlib.Path(second))

            self.assertEqual(left.manifest_path.read_bytes(), right.manifest_path.read_bytes())
            self.assertEqual(left.sha256_path.read_bytes(), right.sha256_path.read_bytes())
            self.assertEqual(
                set(left.renders), {"idle", "cruise", "acceleration", "lift", "high_load"}
            )
            required = {
                "idle.wav",
                "cruise.wav",
                "acceleration.wav",
                "lift.wav",
                "high_load.wav",
                "vehicle_state.json",
                "rpm_trace.csv",
                "sound_analysis.json",
                "manifest.json",
                "SHA256.txt",
                "S12 Engine Sound Vertical Slice Report.md",
            }
            self.assertTrue(required <= {path.name for path in pathlib.Path(first).iterdir()})

            manifest = json.loads(left.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["generator_version"], "Synthetic Engine Sound Vertical Slice v0.3")
            self.assertEqual(manifest["labels"], ["synthetic", "uncalibrated", "offline", "not_realtime_qualified"])
            for name, digest in manifest["files"].items():
                self.assertEqual(
                    hashlib.sha256((pathlib.Path(first) / name).read_bytes()).hexdigest(),
                    digest,
                )

            analysis = json.loads((pathlib.Path(first) / "sound_analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(set(analysis["cases"]), set(left.renders))
            for name, case in analysis["cases"].items():
                self.assertEqual(case["sample_rate"], 48000)
                self.assertEqual(case["clipping_count"], 0)
                self.assertTrue(case["engine_source_hash"])
                self.assertTrue(case["ptr_hash"])
                self.assertIn("harmonics", case)
                for image_name in ("spectrum.png", "order_map.png"):
                    image = pathlib.Path(first) / "analysis" / name / image_name
                    self.assertEqual(image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                with wave.open(str(pathlib.Path(first) / f"{name}.wav"), "rb") as rendered:
                    self.assertEqual((rendered.getframerate(), rendered.getnchannels(), rendered.getsampwidth()), (48000, 2, 3))

            for name in ("low_load.wav", "mid_load.wav", "high_load.wav"):
                with wave.open(str(pathlib.Path(first) / "load_map" / name), "rb") as rendered:
                    self.assertEqual((rendered.getframerate(), rendered.getnchannels(), rendered.getsampwidth()), (48000, 2, 3))
            self.assertEqual(len(list((pathlib.Path(first) / "analysis").rglob("*.png"))), 10)

            report = (pathlib.Path(first) / "S12 Engine Sound Vertical Slice Report.md").read_text(encoding="utf-8")
            self.assertIn("PTR coupling", report)
            self.assertIn("OEM calibration: NOT COMPLETED", report)
            self.assertIn("Realtime DSP: NOT COMPLETED", report)


if __name__ == "__main__":
    unittest.main()
