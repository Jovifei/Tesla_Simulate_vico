"""RED/GREEN contracts for the v0.15 acoustic-identity research foundation."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np


S12_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S12_ROOT))

import acoustic_identity_v015 as identity_v015
from acoustic_identity_v015 import SourceRender, VehicleStateTrace, load_research_database
from acoustic_identity_v015.acoustic_analysis import engine_identity_metrics as metric_impl
from acoustic_identity_v015.loudness_manager import LoudnessMetrics
from acoustic_identity_v015.render_identity_v02 import _apply_frozen_ptr, _edge_fade, _loudness_dict, _scenario_trace


V015 = S12_ROOT / "acoustic_identity_v015"
REFERENCE_DATABASE = V015 / "reference_database" / "vehicle_records.json"
SYNTHESIS_TARGETS = V015 / "targets" / "synthesis_targets.json"
CHARACTER_MATRIX = V015 / "reference_database" / "vehicle_sound_character_matrix.md"
VEHICLE_FACTS = {
    "ferrari_458": {
        "display_name": "Ferrari 458 Italia",
        "topology": {
            "engine": "4497 cc 90-degree V8",
            "power_peak_rpm": 9000,
            "exhaust": "load-dependent bypass exhaust path",
        },
    },
    "hellcat": {
        "display_name": "Dodge Challenger SRT Hellcat",
        "topology": {
            "engine": "6.2 L 90-degree V8",
            "supercharger": "2.4 L twin-screw supercharger",
            "drive_ratio": 2.36,
        },
    },
    "rx7_fd": {
        "display_name": "Mazda RX-7 FD",
        "topology": {
            "engine": "13B two-rotor rotary",
            "turbo": "sequential twin-turbo",
            "rotary_order_character": "integer-order rotary",
        },
    },
}
EXPECTED_VIDEO_IDS = {
    "ferrari_458": {"1fzUnAUarNI", "R6e_5v2aps4", "GzeRNBmH2vY"},
    "hellcat": {"cKx-cb0fzeo"},
    "rx7_fd": {"hCz1YS5yJkw"},
}
SOURCE_MODULES = {
    "flat_plane_v8_source.py",
    "supercharged_hemi_source.py",
    "rotary_turbo_source.py",
    "lamborghini_v12_source.py",
    "mercedes_v8_source.py",
    "lexus_v10_source.py",
    "nissan_v6_turbo_source.py",
    "toyota_i6_turbo_source.py",
}
RENDERER_NAMES = ("render_ferrari_458", "render_hellcat", "render_rx7_fd")
RENDERERS_PRESENT = all(hasattr(identity_v015, name) for name in RENDERER_NAMES)


def _trace(
    *,
    rpm: float = 4500.0,
    load: float = 0.65,
    throttle: float | None = None,
    duration_s: float = 1.0,
) -> VehicleStateTrace:
    time_s = np.linspace(0.0, duration_s, 101)
    return VehicleStateTrace(
        time_s=time_s,
        rpm=np.full(time_s.size, rpm),
        load=np.full(time_s.size, load),
        throttle=np.full(time_s.size, load if throttle is None else throttle),
        acceleration_mps2=np.zeros(time_s.size),
    )


def _rms(signal: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(signal))))


def _high_frequency_energy(signal: np.ndarray, sample_rate_hz: int) -> float:
    spectrum = np.fft.rfft(signal[:, 0] * np.hanning(signal.shape[0]))
    frequencies = np.fft.rfftfreq(signal.shape[0], 1.0 / sample_rate_hz)
    return float(np.sum(np.square(np.abs(spectrum[frequencies >= 1200.0]))))


def _high_frequency_fraction(signal: np.ndarray, sample_rate_hz: int) -> float:
    spectrum = np.fft.rfft(signal[:, 0] * np.hanning(signal.shape[0]))
    frequencies = np.fft.rfftfreq(signal.shape[0], 1.0 / sample_rate_hz)
    energy = np.square(np.abs(spectrum))
    return float(energy[frequencies >= 1200.0].sum() / energy.sum()) if energy.sum() else 0.0


def _unit_rms_correlation(left: np.ndarray, right: np.ndarray) -> float:
    left_mono = left.mean(axis=1)
    right_mono = right.mean(axis=1)
    return float(abs(np.corrcoef(left_mono / _rms(left_mono), right_mono / _rms(right_mono))[0, 1]))


def _relative_db(signal: np.ndarray, reference: np.ndarray) -> float:
    return float(20.0 * np.log10(_rms(signal) / _rms(reference)))


def _order_metrics(signal: np.ndarray, sample_rate_hz: int, engine_hz: float) -> tuple[float, float]:
    steady = signal[-sample_rate_hz // 2 :, 0] * np.hanning(sample_rate_hz // 2)
    spectrum = np.square(np.abs(np.fft.rfft(steady)))
    frequencies = np.fft.rfftfreq(steady.size, 1.0 / sample_rate_hz)

    def energy_at(orders: np.ndarray) -> float:
        return float(sum(spectrum[np.abs(frequencies - order * engine_hz) <= 2.5].sum() for order in orders))

    integer = energy_at(np.arange(1.0, 25.0))
    half = energy_at(np.arange(1.5, 24.5, 1.0))
    total = integer + half
    return integer / total, half / total


def _narrowband_energy(signal: np.ndarray, sample_rate_hz: int, frequency_hz: float) -> float:
    spectrum = np.square(np.abs(np.fft.rfft(signal[-sample_rate_hz:, 0] * np.hanning(sample_rate_hz))))
    frequencies = np.fft.rfftfreq(sample_rate_hz, 1.0 / sample_rate_hz)
    return float(spectrum[np.abs(frequencies - frequency_hz) <= 2.0].sum())


def _assert_finite_diagnostics(test: unittest.TestCase, diagnostics: dict[str, object] | object) -> None:
    if not isinstance(diagnostics, dict):
        test.fail("diagnostics must be a mapping")
    for key, value in diagnostics.items():
        if isinstance(value, (float, int, np.floating, np.integer)):
            test.assertTrue(np.isfinite(value), key)
        elif isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, (float, int, np.floating, np.integer)):
                    test.assertTrue(np.isfinite(item), key)


class AcousticIdentityV015ResearchDatabaseTests(unittest.TestCase):
    def test_three_vehicle_records_preserve_topology_provenance_and_legal_scope(self) -> None:
        payload = json.loads(REFERENCE_DATABASE.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "s12-acoustic-identity-reference-0.15")
        self.assertEqual(set(payload["vehicles"]), set(VEHICLE_FACTS))

        for vehicle_id, expected in VEHICLE_FACTS.items():
            with self.subTest(vehicle_id=vehicle_id):
                record = payload["vehicles"][vehicle_id]
                self.assertEqual(record["display_name"], expected["display_name"])
                self.assertEqual(record["topology"], expected["topology"])
                self.assertIn("manufacturer facts support topology only", record["legal_scope"].lower())
                self.assertIn("not oem reproduction", record["legal_scope"].lower())
                self.assertGreaterEqual(len(record["topology_sources"]), 1)
                for source in record["topology_sources"]:
                    self.assertTrue(source["source_url"].startswith("https://"))
                    self.assertIn(source["source_level"], {"M", "SAE", "service", "NV"})
                    self.assertIn(source.get("provenance_class"), {"A", "B", "C"})
                    self.assertTrue(source["source"])
                    self.assertIn("topology", source["source_scope"].lower())

    def test_specific_public_videos_are_listening_only_with_configuration_caveats(self) -> None:
        payload = json.loads(REFERENCE_DATABASE.read_text(encoding="utf-8"))
        for vehicle_id, record in payload["vehicles"].items():
            with self.subTest(vehicle_id=vehicle_id):
                observations = record.get("public_video_observations", [])
                self.assertEqual({item["video_id"] for item in observations}, EXPECTED_VIDEO_IDS[vehicle_id])
                for observation in observations:
                    self.assertEqual(observation["source_url"], f"https://www.youtube.com/watch?v={observation['video_id']}")
                    self.assertEqual(observation["source_level"], "R2")
                    self.assertEqual(observation["provenance_class"], "B")
                    self.assertEqual(observation["source"], "listening-only")
                    self.assertEqual(observation["calibration_status"], "inconclusive")
                    self.assertTrue(observation["title"])
                    self.assertTrue(observation["configuration_caveat"])
                    self.assertTrue(observation["qualitative_cues"])
                    self.assertTrue(observation["permitted_use"])
                    self.assertTrue(observation["exclusion"])
                    self.assertNotIn("@", observation["source_url"])

    def test_video_configuration_exclusions_are_explicit(self) -> None:
        records = json.loads(REFERENCE_DATABASE.read_text(encoding="utf-8"))["vehicles"]
        videos = {
            item["video_id"]: item
            for record in records.values()
            for item in record.get("public_video_observations", [])
        }
        if "1fzUnAUarNI" not in videos:
            self.fail("missing required specific public-video observations")
        novitec = videos["1fzUnAUarNI"]
        self.assertEqual(novitec["title"], "POV: Novitec Exhaust on a Ferrari 812 GTS (V12 Heaven)")
        self.assertIn("modified", novitec["configuration_caveat"].lower())
        self.assertIn("812", novitec["configuration_caveat"])
        self.assertIn("v12", novitec["configuration_caveat"].lower())
        self.assertIn("high-rpm", novitec["permitted_use"].lower())
        self.assertIn("non-target", novitec["exclusion"].lower())
        self.assertIn("non-calibration", novitec["exclusion"].lower())

        stock_claim = videos["R6e_5v2aps4"]
        self.assertEqual(stock_claim["title"], "Ferrari 458 Italia stock exhaust note and acceleration")
        self.assertIn("unverified", stock_claim["configuration_caveat"].lower())
        self.assertIn("acceleration", stock_claim["permitted_use"].lower())

        straight_pipe = videos["GzeRNBmH2vY"]
        self.assertIn("straight pipe", straight_pipe["configuration_caveat"].lower())
        self.assertIn("manipulated", straight_pipe["configuration_caveat"].lower())
        self.assertIn("excluded", straight_pipe["exclusion"].lower())

        hellcat = videos["cKx-cb0fzeo"]
        self.assertEqual(hellcat["title"], "2016 Dodge Challenger SRT Hellcat - SOUND!")
        self.assertIn("uploader claim", hellcat["configuration_caveat"].lower())
        self.assertIn("unverified", hellcat["configuration_caveat"].lower())
        self.assertIn("revving", hellcat["qualitative_cues"].lower())

        rx7 = videos["hCz1YS5yJkw"]
        for token in ("compilation", "modified", "bridgeported", "antilag"):
            self.assertIn(token, rx7["configuration_caveat"].lower())
        self.assertIn("excluded", rx7["exclusion"].lower())

    def test_numeric_synthesis_targets_are_explicitly_synthetic_and_uncalibrated(self) -> None:
        payload = json.loads(SYNTHESIS_TARGETS.read_text(encoding="utf-8"))
        self.assertEqual(set(payload["vehicles"]), set(VEHICLE_FACTS))
        required_profile_fields = {
            "vehicle",
            "engine_architecture",
            "dominant_character",
            "missing_features",
            "target_metrics",
        }
        for vehicle_id, profile in payload["vehicles"].items():
            with self.subTest(vehicle_id=vehicle_id):
                self.assertTrue(required_profile_fields <= set(profile))
                self.assertEqual(profile["vehicle"], vehicle_id)
                self.assertTrue(profile["engine_architecture"])
                self.assertTrue(profile["dominant_character"])
                self.assertIsInstance(profile["missing_features"], list)
                provenance = profile.get("field_provenance", {})
                self.assertEqual(set(provenance), {"vehicle", "engine_architecture", "dominant_character", "missing_features"})
                if not provenance:
                    continue
                self.assertIn(provenance["engine_architecture"]["provenance_class"], {"A", "B"})
                for field in ("dominant_character", "missing_features"):
                    self.assertEqual(provenance[field]["provenance_class"], "C")
                self.assertGreaterEqual(len(profile["target_metrics"]), 1)
                for target_name, target in profile["target_metrics"].items():
                    self.assertTrue(target_name)
                    self.assertIsInstance(target["value"], (int, float))
                    self.assertEqual(target["provenance_class"], "C")
                    self.assertEqual(target["source_level"], "C")
                    self.assertEqual(target["source"], "synthetic")
                    self.assertEqual(target["calibration_status"], "uncalibrated")
                    self.assertEqual(target["source_url"], "")
                    self.assertIn("separation", target["source_scope"].lower())

    def test_character_matrix_is_substantive_url_backed_and_bounded(self) -> None:
        if not CHARACTER_MATRIX.is_file():
            self.fail(f"missing character matrix: {CHARACTER_MATRIX}")
        matrix = CHARACTER_MATRIX.read_text(encoding="utf-8").lower()
        self.assertGreaterEqual(len(matrix), 1500)
        self.assertGreaterEqual(matrix.count("https://"), 10)
        for token in (
            "ferrari", "flat-plane", "ignition", "pulse", "high-frequency", "attack",
            "hellcat", "exhaust", "blower", "mechanical", "intake", "low-band", "load",
            "rx-7", "non-piston", "phase", "integer-order", "turbo", "lift",
            "limitations", "uncalibrated", "not oem reproduction",
            "title", "configuration caveat", "qualitative cues", "permitted use", "exclusion",
            "1fzunauarni", "r6e_5v2aps4", "gzer nbm".replace(" ", ""), "ckx-cb0fzeo", "hcz1ys5yjkw",
        ):
            self.assertIn(token, matrix)

    def test_loader_returns_exactly_the_researched_vehicle_records_and_targets(self) -> None:
        database = load_research_database()
        self.assertEqual(set(database.vehicles), set(VEHICLE_FACTS))
        self.assertEqual(set(database.synthesis_targets), set(VEHICLE_FACTS))


class VehicleStateTraceContractsTests(unittest.TestCase):
    def test_validate_accepts_finite_monotonic_equal_length_state_arrays(self) -> None:
        trace = VehicleStateTrace(
            time_s=np.array([0.0, 0.02, 0.04]),
            rpm=np.array([900.0, 920.0, 950.0]),
            load=np.array([0.15, 0.16, 0.18]),
            throttle=np.array([0.12, 0.14, 0.17]),
            acceleration_mps2=np.array([0.0, 0.1, 0.2]),
        )
        self.assertIs(trace.validate(), trace)

    def test_validate_rejects_nonmonotonic_or_nonfinite_state_arrays(self) -> None:
        trace = VehicleStateTrace(
            time_s=np.array([0.0, 0.04, 0.02]),
            rpm=np.array([900.0, np.nan, 950.0]),
            load=np.array([0.15, 0.16, 0.18]),
            throttle=np.array([0.12, 0.14, 0.17]),
            acceleration_mps2=np.array([0.0, 0.1, 0.2]),
        )
        with self.assertRaisesRegex(ValueError, "time_s.*strictly increasing"):
            trace.validate()

    def test_validate_rejects_negative_rpm(self) -> None:
        trace = VehicleStateTrace(
            time_s=np.array([0.0, 0.02]), rpm=np.array([900.0, -1.0]),
            load=np.array([0.15, 0.16]), throttle=np.array([0.12, 0.14]),
            acceleration_mps2=np.array([0.0, 0.1]),
        )
        with self.assertRaisesRegex(ValueError, "rpm must be >= 0"):
            trace.validate()

    def test_validate_rejects_load_or_throttle_outside_unit_interval(self) -> None:
        for field, values in (("load", np.array([0.2, 1.01])), ("throttle", np.array([-0.01, 0.2]))):
            with self.subTest(field=field):
                trace = VehicleStateTrace(
                    time_s=np.array([0.0, 0.02]), rpm=np.array([900.0, 920.0]),
                    load=values if field == "load" else np.array([0.15, 0.16]),
                    throttle=values if field == "throttle" else np.array([0.12, 0.14]),
                    acceleration_mps2=np.array([0.0, 0.1]),
                )
                with self.assertRaisesRegex(ValueError, rf"{field} must be in \[0, 1\]"):
                    trace.validate()


class SourceRenderContractsTests(unittest.TestCase):
    def test_validate_accepts_finite_stereo_pressure_and_named_stereo_stems(self) -> None:
        render = SourceRender(
            pressure=np.zeros((4, 2), dtype=np.float64),
            stems={"exhaust": np.ones((4, 2), dtype=np.float64)},
            diagnostics={"vehicle_id": "ferrari_458"},
        )
        self.assertIs(render.validate(), render)

    def test_validate_rejects_nonfinite_or_nonstereo_pressure_and_stems(self) -> None:
        render = SourceRender(
            pressure=np.array([[0.0], [np.nan]], dtype=np.float64),
            stems={"exhaust": np.zeros((2, 1), dtype=np.float64)},
            diagnostics={},
        )
        with self.assertRaisesRegex(ValueError, r"pressure.*\[N, 2\]"):
            render.validate()


class AcousticIdentityV015SourceModelTests(unittest.TestCase):
    def test_public_api_exposes_three_independent_renderers(self) -> None:
        for name in RENDERER_NAMES:
            with self.subTest(name=name):
                self.assertTrue(hasattr(identity_v015, name), f"missing public renderer {name}")
                self.assertTrue(callable(getattr(identity_v015, name, None)))

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_each_renderer_is_deterministic_and_validates_the_shared_contract(self) -> None:
        trace = _trace()
        for name in RENDERER_NAMES:
            with self.subTest(name=name):
                renderer = getattr(identity_v015, name)
                first = renderer(trace)
                second = renderer(trace)
                self.assertIs(first.validate(), first)
                np.testing.assert_array_equal(first.pressure, second.pressure)
                self.assertEqual(set(first.stems), set(second.stems))
                for stem_name in first.stems:
                    np.testing.assert_array_equal(first.stems[stem_name], second.stems[stem_name])

        invalid = _trace()
        invalid = VehicleStateTrace(
            time_s=invalid.time_s,
            rpm=-invalid.rpm,
            load=invalid.load,
            throttle=invalid.throttle,
            acceleration_mps2=invalid.acceleration_mps2,
        )
        for name in RENDERER_NAMES:
            with self.subTest(invalid=name):
                with self.assertRaisesRegex(ValueError, "rpm must be >= 0"):
                    getattr(identity_v015, name)(invalid)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_renderers_accept_contract_valid_short_traces(self) -> None:
        for duration_s in (0.001, 0.05, 0.1, 0.499):
            trace = _trace(duration_s=duration_s)
            expected_samples = int(round(duration_s * 48000.0)) + 1
            for name in RENDERER_NAMES:
                with self.subTest(duration_s=duration_s, name=name):
                    render = getattr(identity_v015, name)(trace)
                    self.assertEqual(render.pressure.shape, (expected_samples, 2))
                    self.assertIs(render.validate(), render)
                    _assert_finite_diagnostics(self, render.diagnostics)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_zero_rpm_is_silent_with_finite_diagnostics_for_every_model(self) -> None:
        silent = _trace(rpm=0.0, load=0.9, throttle=0.9, duration_s=0.1)
        for name in RENDERER_NAMES:
            with self.subTest(name=name):
                render = getattr(identity_v015, name)(silent)
                self.assertTrue(np.array_equal(render.pressure, np.zeros_like(render.pressure)))
                for stem in render.stems.values():
                    self.assertTrue(np.array_equal(stem, np.zeros_like(stem)))
                _assert_finite_diagnostics(self, render.diagnostics)
        rx7 = identity_v015.render_rx7_fd(silent)
        self.assertEqual(rx7.diagnostics["narrowband_integer_share_of_integer_plus_half"], 0.0)
        self.assertEqual(rx7.diagnostics["narrowband_half_share_of_integer_plus_half"], 0.0)
        hellcat = identity_v015.render_hellcat(silent)
        self.assertEqual(hellcat.diagnostics["bank_interval_variation_s"], 0.0)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_ferrari_has_regular_alternating_bank_events_and_impulse_metallic_stem(self) -> None:
        render = identity_v015.render_ferrari_458(_trace(rpm=5000.0))
        self.assertTrue({"left_bank", "right_bank", "metallic"} <= set(render.stems))
        self.assertEqual(render.diagnostics["event_order_direction"], "forward")
        self.assertEqual(render.diagnostics["whole_engine_interval_degrees"], 90.0)
        self.assertGreater(render.diagnostics["event_count"], 10)
        self.assertEqual(render.diagnostics["metallic_model"], "impulse_driven_damped_resonator")
        self.assertGreater(render.diagnostics["metallic_impulse_count"], 10)
        self.assertGreater(_rms(render.stems["left_bank"]), 0.0)
        self.assertGreater(_rms(render.stems["right_bank"]), 0.0)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_ferrari_metallic_and_pressure_are_invariant_to_trace_time_origin(self) -> None:
        base = _trace(rpm=5000.0, load=0.7, duration_s=0.2)
        shifted = VehicleStateTrace(
            time_s=base.time_s + 0.00137,
            rpm=base.rpm.copy(),
            load=base.load.copy(),
            throttle=base.throttle.copy(),
            acceleration_mps2=base.acceleration_mps2.copy(),
        )
        original = identity_v015.render_ferrari_458(base)
        offset = identity_v015.render_ferrari_458(shifted)
        np.testing.assert_allclose(original.stems["metallic"], offset.stems["metallic"], rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(original.pressure, offset.pressure, rtol=0.0, atol=1e-12)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_ferrari_metallic_impulse_launches_a_nonzero_decaying_resonator_tail(self) -> None:
        render = identity_v015.render_ferrari_458(_trace(rpm=60.0, load=0.7, duration_s=0.1))
        early = render.stems["metallic"][:960]
        late = render.stems["metallic"][3360:4320]
        self.assertGreater(_rms(early), 0.0)
        self.assertGreater(_rms(early), 10.0 * _rms(late))

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_ferrari_high_frequency_energy_grows_with_rpm_without_normalization(self) -> None:
        low = identity_v015.render_ferrari_458(_trace(rpm=3000.0, load=0.7))
        high = identity_v015.render_ferrari_458(_trace(rpm=8000.0, load=0.7))
        low_fraction = _high_frequency_fraction(low.pressure, 48000)
        high_fraction = _high_frequency_fraction(high.pressure, 48000)
        self.assertGreaterEqual(high_fraction / low_fraction, 1.35)
        self.assertLessEqual(high_fraction / low_fraction, 8.0)
        self.assertGreaterEqual(low_fraction, 0.02)
        self.assertLessEqual(high_fraction, 0.35)
        self.assertLessEqual(abs(_relative_db(high.pressure, low.pressure)), 1.5)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_ferrari_rms_stays_bounded_from_idle_to_redline_without_output_normalization(self) -> None:
        renders = [identity_v015.render_ferrari_458(_trace(rpm=rpm, load=0.7)) for rpm in (900.0, 3000.0, 8000.0)]
        levels = [20.0 * np.log10(_rms(render.pressure)) for render in renders]
        self.assertLessEqual(max(levels) - min(levels), 1.5)
        self.assertGreater(_rms(renders[0].stems["left_bank"] + renders[0].stems["right_bank"]), 0.0)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_hellcat_keeps_irregular_banks_and_independent_loaded_blower(self) -> None:
        high = identity_v015.render_hellcat(_trace(rpm=4200.0, load=0.85, throttle=0.85))
        low = identity_v015.render_hellcat(_trace(rpm=4200.0, load=0.20, throttle=0.20))
        self.assertTrue({"exhaust", "blower", "mechanical", "intake"} <= set(high.stems))
        self.assertEqual(high.diagnostics["bank_timing"], "cross_plane_irregular")
        self.assertGreater(high.diagnostics["bank_interval_variation_s"], 0.0)
        self.assertGreater(high.diagnostics["blower_frequency_hz"], 0.0)
        self.assertGreater(high.diagnostics["blower_energy"], low.diagnostics["blower_energy"] * 3.0)
        mix_without_blower = high.pressure - high.stems["blower"]
        self.assertGreater(_rms(mix_without_blower), 0.0)
        self.assertGreater(_rms(high.stems["mechanical"]), 0.0)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_hellcat_exhaust_contains_independent_irregular_bank_waveforms(self) -> None:
        render = identity_v015.render_hellcat(_trace(rpm=4200.0, load=0.85, throttle=0.85))
        if not {"exhaust_left_bank", "exhaust_right_bank"} <= set(render.stems):
            self.fail("Hellcat exhaust must expose independent bank waveforms")
        left = render.stems["exhaust_left_bank"][:, 0]
        right = render.stems["exhaust_right_bank"][:, 0]
        self.assertGreater(_rms(left), 0.0)
        self.assertGreater(_rms(right), 0.0)
        self.assertLess(abs(float(np.corrcoef(left, right)[0, 1])), 0.85)
        self.assertTrue(np.allclose(render.stems["exhaust"], render.stems["exhaust_left_bank"] + render.stems["exhaust_right_bank"]))

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_hellcat_blower_has_shaft_lobe_and_upper_families_with_audible_stem_balance(self) -> None:
        render = identity_v015.render_hellcat(_trace(rpm=4200.0, load=0.85, throttle=0.85))
        expected_orders = np.array((2.36, 11.8, 23.6))
        families = render.diagnostics.get("blower_order_families")
        self.assertIsNotNone(families)
        if families is None:
            return
        self.assertTrue(np.allclose(families, expected_orders))
        engine_hz = 4200.0 / 60.0
        for order in expected_orders:
            self.assertGreater(_narrowband_energy(render.stems["blower"], 48000, order * engine_hz), 1.0)
        self.assertGreaterEqual(_relative_db(render.stems["blower"], render.stems["exhaust"]), -16.0)
        self.assertLessEqual(_relative_db(render.stems["blower"], render.stems["exhaust"]), -5.0)
        self.assertGreater(_relative_db(render.stems["mechanical"], render.stems["exhaust"]), -32.0)
        self.assertGreater(_relative_db(render.stems["intake"], render.stems["exhaust"]), -32.0)
        self.assertEqual(render.diagnostics.get("mechanical_model"), "belt_compressor_valvetrain_texture")

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_hellcat_casing_texture_tracks_engine_phase_instead_of_wall_clock(self) -> None:
        idle = identity_v015.render_hellcat(_trace(rpm=850.0, load=0.7))
        loaded = identity_v015.render_hellcat(_trace(rpm=6000.0, load=0.7))
        self.assertIn("casing", idle.stems)
        self.assertIn("casing", loaded.stems)
        correlation = abs(float(np.corrcoef(idle.stems["casing"][:, 0], loaded.stems["casing"][:, 0])[0, 1]))
        self.assertLess(correlation, 0.95)
        self.assertEqual(idle.diagnostics.get("casing_model"), "rpm_phase_coupled_casing_orders")

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_rx7_uses_phase_offset_rotary_events_and_stateful_turbo_lift(self) -> None:
        accelerating_time = np.linspace(0.0, 1.2, 121)
        accelerating = VehicleStateTrace(
            time_s=accelerating_time,
            rpm=np.linspace(2800.0, 6800.0, accelerating_time.size),
            load=np.linspace(0.2, 0.9, accelerating_time.size),
            throttle=np.linspace(0.2, 0.9, accelerating_time.size),
            acceleration_mps2=np.full(accelerating_time.size, 2.0),
        )
        render = identity_v015.render_rx7_fd(accelerating)
        self.assertTrue({"rotary", "turbo", "turbine", "lift"} <= set(render.stems))
        self.assertNotIn("firing_order", render.diagnostics)
        self.assertEqual(render.diagnostics["rotary_event_model"], "two_phase_offset_rotary_trains")
        self.assertGreater(render.diagnostics["rotary_event_count"], 10)
        self.assertGreater(render.diagnostics["turbo_state_end"], render.diagnostics["turbo_state_start"])
        self.assertGreater(render.diagnostics["secondary_spool_peak"], 0.0)
        self.assertGreater(render.diagnostics["secondary_engagement_time_s"], 0.0)

        lift_time = np.linspace(0.0, 1.0, 101)
        lift = VehicleStateTrace(
            time_s=lift_time,
            rpm=np.full(lift_time.size, 5200.0),
            load=np.r_[np.full(50, 0.85), np.full(51, 0.12)],
            throttle=np.r_[np.full(50, 0.85), np.full(51, 0.05)],
            acceleration_mps2=np.r_[np.full(50, 1.0), np.full(51, -1.0)],
        )
        lift_render = identity_v015.render_rx7_fd(lift)
        self.assertGreater(lift_render.diagnostics["lift_state_peak"], 0.0)
        self.assertGreater(_rms(lift_render.stems["lift"][26000:36000]), 0.0)
        self.assertGreaterEqual(_relative_db(lift_render.stems["lift"][26000:36000], lift_render.stems["rotary"][26000:36000]), -24.0)
        self.assertLessEqual(_relative_db(lift_render.stems["lift"][26000:36000], lift_render.stems["rotary"][26000:36000]), -6.0)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_rx7_housing_resonance_is_event_and_engine_phase_coupled(self) -> None:
        idle = identity_v015.render_rx7_fd(_trace(rpm=950.0, load=0.7))
        loaded = identity_v015.render_rx7_fd(_trace(rpm=7000.0, load=0.7))
        correlation = abs(float(np.corrcoef(idle.stems["rotor_housing"][:, 0], loaded.stems["rotor_housing"][:, 0])[0, 1]))
        self.assertLess(correlation, 0.95)
        self.assertEqual(
            idle.diagnostics.get("rotor_housing_model"),
            "event_excited_phase_coupled_housing_resonances",
        )

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_rx7_constant_state_favors_integer_orders_over_half_order_leakage(self) -> None:
        render = identity_v015.render_rx7_fd(_trace(rpm=6000.0, load=0.7))
        integer, half = _order_metrics(render.pressure, 48000, 100.0)
        self.assertGreaterEqual(integer, 0.58)
        self.assertLessEqual(half, 0.15)
        self.assertAlmostEqual(render.diagnostics["narrowband_integer_share_of_integer_plus_half"], integer, places=3)
        self.assertAlmostEqual(render.diagnostics["narrowband_half_share_of_integer_plus_half"], half, places=3)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_rx7_source_diagnostics_name_their_narrowband_denominator_explicitly(self) -> None:
        diagnostics = identity_v015.render_rx7_fd(_trace(rpm=6000.0, load=0.7)).diagnostics
        self.assertNotIn("integer_order_concentration", diagnostics)
        self.assertNotIn("half_order_leakage", diagnostics)
        self.assertIn("narrowband_integer_share_of_integer_plus_half", diagnostics)
        self.assertIn("narrowband_half_share_of_integer_plus_half", diagnostics)
        self.assertTrue(np.isfinite(diagnostics["narrowband_integer_share_of_integer_plus_half"]))
        self.assertTrue(np.isfinite(diagnostics["narrowband_half_share_of_integer_plus_half"]))

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_rx7_event_rate_is_two_phase_offset_events_per_eccentric_shaft_revolution(self) -> None:
        render = identity_v015.render_rx7_fd(_trace(rpm=6000.0, load=0.7))
        expected_events = 2.0 * 6000.0 / 60.0
        self.assertAlmostEqual(render.diagnostics["rotary_event_rate_hz"], expected_events, delta=2.0)
        self.assertLessEqual(render.diagnostics["rotary_event_count"], 205)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_rx7_acceleration_stem_balance_keeps_turbo_and_turbine_audible(self) -> None:
        time_s = np.linspace(0.0, 1.2, 121)
        trace = VehicleStateTrace(
            time_s=time_s,
            rpm=np.linspace(2800.0, 6800.0, time_s.size),
            load=np.linspace(0.2, 0.9, time_s.size),
            throttle=np.linspace(0.2, 0.9, time_s.size),
            acceleration_mps2=np.full(time_s.size, 2.0),
        )
        render = identity_v015.render_rx7_fd(trace)
        self.assertGreaterEqual(_relative_db(render.stems["turbo"], render.stems["rotary"]), -18.0)
        self.assertLessEqual(_relative_db(render.stems["turbo"], render.stems["rotary"]), -6.0)
        self.assertGreaterEqual(_relative_db(render.stems["turbine"], render.stems["rotary"]), -24.0)
        self.assertLessEqual(_relative_db(render.stems["turbine"], render.stems["rotary"]), -10.0)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_models_are_not_scalar_gain_copies(self) -> None:
        trace = _trace(rpm=4800.0, load=0.7)
        renders = [getattr(identity_v015, name)(trace).pressure for name in RENDERER_NAMES]
        for index, left in enumerate(renders):
            for right in renders[index + 1:]:
                self.assertLess(_unit_rms_correlation(left, right), 0.85)

    def test_correlation_gate_rejects_an_inverted_scalar_copy(self) -> None:
        waveform = np.column_stack((np.arange(1.0, 33.0), np.arange(1.0, 33.0)))
        self.assertEqual(_unit_rms_correlation(waveform, -waveform), 1.0)

    @unittest.skipUnless(RENDERERS_PRESENT, "source renderers missing")
    def test_source_modules_do_not_share_an_excitation_or_import_each_other(self) -> None:
        sources = V015 / "sources"
        self.assertEqual({path.name for path in sources.glob("*_source.py")}, SOURCE_MODULES)
        for path in sources.glob("*_source.py"):
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                imported = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.extend(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.append(node.module)
                self.assertFalse(any("source" in name and path.stem not in name for name in imported), imported)
                self.assertFalse(any("excitation" in name or "base" in name for name in imported), imported)


class LowFrequencyBodyTests(unittest.TestCase):
    @staticmethod
    def _impulse_render() -> SourceRender:
        pressure = np.zeros((4800, 2), dtype=np.float64)
        pressure[100] = (1.0, 0.8)
        return SourceRender(
            pressure=pressure,
            stems={
                "exhaust": pressure.copy(),
                "left_bank": pressure.copy(),
                "right_bank": pressure.copy(),
                "rotary": pressure.copy(),
                "metallic": pressure.copy(),
                "mechanical": pressure.copy(),
                "turbine": pressure.copy(),
            },
            diagnostics={"vehicle_id": "test", "scope": "synthetic; uncalibrated; not OEM reproduction"},
        )

    def test_three_named_components_preserve_original_stems_and_sum_exactly_into_pressure(self) -> None:
        source = self._impulse_render()
        components = ("engine_body", "exhaust_pressure", "mechanical_weight")
        for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
            with self.subTest(vehicle_id=vehicle_id):
                render = identity_v015.apply_low_frequency_body(source, vehicle_id)
                added = sum((render.stems[name] for name in components), np.zeros_like(source.pressure))
                for name, original in source.stems.items():
                    np.testing.assert_array_equal(render.stems[name], original)
                np.testing.assert_array_equal(render.stems["low_frequency_body"], added)
                np.testing.assert_array_equal(render.pressure, source.pressure + added)
                for name in components:
                    self.assertGreater(float(np.max(np.abs(render.stems[name][100:]))), 0.0)
                    self.assertTrue(np.array_equal(render.stems[name][:100], np.zeros_like(render.stems[name][:100])))
                    self.assertIn(f"{name}_modes_hz", render.diagnostics)
                    self.assertGreater(render.diagnostics[f"{name}_energy"], 0.0)

    def test_causal_body_preserves_source_stems_and_has_a_stable_resonant_tail(self) -> None:
        source = self._impulse_render()
        for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd"):
            with self.subTest(vehicle_id=vehicle_id):
                render = identity_v015.apply_low_frequency_body(source, vehicle_id)
                self.assertIs(render.validate(), render)
                np.testing.assert_array_equal(render.stems["exhaust"], source.stems["exhaust"])
                body = render.stems["low_frequency_body"]
                self.assertTrue(np.array_equal(body[:100], np.zeros_like(body[:100])))
                self.assertGreater(float(np.max(np.abs(body[100:]))), 0.0)
                self.assertGreater(float(np.max(np.abs(body[101:500]))), float(np.max(np.abs(body[-500:]))) * 10.0)
                np.testing.assert_allclose(render.pressure, source.pressure + body, rtol=0.0, atol=0.0)
                self.assertEqual(render.diagnostics["low_frequency_body_scope"], "synthetic; uncalibrated; not OEM reproduction")

    def test_body_profiles_have_nonflat_different_transfer_and_hellcat_is_deepest(self) -> None:
        source = self._impulse_render()
        bodies = {
            vehicle_id: identity_v015.apply_low_frequency_body(source, vehicle_id).stems["low_frequency_body"][:, 0]
            for vehicle_id in ("ferrari_458", "hellcat", "rx7_fd")
        }

        def energy_in_band(signal: np.ndarray, low_hz: float, high_hz: float) -> float:
            spectrum = np.square(np.abs(np.fft.rfft(signal)))
            frequencies = np.fft.rfftfreq(signal.size, 1.0 / 48000.0)
            return float(spectrum[(frequencies >= low_hz) & (frequencies <= high_hz)].sum())

        deep = {vehicle_id: energy_in_band(body, 40.0, 120.0) for vehicle_id, body in bodies.items()}
        for vehicle_id, body in bodies.items():
            with self.subTest(vehicle_id=vehicle_id):
                self.assertGreater(energy_in_band(body, 40.0, 200.0), 0.0)
                self.assertNotAlmostEqual(deep[vehicle_id], energy_in_band(body, 120.0, 200.0), places=8)
        self.assertGreater(deep["hellcat"], deep["ferrari_458"] * 1.5)
        self.assertGreater(deep["hellcat"], deep["rx7_fd"] * 1.2)
        self.assertFalse(np.array_equal(bodies["ferrari_458"], bodies["rx7_fd"]))
        with self.assertRaisesRegex(ValueError, "vehicle_id"):
            identity_v015.apply_low_frequency_body(source, "unknown")

    def test_zero_input_stays_zero(self) -> None:
        silence = np.zeros((16, 2))
        source = SourceRender(
            pressure=silence, stems={"exhaust": silence.copy(), "mechanical": silence.copy()}, diagnostics={}
        )
        render = identity_v015.apply_low_frequency_body(source, "hellcat")
        self.assertTrue(np.array_equal(render.pressure, source.pressure))
        self.assertTrue(np.array_equal(render.stems["low_frequency_body"], source.pressure))
        for name in ("engine_body", "exhaust_pressure", "mechanical_weight"):
            self.assertTrue(np.array_equal(render.stems[name], source.pressure))


class LoudnessManagerTests(unittest.TestCase):
    @staticmethod
    def _tone(amplitude: float, frequency_hz: float = 100.0) -> np.ndarray:
        time_s = np.arange(48000, dtype=np.float64) / 48000.0
        mono = amplitude * np.sin(2.0 * np.pi * frequency_hz * time_s)
        return np.column_stack((mono, 0.8 * mono))

    def test_loudness_metrics_are_k_weighted_finite_and_report_signal_health(self) -> None:
        audio = self._tone(0.1)
        metrics = identity_v015.measure_loudness(audio, 48000)
        self.assertTrue(np.isfinite(metrics.integrated_lufs))
        self.assertAlmostEqual(metrics.rms_dbfs, 20.0 * np.log10(np.sqrt(np.mean(np.square(audio)))), places=9)
        self.assertAlmostEqual(metrics.peak_dbfs, -20.0, places=9)
        self.assertGreater(metrics.crest_factor_db, 2.5)
        self.assertEqual(metrics.clipping_count, 0)

    def test_integrated_lufs_sums_channel_energy_before_gating(self) -> None:
        stereo = self._tone(0.1)
        mono = stereo[:, 0]
        mono_metrics = identity_v015.measure_loudness(mono)
        stereo_metrics = identity_v015.measure_loudness(np.column_stack((mono, mono)))
        self.assertAlmostEqual(stereo_metrics.integrated_lufs - mono_metrics.integrated_lufs, 10.0 * np.log10(2.0), places=9)

    def test_bundle_loudness_uses_one_fixed_gain_preserves_order_and_observes_peak_cap(self) -> None:
        segments = {
            "idle": self._tone(0.020, 70.0),
            "cruise": self._tone(0.035, 90.0),
            "acceleration": self._tone(0.055, 120.0),
            "lift": self._tone(0.025, 150.0),
            "full_pull": self._tone(0.080, 180.0),
        }
        managed = identity_v015.manage_bundle_loudness(segments)
        repeated = identity_v015.manage_bundle_loudness(segments)
        self.assertFalse(managed.headroom_limited)
        self.assertAlmostEqual(managed.bundle_metrics.integrated_lufs, -18.0, delta=1.0)
        self.assertLessEqual(managed.bundle_metrics.peak_dbfs, -1.0 + 1e-12)
        self.assertEqual(managed.bundle_metrics.clipping_count, 0)
        for name, original in segments.items():
            with self.subTest(name=name):
                np.testing.assert_allclose(managed.segments[name], original * managed.gain_linear, rtol=0.0, atol=0.0)
                np.testing.assert_array_equal(managed.segments[name], repeated.segments[name])
        input_rms = [np.sqrt(np.mean(np.square(value))) for value in segments.values()]
        output_rms = [np.sqrt(np.mean(np.square(managed.segments[name]))) for name in segments]
        np.testing.assert_allclose(np.asarray(output_rms) / output_rms[0], np.asarray(input_rms) / input_rms[0], rtol=1e-12)

    def test_peak_limited_bundle_reports_the_cap_without_distortion(self) -> None:
        impulse = np.zeros((48000, 2), dtype=np.float64)
        impulse[::12000] = (0.99, 0.75)
        managed = identity_v015.manage_bundle_loudness(
            {name: impulse for name in ("idle", "cruise", "acceleration", "lift", "full_pull")}
        )
        self.assertTrue(managed.headroom_limited)
        self.assertAlmostEqual(managed.bundle_metrics.peak_dbfs, -1.0, places=9)
        self.assertEqual(managed.bundle_metrics.clipping_count, 0)
        np.testing.assert_allclose(managed.segments["idle"], impulse * managed.gain_linear, rtol=0.0, atol=0.0)


class EngineIdentityMetricsTests(unittest.TestCase):
    @staticmethod
    def _sweep_trace() -> VehicleStateTrace:
        time_s = np.linspace(0.0, 1.2, 121)
        return VehicleStateTrace(
            time_s=time_s,
            rpm=np.linspace(3000.0, 8000.0, time_s.size),
            load=np.linspace(0.25, 0.9, time_s.size),
            throttle=np.linspace(0.25, 0.9, time_s.size),
            acceleration_mps2=np.full(time_s.size, 2.0),
        )

    def test_public_metrics_api_and_silence_are_finite_json_data(self) -> None:
        silent = SourceRender(
            pressure=np.zeros((256, 2)), stems={"blower": np.zeros((256, 2))}, diagnostics={}
        )
        metrics = identity_v015.compute_engine_identity_metrics("hellcat", silent, _trace(duration_s=0.1))
        self.assertEqual(metrics["spectral_centroid_hz"], 0.0)
        self.assertEqual(metrics["high_energy_fraction_gt_1200hz"], 0.0)
        self.assertEqual(metrics["hellcat"]["blower_stem_energy"], 0.0)
        json.dumps(metrics, allow_nan=False)

    def test_spectral_metrics_and_order_map_are_measured_from_audio(self) -> None:
        sample_rate_hz = 48000
        time_s = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
        mono = 0.8 * np.sin(2.0 * np.pi * 100.0 * time_s) + 0.2 * np.sin(2.0 * np.pi * 2400.0 * time_s)
        audio = np.column_stack((mono, mono))
        trace = _trace(rpm=6000.0)
        render = SourceRender(pressure=audio, stems={"rotary": audio.copy()}, diagnostics={})
        metrics = identity_v015.compute_engine_identity_metrics("rx7_fd", render, trace)
        spectrum = np.square(np.abs(np.fft.rfft(mono * np.hanning(mono.size))))
        frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
        expected_centroid = float(np.sum(frequencies * spectrum) / np.sum(spectrum))
        expected_low = float(spectrum[(frequencies >= 40.0) & (frequencies <= 400.0)].sum() / spectrum.sum())
        self.assertAlmostEqual(metrics["spectral_centroid_hz"], expected_centroid, places=6)
        self.assertAlmostEqual(metrics["low_energy_fraction_40_400hz"], expected_low, places=6)
        order_map = identity_v015.compute_order_map(audio, trace)
        self.assertGreater(order_map.order_energy[np.argmax(order_map.order_energy)], 0.0)
        self.assertLess(abs(order_map.orders[np.argmax(order_map.order_energy)] - 1.0), 0.15)

    def test_vehicle_metrics_use_real_stems_and_state_timeline(self) -> None:
        trace = self._sweep_trace()
        ferrari = identity_v015.render_ferrari_458(trace)
        hellcat = identity_v015.render_hellcat(trace)
        rx7 = identity_v015.render_rx7_fd(trace)
        ferrari_metrics = identity_v015.compute_engine_identity_metrics("ferrari_458", ferrari, trace)
        hellcat_metrics = identity_v015.compute_engine_identity_metrics("hellcat", hellcat, trace)
        rx7_metrics = identity_v015.compute_engine_identity_metrics("rx7_fd", rx7, trace)
        self.assertAlmostEqual(
            hellcat_metrics["hellcat"]["blower_stem_energy"], float(np.sum(np.square(hellcat.stems["blower"]))), places=9
        )
        self.assertGreater(ferrari_metrics["ferrari"]["high_frequency_ratio"], 0.0)
        self.assertGreater(hellcat_metrics["hellcat"]["blower_load_correlation"], 0.80)
        self.assertGreaterEqual(rx7_metrics["rx7"]["integer_order_concentration"], 0.0)
        self.assertGreaterEqual(rx7_metrics["rx7"]["turbo_primary_rise"], 0.0)
        self.assertGreaterEqual(rx7_metrics["rx7"]["turbo_secondary_rise"], 0.0)

    def test_same_state_comparison_rejects_scalar_and_inverted_copies(self) -> None:
        trace = _trace(rpm=4800.0, load=0.7)
        base = identity_v015.render_ferrari_458(trace).pressure
        comparisons = identity_v015.compare_identity_renders({"base": base, "gain": 3.0 * base, "inverted": -base}, trace)
        for pair in comparisons["pairs"].values():
            self.assertAlmostEqual(pair["absolute_waveform_correlation"], 1.0, places=10)
            self.assertAlmostEqual(pair["log_order_cosine_distance"], 0.0, places=10)
            self.assertFalse(pair["passes"])
        json.dumps(comparisons, allow_nan=False)

    def test_headless_plot_writers_emit_nonempty_pngs(self) -> None:
        trace = _trace(rpm=6000.0, duration_s=0.25)
        render = identity_v015.render_rx7_fd(trace)
        order_map = identity_v015.compute_order_map(render.pressure, trace)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "requested" / "plots"
            spectrogram = identity_v015.write_spectrogram(root / "spectrogram.png", render.pressure)
            order_png = identity_v015.write_order_map(root / "order_map.png", order_map)
            self.assertTrue(spectrogram.is_file() and spectrogram.stat().st_size > 0)
            self.assertTrue(order_png.is_file() and order_png.stat().st_size > 0)


class EngineIdentityMetricsReviewRegressionTests(unittest.TestCase):
    @staticmethod
    def _sweep_trace() -> VehicleStateTrace:
        time_s = np.linspace(0.0, 1.2, 121)
        return VehicleStateTrace(
            time_s=time_s,
            rpm=np.linspace(3000.0, 8000.0, time_s.size),
            load=np.linspace(0.25, 0.9, time_s.size),
            throttle=np.linspace(0.25, 0.9, time_s.size),
            acceleration_mps2=np.full(time_s.size, 2.0),
        )

    def test_stereo_summed_spectrum_order_map_and_full_stereo_correlation_keep_right_channel(self) -> None:
        sample_rate_hz = 48000
        time_s = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
        tone = np.sin(2.0 * np.pi * 100.0 * time_s)
        right_only = np.column_stack((np.zeros_like(tone), tone))
        trace = _trace(rpm=6000.0)
        render = SourceRender(pressure=right_only, stems={"rotary": right_only.copy()}, diagnostics={})
        metrics = identity_v015.compute_engine_identity_metrics("rx7_fd", render, trace)
        self.assertAlmostEqual(metrics["spectral_centroid_hz"], 100.0, delta=0.1)
        order_map = identity_v015.compute_order_map(right_only, trace)
        self.assertLess(abs(order_map.orders[np.argmax(order_map.order_energy)] - 1.0), 0.15)
        left_only = np.column_stack((tone, np.zeros_like(tone)))
        pair = identity_v015.compare_identity_renders({"left": left_only, "right": right_only}, trace)["pairs"]["left__right"]
        self.assertAlmostEqual(pair["absolute_waveform_correlation"], 0.0, places=12)

    def test_db_centered_order_shape_rejects_disjoint_one_hot_and_scalar_copies(self) -> None:
        left = np.array((1.0, 0.0, 0.0, 0.0))
        right = np.array((0.0, 1.0, 0.0, 0.0))
        self.assertAlmostEqual(metric_impl._log_order_cosine_distance(left, left), 0.0, places=12)
        self.assertGreater(metric_impl._log_order_cosine_distance(left, right), 0.20)

    def test_real_cross_vehicle_fixed_separation_gates_pass_after_stereo_db_measurement(self) -> None:
        trace = _trace(rpm=4800.0, load=0.7)
        renders = {
            "ferrari_458": identity_v015.render_ferrari_458(trace),
            "hellcat": identity_v015.render_hellcat(trace),
            "rx7_fd": identity_v015.render_rx7_fd(trace),
        }
        comparison = identity_v015.compare_identity_renders(renders, trace)
        self.assertTrue(comparison["passes"])
        for pair in comparison["pairs"].values():
            self.assertLess(pair["absolute_waveform_correlation"], 0.85)
            self.assertGreater(pair["log_order_cosine_distance"], 0.20)

    def test_rx_order_fractions_include_quarter_order_energy_in_the_denominator(self) -> None:
        order_map = identity_v015.OrderMap(
            time_s=np.array((0.0,)),
            orders=np.array((1.0, 1.25, 1.5)),
            power=np.array(((4.0, 4.0, 2.0),)),
            engine_hz=np.array((100.0,)),
        )
        integer, half = metric_impl._integer_half_order_fractions(order_map)
        self.assertAlmostEqual(integer, 0.4, places=12)
        self.assertAlmostEqual(half, 0.2, places=12)

    def test_rx_constant_state_full_pressure_qualifies_order_shape_and_stem_balance(self) -> None:
        trace = _trace(rpm=6000.0, load=0.7, throttle=0.7)
        render = identity_v015.render_rx7_fd(trace)
        metrics = identity_v015.compute_engine_identity_metrics("rx7_fd", render, trace)["rx7"]
        self.assertGreaterEqual(metrics["integer_order_concentration"], 0.58)
        self.assertLessEqual(metrics["half_order_leakage"], 0.15)
        self.assertGreaterEqual(_relative_db(render.stems["turbo"], render.stems["rotary"]), -18.0)
        self.assertLessEqual(_relative_db(render.stems["turbo"], render.stems["rotary"]), -6.0)
        self.assertGreaterEqual(_relative_db(render.stems["turbine"], render.stems["rotary"]), -24.0)
        self.assertLessEqual(_relative_db(render.stems["turbine"], render.stems["rotary"]), -10.0)

    def test_turbo_transition_and_lift_boundary_are_actual_stem_finite_json_metrics(self) -> None:
        time_s = np.linspace(0.0, 1.0, 101)
        sweep = VehicleStateTrace(
            time_s=time_s,
            rpm=np.linspace(3000.0, 8000.0, time_s.size),
            load=np.linspace(0.25, 0.9, time_s.size),
            throttle=np.linspace(0.25, 0.9, time_s.size),
            acceleration_mps2=np.full(time_s.size, 2.0),
        )
        render = identity_v015.render_rx7_fd(sweep)
        active = identity_v015.compute_engine_identity_metrics("rx7_fd", render, sweep)["rx7"]["turbo_transition_s"]
        zeroed = SourceRender(
            pressure=render.pressure,
            stems={**render.stems, "turbo": np.zeros_like(render.stems["turbo"]), "turbine": np.zeros_like(render.stems["turbine"])},
            diagnostics=render.diagnostics,
        )
        self.assertGreater(active, 0.0)
        self.assertEqual(identity_v015.compute_engine_identity_metrics("rx7_fd", zeroed, sweep)["rx7"]["turbo_transition_s"], 0.0)
        final_drop = VehicleStateTrace(
            time_s=time_s,
            rpm=np.full(time_s.size, 5200.0),
            load=np.full(time_s.size, 0.8),
            throttle=np.r_[np.full(time_s.size - 1, 0.8), 0.0],
            acceleration_mps2=np.zeros(time_s.size),
        )
        finite = identity_v015.compute_engine_identity_metrics("rx7_fd", identity_v015.render_rx7_fd(final_drop), final_drop)
        json.dumps(finite, allow_nan=False)

    def test_ferrari_sweep_reports_relative_accuracy_and_rejects_wrong_order_chirps(self) -> None:
        trace = self._sweep_trace()
        ferrari = identity_v015.compute_engine_identity_metrics("ferrari_458", identity_v015.render_ferrari_458(trace), trace)
        self.assertLessEqual(ferrari["ferrari"]["order_sweep_relative_error"], 0.10)
        sample_rate_hz = 48000
        count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
        samples = np.arange(count, dtype=np.float64) / sample_rate_hz
        rpm = np.interp(samples, trace.time_s, trace.rpm)
        phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
        for wrong_order in (1.55, 2.45):
            chirp = np.sin(2.0 * np.pi * wrong_order * phase)
            correlation, error = metric_impl._order_sweep_tracking(np.column_stack((chirp, chirp)), trace, sample_rate_hz, 2.0)
            self.assertGreater(correlation, 0.98)
            self.assertGreater(error, 0.10)


class SourceToPtrBundleLoudnessIntegrationTests(unittest.TestCase):
    _renderers = {
        "ferrari_458": identity_v015.render_ferrari_458,
        "hellcat": identity_v015.render_hellcat,
        "rx7_fd": identity_v015.render_rx7_fd,
    }
    _constant_rpm = {
        "ferrari_458": (1100.0, 4500.0, 8000.0),
        "hellcat": (850.0, 3000.0, 6000.0),
        "rx7_fd": (950.0, 4000.0, 7000.0),
    }
    _clips = ("idle", "cruise", "acceleration", "lift", "full_pull")
    _duration_s = 0.55

    def _ptr_render(self, vehicle_id: str, trace: VehicleStateTrace) -> np.ndarray:
        source = self._renderers[vehicle_id](trace)
        body = identity_v015.apply_low_frequency_body(source, vehicle_id)
        return _edge_fade(_apply_frozen_ptr(body.pressure))

    def test_formal_vehicle_bundles_keep_every_clip_audible_with_one_gain(self) -> None:
        for vehicle_id in self._renderers:
            raw = {
                name: self._ptr_render(vehicle_id, _scenario_trace(vehicle_id, name, self._duration_s))
                for name in self._clips
            }
            managed = identity_v015.manage_bundle_loudness(raw)
            if not managed.headroom_limited:
                self.assertAlmostEqual(managed.bundle_metrics.integrated_lufs, -18.0, delta=1.0)
            self.assertLessEqual(managed.bundle_metrics.peak_dbfs, -1.0 + 1e-12)
            self.assertEqual(managed.bundle_metrics.clipping_count, 0)
            for name in self._clips:
                with self.subTest(vehicle_id=vehicle_id, name=name):
                    metrics = managed.segment_metrics[name]
                    self.assertTrue(np.isfinite(metrics.integrated_lufs))
                    self.assertGreaterEqual(metrics.integrated_lufs, -30.0)
                    self.assertLessEqual(metrics.peak_dbfs, -1.0 + 1e-12)
                    self.assertEqual(metrics.clipping_count, 0)
                    self.assertAlmostEqual(_rms(managed.segments[name]) / _rms(raw[name]), managed.gain_linear, places=12)

    def test_same_load_rpm_probes_change_timbre_without_gross_level_spread(self) -> None:
        for vehicle_id, rpms in self._constant_rpm.items():
            metrics = []
            for rpm in rpms:
                audio = self._ptr_render(vehicle_id, _trace(rpm=rpm, load=0.7, throttle=0.7, duration_s=self._duration_s))
                metrics.append(identity_v015.measure_loudness(audio))
            loudness = [item.integrated_lufs for item in metrics]
            rms = [item.rms_dbfs for item in metrics]
            with self.subTest(vehicle_id=vehicle_id, metric="LUFS"):
                self.assertTrue(np.all(np.isfinite(loudness)))
                self.assertLessEqual(max(loudness) - min(loudness), 4.0)
            with self.subTest(vehicle_id=vehicle_id, metric="RMS"):
                self.assertLessEqual(max(rms) - min(rms), 4.0)


class IdentityV02PublicationTests(unittest.TestCase):
    def test_subthreshold_segment_loudness_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "integrated_lufs must be finite and measured"):
            _loudness_dict(LoudnessMetrics(float("-inf"), -75.0, -65.0, 10.0, 0))

    def test_short_publication_emits_reopenable_bundle_metrics_and_common_ab_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary) / "identity_v02"
            publication = identity_v015.publish_identity_v02(output_root, scenario_duration_s=0.55)
            self.assertEqual(publication["output_root"], str(output_root))
            self.assertEqual(publication["identity_v02_root"], str(output_root / "identity_v02"))
            self.assertFalse(any((output_root / vehicle).exists() for vehicle in ("ferrari_458", "hellcat", "rx7_fd")))
            self.assertTrue(publication["comparison"]["passes"])
            self.assertEqual(publication["comparison"]["audio_domain"], "final_pcm_after_ptr_edge_and_bundle_gain")
            self.assertEqual(publication["comparison"]["comparison_scope"], "same_trace_unit_rms_analysis_only")
            self.assertEqual(set(publication["vehicles"]), {"ferrari_458", "hellcat", "rx7_fd"})
            expected_clips = {"idle", "cruise", "acceleration", "lift", "full_pull"}
            for vehicle, details in publication["vehicles"].items():
                vehicle_root = output_root / "identity_v02" / vehicle
                self.assertEqual(set(details["clips"]), expected_clips)
                self.assertEqual(len({clip["loudness_gain_db"] for clip in details["clips"].values()}), 1)
                for name in expected_clips:
                    wav_path = vehicle_root / f"{name}.wav"
                    self.assertTrue(wav_path.is_file() and wav_path.stat().st_size > 44)
                    with wave.open(str(wav_path), "rb") as reopened:
                        self.assertEqual((reopened.getframerate(), reopened.getnchannels(), reopened.getsampwidth()), (48000, 2, 3))
                        self.assertGreater(reopened.getnframes(), 0)
                metrics_path = vehicle_root / "identity_metrics.json"
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                json.dumps(metrics, allow_nan=False)
                self.assertTrue(metrics["health"]["passes"])
                self.assertEqual(metrics["provenance"]["parameter_class"], "C/synthetic")
                self.assertIn("runtime_ptr_adapter_sha256", metrics["ptr_provenance"])
                self.assertEqual(metrics["vehicle_metrics_domain"], "final_pcm_after_ptr_edge_and_bundle_gain")
                bundle = metrics["bundle"]
                self.assertTrue(bundle["headroom_limited"] or abs(bundle["metrics"]["integrated_lufs"] + 18.0) <= 1.0)
                self.assertEqual(set(metrics["clips"]), expected_clips)
                for name, clip in metrics["clips"].items():
                    self.assertEqual(clip["loudness_gain_db"], bundle["gain_db"])
                    self.assertTrue(np.isfinite(clip["loudness"]["integrated_lufs"]), name)
                    self.assertGreaterEqual(clip["loudness"]["integrated_lufs"], -30.0, name)
                    self.assertTrue(clip["health"]["passes"], name)
                for image_name in ("spectrogram.png", "order_map.png"):
                    self.assertGreater((vehicle_root / image_name).stat().st_size, 0)
            for report_name in ("identity_comparison_report.md", "S12_Engine_Acoustic_Identity_v015_Report.md", "S12_Engine_Acoustic_Identity_v015_Final_Report.md"):
                report = (output_root / report_name).read_text(encoding="utf-8")
                self.assertIn("HUMAN_BLIND_AUDITION_PENDING_JOVI", report)
                self.assertIn("not OEM reproduction", report)
                for section in ("Research evidence and caveats", "Independent model structures", "C/synthetic provenance", "Low-frequency components", "Loudness results", "Vehicle metrics", "Artifact links", "Same-state final-PCM A/B", "Frozen PTR boundary", "Perceptual candidate answers", "Limitations"):
                    self.assertIn(f"## {section}", report)
                self.assertIn("identity_v02/ferrari_458/full_pull.wav", report)
            manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
            expected_artifacts = {
                f"identity_v02/{vehicle}/{name}"
                for vehicle in ("ferrari_458", "hellcat", "rx7_fd")
                for name in ("idle.wav", "cruise.wav", "acceleration.wav", "lift.wav", "full_pull.wav", "spectrogram.png", "order_map.png", "identity_metrics.json")
            } | {"comparison.json", "identity_comparison_report.md", "S12_Engine_Acoustic_Identity_v015_Report.md", "S12_Engine_Acoustic_Identity_v015_Final_Report.md"}
            self.assertEqual(set(manifest["files"]), expected_artifacts)
            for relative_path, digest in manifest["files"].items():
                self.assertEqual(digest, hashlib.sha256((output_root / relative_path).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
