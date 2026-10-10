import json
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

import jsonschema


ROOT = Path(__file__).resolve().parents[5]
PACKAGE = ROOT / "tools" / "sound_sim" / "s12" / "runtime_validation"
sys.path.insert(0, str(PACKAGE))

from contracts import validate_motion_sample, validate_vehicle_profile  # noqa: E402
from golden_export import export_golden_bundle  # noqa: E402
from profiles import load_builtin_profiles  # noqa: E402


CONTRACT_ROOT = ROOT / "contracts" / "runtime"
BASE_SHA = "29b50961d9628f835e7172b797380ccb36a7f38d"


def valid_sample(**overrides):
    sample = {
        "schema_version": "s12.motion-sample.v1",
        "source": {"id": "replay-01", "kind": "replay"},
        "sequence": 1,
        "clock_domain": "monotonic",
        "measurement_time_ns": 1_000_000_000,
        "received_time_ns": 1_010_000_000,
        "speed_mps": 12.5,
        "longitudinal_acceleration_mps2": 0.4,
        "direction": "forward",
        "valid": True,
        "quality": {"score": 0.95, "uncertainty_mps": 0.2},
        "data_age_ms": 10,
    }
    sample.update(overrides)
    return sample


class RuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.motion_schema = json.loads(
            (CONTRACT_ROOT / "motion-sample-v1.schema.json").read_text(encoding="utf-8")
        )
        cls.profile_schema = json.loads(
            (CONTRACT_ROOT / "vehicle-profile-v1.schema.json").read_text(encoding="utf-8")
        )

    def test_motion_contract_accepts_a_fresh_synthetic_sample(self):
        sample = valid_sample()
        jsonschema.Draft202012Validator(self.motion_schema).validate(sample)
        accepted = validate_motion_sample(sample, now_monotonic_ns=1_020_000_000)
        self.assertEqual(accepted, sample)

    def test_motion_contract_rejects_missing_extra_nonfinite_and_invalid_values(self):
        validator = jsonschema.Draft202012Validator(self.motion_schema)
        invalid_samples = (
            {key: value for key, value in valid_sample().items() if key != "sequence"},
            {**valid_sample(), "unexpected": "field"},
            valid_sample(speed_mps=-0.1),
        )
        for sample in invalid_samples:
            with self.subTest(sample=sample):
                self.assertTrue(list(validator.iter_errors(sample)))

        for sample in (
            valid_sample(speed_mps=float("nan")),
            valid_sample(longitudinal_acceleration_mps2=float("inf")),
        ):
            with self.subTest(sample=sample):
                with self.assertRaisesRegex(ValueError, "finite"):
                    validate_motion_sample(sample, now_monotonic_ns=1_020_000_000)

    def test_motion_validation_fails_closed_on_invalid_stale_or_nonmonotonic_samples(self):
        with self.assertRaisesRegex(ValueError, "valid"):
            validate_motion_sample(valid_sample(valid=False), now_monotonic_ns=1_020_000_000)
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_motion_sample(valid_sample(), now_monotonic_ns=2_000_000_000, max_age_ms=500)

        previous = validate_motion_sample(valid_sample(), now_monotonic_ns=1_020_000_000)
        out_of_order = valid_sample(
            sequence=2,
            measurement_time_ns=999_000_000,
            received_time_ns=1_009_000_000,
        )
        with self.assertRaisesRegex(ValueError, "monotonic"):
            validate_motion_sample(
                out_of_order,
                now_monotonic_ns=1_020_000_000,
                previous=previous,
            )

    def test_only_experimental_synthetic_profiles_are_valid(self):
        profiles = load_builtin_profiles()
        self.assertEqual({profile["profile_id"] for profile in profiles}, {
            "experimental-rotary-synth",
            "experimental-v8-synth",
        })
        for profile in profiles:
            with self.subTest(profile=profile["profile_id"]):
                jsonschema.Draft202012Validator(self.profile_schema).validate(profile)
                self.assertEqual(validate_vehicle_profile(profile), profile)
                self.assertEqual(profile["provenance"]["kind"], "synthetic")
                self.assertEqual(profile["qualification"], "EXPERIMENTAL_NOT_QUALIFIED")

        tampered = deepcopy(profiles[0])
        tampered["state_mapping"]["idle_rpm"] += 1.0
        with self.assertRaisesRegex(ValueError, "profile hash"):
            validate_vehicle_profile(tampered)

        rejected_status = {**profiles[0], "qualification": "HUMAN_ACCEPTED"}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.profile_schema).validate(rejected_status)

        rejected_feature = {
            **profiles[0],
            "supported_features": ["can_bus_vehicle_identity"],
        }
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.profile_schema).validate(rejected_feature)


class GoldenExportTests(unittest.TestCase):
    def test_golden_export_is_deterministic_and_binds_all_synthetic_receipts(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = export_golden_bundle(Path(first_dir), source_revision=BASE_SHA, seed=20260924)
            second = export_golden_bundle(Path(second_dir), source_revision=BASE_SHA, seed=20260924)

            def files(root):
                return {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                }

            self.assertEqual(files(Path(first_dir)), files(Path(second_dir)))
            self.assertEqual(first["source_commit"], BASE_SHA)
            self.assertEqual(first["seed"], 20260924)
            self.assertEqual(first["sample_rate_hz"], 48000)
            self.assertEqual(first["control_rate_hz"], 100)
            self.assertEqual(
                {case["scenario_id"] for case in first["cases"]},
                {"idle", "cruise", "acceleration", "lift_coast", "shift"},
            )
            self.assertEqual(len(first["cases"]), 10)
            self.assertTrue(all(case["pcm_sha256"] and case["motion_sha256"] for case in first["cases"]))
            self.assertEqual(first["qualification"], "EXPERIMENTAL_SYNTHETIC_NOT_QUALIFIED")
            self.assertEqual(first["comparison_tolerances"], {
                "virtual_rpm_abs": 0.001,
                "load_abs": 0.000001,
                "pcm_sample_abs": 0.00005,
                "pcm_rms_abs": 0.000005,
                "events": "exact_sequence_and_sample_index",
            })
            shift_cases = [case for case in first["cases"] if case["scenario_id"] == "shift"]
            self.assertTrue(all(case["shift_events"] > 0 for case in shift_cases))


if __name__ == "__main__":
    unittest.main()
