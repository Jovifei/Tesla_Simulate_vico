"""Offline v4 readiness gates; never imports or invokes MATLAB."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "playground"


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class V4OfflineReadinessTests(unittest.TestCase):
    def test_authorization_derives_runtime_plan_from_blocked_plan(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_authorization.m")
        for field in (
            "decision",
            "authorization_schema_version",
            "reviewed_package_path",
            "reviewed_package_sha256",
            "reviewed_source_tree_sha256",
            "approving_audit_report_path",
            "approving_audit_report_sha256",
            "historical_invalid_sha256",
            "workspace_intermediate_sha256",
            "authorized_operations",
            "authorized_by",
            "authorization_id",
        ):
            self.assertIn(field, text)
        self.assertIn("READY_FOR_CONTROLLED_REBUILD", text)
        self.assertIn("REQUIRES_CONTROLLED_RUNTIME_CONFIRMATION", text)
        self.assertIn("already used", text)
        self.assertIn("assertApprovedFile", text)
        self.assertIn("s12.playground.controlled-rebuild-authorization.v1", text)
        self.assertNotIn('"audit_version"', text)

    def test_authorization_has_fail_closed_negative_gates(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_authorization.m")
        for gate in (
            "AuthorizationField",
            "AuthorizationDecision",
            "AuthorizationSchema",
            "AuthorizationSha",
            "AuthorizationReuse",
            "AuthorizationOperations",
            "s12_sound_playground_require_sha256_equal",
            "AuthorizationArtifact",
        ):
            self.assertIn(gate, text)

    def test_blocked_base_plan_and_direct_builder_stay_non_executable(self) -> None:
        plan = source("s12_sound_playground_build_plan.m")
        build = source("s12_sound_playground_build.m")
        self.assertIn("BLOCKED_PENDING_EXPLICIT_AUTHORIZATION_AND_INDEPENDENT_REVIEW", plan)
        self.assertIn("PLAN_ONLY_NOT_EXECUTED", build)
        self.assertIn("DirectBuildForbidden", build)
        self.assertIn("single controlled rebuild orchestrator", build)

    def test_evidence_roles_are_unambiguous(self) -> None:
        text = source("s12_sound_playground_port_contract.m")
        for role in (
            "historical_pre_repair_invalid",
            "workspace_unvalidated_intermediate",
            "temporary_candidate",
            "formal_repaired_candidate",
            "future_canonical",
        ):
            self.assertIn(role, text)
        self.assertNotIn('"formal_model_path"', text)
        self.assertNotIn('"formal_sha256"', text)

    def test_stateflow_uses_supported_fixed_double_api_and_readback(self) -> None:
        text = source("s12_sound_playground_configure_function_interfaces.m")
        self.assertNotIn("Props.Type.Primitive", text)
        self.assertNotIn("Props.Array.FirstIndex", text)
        self.assertIn('data.DataType = "double"', text)
        self.assertIn("data.Props.Array.Size", text)
        self.assertIn("data.Props.Array.IsDynamic = false", text)
        self.assertIn("verifyConfiguredData", text)
        self.assertIn("expected", text)
        self.assertIn("actual", text)

    def test_stateflow_checks_exact_named_collections(self) -> None:
        text = source("s12_sound_playground_configure_function_interfaces.m")
        self.assertIn("numel(actualNames) ~= numel(expectedNames)", text)
        self.assertIn("isequal(sort(actualNames), sort(expectedNames))", text)
        self.assertIn("SupportVariableSizing = false", text)
        self.assertIn("VectorOutputs1D = false", text)
        self.assertIn("TreatDimensionOfLengthOneAsFixedSize = true", text)

    def test_owned_model_lifecycle_is_shared_by_inspector_and_runner(self) -> None:
        self.assertTrue((ROOT / "s12_sound_playground_open_owned_model.m").is_file())
        self.assertTrue((ROOT / "s12_sound_playground_close_owned_model_without_save.m").is_file())
        for name in (
            "s12_sound_playground_inspect_model.m",
            "s12_sound_playground_run_simulink_case.m",
        ):
            text = source(name)
            self.assertIn("s12_sound_playground_open_owned_model", text)
            self.assertIn("onCleanup", text)
            self.assertIn("s12_sound_playground_close_owned_model_without_save", text)

    def test_inspector_checks_named_ports_links_and_default_ports(self) -> None:
        text = source("s12_sound_playground_inspect_model.m")
        for requirement in (
            "inspectPorts",
            "assertExactTopLevelLinks",
            "assertNoDefaultPorts",
            "s12_sound_playground_validate_ports",
        ):
            self.assertIn(requirement, text)
        self.assertIn(
            "s12_sound_playground_validate_dimensions",
            source("s12_sound_playground_compile_and_inspect_dimensions.m"),
        )

    def test_configuration_shape_is_explicit_everywhere(self) -> None:
        signal = source("s12_sound_playground_signal_contract.m")
        self.assertIn("frame_period_s", signal)
        self.assertIn("frame_duration_s = 0.02", signal)
        builder = source("s12_sound_playground_build_temp.m")
        for checkpoint in (
            "Interactive Configuration [18x1]",
            "Qualification Configuration [18x1]",
            "Selected Configuration [18x1]",
            "Vehicle State Fixed Packed [18x1]",
            "Engine Excitation Fixed Packed [18x1]",
        ):
            self.assertIn(checkpoint, builder)
        self.assertIn('"simulink/Signal Attributes/Signal Specification"', builder)
        self.assertIn("[18 1]", builder)
        self.assertNotIn("DimensionsMode", builder)
        self.assertIn('"OutDataTypeStr", "double"', builder)
        self.assertIn("configuration_shape_checkpoints", signal)
        inspector = source("s12_sound_playground_compile_and_inspect_dimensions.m")
        for checkpoint in (
            "configuration_vehicle_input",
            "configuration_vehicle_output",
            "configuration_engine_input",
        ):
            self.assertIn(checkpoint, inspector)

    def test_four_cylinder_scope_is_fixed_and_permutation_checked(self) -> None:
        text = source("s12_sound_playground_parameters.m")
        self.assertIn("params.cylinder_count ~= 4", text)
        self.assertIn("numel(params.firing_order) ~= 4", text)
        self.assertIn("sort(reshape(params.firing_order, 1, []))", text)
        self.assertIn("1:4", text)
        self.assertNotIn('">=", 2, "<=", 12', text)

    def test_promotion_handles_first_create_rollback_and_persists_manifest(self) -> None:
        text = source("s12_sound_playground_promote_temp.m")
        self.assertIn("quarantine", text)
        self.assertIn("first_create", text)
        self.assertIn("formal_path_absent_after_rollback", text)
        self.assertIn("promotion_manifest.json", text)
        self.assertNotIn("manual recovery is required", text.lower())

    def test_promotion_requires_closed_candidates_and_preserves_evidence(self) -> None:
        text = source("s12_sound_playground_promote_temp.m")
        self.assertIn("assertPromotionModelsClosed", text)
        self.assertIn("workspace unvalidated intermediate", text)
        self.assertIn("evidence_sha256_before", text)
        self.assertIn("evidence_sha256_after", text)
        self.assertIn("writePromotionError", text)

    def test_orchestrator_is_one_shot_fail_fast_future_only(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        ordered = [
            "environment_preflight",
            "authorization_verification",
            "temporary_build",
            "post_build_port_contract",
            "cold_reload_compile",
            "promote_repaired_candidate",
            "idle_simulation",
            "cruise_simulation",
            "acceleration_simulation",
            "repeatability",
            "qualification_report",
            "completion_receipt",
        ]
        cursor = -1
        for stage in ordered:
            position = text.index(stage)
            self.assertGreater(position, cursor)
            cursor = position
        schema = source("s12_sound_playground_empty_progress.m")
        for field in (
            "run_id",
            "stage",
            "status",
            "started_at",
            "ended_at",
            "artifact",
            "error_identifier",
            "error_message",
            "error_stack",
        ):
            self.assertIn(field, schema)
        self.assertIn("execute = false", text)
        self.assertIn("finishFailed", text)

    def test_orchestrator_records_stage_failures_and_authorization_claims(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        self.assertIn("authorization_verification", text)
        self.assertIn("authorizeAndClaim", text)
        self.assertIn("authorization_registry_root", text)
        self.assertIn('"FAILED"', text)
        self.assertIn('getReport(cause, "extended"', text)

    def test_expected_stage_manifest_matches_future_orchestrator(self) -> None:
        manifest = json.loads(
            (ROOT / "audit_manifests/expected_stage_manifest.json").read_text(encoding="utf-8")
        )
        text = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        self.assertTrue(manifest["fail_fast"])
        for stage in manifest["ordering"]:
            self.assertIn(stage, text)
        self.assertEqual(
            manifest["progress_record_fields"],
            [
                "run_id",
                "stage",
                "status",
                "started_at",
                "ended_at",
                "artifact",
                "error_identifier",
                "error_message",
                "error_stack",
            ],
        )

    def test_evidence_manifest_preserves_two_immutable_binaries(self) -> None:
        manifest = json.loads(
            (ROOT / "audit_manifests/evidence_identity_manifest.json").read_text(encoding="utf-8")
        )
        for name in ("historical_pre_repair_invalid", "workspace_unvalidated_intermediate"):
            role = manifest[name]
            self.assertFalse(role["mutable"])
            self.assertIn("package_relative_path", role)
            self.assertEqual(len(role["sha256"]), 64)

    def test_source_tree_hash_scope_is_package_complete(self) -> None:
        text = source("s12_sound_playground_source_tree_sha256.m")
        self.assertIn("collectPlaygroundTests", text)
        self.assertIn("immutable_playground_source_contracts_and_named_tests", text)
        self.assertIn("test_package_self_contained.py", text)

    def test_package_self_test_is_source_independent(self) -> None:
        text = (Path(__file__).with_name("test_package_self_contained.py")).read_text(
            encoding="utf-8"
        )
        self.assertIn("evidence_identity_manifest.json", text)
        self.assertIn("package_relative_path", text)
        self.assertIn("sha256", text)
        self.assertNotIn("E:\\\\Tesla_speed", text)


if __name__ == "__main__":
    unittest.main()
