import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from build_c63_hybrid_targets import (
    FEATURE_KEYS,
    build,
    features,
    main,
    minimum_phase_kernel,
)


RATE = 48000
CLIP_SAMPLES = RATE * 6
CLIP_NAMES = (
    "ref_steady_low.wav",
    "ref_steady_mid.wav",
    "ref_full_pull.wav",
    "ref_steady_high.wav",
    "ref_hot_idle.wav",
    "ref_afterfire.wav",
    "ref_shift.wav",
)


def _synthetic_clip(filename):
    t = np.arange(CLIP_SAMPLES, dtype=np.float64) / RATE
    if filename == "ref_hot_idle.wav":
        active = t < 1.2
        x = np.where(active, 0.18 * np.sin(2 * np.pi * 115 * t), 0.0)
    elif filename == "ref_afterfire.wav":
        envelope = np.full_like(t, 0.025)
        for center in (0.35, 1.15, 2.05, 3.05, 4.0, 5.1):
            envelope += 0.65 * np.exp(-0.5 * ((t - center) / 0.025) ** 2)
        x = envelope * (np.sin(2 * np.pi * 620 * t) + 0.3 * np.sin(2 * np.pi * 1240 * t))
    else:
        frequencies = {
            "ref_steady_low.wav": (110, 0.12),
            "ref_steady_mid.wav": (340, 0.18),
            "ref_full_pull.wav": (520, 0.24),
            "ref_steady_high.wav": (840, 0.31),
            "ref_shift.wav": (460, 0.21),
        }
        carrier, modulation = frequencies[filename]
        envelope = 1.0 + 0.25 * np.sin(2 * np.pi * modulation * t)
        x = 0.2 * envelope * (
            np.sin(2 * np.pi * carrier * t)
            + 0.35 * np.sin(2 * np.pi * 2.3 * carrier * t)
            + 0.1 * np.sin(2 * np.pi * 4.1 * carrier * t)
        )
    return np.round(np.clip(x, -0.95, 0.95) * 32767).astype(np.int16)


class HybridTargetsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bundle = Path(self.temp.name) / "bundle"
        self.bundle.mkdir()
        clips = {}
        for filename in CLIP_NAMES:
            path = self.bundle / filename
            wavfile.write(path, RATE, _synthetic_clip(filename))
            source_label = "pull-high-source" if filename in (
                "ref_full_pull.wav",
                "ref_steady_high.wav",
            ) else f"source:{filename}"
            source_sha = hashlib.sha256(source_label.encode("utf-8")).hexdigest()
            source_start = CLIP_SAMPLES if filename == "ref_steady_high.wav" else 0
            clips[filename] = {
                "filename": filename,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_sha256": source_sha,
                "source_id": source_label,
                "start_sample": source_start,
                "evidence_level": "SYNTHETIC_TEST_FIXTURE",
                "rights_status": "SYNTHETIC_TEST_ONLY",
            }
        (self.bundle / "reference_clip_receipt.json").write_text(
            json.dumps({"clips": clips}), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_minimum_phase_kernel_contract_and_truncated_shape(self):
        levels = np.array([-9.0, -6.0, -2.0, 0.0, 2.0, 0.0, -3.0, -7.0])
        kernel = minimum_phase_kernel(levels)
        repeated = minimum_phase_kernel(levels)

        self.assertEqual(kernel.shape, (2048,))
        self.assertTrue(np.isfinite(kernel).all())
        self.assertLessEqual(abs(float(kernel.sum())), 1e-10)
        self.assertEqual(float(kernel[-1]), 0.0)
        self.assertAlmostEqual(float(np.dot(kernel, kernel)), 1.0, places=12)
        np.testing.assert_array_equal(kernel, repeated)

        centers = np.geomspace(200.0, 6300.0, 8)
        fft_freqs = np.fft.rfftfreq(32768, d=1.0 / RATE)
        magnitude_db = 20 * np.log10(np.maximum(np.abs(np.fft.rfft(kernel, n=32768)), 1e-12))
        actual_centers = np.interp(centers, fft_freqs, magnitude_db)
        correlation = np.corrcoef(levels, actual_centers)[0, 1]
        self.assertGreater(correlation, 0.85)

    def test_minimum_phase_kernel_rejects_malformed_controls(self):
        invalid = (
            np.zeros(7),
            np.zeros((2, 4)),
            np.array([0.0] * 7 + [np.nan]),
            np.array([0.0] * 7 + [np.inf]),
        )
        for controls in invalid:
            with self.subTest(controls=controls):
                with self.assertRaises(ValueError):
                    minimum_phase_kernel(controls)

    def test_flat_controls_meet_fixed_final_kernel_stopbands(self):
        kernel = minimum_phase_kernel(np.zeros(8))
        freqs = np.fft.rfftfreq(65536, d=1.0 / RATE)
        power = np.abs(np.fft.rfft(kernel, n=65536)) ** 2
        reference_power = float(np.interp(1000.0, freqs, power))

        for stopband_hz in (100.0, 12600.0):
            with self.subTest(stopband_hz=stopband_hz):
                stopband_power = float(np.interp(stopband_hz, freqs, power))
                attenuation_db = 10.0 * np.log10(stopband_power / reference_power)
                self.assertLessEqual(attenuation_db, -18.0)

    def test_features_reject_silent_short_and_nonfinite_pcm(self):
        for pcm in (
            np.zeros(RATE // 2),
            np.zeros(RATE * 2),
            np.full(RATE * 2, np.nan),
            np.full(RATE * 2, np.inf),
            np.zeros((RATE * 2, 2)),
        ):
            with self.subTest(shape=np.shape(pcm)):
                with self.assertRaises(ValueError):
                    features(pcm)

    def test_gain_changes_absolute_power_but_not_shape_or_modulation(self):
        t = np.arange(RATE * 4, dtype=np.float64) / RATE
        envelope = (
            1.0
            + 0.30 * np.sin(2 * np.pi * 3 * t)
            + 0.15 * np.sin(2 * np.pi * 11 * t)
            + 0.08 * np.sin(2 * np.pi * 27 * t)
        )
        pcm = envelope * (
            np.sin(2 * np.pi * 440 * t)
            + 0.45 * np.sin(2 * np.pi * 1320 * t)
            + 0.18 * np.sin(2 * np.pi * 3100 * t)
        )
        original = features(pcm)
        quieter = features(0.4 * pcm)

        self.assertEqual(set(FEATURE_KEYS), {f"spec{i}" for i in range(8)} | {f"mod{i}" for i in range(4)} | {"env_cv"})
        for key in FEATURE_KEYS:
            self.assertAlmostEqual(original[key], quieter[key], places=9)
        self.assertAlmostEqual(quieter["rms"] / original["rms"], 0.4, places=12)
        np.testing.assert_allclose(
            np.asarray(quieter["absolute_band_power"])
            / np.asarray(original["absolute_band_power"]),
            0.16,
            rtol=1e-9,
            atol=1e-12,
        )

    def test_build_reuses_source_range_overlap_validation(self):
        receipt_path = self.bundle / "reference_clip_receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["clips"]["ref_steady_high.wav"]["start_sample"] = 0
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Overlapping source samples"):
            build(self.bundle)

    def test_build_rejects_clip_sha_mismatch(self):
        path = self.bundle / "ref_steady_low.wav"
        path.write_bytes(path.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "Reference clip identity changed"):
            build(self.bundle)

    def test_sustained_distributions_exclude_event_references(self):
        result = build(self.bundle)
        windows = result["windows"]
        sustained = [
            row
            for row in windows
            if row["split"] == "calibration"
            and row["filename"] not in ("ref_afterfire.wav", "ref_shift.wav")
        ]

        self.assertEqual(result["scope"], "R2_RIGHTS_UNVERIFIED_RESEARCH_ONLY")
        self.assertEqual(set(result["sustained_window_ids"]), {row["id"] for row in sustained})
        self.assertFalse(any("afterfire" in key or "shift" in key for key in result["sustained_window_ids"]))
        for key in FEATURE_KEYS:
            floor = 0.05 if key == "env_cv" else 1.0
            expected = max(float(np.std([row["features"][key] for row in sustained])), floor)
            self.assertAlmostEqual(result["calibration_scales"][key], expected, places=12)

        self.assertIn("calibration", result["feature_distributions"])
        self.assertIn("holdout", result["feature_distributions"])
        self.assertIn("context", result["feature_distributions"])
        self.assertAlmostEqual(sum(result["weights"][key] for key in (f"spec{i}" for i in range(8))), 0.50)
        self.assertAlmostEqual(sum(result["weights"][key] for key in (f"mod{i}" for i in range(4))), 0.35)
        self.assertAlmostEqual(result["weights"]["env_cv"], 0.15)
        self.assertEqual(
            result["reference_identity"]["receipt_sha256"],
            hashlib.sha256((self.bundle / "reference_clip_receipt.json").read_bytes()).hexdigest(),
        )
        self.assertEqual(set(result["reference_identity"]["clips"]), set(CLIP_NAMES))
        self.assertEqual(result["afterfire_reference"]["schema"], "c63.ar2.event_reference.v1")
        self.assertEqual(
            result["afterfire_reference"]["labels"],
            "UNVERIFIED_TRANSIENTS_NOT_CONFIRMED_COMBUSTION",
        )
        self.assertIn("censored", result["afterfire_reference"]["calibration"])
        self.assertIn("censored", result["afterfire_reference"]["same_source_time_holdout"])
        self.assertEqual(result["afterfire_support"], "UNLABELED_CENSORED_LOCAL_TRANSIENTS")
        self.assertEqual(result["rpm_load_assignment"], "NONE_UNLABELED_REFERENCE_FEATURES_ONLY")
        self.assertFalse(
            any("rpm" in key.lower() or "load" in key.lower() for row in windows for key in row)
        )

    def test_cli_refuses_to_overwrite_existing_output(self):
        output = Path(self.temp.name) / "existing.json"
        output.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            main(["--bundle", str(self.bundle), "--out", str(output)])
        self.assertEqual(output.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
