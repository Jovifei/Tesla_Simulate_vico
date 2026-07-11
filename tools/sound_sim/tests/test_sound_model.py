import json
import math
import pathlib
import sys
import tempfile
import unittest
import wave


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sound_model import (  # noqa: E402
    DrivePoint,
    SoundModel,
    build_demo_drive_cycle,
    export_firmware_params,
    render_drive_cycle,
    write_wav,
)


class SoundModelTests(unittest.TestCase):
    def test_acceleration_increases_rpm_brightness_and_harmonics(self):
        model = SoundModel(smoothing=1.0)

        cruise = model.map_point(
            DrivePoint(time_s=0.0, speed_kmh=50.0, throttle=0.20, accel_mps2=0.0)
        )
        launch = model.map_point(
            DrivePoint(time_s=0.1, speed_kmh=50.0, throttle=0.85, accel_mps2=2.8)
        )

        self.assertGreater(launch.rpm, cruise.rpm)
        self.assertGreater(launch.brightness, cruise.brightness)
        self.assertGreater(launch.harmonics[2], cruise.harmonics[2])
        self.assertLessEqual(max(launch.harmonics), 1.0)

    def test_overspeed_mute_renders_silence_but_keeps_trace(self):
        cycle = [
            DrivePoint(time_s=0.0, speed_kmh=120.0, throttle=0.4, accel_mps2=0.0),
            DrivePoint(time_s=0.1, speed_kmh=151.0, throttle=0.6, accel_mps2=1.0),
        ]

        samples, trace = render_drive_cycle(cycle, sample_rate=8000, block_hz=10)

        self.assertEqual(len(samples), 1600)
        self.assertTrue(any(point.muted for point in trace))
        self.assertEqual(samples[800:], [0] * 800)

    def test_wav_and_firmware_params_are_exported(self):
        cycle = build_demo_drive_cycle(duration_s=2.0, step_s=0.1)
        samples, trace = render_drive_cycle(cycle, sample_rate=8000, block_hz=10)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            wav_path = tmp_path / "demo.wav"
            params_path = tmp_path / "params.json"

            write_wav(wav_path, samples, sample_rate=8000)
            export_firmware_params(params_path, trace)

            with wave.open(str(wav_path), "rb") as reader:
                self.assertEqual(reader.getframerate(), 8000)
                self.assertEqual(reader.getnchannels(), 1)
                self.assertEqual(reader.getsampwidth(), 2)
                self.assertEqual(reader.getnframes(), len(samples))

            params = json.loads(params_path.read_text(encoding="utf-8"))
            self.assertEqual(params["schema"], "jovi.sound_model.v1")
            self.assertGreaterEqual(params["sample_rate_hz"], 8000)
            self.assertGreaterEqual(len(params["rpm_breakpoints"]), 4)
            self.assertTrue(all(math.isfinite(x) for x in params["harmonic_gains_q15"]))


if __name__ == "__main__":
    unittest.main()
