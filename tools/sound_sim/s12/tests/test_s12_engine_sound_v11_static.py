"""Static contract checks for the v1.1 provenance foundation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
VEHICLES = (
    "hellcat_2022_stock",
    "gtr_r35_2007_stock",
    "c63_w204_facelift_stock",
    "supra_jza80_rz_stock",
    "rx7_fd_1991_stock",
    "lexus_lfa_stock",
    "ferrari_458_stock",
    "aventador_lp700_stock",
)
PACKAGE_FILES = {
    "README.md",
    "profile.json",
    "reference_manifest.json",
    "acoustic_targets.json",
    "afterfire_profile.json",
}
REQUIRED_PROVENANCE_FIELDS = {"source_level", "source_type", "source_url", "claim"}
ALLOWED_SOURCE_LEVELS = {"A", "B", "C", "pending", "synthetic_assumption"}


class S12EngineSoundV11StaticTests(unittest.TestCase):
    def test_vehicle_folders_have_exactly_the_required_files(self) -> None:
        vehicle_root = V11 / "vehicles"
        self.assertTrue(vehicle_root.is_dir())
        self.assertEqual({path.name for path in vehicle_root.iterdir() if path.is_dir()}, set(VEHICLES))
        for vehicle_id in VEHICLES:
            package = vehicle_root / vehicle_id
            expected = PACKAGE_FILES | {f"S12_{vehicle_id}_v11.slx"}
            self.assertEqual({path.name for path in package.iterdir() if path.is_file()}, expected)

    def test_all_payloads_have_complete_synthetic_provenance(self) -> None:
        for vehicle_id in VEHICLES:
            for name in ("profile.json", "reference_manifest.json", "acoustic_targets.json", "afterfire_profile.json"):
                payload = load_json(vehicle_id, name)
                provenance = payload["provenance"]
                self.assertEqual(set(provenance), REQUIRED_PROVENANCE_FIELDS)
                self.assertIn(provenance["source_level"], ALLOWED_SOURCE_LEVELS)
                if provenance["source_level"] in {"A", "B"}:
                    self.assertTrue(provenance["source_url"].startswith("https://"))
                else:
                    self.assertEqual(provenance["source_url"], "")
                self.assertNotIn("real", provenance["claim"].lower())
                self.assertNotIn("oem", provenance["claim"].lower())
                if "scope" in payload:
                    self.assertTrue(payload["scope"]["synthetic"])
                    self.assertTrue(payload["scope"]["uncalibrated"])
                    self.assertTrue(payload["scope"]["offline"])
                    self.assertEqual(payload["scope"]["oem_status"], "non-OEM")
                    self.assertEqual(payload["scope"]["perspective"], "exterior-rear")
                    self.assertEqual(payload["scope"]["orientation"], "stock-oriented")

    def test_payload_identities_are_identical_within_each_vehicle_package(self) -> None:
        for vehicle_id in VEHICLES:
            identities = []
            for name in ("profile.json", "reference_manifest.json", "acoustic_targets.json", "afterfire_profile.json"):
                payload = load_json(vehicle_id, name)
                self.assertEqual(payload["vehicle_id"], vehicle_id)
                identities.append(payload["vehicle_identity"])
            self.assertTrue(all(identity == identities[0] for identity in identities[1:]))

    def test_validator_declares_required_rejection_identifiers(self) -> None:
        validator = (V11 / "common" / "s12_v11_validate_vehicle_package.m").read_text(encoding="utf-8")
        for identifier in (
            "S12:EngineSoundV11:Provenance",
            "S12:EngineSoundV11:UnknownField",
            "S12:EngineSoundV11:Identity",
            "S12:EngineSoundV11:SourceLevel",
            "S12:EngineSoundV11:Claim",
        ):
            self.assertIn(identifier, validator)
        self.assertIn('"A", "B", "C", "pending", "synthetic_assumption"', validator)
        self.assertIn('isrow(value) || isempty(value)', validator)


def load_json(vehicle_id: str, name: str) -> dict:
    return json.loads((V11 / "vehicles" / vehicle_id / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
