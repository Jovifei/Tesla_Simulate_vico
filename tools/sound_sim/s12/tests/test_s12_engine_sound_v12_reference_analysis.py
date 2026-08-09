"""Executable contracts for the v1.2 reference-analysis boundary."""

from __future__ import annotations

import hashlib
import json
import math
import sys
import unittest
from copy import deepcopy
from pathlib import Path

import jsonschema
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
V12 = ROOT / "playground_v12"
REFERENCE_ANALYSIS = V12 / "common" / "reference_analysis"
SCHEMAS = V12 / "common" / "schemas"
sys.path.insert(0, str(REFERENCE_ANALYSIS))


def source_record() -> dict:
    url = "https://example.invalid/stock-exterior-rear-reference"
    return {
        "url": url,
        "publisher": "Test fixture publisher",
        "source_url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
    }


def vehicle_identity() -> dict:
    return {
        "make": "Fixture Motors",
        "model": "Reference Coupe",
        "model_year": 2022,
        "market": "US",
        "trim": "Stock",
    }


def research_boundary() -> dict:
    return {
        "raw_media_root": r"E:\Claude_allow\Download\tesla-sound-research-v12",
    }


def r1_reference(rpm_source: str = "tachometer_trace") -> dict:
    return {
        "schema_version": "s12-engine-sound-v12-reference-1",
        "reference_id": "fixture-r1",
        "vehicle_id": "fixture_vehicle_stock",
        "quality_class": "R1",
        "inventory_use": "calibration",
        "vehicle": vehicle_identity(),
        "source": source_record(),
        "clip_window": {"start_s": 0.0, "end_s": 1.0},
        "rpm_evidence": {
            "source": rpm_source,
            "samples": [
                {"time_s": 0.0, "rpm": 1200.0},
                {"time_s": 0.5, "rpm": 2400.0},
                {"time_s": 1.0, "rpm": 3600.0},
            ],
        },
        "stock_evidence": {
            "is_stock": True,
            "description": "Exact stock trim is shown and declared by the publisher.",
            "evidence_url": source_record()["url"],
        },
        "perspective": "exterior_rear",
        "research_boundary": research_boundary(),
    }


def r2_reference() -> dict:
    value = r1_reference()
    value["reference_id"] = "fixture-r2"
    value["quality_class"] = "R2"
    value["inventory_use"] = "listening_only"
    value["perspective"] = "exterior_side"
    value.pop("rpm_evidence")
    value.pop("stock_evidence")
    return value


def r3_reference() -> dict:
    value = r2_reference()
    value["reference_id"] = "fixture-r3"
    value["quality_class"] = "R3"
    value["inventory_use"] = "rejected"
    value["rejection_reason"] = "Music masks the exhaust throughout the clip."
    value.pop("perspective")
    return value


def synthetic_order_sweep(
    sample_rate_hz: int = 48000,
    duration_s: float = 1.0,
    modulation_hz: float = 4.0,
):
    sample_count = round(sample_rate_hz * duration_s)
    time_s = np.arange(sample_count, dtype=np.float64) / sample_rate_hz
    rpm = 1200.0 + 2400.0 * time_s
    revolutions = np.cumsum(rpm / 60.0) / sample_rate_hz
    envelope = 0.75 + 0.25 * np.sin(2.0 * math.pi * modulation_hz * time_s)
    pcm = envelope * 0.20 * np.sin(2.0 * math.pi * 2.0 * revolutions)
    pcm += 0.05 * np.sin(2.0 * math.pi * 4.0 * revolutions + 0.2)
    pcm += 0.015 * np.sin(2.0 * math.pi * 900.0 * time_s)
    trace = [
        {"time_s": 0.0, "rpm": 1200.0},
        {"time_s": 0.5 * duration_s, "rpm": 2400.0},
        {"time_s": duration_s, "rpm": 3600.0},
    ]
    events = [
        {"time_s": 0.60, "kind": "upshift_bark", "energy": 0.10, "cluster_id": "a"},
        {"time_s": 0.72, "kind": "overrun_crackle", "energy": 0.08, "cluster_id": "b"},
        {"time_s": 0.78, "kind": "overrun_crackle", "energy": 0.04, "cluster_id": "b"},
    ]
    return pcm, trace, events


def rehash_analysis(analysis: dict) -> dict:
    body = {key: value for key, value in analysis.items() if key != "analysis_sha256"}
    analysis["analysis_sha256"] = hashlib.sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return analysis


def synthetic_resonant_sweep(
    sample_rate_hz: int = 48000,
    duration_s: float = 1.0,
    resonance_hz: float = 2300.0,
):
    sample_count = round(sample_rate_hz * duration_s)
    time_s = np.arange(sample_count, dtype=np.float64) / sample_rate_hz
    rpm = 1200.0 + 2400.0 * time_s
    revolutions = np.cumsum(rpm / 60.0) / sample_rate_hz
    strong_orders = 0.8 * np.sin(2.0 * math.pi * 2.0 * revolutions)
    strong_orders += 0.4 * np.sin(2.0 * math.pi * 4.0 * revolutions + 0.3)

    rng = np.random.default_rng(123456)
    noise_spectrum = np.fft.rfft(rng.standard_normal(sample_count))
    frequencies_hz = np.fft.rfftfreq(sample_count, d=1.0 / sample_rate_hz)
    resonant_envelope = np.exp(
        -0.5 * ((frequencies_hz - resonance_hz) / 180.0) ** 2
    )
    resonant_noise = np.fft.irfft(noise_spectrum * resonant_envelope, sample_count)
    resonant_noise /= max(float(np.std(resonant_noise)), np.finfo(float).eps)
    pcm = strong_orders + 0.35 * resonant_noise
    trace = [
        {"time_s": 0.0, "rpm": 1200.0},
        {"time_s": 0.5, "rpm": 2400.0},
        {"time_s": duration_s, "rpm": 3600.0},
    ]
    return pcm, trace


class S12V12ReferenceAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from s12_reference_analysis import (  # pylint: disable=import-error
            ReferenceContractError,
            analyze_reference,
            build_acoustic_target,
            canonical_json,
            validate_reference,
        )

        cls.ReferenceContractError = ReferenceContractError
        cls.analyze_reference = staticmethod(analyze_reference)
        cls.build_acoustic_target = staticmethod(build_acoustic_target)
        cls.canonical_json = staticmethod(canonical_json)
        cls.validate_reference = staticmethod(validate_reference)
        cls.reference_schema = json.loads(
            (SCHEMAS / "reference_manifest_v12.schema.json").read_text(encoding="utf-8")
        )
        cls.target_schema = json.loads(
            (SCHEMAS / "acoustic_target_v12.schema.json").read_text(encoding="utf-8")
        )

    def analyze_fixture(
        self,
        reference: dict | None = None,
        sample_rate_hz: int = 48000,
    ) -> dict:
        pcm, _trace, events = synthetic_order_sweep(sample_rate_hz)
        return self.analyze_reference(
            r1_reference() if reference is None else reference,
            pcm,
            sample_rate_hz,
            events,
        )

    def target_fixture(
        self,
        reference: dict | None = None,
        sample_rate_hz: int = 48000,
    ) -> dict:
        pcm, _trace, events = synthetic_order_sweep(sample_rate_hz)
        return self.build_acoustic_target(
            r1_reference() if reference is None else reference,
            pcm,
            sample_rate_hz,
            events,
        )

    def test_json_schemas_accept_valid_r1_r2_and_r3_inventory_records(self) -> None:
        validator = jsonschema.Draft202012Validator(
            self.reference_schema,
            format_checker=jsonschema.FormatChecker(),
        )
        for reference in (r1_reference(), r2_reference(), r3_reference()):
            self.assertEqual(list(validator.iter_errors(reference)), [])
            self.assertEqual(
                self.validate_reference(reference)["quality_class"],
                reference["quality_class"],
            )

    def test_r1_requires_exact_vehicle_identity_and_explicit_stock_proof(self) -> None:
        for field in ("make", "model", "model_year", "market", "trim"):
            reference = r1_reference()
            reference["vehicle"].pop(field)
            with self.subTest(field=field):
                with self.assertRaises(self.ReferenceContractError):
                    self.validate_reference(reference)
        reference = r1_reference()
        reference["stock_evidence"].pop("evidence_url")
        with self.assertRaisesRegex(self.ReferenceContractError, "stock|schema"):
            self.validate_reference(reference)

    def test_r1_requires_trace_or_three_ordered_anchors_covering_clip(self) -> None:
        reference = r1_reference("rpm_anchors")
        reference["rpm_evidence"]["samples"] = reference["rpm_evidence"]["samples"][:2]
        with self.assertRaisesRegex(self.ReferenceContractError, "RPM|schema"):
            self.validate_reference(reference)
        reference = r1_reference()
        reference["rpm_evidence"]["samples"][0]["time_s"] = 0.1
        with self.assertRaisesRegex(self.ReferenceContractError, "cover"):
            self.validate_reference(reference)
        reference = r1_reference()
        reference["rpm_evidence"]["samples"][2]["time_s"] = 0.4
        with self.assertRaisesRegex(self.ReferenceContractError, "strictly increasing"):
            self.validate_reference(reference)

    def test_schema_version_publisher_rpm_source_and_unknown_fields_are_strict(self) -> None:
        mutations = []
        bad_version = r1_reference()
        bad_version["schema_version"] = "v12-ish"
        mutations.append(bad_version)
        missing_publisher = r1_reference()
        missing_publisher["source"].pop("publisher")
        mutations.append(missing_publisher)
        bad_rpm_source = r1_reference()
        bad_rpm_source["rpm_evidence"]["source"] = "guessed"
        mutations.append(bad_rpm_source)
        unknown = r1_reference()
        unknown["surprise"] = True
        mutations.append(unknown)
        for reference in mutations:
            with self.subTest(reference=reference):
                with self.assertRaises(self.ReferenceContractError):
                    self.validate_reference(reference)

    def test_r2_and_r3_cannot_be_analyzed_or_build_targets(self) -> None:
        pcm, _trace, events = synthetic_order_sweep()
        for reference in (r2_reference(), r3_reference()):
            with self.subTest(quality=reference["quality_class"]):
                with self.assertRaisesRegex(self.ReferenceContractError, "R1"):
                    self.analyze_reference(reference, pcm, 48000, events)
                with self.assertRaisesRegex(self.ReferenceContractError, "R1"):
                    self.build_acoustic_target(reference, pcm, 48000, events)

    def test_analysis_requires_sample_rate_capable_of_16khz_measurement(self) -> None:
        pcm, _trace, events = synthetic_order_sweep(16000)
        with self.assertRaisesRegex(self.ReferenceContractError, "32000"):
            self.analyze_reference(r1_reference(), pcm, 16000, events)

    def test_analysis_is_windowed_dynamic_crank_angle_map_and_deterministic(self) -> None:
        first = self.analyze_fixture()
        second = self.analyze_fixture(reference=deepcopy(r1_reference()))
        self.assertEqual(self.canonical_json(first), self.canonical_json(second))

        method = first["analysis_method"]
        self.assertEqual(method["domain"], "windowed_dynamic_crank_angle_order_map")
        self.assertEqual(method["cycle_degrees"], 720)
        self.assertEqual(method["order_range"], [0.5, 18.0])
        self.assertEqual(method["order_step"], 0.5)
        self.assertFalse(method["ordinary_average_rpm_fft"])
        self.assertEqual(method["source_sample_rate_hz"], 48000)
        self.assertGreater(method["window_duration_s"], method["hop_duration_s"])
        self.assertGreater(method["envelope_block_duration_s"], 0)
        self.assertEqual(
            method["formant_tracking"],
            "time_windowed_local_rpm_order_ridge_exclusion",
        )
        self.assertGreater(method["formant_persistence_fraction"], 0)

        metrics = first["derived_metrics"]
        expected_orders = [0.5 * index for index in range(1, 37)]
        self.assertEqual(metrics["orders"], expected_orders)
        self.assertEqual(len(metrics["order_amplitudes"]), 36)
        self.assertEqual(len(metrics["order_phases_rad"]), 36)
        order_map = metrics["order_map"]
        self.assertEqual(order_map["orders"], expected_orders)
        self.assertGreater(len(order_map["frames"]), 2)
        self.assertEqual(order_map["frames"][0]["start_time_s"], 0.0)
        self.assertEqual(order_map["frames"][-1]["end_time_s"], 1.0)
        center_times = [frame["center_time_s"] for frame in order_map["frames"]]
        self.assertTrue(all(a < b for a, b in zip(center_times, center_times[1:])))
        for frame in order_map["frames"]:
            self.assertEqual(len(frame["amplitudes"]), 36)
            self.assertEqual(len(frame["phases_rad"]), 36)
            expected_rpm = 1200.0 + 2400.0 * frame["center_time_s"]
            self.assertAlmostEqual(frame["center_rpm"], expected_rpm, delta=1.0)
        order_two_index = expected_orders.index(2.0)
        order_one_index = expected_orders.index(1.0)
        dominant_frames = sum(
            frame["amplitudes"][order_two_index] > frame["amplitudes"][order_one_index]
            for frame in order_map["frames"]
        )
        self.assertGreaterEqual(dominant_frames, len(order_map["frames"]) - 1)

    def test_global_metric_shape_and_formant_spacing_are_portable(self) -> None:
        analysis = self.analyze_fixture()
        metrics = analysis["derived_metrics"]
        self.assertEqual(
            metrics["fixed_bands_hz"],
            [[20, 120], [120, 500], [500, 2000], [2000, 8000], [8000, 16000]],
        )
        self.assertEqual(len(metrics["band_energy_ratios"]), 5)
        self.assertAlmostEqual(sum(metrics["band_energy_ratios"]), 1.0, places=10)
        formants = metrics["formants_hz"]
        self.assertTrue(all(b - a >= 100.0 for a, b in zip(formants, formants[1:])))
        for key in (
            "spectral_centroid_hz",
            "spectral_rolloff_hz",
            "spectral_flatness",
            "modulation_depth",
            "pulse_amplitude_cv",
        ):
            self.assertTrue(math.isfinite(metrics[key]))

    def test_modulation_blocks_are_time_based_across_sample_rates(self) -> None:
        at_32k = self.analyze_fixture(sample_rate_hz=32000)["derived_metrics"]
        at_48k = self.analyze_fixture(sample_rate_hz=48000)["derived_metrics"]
        self.assertAlmostEqual(at_32k["modulation_depth"], at_48k["modulation_depth"], delta=0.01)
        self.assertAlmostEqual(
            at_32k["pulse_amplitude_cv"],
            at_48k["pulse_amplitude_cv"],
            delta=0.01,
        )

    def test_events_must_have_nonnegative_energy_and_lie_inside_clip(self) -> None:
        pcm, _trace, events = synthetic_order_sweep()
        bad_energy = deepcopy(events)
        bad_energy[0]["energy"] = -0.1
        with self.assertRaisesRegex(self.ReferenceContractError, "energy"):
            self.analyze_reference(r1_reference(), pcm, 48000, bad_energy)
        outside = deepcopy(events)
        outside[0]["time_s"] = 1.1
        with self.assertRaisesRegex(self.ReferenceContractError, "clip"):
            self.analyze_reference(r1_reference(), pcm, 48000, outside)

    def test_event_statistics_include_cluster_delay_decay_and_tail(self) -> None:
        statistics = self.analyze_fixture()["derived_metrics"]["afterfire_statistics"]
        self.assertEqual(statistics["event_count"], 2)
        self.assertEqual(statistics["cluster_count"], 1)
        self.assertAlmostEqual(statistics["first_event_delay_s"], 0.72)
        self.assertAlmostEqual(statistics["energy_decay_ratio"], 0.5)
        self.assertAlmostEqual(statistics["tail_duration_s"], 0.06)
        self.assertGreater(statistics["total_energy"], 0)

    def test_recursive_media_safety_rejects_paths_hashes_and_cache_keys(self) -> None:
        bad_payloads = [
            {"audio_path": "secret.wav"},
            {"nested": {"pcm_cache": "bytes"}},
            {"nested": [{"waveform_file": "clip.bin"}]},
            {"raw_content_sha256": "0" * 64},
            {"media_blob": "base64"},
        ]
        for payload in bad_payloads:
            reference = r1_reference()
            reference["source"]["metadata"] = payload
            with self.subTest(payload=payload):
                with self.assertRaises(self.ReferenceContractError):
                    self.validate_reference(reference)
        self.assertEqual(
            self.validate_reference(r1_reference())["research_boundary"],
            research_boundary(),
        )

    def test_target_consumes_valid_dynamic_map_and_schema_rejects_extra_keys(self) -> None:
        reference = r1_reference()
        analysis = self.analyze_fixture(reference)
        target = self.target_fixture(reference)
        jsonschema.Draft202012Validator(self.target_schema).validate(target)
        self.assertEqual(target["reference_quality"], "R1")
        self.assertEqual(target["analysis_sha256"], analysis["analysis_sha256"])
        self.assertEqual(
            target["derived_metrics"]["order_map"],
            analysis["derived_metrics"]["order_map"],
        )
        extra = deepcopy(target)
        extra["derived_metrics"]["unreviewed_metric"] = 1
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.target_schema).validate(extra)

    def test_target_never_accepts_persisted_or_fabricated_analysis_as_pcm(self) -> None:
        analysis = self.analyze_fixture()
        fft_labelled = deepcopy(analysis)
        fft_labelled["analysis_method"]["domain"] = "ordinary_fft"
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(r1_reference(), fft_labelled, 48000, ())
        fabricated = deepcopy(analysis)
        fabricated["derived_metrics"]["order_map"]["frames"] = []
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(r1_reference(), fabricated, 48000, ())

    def test_target_and_analysis_reject_recursive_media_fields(self) -> None:
        analysis = self.analyze_fixture()
        analysis["derived_metrics"]["audio_cache_path"] = "forbidden"
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(r1_reference(), analysis, 48000, ())

    def test_analysis_self_hash_binds_exact_r1_provenance(self) -> None:
        reference = r1_reference()
        analysis = self.analyze_fixture(reference)
        expected_manifest_digest = hashlib.sha256(
            self.canonical_json(reference).encode("utf-8")
        ).hexdigest()
        self.assertEqual(
            analysis["reference_binding"],
            {
                "reference_manifest_sha256": expected_manifest_digest,
            },
        )

    def test_target_rejects_cross_reference_reuse_and_rehashed_forgery(self) -> None:
        original = r1_reference()
        analysis = self.analyze_fixture(original)

        other = deepcopy(original)
        other["vehicle"]["trim"] = "Changed trim"
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(other, analysis, 48000, ())

        forged = deepcopy(analysis)
        forged["reference_binding"]["reference_manifest_sha256"] = "0" * 64
        rehash_analysis(forged)
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(original, forged, 48000, ())

        changed_target = self.target_fixture(other)
        original_target = self.target_fixture(original)
        self.assertNotEqual(
            changed_target["reference_binding"]["reference_manifest_sha256"],
            original_target["reference_binding"]["reference_manifest_sha256"],
        )

    def test_media_policy_rejects_unsafe_string_values_and_non_https_urls(self) -> None:
        unsafe_publishers = (
            "file:///E:/research/reference.wav",
            "data:audio/wav;base64,AAAA",
            r"E:\research\reference.wav",
            "../cache/reference.flac",
            "/tmp/reference.raw",
            r"\\server\share\reference.mp3",
        )
        for publisher in unsafe_publishers:
            reference = r1_reference()
            reference["source"]["publisher"] = publisher
            with self.subTest(publisher=publisher):
                with self.assertRaisesRegex(
                    self.ReferenceContractError, "media|path|URI|value"
                ):
                    self.validate_reference(reference)

        for url in (
            "http://example.invalid/reference",
            "file:///E:/reference.wav",
            "https://example.invalid/reference.wav",
            "https://example.invalid/download?file=reference.wav",
            "https://example.invalid/download?clip=..%2Fcache%2Freference.wav&token=x",
        ):
            reference = r1_reference()
            reference["source"]["url"] = url
            reference["source"]["source_url_sha256"] = hashlib.sha256(
                url.encode("utf-8")
            ).hexdigest()
            with self.subTest(url=url):
                with self.assertRaisesRegex(
                    self.ReferenceContractError, "HTTPS|media|path|URI|value"
                ):
                    self.validate_reference(reference)

    def test_raw_media_root_is_the_only_path_value_exception(self) -> None:
        self.assertEqual(
            self.validate_reference(r1_reference())["research_boundary"],
            research_boundary(),
        )
        reference = r1_reference()
        reference["research_boundary"]["raw_media_root"] = r"E:\other\location"
        with self.assertRaises(self.ReferenceContractError):
            self.validate_reference(reference)

    def test_dynamic_frames_partition_exact_clip_without_gap_or_overlap(self) -> None:
        frames = self.analyze_fixture()["derived_metrics"]["order_map"]["frames"]
        self.assertEqual(frames[0]["start_time_s"], 0.0)
        self.assertEqual(frames[-1]["end_time_s"], 1.0)
        for left, right in zip(frames, frames[1:]):
            self.assertAlmostEqual(left["end_time_s"], right["start_time_s"], places=12)
        for frame in frames:
            self.assertLess(frame["start_time_s"], frame["end_time_s"])
            self.assertGreaterEqual(frame["center_time_s"], frame["start_time_s"])
            self.assertLessEqual(frame["center_time_s"], frame["end_time_s"])

    def test_rehashed_analysis_rejects_inconsistent_global_order_aggregation(self) -> None:
        analysis = self.analyze_fixture()
        analysis["derived_metrics"]["order_amplitudes"][0] += 0.25
        rehash_analysis(analysis)
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(r1_reference(), analysis, 48000, ())

        analysis = self.analyze_fixture()
        analysis["derived_metrics"]["order_phases_rad"][0] += 0.25
        rehash_analysis(analysis)
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(r1_reference(), analysis, 48000, ())

    def test_rehashed_analysis_rejects_band_formant_and_event_inconsistency(self) -> None:
        analysis = self.analyze_fixture()
        analysis["derived_metrics"]["band_energy_ratios"] = [0.2] * 4 + [0.3]
        rehash_analysis(analysis)
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(r1_reference(), analysis, 48000, ())

        analysis = self.analyze_fixture()
        analysis["derived_metrics"]["formants_hz"] = [900.0, 850.0]
        rehash_analysis(analysis)
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(r1_reference(), analysis, 48000, ())

        analysis = self.analyze_fixture()
        analysis["derived_metrics"]["afterfire_statistics"]["event_count"] += 1
        rehash_analysis(analysis)
        with self.assertRaisesRegex(self.ReferenceContractError, "PCM|finite|vector"):
            self.build_acoustic_target(r1_reference(), analysis, 48000, ())

    def test_afterfire_decay_is_reported_for_each_cluster(self) -> None:
        pcm, _trace, events = synthetic_order_sweep()
        events.extend(
            [
                {
                    "time_s": 0.82,
                    "kind": "overrun_crackle",
                    "energy": 0.06,
                    "cluster_id": "c",
                },
                {
                    "time_s": 0.90,
                    "kind": "overrun_crackle",
                    "energy": 0.015,
                    "cluster_id": "c",
                },
            ]
        )
        analysis = self.analyze_reference(r1_reference(), pcm, 48000, events)
        clusters = {
            row["cluster_id"]: row
            for row in analysis["derived_metrics"]["afterfire_statistics"]["clusters"]
        }
        self.assertEqual(
            set(clusters["b"]),
            {
                "cluster_id",
                "event_count",
                "total_energy",
                "start_delay_s",
                "energy_decay_ratio",
                "tail_duration_s",
            },
        )
        self.assertAlmostEqual(clusters["b"]["energy_decay_ratio"], 0.5)
        self.assertAlmostEqual(clusters["c"]["energy_decay_ratio"], 0.25)

    def test_formant_envelope_keeps_broadband_resonance_and_avoids_order_ridges(self) -> None:
        pcm, _trace = synthetic_resonant_sweep()
        analysis = self.analyze_reference(r1_reference(), pcm, 48000)
        formants = analysis["derived_metrics"]["formants_hz"]
        self.assertTrue(any(abs(frequency - 2300.0) <= 150.0 for frequency in formants))

        mean_rpm = 2400.0
        predicted_ridges = [
            (0.5 * index) * mean_rpm / 60.0 for index in range(1, 37)
        ]
        self.assertTrue(
            all(
                min(abs(frequency - ridge) for ridge in predicted_ridges) >= 50.0
                for frequency in formants
            )
        )

    def test_pure_dynamic_order_sweep_does_not_create_a_persistent_formant(self) -> None:
        sample_rate_hz = 48000
        time_s = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
        rpm = 1200.0 + 2400.0 * time_s
        revolutions = np.cumsum(rpm / 60.0) / sample_rate_hz
        pure_order_pcm = 0.20 * np.sin(2.0 * math.pi * 18.0 * revolutions)

        analysis = self.analyze_reference(r1_reference(), pure_order_pcm, sample_rate_hz)
        self.assertEqual(analysis["derived_metrics"]["formants_hz"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
