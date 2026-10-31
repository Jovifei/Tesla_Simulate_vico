import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

LAB = Path(__file__).resolve().parent


class IndependentAnalysis(unittest.TestCase):
    def setUp(self):
        path = LAB / "analyze_cabin_candidate.py"
        self.assertTrue(path.is_file(), "independent PCM/WAV analyzer must exist")
        spec = importlib.util.spec_from_file_location("cabin_analysis", path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_pcm24_round_trip_and_mismatch_detection(self):
        with tempfile.TemporaryDirectory(dir=LAB) as directory:
            directory = Path(directory)
            samples = np.tile(np.array([[0.0, 0.25], [-0.05, 0.2]], dtype=np.float64), (480, 1))
            pcm = directory / "samples.f64le"
            wav = directory / "samples.wav"
            samples.astype("<f8").tofile(pcm)
            sf.write(wav, samples, 48000, subtype="PCM_24")
            report = self.module.inspect_pair(pcm, wav)
            self.assertEqual(report["samples_per_channel"], 960)
            self.assertLessEqual(report["pcm24_max_error"], 2**-23)
            samples[0, 0] = 0.1
            samples.astype("<f8").tofile(pcm)
            with self.assertRaisesRegex(ValueError, "PCM24"):
                self.module.inspect_pair(pcm, wav)

    def test_band_and_coherent_cross_term(self):
        t = np.arange(48000) / 48000
        a = np.sin(2 * np.pi * 160 * t)
        b = 0.5 * a
        powers = self.module.band_powers(np.column_stack((a, a)))
        self.assertGreater(powers["80-250"], 0.49)
        self.assertLess(powers["1000-2000"], 1e-8)
        cross = self.module.cross_term(a, b)
        self.assertAlmostEqual(cross, 0.5, places=10)
        self.assertAlmostEqual(np.mean((a + b) ** 2), np.mean(a**2) + np.mean(b**2) + cross, places=10)

    def test_ffmpeg_reports_integrated_loudness_and_true_peak(self):
        with tempfile.TemporaryDirectory(dir=LAB) as directory:
            directory = Path(directory)
            t = np.arange(3 * 48000) / 48000
            samples = 0.1 * np.sin(2 * np.pi * 1000 * t)
            wav = directory / "sine.wav"
            sf.write(wav, np.column_stack((samples, samples)), 48000, subtype="PCM_24")
            report = self.module.measure_loudness(wav, directory / "ffmpeg.log")
            self.assertGreater(report["lufs"], -26)
            self.assertLess(report["lufs"], -18)
            self.assertGreater(report["true_peak_dbtp"], -21)
            self.assertLess(report["true_peak_dbtp"], -19)

    def test_audition_uses_one_safe_target_for_entire_group(self):
        path = LAB / "make_audition.py"
        self.assertTrue(path.is_file(), "fixed-scalar audition builder must exist")
        spec = importlib.util.spec_from_file_location("cabin_audition", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        group = [{"lufs": -20.0, "true_peak_dbtp": -1.0, "peak": 0.5},
                 {"lufs": -30.0, "true_peak_dbtp": 0.0, "peak": 0.5}]
        target = module.safe_target(group)
        self.assertAlmostEqual(target, -31.5)
        for item in group:
            self.assertLessEqual(item["true_peak_dbtp"] + target - item["lufs"], -1.5 + 1e-12)
            self.assertLessEqual(item["peak"] * module.scalar(item["lufs"], target), 1.0)

    def test_audition_outputs_derive_from_raw_with_hidden_repeat(self):
        path = LAB / "make_audition.py"
        self.assertTrue(path.is_file())
        spec = importlib.util.spec_from_file_location("cabin_audition_integration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=LAB) as directory:
            root = Path(directory)
            output = root / "output"
            output.mkdir()
            t = np.arange(3 * 48000) / 48000
            raw = {}
            for label, amplitude in (("N", 0.04), ("MD", 0.06)):
                case = root / label
                case.mkdir()
                wave = amplitude * np.sin(2 * np.pi * 1000 * t)
                raw[label] = np.column_stack((wave, wave))
                pcm = case / "candidate.pcm.f64le"
                raw[label].astype("<f8").tofile(pcm)
                (case / "receipt.json").write_text(json.dumps({"pcm_sha256": self.module.digest(pcm)}), encoding="utf-8")
            result = module.build_group(root, output, "trial", {"N": ("N", 0, None), "MD": ("MD", 0, None)})
            self.assertEqual(result["blind_items"], 3)
            group = output / "trial"
            manifest = json.loads((group / "named" / "manifest.json").read_text(encoding="utf-8"))
            wave, fs = sf.read(group / "named" / "MD.wav", always_2d=True)
            self.assertEqual(fs, 48000)
            expected = raw["MD"] * manifest["items"]["MD"]["scalar"]
            self.assertLessEqual(np.max(np.abs(wave - expected)), 2**-23)
            key = json.loads((group / "blind-key.json").read_text(encoding="utf-8"))
            self.assertEqual(list(key.values()).count("MD"), 2)


if __name__ == "__main__":
    unittest.main()
