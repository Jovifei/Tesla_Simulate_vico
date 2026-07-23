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

from s12_acoustic_audition import load_trace, render_audition  # noqa: E402


TRACE_CSV = (
    ROOT
    / "s12"
    / "benchmark"
    / "baselines"
    / "sprint-4d-b"
    / "radiation-time-domain-traces.csv"
)


class S12AcousticAuditionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
