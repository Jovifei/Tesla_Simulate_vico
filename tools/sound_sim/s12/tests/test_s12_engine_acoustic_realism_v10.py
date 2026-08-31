"""RED/GREEN contracts for the stateful S12 acoustic-realism v1.0 layer."""

from __future__ import annotations

import json
import importlib
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np


S12_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S12_ROOT))

import acoustic_identity_v015 as identity
from acoustic_identity_v015 import SourceRender, VehicleStateTrace
from acoustic_identity_v015.render_realism_v10 import _RENDERERS as _FORMAL_RENDERERS


V015 = S12_ROOT / "acoustic_identity_v015"
REFERENCE_MANIFEST = V015 / "reference_database" / "realism_reference_manifest.json"
REFERENCE_TARGETS = V015 / "targets" / "realism_feature_targets.json"
CHARACTER_MATRIX = V015 / "reference_database" / "vehicle_sound_character_matrix.md"
_RENDERERS = dict(_FORMAL_RENDERERS)
_ANCHOR_VEHICLE_IDS = {"ferrari_458", "hellcat", "rx7_fd"}


def _trace(
    rpm: float = 950.0,
    load: float = 0.18,
    throttle: float | None = None,
    duration_s: float = 0.8,
) -> VehicleStateTrace:
    time_s = np.linspace(0.0, duration_s, int(duration_s * 100) + 1)
    return VehicleStateTrace(
        time_s=time_s,
        rpm=np.full(time_s.size, rpm),
        load=np.full(time_s.size, load),
        throttle=np.full(time_s.size, load if throttle is None else throttle),
        acceleration_mps2=np.zeros(time_s.size),
    ).validate()


def _deceleration_trace(rpm: float = 5600.0, duration_s: float = 0.9) -> VehicleStateTrace:
    time_s = np.linspace(0.0, duration_s, int(duration_s * 100) + 1)
    closing = time_s >= duration_s * 0.40
    return VehicleStateTrace(
        time_s=time_s,
        rpm=np.where(closing, rpm - 900.0 * (time_s - duration_s * 0.40), rpm),
        load=np.where(closing, 0.16, 0.78),
        throttle=np.where(closing, 0.03, 0.82),
        acceleration_mps2=np.zeros(time_s.size),
    ).validate()


def _band_energy(stereo: np.ndarray, low_hz: float, high_hz: float, sample_rate_hz: int = 48000) -> float:
    signal = np.asarray(stereo, dtype=np.float64).mean(axis=1)
    spectrum = np.square(np.abs(np.fft.rfft(signal * np.hanning(signal.size))))
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / sample_rate_hz)
    return float(spectrum[(frequencies >= low_hz) & (frequencies <= high_hz)].sum())


class RealismReferenceDatabaseTests(unittest.TestCase):
    def test_manifest_keeps_extracted_r2_media_outside_repo_and_records_risk(self) -> None:
        manifest = json.loads(REFERENCE_MANIFEST.read_text(encoding="utf-8"))
        targets = json.loads(REFERENCE_TARGETS.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "s12-acoustic-realism-reference-1.0")
        self.assertEqual(set(manifest["vehicles"]), set(_RENDERERS))
        self.assertEqual(set(targets["vehicles"]), _ANCHOR_VEHICLE_IDS)
        for vehicle_id, record in manifest["vehicles"].items():
            self.assertEqual(record["calibration_status"], "uncalibrated")
            self.assertIn("risk", record["recording"])
            if vehicle_id in _ANCHOR_VEHICLE_IDS:
                self.assertEqual(record["source_level"], "R2")
                self.assertIn("sha256", record["external_media"])
            else:
                self.assertEqual(record["source_level"], "R2")
                self.assertIn("pending_online_research", record["external_media"].get("note", ""))
            self.assertNotIn("path", json.dumps(record).lower())
            if vehicle_id in _ANCHOR_VEHICLE_IDS:
                self.assertTrue(targets["vehicles"][vehicle_id]["targets_are_relative_only"])
        matrix = CHARACTER_MATRIX.read_text(encoding="utf-8").lower()
        for token in ("r2", "idle", "steady", "acceleration", "deceleration", "uncalibrated"):
            self.assertIn(token, matrix)

    def test_reference_feature_analyzer_returns_relative_stft_bands_and_transient_count(self) -> None:
        analyzer = importlib.import_module("acoustic_identity_v015.acoustic_analysis.reference_features")
        samples = (0.20 * np.sin(2.0 * np.pi * 160.0 * np.arange(48000) / 48000.0) * 32767.0).astype("<i2")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reference.wav"
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(48000)
                stream.writeframes(samples.tobytes())
            result = analyzer.analyze_reference_wav(path, {"steady": (0.10, 0.90)})
        steady = result["segments"]["steady"]
        self.assertEqual(result["analysis_domain"], "relative_recording_features_only")
        self.assertGreater(steady["spectral_centroid_hz"], 100.0)
        self.assertGreater(steady["band_energy_fraction"]["40_200hz"], 0.90)
        self.assertGreaterEqual(steady["transient_event_count"], 0)


class IdleAndPressureTests(unittest.TestCase):
    def test_idle_dynamics_are_deterministic_phase_anchored_and_vehicle_distinct(self) -> None:
        trace = _trace()
        idle_stems = {}
        for vehicle_id, renderer in _RENDERERS.items():
            source = renderer(trace)
            first = identity.apply_idle_dynamics(source, vehicle_id, trace)
            second = identity.apply_idle_dynamics(source, vehicle_id, trace)
            np.testing.assert_array_equal(first.pressure, second.pressure)
            self.assertTrue({"idle_combustion_variation", "idle_accessory", "idle_valvetrain", "idle_crank"} <= set(first.stems))
            self.assertGreater(first.diagnostics["idle_cycle_amplitude_std"], 0.0)
            self.assertGreater(first.diagnostics["idle_phase_jitter_samples_peak"], 0.0)
            idle_stems[vehicle_id] = first.stems["idle_combustion_variation"]
        self.assertFalse(np.array_equal(idle_stems["ferrari_458"], idle_stems["hellcat"]))
        self.assertFalse(np.array_equal(idle_stems["hellcat"], idle_stems["rx7_fd"]))

    def test_pressure_chain_is_causal_state_driven_and_hellcat_has_deepest_body(self) -> None:
        trace = _trace(rpm=2200.0, load=0.72, throttle=0.72)
        deep_energy = {}
        for vehicle_id, renderer in _RENDERERS.items():
            pressured = identity.apply_low_frequency_body(renderer(trace), vehicle_id, trace)
            self.assertTrue({"pressure_pulse", "exhaust_coupling", "body_resonance", "radiation"} <= set(pressured.stems))
            self.assertEqual(pressured.diagnostics["pressure_chain"], "pressure_pulse -> exhaust_coupling -> body_resonance -> radiation")
            self.assertGreater(pressured.diagnostics["pressure_state_variation"], 0.0)
            deep_energy[vehicle_id] = _band_energy(pressured.stems["radiation"], 40.0, 200.0)
        self.assertGreater(deep_energy["hellcat"], deep_energy["ferrari_458"] * 1.25)
        self.assertGreater(deep_energy["hellcat"], deep_energy["rx7_fd"] * 1.15)


class StateDependentTransientTests(unittest.TestCase):
    def test_afterfire_requires_hot_high_rpm_closed_throttle_and_is_deterministic(self) -> None:
        deceleration = _deceleration_trace()
        steady = _trace(rpm=5600.0, load=0.78, throttle=0.82, duration_s=0.9)
        for vehicle_id, renderer in _RENDERERS.items():
            active = identity.apply_afterfire(renderer(deceleration), vehicle_id, deceleration)
            repeated = identity.apply_afterfire(renderer(deceleration), vehicle_id, deceleration)
            inactive = identity.apply_afterfire(renderer(steady), vehicle_id, steady)
            np.testing.assert_array_equal(active.stems["afterfire"], repeated.stems["afterfire"])
            self.assertGreater(active.diagnostics["afterfire_event_count"], 0)
            self.assertGreater(float(np.sum(np.square(active.stems["afterfire"]))), 0.0)
            self.assertEqual(inactive.diagnostics["afterfire_event_count"], 0)
            self.assertEqual(float(np.sum(np.square(inactive.stems["afterfire"]))), 0.0)

    def test_forced_induction_exposes_state_not_static_tone(self) -> None:
        low = identity.render_hellcat(_trace(rpm=3800.0, load=0.20, throttle=0.20))
        high = identity.render_hellcat(_trace(rpm=3800.0, load=0.90, throttle=0.90))
        self.assertGreater(high.diagnostics["blower_boost_state_peak"], low.diagnostics["blower_boost_state_peak"])
        self.assertGreater(high.diagnostics["blower_energy"], low.diagnostics["blower_energy"])
        rx = identity.render_rx7_fd(_deceleration_trace(rpm=6200.0))
        self.assertGreater(rx.diagnostics["boost_state_peak"], 0.0)
        self.assertGreater(rx.diagnostics["blow_off_state_peak"], 0.0)
        self.assertIn("blow_off", rx.stems)


class RealismMetricAndPublicationTests(unittest.TestCase):
    def test_metrics_measure_vehicle_specific_idle_body_and_transient_features(self) -> None:
        trace = _deceleration_trace()
        for vehicle_id, renderer in _RENDERERS.items():
            rendered = identity.apply_afterfire(identity.apply_idle_dynamics(renderer(trace), vehicle_id, trace), vehicle_id, trace)
            rendered = identity.apply_low_frequency_body(rendered, vehicle_id, trace)
            metrics = identity.compute_realism_metrics(vehicle_id, rendered, trace)
            self.assertTrue(metrics["finite"])
            self.assertGreater(metrics["low_frequency"]["energy_fraction_40_200hz"], 0.0)
            self.assertGreaterEqual(metrics["transients"]["afterfire_event_count"], 0)
            self.assertIn(vehicle_id, metrics["vehicle_features"])

    def test_short_publication_emits_exact_review_bundle_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            publication = identity.publish_realism_v10(root, scenario_duration_s=0.55)
            self.assertTrue(publication["comparison"]["passes"])
            for vehicle_id in _RENDERERS:
                folder = root / "identity_v10" / vehicle_id
                self.assertEqual(
                    {path.name for path in folder.glob("*.wav")},
                    {"idle.wav", "acceleration.wav", "deceleration.wav", "full_pull.wav"},
                )
                self.assertTrue((folder / "spectrogram.png").stat().st_size > 0)
                self.assertTrue((folder / "order_map.png").stat().st_size > 0)
                metrics = json.loads((folder / "identity_metrics.json").read_text(encoding="utf-8"))
                self.assertIn("loudness", metrics)
                self.assertIn("crest_factor_db", metrics["loudness"]["bundle"])
            self.assertTrue((root / "identity_comparison_report.md").is_file())
            self.assertTrue((root / "S12_Acoustic_Realism_Report.md").is_file())


class CompleteDriveCycleTests(unittest.TestCase):
    def test_continuous_drive_cycle_preserves_hot_lift_afterfire_for_each_vehicle(self) -> None:
        from acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace, render_drive_cycle_source

        for vehicle_id in _RENDERERS:
            trace = build_drive_cycle_trace(vehicle_id, duration_s=3.0)
            rendered = render_drive_cycle_source(vehicle_id, trace)
            lift_time_s = rendered.diagnostics["drive_cycle_lift_time_s"]
            afterfire = rendered.stems["afterfire"]
            active = np.flatnonzero(np.max(np.abs(afterfire), axis=1) > 0.0)
            self.assertAlmostEqual(lift_time_s, 1.8, places=6)
            self.assertGreater(rendered.diagnostics["afterfire_event_count"], 0)
            self.assertGreater(rendered.diagnostics["afterfire_stem_energy"], 0.0)
            self.assertGreater(active.size, 0)
            self.assertGreaterEqual(trace.time_s[active[0]], lift_time_s)
            self.assertLessEqual(trace.throttle[active[0]], 0.04)


if __name__ == "__main__":
    unittest.main()
