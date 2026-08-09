"""Static contracts for the S12 Engine Identity Acoustic Model v0.14."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
V12 = ROOT / "playground_v12"
COMMON = V12 / "common"
SCHEMA_PATH = COMMON / "schemas" / "engine_identity_profile_v04.schema.json"
VEHICLES = V12 / "vehicles"

EXPECTED = {
    "hellcat_2022_stock": ("supercharged_cross_plane_v8", 8, 6500),
    "ferrari_458_stock": ("naturally_aspirated_flat_plane_v8", 8, 9000),
    "rx7_fd_1991_stock": ("twin_rotor_turbo", 2, 8000),
}
PARAMETER_GROUPS = (
    "firing_character",
    "order_profile",
    "harmonic_profile",
    "transient_profile",
    "mechanical_noise_profile",
    "turbo_or_supercharger_profile",
    "acoustic_color_profile",
)


class EngineIdentityProfileContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_three_identity_profiles_are_synthetic_and_complete(self) -> None:
        validator = jsonschema.Draft202012Validator(self.schema)
        for profile_id, (engine_type, cylinder_count, rpm_limit) in EXPECTED.items():
            with self.subTest(profile_id=profile_id):
                payload = json.loads(
                    (VEHICLES / profile_id / "engine_identity_profile.json").read_text(
                        encoding="utf-8"
                    )
                )
                validator.validate(payload)
                self.assertEqual(payload["schema_version"], "s12-engine-identity-profile-0.4")
                self.assertTrue(payload["synthetic"])
                self.assertEqual(payload["engine_type"]["value"], engine_type)
                self.assertEqual(payload["cylinder_count"]["value"], cylinder_count)
                self.assertEqual(payload["rpm_limit"]["value"], rpm_limit)
                self._assert_synthetic_parameter(payload["engine_type"])
                self._assert_synthetic_parameter(payload["cylinder_count"])
                self._assert_synthetic_parameter(payload["combustion_type"])
                self._assert_synthetic_parameter(payload["rpm_limit"])
                for group in PARAMETER_GROUPS:
                    for parameter in payload[group].values():
                        self._assert_synthetic_parameter(parameter)

    def test_schema_rejects_missing_parameter_provenance(self) -> None:
        payload = json.loads(
            (VEHICLES / "hellcat_2022_stock" / "engine_identity_profile.json").read_text(
                encoding="utf-8"
            )
        )
        payload["turbo_or_supercharger_profile"]["whine_gain"].pop("source_level")
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(payload)

    @staticmethod
    def _assert_synthetic_parameter(parameter: dict) -> None:
        assert parameter["source_level"] == "C"
        assert parameter["source"] == "synthetic"
        assert parameter["verification_state"] == "synthetic_assumption"
        assert parameter["source_url"] == ""


if __name__ == "__main__":
    unittest.main()
