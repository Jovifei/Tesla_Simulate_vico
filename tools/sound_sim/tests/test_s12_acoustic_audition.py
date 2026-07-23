import hashlib
import json
import math
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
from s12_engine_sound_design import (  # noqa: E402
    OrderSchedule,
    _looped_texture_at,
    fundamental_frequency_hz,
    load_design_parameters,
    load_order_profile,
    render_sound_design,
)
from s12_engine_sound_renderer import render_designed_wav  # noqa: E402
from s12_engine_sound_demo import run_engine_sound_demo  # noqa: E402


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

    @staticmethod
    def _engine_sound_texture():
        source = synthesize_four_stroke(
            EngineSourceConfig(2000.0, 0.25), 0.05
        )
        return run_ptr_network(source)

    def test_loads_synthetic_order_profile_and_parameter_provenance(self):
        profile = load_order_profile()
        parameters = load_design_parameters()

        self.assertEqual(profile["schema"], "s12.engine_order_profile.v1")
        self.assertEqual(profile["source"], "synthetic")
        self.assertEqual(profile["engine_type"], "synthetic_four_cylinder_four_stroke_reference")
        self.assertEqual(profile["firing_order"], "1-3-4-2")
        self.assertEqual(
            {entry["name"]: entry["order"] for entry in profile["orders"]},
            {"fundamental": 1.0, "second": 2.0, "third": 3.0, "firing": 2.0},
        )
        self.assertTrue(all(entry["source"] == "synthetic" for entry in profile["orders"]))
        self.assertEqual(parameters["generator_version"], "Synthetic Engine Sound v0.2")
        self.assertEqual(
            set(parameters["parameters"]),
            {
                "attack_s",
                "crossfade_s",
                "decay_s",
                "fixed_output_gain",
                "fundamental_load_floor",
                "fundamental_load_span",
                "high_order_load_floor",
                "high_order_load_span",
                "load_rate_reference",
                "max_adjacent_step",
                "max_dc",
                "rpm_rate_reference",
                "stereo_order",
                "stereo_order_weight",
                "stereo_phase_rad",
                "stereo_texture_weight",
                "stereo_width",
                "texture_mix",
                "transient_gain",
                "transient_load_floor",
                "transient_load_span",
                "transient_order",
                "transient_phase_rad",
            },
        )
        for entry in parameters["parameters"].values():
            self.assertEqual(entry["classification"], "C/synthetic")
            self.assertEqual(entry["source"], "synthetic")
            self.assertTrue(entry["rationale"])

        self.assertEqual(fundamental_frequency_hz(3000.0), 50.0)
        with self.assertRaises(ValueError):
            fundamental_frequency_hz(0.0)

    def test_looped_texture_crossfade_preserves_constant_source_level(self):
        samples = [0.75] * 2400
        crossfade_frames = 960
        period_frames = len(samples) - crossfade_frames
        looped = [
            _looped_texture_at(samples, index, crossfade_frames)
            for index in range(3 * period_frames)
        ]

        self.assertTrue(
            all(math.isclose(value, 0.75, abs_tol=1.0e-12) for value in looped)
        )

    def test_looped_texture_crossfade_uses_true_tail_head_overlap(self):
        samples = [-0.8, -0.6, 0.25, 0.4, -0.1, 0.3, -0.7, 0.9]
        crossfade_frames = 2
        period_frames = len(samples) - crossfade_frames
        looped = [
            _looped_texture_at(samples, index, crossfade_frames)
            for index in range(2 * period_frames + 1)
        ]

        self.assertEqual(
            looped[len(samples) - 2 * crossfade_frames],
            0.5 * samples[-2] + 0.5 * samples[0],
        )
        self.assertEqual(
            looped[len(samples) - 2 * crossfade_frames + 1],
            samples[1],
        )
        self.assertEqual(looped[period_frames], samples[crossfade_frames])
        crossfaded_wrap_jump = abs(
            looped[period_frames] - looped[period_frames - 1]
        )
        direct_modulo_wrap_jump = abs(samples[0] - samples[-1])
        self.assertLess(crossfaded_wrap_jump, direct_modulo_wrap_jump)

    def test_renders_fixed_rpm_load_orders_with_one_fixed_gain(self):
        texture = self._engine_sound_texture()
        profile = load_order_profile()
        parameters = load_design_parameters()
        traces = {}
        for rpm in (1000.0, 3000.0, 6000.0):
            traces[rpm] = render_sound_design(
                texture,
                OrderSchedule.fixed(rpm, 0.5, 0.10),
                profile,
                parameters,
            )
            self.assertEqual(traces[rpm].firing_frequency_hz, 2.0 * rpm / 60.0)
            self.assertEqual(traces[rpm].fixed_output_gain, parameters["parameters"]["fixed_output_gain"]["value"])
            self.assertEqual(traces[rpm].generator_version, "Synthetic Engine Sound v0.2")

        low_load = render_sound_design(
            texture, OrderSchedule.fixed(3000.0, 0.0, 0.10), profile, parameters
        )
        medium_load = render_sound_design(
            texture, OrderSchedule.fixed(3000.0, 0.5, 0.10), profile, parameters
        )
        high_load = render_sound_design(
            texture, OrderSchedule.fixed(3000.0, 1.0, 0.10), profile, parameters
        )
        self.assertLess(
            low_load.source_component_rms["third"],
            medium_load.source_component_rms["third"],
        )
        self.assertLess(
            medium_load.source_component_rms["third"],
            high_load.source_component_rms["third"],
        )
        for name in ("second", "third", "firing"):
            relative_component = [
                trace.source_component_rms[name]
                / trace.source_component_rms["fundamental"]
                for trace in (low_load, medium_load, high_load)
            ]
            self.assertLess(relative_component[0], relative_component[1])
            self.assertLess(relative_component[1], relative_component[2])
        final_third_to_fundamental = [
            trace.order_spectrum_rms["order_3"]
            / trace.order_spectrum_rms["order_1"]
            for trace in (low_load, medium_load, high_load)
        ]
        self.assertLess(
            final_third_to_fundamental[0],
            final_third_to_fundamental[1],
        )
        self.assertLess(
            final_third_to_fundamental[1],
            final_third_to_fundamental[2],
        )

    def test_rejects_nonuniform_sound_design_texture(self):
        texture = self._engine_sound_texture()
        nonuniform = PressureTrace(
            texture.case_id,
            [0.0, 1.0 / 48000.0, 2.5 / 48000.0],
            texture.pressure_pa[:3],
            texture.source_csv_sha256,
            texture.source_identity_sha256,
            48000,
            texture.firing_frequency_hz,
            texture.reference_plane,
            texture.provenance,
        )

        with self.assertRaises(ValueError):
            render_sound_design(
                nonuniform,
                OrderSchedule.fixed(3000.0, 0.5, 0.10),
                load_order_profile(),
                load_design_parameters(),
            )

    def test_rpm_ramp_preserves_phase_and_stays_click_free(self):
        trace = render_sound_design(
            self._engine_sound_texture(),
            OrderSchedule.ramp(1000.0, 6000.0, 0.3, 0.95, 0.20),
            load_order_profile(),
            load_design_parameters(),
        )

        self.assertIsNone(trace.firing_frequency_hz)
        self.assertEqual(len(trace.left), 9600)
        self.assertEqual(len(trace.fundamental_phase_rad), 9600)
        for index in range(1, len(trace.fundamental_phase_rad)):
            expected = (
                2.0
                * math.pi
                * trace.instantaneous_rpm[index]
                / (60.0 * trace.sample_rate_hz)
            )
            self.assertAlmostEqual(
                trace.fundamental_phase_rad[index]
                - trace.fundamental_phase_rad[index - 1],
                expected,
                places=12,
            )
        max_step = max(
            abs(current - previous)
            for channel in (trace.left, trace.right)
            for previous, current in zip(channel, channel[1:])
        )
        self.assertLessEqual(
            max_step,
            load_design_parameters()["parameters"]["max_adjacent_step"]["value"],
        )

    def test_load_continuously_scales_rpm_transient_intensity(self):
        texture = self._engine_sound_texture()
        profile = load_order_profile()
        parameters = load_design_parameters()
        low_load = render_sound_design(
            texture,
            OrderSchedule.ramp(1000.0, 6000.0, 0.0, 0.0, 0.20),
            profile,
            parameters,
        )
        high_load = render_sound_design(
            texture,
            OrderSchedule.ramp(1000.0, 6000.0, 1.0, 1.0, 0.20),
            profile,
            parameters,
        )

        self.assertGreater(high_load.transient_rms, low_load.transient_rms)
        self.assertEqual(
            high_load.fundamental_phase_rad,
            low_load.fundamental_phase_rad,
        )
        for trace in (low_load, high_load):
            self.assertLess(max(abs(value) for value in trace.left + trace.right), 1.0)
            for index in range(1, len(trace.fundamental_phase_rad)):
                expected = (
                    2.0
                    * math.pi
                    * trace.instantaneous_rpm[index]
                    / (60.0 * trace.sample_rate_hz)
                )
                self.assertAlmostEqual(
                    trace.fundamental_phase_rad[index]
                    - trace.fundamental_phase_rad[index - 1],
                    expected,
                    places=12,
                )

    def test_writes_deterministic_24_bit_stereo_metadata(self):
        trace = render_sound_design(
            self._engine_sound_texture(),
            OrderSchedule.fixed(3000.0, 0.5, 0.10),
            load_order_profile(),
            load_design_parameters(),
        )
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = pathlib.Path(first)
            second_root = pathlib.Path(second)
            result = render_designed_wav(
                trace, first_root / "cruise.wav", first_root / "cruise.metadata.json"
            )
            repeat = render_designed_wav(
                trace, second_root / "cruise.wav", second_root / "cruise.metadata.json"
            )

            self.assertEqual(result.wav_path.read_bytes(), repeat.wav_path.read_bytes())
            self.assertEqual(result.metadata_path.read_bytes(), repeat.metadata_path.read_bytes())
            with wave.open(str(result.wav_path), "rb") as rendered:
                self.assertEqual(rendered.getframerate(), 48000)
                self.assertEqual(rendered.getnchannels(), 2)
                self.assertEqual(rendered.getsampwidth(), 3)
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            for key in (
                "rpm_range", "load", "source_hash", "generator_version",
                "synthetic", "labels", "profile_sha256", "parameter_ledger_sha256",
                "fixed_output_gain", "clipping_count", "dc", "max_adjacent_step",
                "sample_rate_hz", "channels", "sample_width",
                "order_spectrum_rms", "source_component_rms",
                "transient_rms",
            ):
                self.assertIn(key, metadata)
            self.assertTrue(metadata["synthetic"])
            self.assertEqual(metadata["clipping_count"], 0)
            self.assertEqual(metadata["order_spectrum_rms"], trace.order_spectrum_rms)
            self.assertEqual(
                set(metadata["order_spectrum_rms"]),
                {"order_1", "order_2", "order_3"},
            )

    def test_builds_deterministic_five_case_engine_sound_demo(self):
        expected = {
            "idle", "cruise", "acceleration", "throttle_lift", "high_load"
        }
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            sentinel = pathlib.Path(first) / "sentinel.txt"
            sentinel.write_text("unrelated user file", encoding="utf-8")
            left = run_engine_sound_demo(pathlib.Path(first))
            right = run_engine_sound_demo(pathlib.Path(second))

            self.assertEqual(set(left.renders), expected)
            self.assertEqual(left.manifest_path.read_bytes(), right.manifest_path.read_bytes())
            manifest = json.loads(left.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(manifest["files"]),
                {
                    f"{name}{suffix}"
                    for name in expected
                    for suffix in (".wav", ".metadata.json")
                },
            )
            self.assertNotIn(sentinel.name, manifest["files"])
            self.assertEqual(left.total_clipping_count, 0)
            self.assertEqual(
                {path.stem for path in pathlib.Path(first).glob("*.wav")},
                expected,
            )
            review = left.review_path.read_text(encoding="utf-8")
            self.assertTrue(review.startswith("# Synthetic Engine Sound v0.2 Review"))
            self.assertIn("automated proxies", review)
            self.assertIn("human listening is not performed", review)
            self.assertIn("not an OEM clone", review)
            self.assertIn("Engine resemblance: INCONCLUSIVE", review)
            self.assertIn("Mechanical character: INCONCLUSIVE", review)
            self.assertIn("Electronic character: INCONCLUSIVE", review)
            self.assertIn("Continuity proxy: PASS", review)
            self.assertIn("final-output order projection", review)


if __name__ == "__main__":
    unittest.main()
