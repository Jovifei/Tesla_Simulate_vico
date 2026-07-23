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

from s12_acoustic_audition import PressureTrace, load_trace, render_audition  # noqa: E402
from s12_operating_points import lookup_operating_point  # noqa: E402
from s12_engine_source import (  # noqa: E402
    EngineSourceConfig,
    synthesize_four_stroke,
    synthesize_four_stroke_profile,
)
from s12_ptr_network import QUALIFICATION_COMMIT, load_radiation_package, run_ptr_network  # noqa: E402
from s12_synthetic_engine_demo import run_demo  # noqa: E402


TRACE_CSV = (
    ROOT
    / "s12"
    / "benchmark"
    / "baselines"
    / "sprint-4d-b"
    / "radiation-time-domain-traces.csv"
)


class S12AcousticAuditionTests(unittest.TestCase):
    def test_looks_up_and_interpolates_synthetic_operating_points(self):
        point = lookup_operating_point(4000.0, 0.60)
        self.assertEqual(point.pressure_amplitude_pa, 4.5)

        interpolated = lookup_operating_point(3000.0, 0.425)
        self.assertEqual(interpolated.pressure_amplitude_pa, 2.875)

        with self.assertRaises(ValueError):
            lookup_operating_point(1999.0, 0.60)

    def test_synthesizes_deterministic_zero_mean_four_stroke_trace(self):
        config = EngineSourceConfig(rpm=3000.0, load=0.60)
        trace = synthesize_four_stroke(config, 0.05)

        self.assertEqual(trace.firing_frequency_hz, 100.0)
        self.assertEqual(len(trace.pressure_pa), 2400)
        self.assertLess(abs(sum(trace.pressure_pa) / len(trace.pressure_pa)), 1e-12)
        self.assertLessEqual(max(abs(sample) for sample in trace.pressure_pa), 4.5)
        self.assertEqual(trace.sample_rate_hz, 48000)
        self.assertEqual(trace.reference_plane, "engine_exhaust_port")
        self.assertEqual(
            trace.provenance,
            (
                "synthetic",
                "uncalibrated",
                "offline",
                "not_realtime_qualified",
                "firing_order=1-3-4-2",
            ),
        )
        self.assertEqual(trace, synthesize_four_stroke(config, 0.05))

        with self.assertRaises(ValueError):
            synthesize_four_stroke(config, 0.0)
        with self.assertRaises(ValueError):
            synthesize_four_stroke(
                EngineSourceConfig(rpm=3000.0, load=0.60, firing_order=(1, 3)),
                0.05,
            )

    def test_four_stroke_waveform_repeats_at_firing_frequency(self):
        trace = synthesize_four_stroke(
            EngineSourceConfig(rpm=3000.0, load=0.60), 0.05
        )

        period_at_100_hz = 480
        period_at_400_hz = 120
        self.assertLess(
            max(
                abs(first - second)
                for first, second in zip(
                    trace.pressure_pa,
                    trace.pressure_pa[period_at_100_hz:],
                )
            ),
            1e-12,
        )
        self.assertGreater(
            max(
                abs(first - second)
                for first, second in zip(
                    trace.pressure_pa,
                    trace.pressure_pa[period_at_400_hz:],
                )
            ),
            1e-6,
        )

    def test_firing_order_is_auditable_while_common_port_waveform_is_symmetric(self):
        first = synthesize_four_stroke(
            EngineSourceConfig(rpm=3000.0, load=0.60, firing_order=(1, 3, 4, 2)),
            0.05,
        )
        second = synthesize_four_stroke(
            EngineSourceConfig(rpm=3000.0, load=0.60, firing_order=(1, 2, 3, 4)),
            0.05,
        )

        self.assertEqual(
            first.case_id,
            "synthetic_four_stroke.v1:firing_order=1-3-4-2",
        )
        self.assertEqual(
            second.case_id,
            "synthetic_four_stroke.v1:firing_order=1-2-3-4",
        )
        self.assertIn("firing_order=1-3-4-2", first.provenance)
        self.assertIn("firing_order=1-2-3-4", second.provenance)
        self.assertEqual(first.pressure_pa, second.pressure_pa)

    def test_uniform_trace_preserves_shared_provenance_contract(self):
        trace = PressureTrace.uniform(
            "synthetic_four_stroke.v1",
            [0.0, 0.25],
            48000,
            100.0,
            "engine_exhaust_port",
            ("synthetic", "uncalibrated"),
        )

        self.assertEqual(trace.time_s, [0.0, 1.0 / 48000.0])
        self.assertEqual(trace.firing_frequency_hz, 100.0)
        self.assertEqual(trace.reference_plane, "engine_exhaust_port")
        self.assertEqual(trace.provenance, ("synthetic", "uncalibrated"))
        self.assertEqual(trace.source_csv_sha256, "")
        self.assertEqual(len(trace.source_identity_sha256), 64)

    def test_synthesizes_variable_operating_profile(self):
        ramp = synthesize_four_stroke_profile(
            (EngineSourceConfig(2000.0, 0.25), EngineSourceConfig(6000.0, 1.0)),
            4800,
            "linear",
        )
        step = synthesize_four_stroke_profile(
            (EngineSourceConfig(4000.0, 0.25), EngineSourceConfig(4000.0, 1.0)),
            4800,
            "step",
        )

        self.assertIsNone(ramp.firing_frequency_hz)
        self.assertEqual(len(ramp.pressure_pa), 4800)
        self.assertLessEqual(max(abs(value) for value in ramp.pressure_pa), 8.0)
        self.assertEqual(
            ramp.provenance[-2:],
            ("firing_frequency=variable", "profile_mode=linear"),
        )
        self.assertNotEqual(ramp, step)
        with self.assertRaises(ValueError):
            synthesize_four_stroke_profile(
                (EngineSourceConfig(2000.0, 0.25),), 4800, "linear"
            )

    def test_renders_deterministic_native_and_looped_audition_artifacts(self):
        trace = load_trace(TRACE_CSV, "radiation_chirp")

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            result = render_audition(trace, pathlib.Path(first))
            repeat = render_audition(trace, pathlib.Path(second))

            self.assertEqual(result.sample_rate_hz, 48000)
            self.assertEqual(result.clipping_count, 0)
            self.assertEqual(result.source_duration_s, trace.time_s[-1] - trace.time_s[0])
            self.assertEqual(
                result.native_wav_duration_s,
                result.native_frame_count / result.sample_rate_hz,
            )
            self.assertLessEqual(
                abs(result.native_wav_duration_s - result.source_duration_s),
                0.5 / result.sample_rate_hz,
            )
            self.assertEqual(result.manifest_path.read_bytes(), repeat.manifest_path.read_bytes())
            self.assertTrue(result.source_pressure_csv_path.is_file())
            self.assertEqual(result.waveform_png_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(result.spectrum_png_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

            with wave.open(str(result.native_wav_path), "rb") as native:
                self.assertEqual(native.getframerate(), 48000)
                self.assertEqual(native.getnframes(), result.native_frame_count)
                self.assertEqual(
                    native.getnframes() / native.getframerate(),
                    result.native_wav_duration_s,
                )
            with wave.open(str(result.looped_preview_wav_path), "rb") as preview:
                self.assertEqual(preview.getframerate(), 48000)
                self.assertGreater(preview.getnframes(), result.native_frame_count)

            metadata = json.loads(result.metadata_json_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["labels"], ["synthetic", "uncalibrated", "offline", "not_realtime_qualified"])
            self.assertEqual(metadata["preview"], "looped audition preview; no time scaling")
            self.assertEqual(metadata["source_duration_s"], result.source_duration_s)
            self.assertEqual(metadata["native_wav_duration_s"], result.native_wav_duration_s)
            self.assertEqual(metadata["clipping_count"], 0)
            self.assertNotIn("native_duration_s", metadata)
            self.assertNotIn("generated_at", metadata)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["sha256"], hashlib.sha256(result.native_wav_path.read_bytes()).hexdigest())

    def test_loads_accepted_package_and_applies_causal_finite_ptr(self):
        package = load_radiation_package()
        self.assertEqual(package.source_commit, QUALIFICATION_COMMIT)
        trace = PressureTrace.uniform(
            "one-sample", [1.0] + [0.0] * 63, 48000, 100.0,
            "engine_exhaust_port", ("synthetic",),
        )
        result = run_ptr_network(trace)
        self.assertEqual(result.reference_plane, "bore_end")
        self.assertEqual(result, run_ptr_network(trace))
        self.assertTrue(all(abs(value) == 0.0 for value in result.pressure_pa[:20]))
        self.assertTrue(all(__import__("math").isfinite(value) for value in result.pressure_pa))

        short = PressureTrace.uniform(
            "short", [1.0], 48000, 100.0, "engine_exhaust_port", ("synthetic",),
        )
        delayed_short = run_ptr_network(short)
        self.assertEqual(len(delayed_short.pressure_pa), len(short.pressure_pa))
        self.assertEqual(len(delayed_short.time_s), len(short.time_s))
        self.assertEqual(delayed_short.pressure_pa, [0.0])

    def test_renders_deterministic_synthetic_engine_demo(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            left = run_demo(pathlib.Path(first))
            right = run_demo(pathlib.Path(second))
            self.assertEqual(left.manifest_path.read_bytes(), right.manifest_path.read_bytes())
            self.assertEqual(len(left.cases), 5)
            self.assertEqual(left.total_clipping_count, 0)
            for result in left.cases.values():
                with wave.open(str(result.native_wav_path), "rb") as rendered:
                    self.assertEqual(rendered.getframerate(), 48000)


if __name__ == "__main__":
    unittest.main()
