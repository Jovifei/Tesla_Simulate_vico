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

from engine_excitation import EngineStateInput, build_default_engine_state_cases, generate_engine_excitation, load_json_package  # noqa: E402
from s12_engine_sound_v04_renderer import render_ptr_trace_wav  # noqa: E402
from s12_ptr_network import run_ptr_network  # noqa: E402


class EngineSoundV04Tests(unittest.TestCase):
    def test_all_v04_contract_values_are_source_classified(self):
        for name in ("engine_state_schema.json", "order_profile.json", "engine_excitation_parameters.json"):
            package = load_json_package(DEMO_ROOT / name)
            entries = package["fields"] if name == "engine_state_schema.json" else package["parameters"]
            values = list(entries.values()) if isinstance(entries, dict) else list(entries)
            if name == "engine_state_schema.json":
                values.extend(package["case_profiles"].values())
                values.extend(package["parameters"].values())
            for item in values:
                self.assertEqual(item["source_level"], "C")
                self.assertEqual(item["source"], "synthetic")
                self.assertTrue(item["description"])

    def test_state_contract_consumes_speed_and_acceleration(self):
        cases = build_default_engine_state_cases()
        state = cases["cruise"]
        fast = EngineStateInput(
            "same-rpm-fast", state.timestamp, state.rpm, state.speed,
            tuple(4.0 for _ in state.acceleration), state.load, state.throttle,
        )
        slow = EngineStateInput(
            "same-rpm-slow", state.timestamp, state.rpm,
            tuple(0.0 for _ in state.speed), tuple(0.0 for _ in state.acceleration),
            state.load, state.throttle,
        )
        fast_trace = generate_engine_excitation(fast)
        slow_trace = generate_engine_excitation(slow)
        self.assertNotEqual(fast_trace.source_identity_sha256, slow_trace.source_identity_sha256)
        self.assertNotEqual(fast_trace.pressure_pa, slow_trace.pressure_pa)

    def test_speed_only_change_propagates_to_ptr_then_audio(self):
        state = build_default_engine_state_cases()["cruise"]
        slow = EngineStateInput("speed-slow", state.timestamp, state.rpm, tuple(0.0 for _ in state.speed), state.acceleration, state.load, state.throttle)
        fast = EngineStateInput("speed-fast", state.timestamp, state.rpm, tuple(30.0 for _ in state.speed), state.acceleration, state.load, state.throttle)
        slow_ptr, fast_ptr = run_ptr_network(generate_engine_excitation(slow)), run_ptr_network(generate_engine_excitation(fast))
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root)
            render_ptr_trace_wav(slow_ptr, folder / "slow.wav", folder / "slow.json", 48000, 0.70, 0.004)
            render_ptr_trace_wav(fast_ptr, folder / "fast.wav", folder / "fast.json", 48000, 0.70, 0.004)
            self.assertNotEqual((folder / "slow.wav").read_bytes(), (folder / "fast.wav").read_bytes())

    def test_acceleration_change_propagates_to_ptr_then_audio(self):
        states = build_default_engine_state_cases()
        state = states["cruise"]
        quiet = EngineStateInput("quiet", state.timestamp, state.rpm, state.speed, tuple(0.0 for _ in state.acceleration), state.load, state.throttle)
        active = EngineStateInput("active", state.timestamp, state.rpm, state.speed, tuple(6.0 for _ in state.acceleration), state.load, state.throttle)
        quiet_source, active_source = generate_engine_excitation(quiet), generate_engine_excitation(active)
        quiet_ptr, active_ptr = run_ptr_network(quiet_source), run_ptr_network(active_source)
        self.assertNotEqual(quiet_source.source_identity_sha256, active_source.source_identity_sha256)
        self.assertNotEqual(quiet_ptr.source_identity_sha256, active_ptr.source_identity_sha256)
        self.assertNotEqual(quiet_ptr.pressure_pa, active_ptr.pressure_pa)
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root)
            render_ptr_trace_wav(quiet_ptr, folder / "quiet.wav", folder / "quiet.json", 48000, 0.70, 0.004)
            render_ptr_trace_wav(active_ptr, folder / "active.wav", folder / "active.json", 48000, 0.70, 0.004)
            self.assertNotEqual((folder / "quiet.wav").read_bytes(), (folder / "active.wav").read_bytes())

    def test_v04_topology_has_no_post_ptr_sound_design(self):
        source = (DEMO_ROOT / "s12_engine_sound_v04.py").read_text(encoding="utf-8")
        self.assertNotIn("render_sound_design", source)
        self.assertNotIn("s12_engine_sound_design", source)
        self.assertLess(source.index("generate_engine_excitation"), source.index("run_ptr_network"))

    def test_v04_demo_is_deterministic_and_renderer_is_48khz_24bit_stereo(self):
        from s12_engine_sound_v04 import run_v04_demo

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            left = run_v04_demo(pathlib.Path(first))
            right = run_v04_demo(pathlib.Path(second))
            self.assertEqual(left.manifest_path.read_bytes(), right.manifest_path.read_bytes())
            self.assertEqual(left.sha256_path.read_bytes(), right.sha256_path.read_bytes())
            root = pathlib.Path(first) / "v04_demo"
            for name in ("idle", "cruise", "acceleration", "lift", "high_load"):
                with wave.open(str(root / f"{name}.wav"), "rb") as audio:
                    self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()), (48000, 2, 3))
            metadata = json.loads((root / "metadata" / "acceleration.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["architecture"], "excitation_to_ptr_to_radiation")
            self.assertTrue(metadata["synthetic"])
            self.assertFalse(metadata["calibrated"])
            self.assertEqual(metadata["clipping_count"], 0)
            manifest = json.loads(left.manifest_path.read_text(encoding="utf-8"))
            for name, digest in manifest["files"].items():
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
