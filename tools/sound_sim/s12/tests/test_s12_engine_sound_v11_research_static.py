"""Static contracts for honest v1.1 research deliverables.

These checks intentionally validate catalog metadata only. They never fetch or
decode media, so a green result is not audio-analysis evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V11 = ROOT / "playground_v11"
OBSIDIAN = Path(
    os.environ.get(
        "S12_OBSIDIAN_V11_ROOT",
        r"E:\AI_Tools\Obsidian\data\notes-personal\tesla\S12-Engine-Sound-v11",
    )
)
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
REQUIRED_REFERENCE_FIELDS = {
    "reference_id",
    "source_url",
    "source_url_sha256",
    "publisher",
    "source_classification",
    "vehicle_binding",
    "vehicle_binding_state",
    "stock_modified_status",
    "listening_perspective",
    "clip_time_metadata",
    "content_hash_state",
    "licensing_use_boundary",
    "derived_analysis_state",
}
REQUIRED_DOC_MARKERS = (
    "## Official configuration evidence",
    "## Candidate sound references",
    "## Perspective and stock scope",
    "## Expected synthetic acoustic targets",
    "## Shift and afterfire hypotheses",
    "## Gap and tuning log",
    "not measured",
    "pending",
)
C63_FACELIFT_SOURCE = (
    "https://mercedes-benz-publicarchive.com/marsClassic/en/instance/ko/"
    "C-63-AMG-2011---2014.xhtml?oid=189266534"
)


class S12EngineSoundV11ResearchStaticTests(unittest.TestCase):
    def test_manifests_catalog_nonempty_honest_research_references(self) -> None:
        for vehicle_id in VEHICLES:
            manifest = load_manifest(vehicle_id)
            self.assertFalse(manifest["raw_reference_audio_in_git"])
            self.assertEqual(manifest["research_status"], "cataloged_not_acquired")
            self.assertEqual(manifest["analysis_boundary"]["raw_audio_state"], "not_acquired")
            self.assertEqual(manifest["analysis_boundary"]["spectral_order_analysis_state"], "not_analyzed")
            self.assertEqual(manifest["analysis_boundary"]["derived_metrics_state"], "not_analyzed")
            self.assertTrue(manifest["references"])
            self.assertTrue(
                any(
                    reference["source_classification"]
                    == "official_manufacturer_configuration"
                    for reference in manifest["references"]
                )
            )
            self.assertTrue(
                any(
                    reference["source_classification"]
                    == "public_candidate_sound_reference_discovery"
                    for reference in manifest["references"]
                )
            )
            for reference in manifest["references"]:
                self.assertEqual(set(reference), REQUIRED_REFERENCE_FIELDS)
                self.assertTrue(reference["source_url"].startswith("https://"))
                self.assertEqual(
                    reference["source_url_sha256"],
                    url_sha256(reference["source_url"]),
                )
                self.assertEqual(reference["vehicle_binding"], manifest["vehicle_identity"])
                self.assertIn(
                    reference["vehicle_binding_state"],
                    {
                        "identity_verified",
                        "identity_pending",
                        "query_scoped_candidate_not_verified",
                    },
                )
                self.assertIn(
                    reference["stock_modified_status"],
                    {
                        "manufacturer_identity_only",
                        "manufacturer_identity_pending",
                        "unverified_candidate",
                    },
                )
                if (
                    reference["source_classification"]
                    == "official_manufacturer_configuration"
                ):
                    self.assertIn(
                        (
                            reference["vehicle_binding_state"],
                            reference["stock_modified_status"],
                        ),
                        {
                            ("identity_verified", "manufacturer_identity_only"),
                            ("identity_pending", "manufacturer_identity_pending"),
                        },
                    )
                else:
                    self.assertEqual(
                        reference["vehicle_binding_state"],
                        "query_scoped_candidate_not_verified",
                    )
                    self.assertEqual(
                        reference["stock_modified_status"],
                        "unverified_candidate",
                    )
                self.assertIn(
                    reference["listening_perspective"],
                    {"not_applicable", "not_available"},
                )
                self.assertEqual(
                    reference["clip_time_metadata"],
                    {"state": "not_available", "start_s": "", "end_s": ""},
                )
                self.assertEqual(reference["content_hash_state"], "not_acquired")
                self.assertEqual(reference["derived_analysis_state"], "not_analyzed")

    def test_schema_and_validator_require_honest_nonempty_manifests(self) -> None:
        schema = json.loads(
            (V11 / "common" / "schemas" / "vehicle_package.schema.json").read_text(
                encoding="utf-8"
            )
        )
        contract = schema["reference_manifest_contract"]
        self.assertIn("research_status", schema["documents"]["reference_manifest"])
        self.assertIn("analysis_boundary", schema["documents"]["reference_manifest"])
        self.assertEqual(set(contract["reference_fields"]), REQUIRED_REFERENCE_FIELDS)
        self.assertIn("not_acquired", contract["allowed_content_hash_states"])
        self.assertIn("not_analyzed", contract["allowed_derived_analysis_states"])
        self.assertIn("identity_pending", contract["allowed_vehicle_binding_states"])
        validator = (
            V11 / "common" / "s12_v11_validate_vehicle_package.m"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "Reference manifests must catalog at least one honest non-audio source.",
            validator,
        )
        self.assertIn("content_hash_state", validator)
        self.assertNotIn("~isempty(manifest.references)", validator)

    def test_obsidian_research_docs_disclose_pending_measurement_state(self) -> None:
        if not OBSIDIAN.is_dir():
            self.skipTest(
                "external Obsidian vault is unavailable; set S12_OBSIDIAN_V11_ROOT "
                "to run the vault-mirror contract"
            )
        expected = (
            "00-八车型声纹研究与执行计划.md",
            "01-Hellcat.md",
            "02-GT-R-R35.md",
            "03-C63-W204.md",
            "04-Supra-JZA80.md",
            "05-RX-7-FD.md",
            "06-LFA.md",
            "07-Ferrari-458-Italia.md",
            "08-Aventador-LP700.md",
        )
        actual = {path.name for path in OBSIDIAN.iterdir() if path.is_file()}
        self.assertTrue(set(expected).issubset(actual))
        for name in expected:
            content = (OBSIDIAN / name).read_text(encoding="utf-8").lower()
            for marker in REQUIRED_DOC_MARKERS:
                self.assertIn(marker.lower(), content, f"{name} is missing {marker!r}")
            self.assertNotIn("spectrum measured", content)
            self.assertNotIn("order map measured", content)

    def test_vehicle_years_are_structured_and_c63_uses_facelift_source(self) -> None:
        for vehicle_id in VEHICLES:
            identity = load_manifest(vehicle_id)["vehicle_identity"]
            model_year = identity["model_year"]
            if isinstance(model_year, int):
                self.assertGreaterEqual(model_year, 1886)
            else:
                self.assertIsInstance(model_year, list)
                self.assertEqual(len(model_year), 2)
                self.assertTrue(all(isinstance(value, int) for value in model_year))
                self.assertLessEqual(model_year[0], model_year[1])
            self.assertNotEqual(identity["market"], "unspecified")
            self.assertNotEqual(identity["trim"], "unspecified")

        c63 = load_manifest("c63_w204_facelift_stock")
        self.assertEqual(c63["vehicle_identity"]["model_year"], [2011, 2014])
        official = next(
            reference
            for reference in c63["references"]
            if reference["source_classification"]
            == "official_manufacturer_configuration"
        )
        self.assertEqual(official["source_url"], C63_FACELIFT_SOURCE)
        self.assertEqual(
            official["source_url_sha256"], url_sha256(C63_FACELIFT_SOURCE)
        )

    def test_profile_manufacturer_source_matches_official_manifest_source(self) -> None:
        for vehicle_id in VEHICLES:
            profile = json.loads(
                (V11 / "vehicles" / vehicle_id / "profile.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(profile["provenance"]["source_level"], "A", vehicle_id)
            self.assertEqual(
                profile["provenance"]["source_type"], "manufacturer", vehicle_id
            )
            self.assertTrue(
                profile["provenance"]["source_url"].startswith("https://"),
                vehicle_id,
            )
            manifest = load_manifest(vehicle_id)
            official_urls = {
                reference["source_url"]
                for reference in manifest["references"]
                if reference["source_classification"]
                == "official_manufacturer_configuration"
            }
            self.assertIn(
                profile["provenance"]["source_url"], official_urls, vehicle_id
            )
        validator = (
            V11 / "common" / "s12_v11_validate_vehicle_package.m"
        ).read_text(encoding="utf-8")
        self.assertIn("validateProfileManifestSourceLink", validator)
        self.assertIn(
            "Profile A/manufacturer source_url must equal one official manufacturer manifest source_url.",
            validator,
        )
        self.assertIn(
            "Canonical profile provenance must be source level A and manufacturer.",
            validator,
        )
        self.assertNotIn(
            'if string(provenance.source_level) ~= "A" || string(provenance.source_type) ~= "manufacturer"\n    return;',
            validator,
        )
        schema = json.loads(
            (V11 / "common" / "schemas" / "vehicle_package.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            schema["profile_provenance_contract"],
            {"source_level": "A", "source_type": "manufacturer"},
        )

    def test_matlab_provenance_suite_has_bad_year_and_semantic_pair_fixtures(
        self,
    ) -> None:
        suite = (ROOT / "tests" / "test_s12_engine_sound_v11_provenance.m").read_text(
            encoding="utf-8"
        )
        for test_name in (
            "testRejectsUnstructuredC63ModelYear",
            "testRejectsDescendingC63YearRange",
            "testRejectsInvalidOfficialReferenceSemanticPair",
            "testRejectsInvalidCandidateReferenceSemanticPair",
            "testRejectsProfileOfficialManifestSourceDrift",
            "testRejectsCanonicalProfileProvenanceDowngrade",
        ):
            self.assertIn(test_name, suite)


def load_manifest(vehicle_id: str) -> dict:
    return json.loads(
        (V11 / "vehicles" / vehicle_id / "reference_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def url_sha256(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main(verbosity=2)
