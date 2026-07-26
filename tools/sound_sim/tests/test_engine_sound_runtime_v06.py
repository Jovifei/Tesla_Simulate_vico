import math
import pathlib
import sys
import unittest
import json
import tempfile
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "s12" / "acoustic_demo"
sys.path.insert(0, str(DEMO_ROOT))


from engine_runtime import EngineSoundRuntime, RuntimeMode, RuntimeStateMachine  # noqa: E402
from engine_operating_points.library import load_operating_point_library  # noqa: E402
from sound_renderer.s12_product_renderer import renderer_profile_from_library  # noqa: E402
from app_runtime_interface import parse_app_vehicle_state  # noqa: E402
from audio_parameter_package.runtime_package import (  # noqa: E402
    build_runtime_audio_parameter_package,
    validate_runtime_audio_parameter_package,
)
from runtime_pcm import PcmRingBuffer, SimulatedPcmSink, WindowsWaveOutSink  # noqa: E402
from runtime_ptr_adapter import RuntimePtrAdapter  # noqa: E402
from s12_acoustic_audition import PressureTrace  # noqa: E402
from s12_engine_sound_runtime import run_runtime_demo  # noqa: E402
from s12_ptr_network import run_ptr_network  # noqa: E402
from vehicle_state_runtime.stream import RuntimeDriveCycle, VehicleState  # noqa: E402


class RuntimeVehicleStateTests(unittest.TestCase):
    def test_drive_cycle_is_100hz_continuous_and_contains_required_modes(self):
        cycle = RuntimeDriveCycle(duration_s=600.0)
        states = list(cycle.iter_updates())

        self.assertEqual(len(states), 60001)
        self.assertTrue(all(
            current.timestamp_s > previous.timestamp_s
            for previous, current in zip(states, states[1:])
        ))
        self.assertTrue(all(
            math.isfinite(value)
            for state in states
            for value in (state.rpm, state.speed_mps, state.acceleration_mps2, state.load, state.throttle)
        ))
        self.assertTrue(all(800.0 <= state.rpm <= 6000.0 and 0.0 <= state.load <= 1.0 for state in states))
        self.assertLess(max(abs(current.rpm - previous.rpm) for previous, current in zip(states, states[1:])), 20.0)
        self.assertLess(max(abs(current.load - previous.load) for previous, current in zip(states, states[1:])), 0.02)

        state_machine = RuntimeStateMachine(transition_s=0.10)
        observed = {state_machine.classify(state) for state in states}
        self.assertTrue({RuntimeMode.IDLE, RuntimeMode.CRUISE, RuntimeMode.ACCELERATION, RuntimeMode.DECELERATION, RuntimeMode.HIGH_LOAD} <= observed)

    def test_state_machine_smooths_mode_changes(self):
        state_machine = RuntimeStateMachine(transition_s=0.10)
        idle = VehicleState(0.00, 800.0, 0.0, 0.0, 0.0, 0.0)
        accelerating = VehicleState(0.01, 1600.0, 8.0, 2.0, 0.6, 0.6)

        first = state_machine.update(idle)
        transition = state_machine.update(accelerating)

        self.assertEqual(first.mode, RuntimeMode.IDLE)
        self.assertEqual(transition.mode, RuntimeMode.IDLE)
        self.assertEqual(transition.target_mode, RuntimeMode.ACCELERATION)
        self.assertGreater(transition.progress, 0.0)
        self.assertLess(transition.progress, 1.0)

        for index in range(2, 12):
            transition = state_machine.update(VehicleState(index / 100.0, 1600.0, 8.0, 2.0, 0.6, 0.6))
        self.assertEqual(transition.mode, RuntimeMode.ACCELERATION)
        self.assertEqual(transition.progress, 1.0)


class RuntimeAudioTests(unittest.TestCase):
    def test_runtime_callback_meets_the_20ms_block_budget(self):
        runtime = EngineSoundRuntime()
        start = time.perf_counter()
        for index in range(20):
            runtime.audio_callback(VehicleState(index * 0.02, 2000.0, 60.0 / 3.6, 0.0, 0.30, 0.30))
        mean_callback_s = (time.perf_counter() - start) / 20.0

        self.assertLessEqual(mean_callback_s, 0.020)

    def test_audio_callback_keeps_phase_across_20ms_pcm_blocks(self):
        runtime = EngineSoundRuntime()
        first = runtime.audio_callback(VehicleState.synthetic_idle(0.00))
        second = runtime.audio_callback(VehicleState.synthetic_idle(0.02))

        self.assertEqual((first.sample_rate_hz, first.channels, first.bits_per_sample), (48000, 2, 24))
        self.assertEqual(len(first.normalized_samples), 960)
        self.assertEqual(len(first.pcm_s24le_stereo), 960 * 2 * 3)
        self.assertLess(abs(second.normalized_samples[0] - first.normalized_samples[-1]), 0.10)
        self.assertFalse(first.fallback_applied)

    def test_callback_consumes_two_100hz_state_updates_per_pcm_block(self):
        runtime = EngineSoundRuntime()
        runtime.update_vehicle_state(VehicleState.synthetic_idle(0.00))
        runtime.update_vehicle_state(VehicleState.synthetic_idle(0.01))

        frame = runtime.audio_callback()

        self.assertEqual(len(frame.normalized_samples), 960)
        self.assertEqual(runtime.state_updates_consumed, 2)

    def test_load_and_acceleration_change_runtime_pcm_before_ptr(self):
        steady = VehicleState(0.00, 2000.0, 60.0 / 3.6, 0.0, 0.30, 0.30)
        loaded = VehicleState(0.00, 2000.0, 60.0 / 3.6, 0.0, 1.00, 1.00)
        accelerating = VehicleState(0.00, 2000.0, 60.0 / 3.6, 2.0, 0.30, 0.30)

        self.assertNotEqual(EngineSoundRuntime().audio_callback(steady).pcm_s24le_stereo, EngineSoundRuntime().audio_callback(loaded).pcm_s24le_stereo)
        self.assertNotEqual(EngineSoundRuntime().audio_callback(steady).pcm_s24le_stereo, EngineSoundRuntime().audio_callback(accelerating).pcm_s24le_stereo)

    def test_invalid_and_sudden_states_render_the_safe_fallback(self):
        runtime = EngineSoundRuntime()
        runtime.audio_callback(VehicleState.synthetic_idle(0.00))

        negative = runtime.audio_callback(VehicleState(0.02, -10.0, 0.0, 0.0, 0.0, 0.0))
        nan = runtime.audio_callback(VehicleState(0.04, math.nan, 0.0, 0.0, 0.0, 0.0))
        jump = runtime.audio_callback(VehicleState(0.06, 6000.0, 60.0, 0.0, 1.0, 1.0))

        self.assertTrue(negative.fallback_applied)
        self.assertTrue(nan.fallback_applied)
        self.assertTrue(jump.fallback_applied)
        self.assertEqual(runtime.fallback_count, 3)

    def test_rpm_ramp_keeps_phase_continuous_at_block_boundaries(self):
        runtime = EngineSoundRuntime()
        previous = None
        maximum_boundary_delta = 0.0
        for index in range(101):
            rpm = 1000.0 + 5000.0 * index / 100.0
            frame = runtime.audio_callback(VehicleState(index * 0.02, rpm, 20.0, 2.0, 0.70, 0.70))
            if previous is not None:
                maximum_boundary_delta = max(maximum_boundary_delta, abs(frame.normalized_samples[0] - previous.normalized_samples[-1]))
            previous = frame
        self.assertLess(maximum_boundary_delta, 0.10)

    def test_stateful_ptr_adapter_matches_the_frozen_batch_network(self):
        samples = [0.15 * math.sin(index * 0.07) for index in range(1024)]
        trace = PressureTrace.uniform("runtime-ptr", samples, 48000, 40.0, "engine_exhaust_port", ("synthetic",))

        expected = run_ptr_network(trace).pressure_pa
        adapter = RuntimePtrAdapter()
        actual = adapter.process(samples[:317]) + adapter.process(samples[317:])

        self.assertEqual(len(actual), len(expected))
        self.assertTrue(all(abs(left - right) < 1.0e-12 for left, right in zip(actual, expected)))

    def test_pcm_ring_buffer_records_underrun_without_dropping_audio(self):
        runtime = EngineSoundRuntime()
        queue = PcmRingBuffer(capacity_frames=2)
        sink = SimulatedPcmSink(block_duration_s=0.02)

        self.assertIsNone(sink.consume(queue))
        frame = runtime.audio_callback(VehicleState.synthetic_idle(0.00))
        queue.push(frame)

        self.assertEqual(sink.consume(queue), frame)
        self.assertEqual(sink.underrun_count, 1)
        self.assertEqual(queue.depth, 0)

    @unittest.skipUnless(sys.platform == "win32", "Windows waveOut is a Windows-only PC audio adapter")
    def test_windows_waveout_adapter_is_available_without_opening_a_device(self):
        self.assertTrue(WindowsWaveOutSink.is_supported())


class RuntimeProductContractTests(unittest.TestCase):
    def test_app_json_ingress_maps_the_documented_synthetic_fallback(self):
        state = parse_app_vehicle_state({"speed": 60.0, "acceleration": 0.5, "timestamp": 123.0})

        self.assertEqual(state.timestamp_s, 123.0)
        self.assertAlmostEqual(state.speed_mps, 60.0 / 3.6)
        self.assertAlmostEqual(state.rpm, 2050.0)
        self.assertAlmostEqual(state.load, 0.35)
        self.assertAlmostEqual(state.throttle, 0.35)

    def test_app_nan_payload_reaches_runtime_fallback(self):
        state = parse_app_vehicle_state({"speed": math.nan, "acceleration": 0.5, "timestamp": 123.0})
        frame = EngineSoundRuntime().audio_callback(state)
        self.assertTrue(frame.fallback_applied)

    def test_audio_parameter_package_v02_contains_runtime_controls(self):
        library = load_operating_point_library()
        package = build_runtime_audio_parameter_package(
            library,
            renderer_profile_from_library(library),
            "0123456789abcdef0123456789abcdef01234567",
        )

        validate_runtime_audio_parameter_package(package)
        self.assertEqual(package["version"], "AudioParameterPackage v0.2")
        self.assertEqual(set(package["runtime_profile"]), {"rpm_map", "load_map", "transition_curve", "renderer_config", "pcm"})
        self.assertEqual(package["runtime_profile"]["pcm"], {"sample_rate_hz": 48000, "block_samples": 960, "channels": 2, "bits_per_sample": 24})

    def test_runtime_demo_is_deterministic_and_writes_only_a_report(self):
        with tempfile.TemporaryDirectory() as left_root, tempfile.TemporaryDirectory() as right_root:
            left = run_runtime_demo(pathlib.Path(left_root), duration_s=2.0)
            right = run_runtime_demo(pathlib.Path(right_root), duration_s=2.0)

            self.assertEqual(left.audio_sha256, right.audio_sha256)
            self.assertEqual(left.pcm_frames, 100)
            self.assertEqual(left.underrun_count, 0)
            self.assertEqual(left.state_update_hz, 100)
            self.assertTrue(left.report_path.is_file())
            self.assertFalse(any(path.suffix.lower() == ".wav" for path in pathlib.Path(left_root).rglob("*")))
            report = json.loads(left.report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["duration_s"], 2.0)
            self.assertEqual(report["pcm_frames"], 100)
            self.assertEqual(report["state_updates_consumed"], 200)
            self.assertEqual(report["audio"]["clipping_count"], 0)
            self.assertEqual(report["buffer"]["underrun_count"], 0)
            self.assertIn("latency", report)
            self.assertIn("performance", report)
            self.assertIn("memory", report)
            self.assertGreater(report["memory"]["process_working_set_before_bytes"], 0)
            self.assertGreater(report["memory"]["process_working_set_after_bytes"], 0)

    def test_runtime_runner_avoids_per_sample_diagnostic_overhead(self):
        with tempfile.TemporaryDirectory() as folder:
            start = time.perf_counter()
            run_runtime_demo(pathlib.Path(folder), duration_s=1.0)
        self.assertLess(time.perf_counter() - start, 1.5)


if __name__ == "__main__":
    unittest.main()
