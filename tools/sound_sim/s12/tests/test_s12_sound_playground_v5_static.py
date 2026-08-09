"""Offline v5 readiness gates; source inspection only, never invokes MATLAB."""

from __future__ import annotations

import json
import hashlib
import shutil
import tempfile
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "playground"


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def immutable_scope_hash(playground: Path) -> str:
    s12_root = playground.parent
    tests = s12_root / "tests"
    names = [
        "test_s12_sound_playground.m",
        "test_s12_sound_playground_offline_repair.m",
        "test_s12_sound_playground_v3_static.py",
        "test_s12_sound_playground_v4_static.py",
        "test_s12_sound_playground_v5_static.py",
        "test_package_self_contained.py",
    ]
    files = [*playground.glob("*.m"), *playground.glob("*.json"), *playground.glob("*.py")]
    files.extend((playground / "audit_manifests").glob("*.json"))
    files.extend(tests / name for name in names)
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(s12_root).as_posix()):
        digest.update((path.relative_to(s12_root).as_posix() + "\n").encode())
        digest.update((hashlib.sha256(path.read_bytes()).hexdigest().upper() + "\n").encode())
    return digest.hexdigest().upper()


class V5OfflineReadinessTests(unittest.TestCase):
    def test_source_hash_excludes_runtime_writes_but_detects_immutable_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied_s12 = Path(temporary) / "s12"
            shutil.copytree(ROOT, copied_s12 / "playground")
            shutil.copytree(ROOT.parent / "tests", copied_s12 / "tests")
            copied_playground = copied_s12 / "playground"
            before = immutable_scope_hash(copied_playground)
            runtime = Path(temporary) / "runtime"
            runtime.mkdir()
            (runtime / "transaction.json").write_text(
                '{"stage":"temporary_build"}\n', encoding="utf-8"
            )
            self.assertEqual(before, immutable_scope_hash(copied_playground))
            (runtime / "authorization_claim.json").write_text(
                '{"authorization_id":"a"}\n', encoding="utf-8"
            )
            self.assertEqual(before, immutable_scope_hash(copied_playground))
            target = copied_playground / "s12_sound_playground_signal_contract.m"
            target.write_text(
                target.read_text(encoding="utf-8") + "\n% immutable-change-probe\n",
                encoding="utf-8",
            )
            self.assertNotEqual(before, immutable_scope_hash(copied_playground))

    def test_runtime_paths_are_external_and_source_hash_is_an_allow_list(self) -> None:
        paths = source("s12_sound_playground_runtime_paths.m")
        tree = source("s12_sound_playground_source_tree_sha256.m")
        self.assertIn("tasks", paths)
        self.assertIn("reports", paths)
        self.assertIn("runtime", paths)
        self.assertIn("is_subpath", paths)
        self.assertIn("immutableSourceFiles", tree)
        self.assertNotIn('"**"', tree)

    def test_runtime_json_and_claims_are_outside_the_source_tree(self) -> None:
        plan = source("s12_sound_playground_build_plan.m")
        orchestrator = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        self.assertIn("s12_sound_playground_runtime_paths", plan)
        self.assertIn("blockedPlan.runtime", orchestrator)
        self.assertNotIn(".s12_playground_temp", plan)
        self.assertNotIn(".s12_playground_transactions", orchestrator)
        self.assertNotIn(".s12_playground_authorization_registry", orchestrator)

    def test_authorization_rechecks_immutable_source_identity_at_each_boundary(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        self.assertGreaterEqual(text.count("assertImmutableSourceTree"), 4)
        self.assertIn("blockedPlan.source_tree.sha256", text)
        self.assertIn("authorization.reviewed_source_tree_sha256", text)

    def test_environment_preflight_is_a_fresh_external_evidence_gate(self) -> None:
        schema = json.loads(
            (ROOT / "audit_manifests/environment_preflight_schema.json").read_text(encoding="utf-8")
        )
        required = {
            "desktop_root_count",
            "desktop_pid",
            "desktop_command_line",
            "desktop_responding",
            "catapult_child_count",
            "catapult_child_pids",
            "catapult_parent_pid",
            "other_matlab_process_count",
            "other_matlab_pids",
            "mcp_root_count",
            "watchdog_count",
            "batch_process_count",
            "engine_process_count",
            "crash_dump_latest_time",
            "active_run_lock",
            "captured_at",
            "expires_at",
        }
        self.assertTrue(required <= set(schema["required_fields"]))
        verifier = source("s12_sound_playground_verify_environment_preflight.m")
        self.assertIn("ENVIRONMENT_GATE_FAIL", verifier)
        self.assertIn("expires_at", verifier)
        self.assertIn("crash dump timestamp", verifier)
        self.assertIn("-batch", verifier)
        self.assertIn("-nodesktop", verifier)

    def test_preflight_precedes_authorization_consumption(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        self.assertLess(
            text.index("environment_preflight"), text.index("authorization_verification")
        )
        self.assertLess(
            text.index("verify_environment_preflight"), text.index("claimAuthorization")
        )

    def test_active_compile_lifecycle_is_a_single_helper(self) -> None:
        helper = source("s12_sound_playground_compile_and_inspect_dimensions.m")
        self.assertIn('SimulationCommand", "update', helper)
        self.assertIn('feval(model, [], [], [], "compile")', helper)
        self.assertIn('feval(model, [], [], [], "term")', helper)
        self.assertNotIn("onCleanup", helper)
        self.assertIn("if compiled", helper)
        self.assertIn("UPDATE_DIAGRAM_PASSED", helper)
        self.assertIn("COMPILED_DIMENSIONS_PASSED", helper)
        inspector = source("s12_sound_playground_inspect_model.m")
        self.assertIn("s12_sound_playground_compile_and_inspect_dimensions", inspector)
        self.assertNotIn("CompiledPortDimensions", inspector)

    def test_compile_cleanup_is_visible_and_preserves_a_primary_failure(self) -> None:
        helper = source("s12_sound_playground_compile_and_inspect_dimensions.m")
        self.assertIn("compile_term", helper)
        self.assertIn('feval(model, [], [], [], "term")', helper)
        self.assertIn("if compiled", helper)
        self.assertIn("rethrow(cause)", helper)

    def test_builder_has_real_reshape_blocks_before_fixed_signal_specifications(self) -> None:
        builder = source("s12_sound_playground_build_temp.m")
        self.assertIn("simulink/Math Operations/Reshape", builder)
        self.assertGreaterEqual(builder.count("addFixedConfigurationReshape"), 3)
        self.assertIn('"OutputDimensionality", "Customize", "OutputDimensions", "[18,1]"', builder)
        self.assertLess(
            builder.index("Interactive Configuration Reshape"),
            builder.index("Interactive Configuration [18x1]"),
        )
        self.assertLess(
            builder.index("Qualification Configuration Reshape"),
            builder.index("Qualification Configuration [18x1]"),
        )
        scripts = source("s12_sound_playground_function_scripts.m")
        self.assertNotIn("reshape(packed", scripts)
        self.assertIn("gain = 10^(packed", scripts)

    def test_qualification_source_uses_true_18_by_1_by_frame_time_layout(self) -> None:
        text = source("s12_sound_playground_finalize_scenario.m")
        self.assertIn("reshape(frames, 18, 1, frameCount)", text)
        self.assertIn('"dimensions", [18, 1]', text)
        self.assertNotIn("frames.'", text)

    def test_runner_requires_a_controlled_output_root_and_rethrows(self) -> None:
        text = source("s12_sound_playground_run_simulink_case.m")
        self.assertIn("OutputRootRequired", text)
        self.assertIn("assertControlledOutputDirectory", text)
        self.assertIn("writeFailure", text)
        self.assertIn("rethrow(cause)", text)

    def test_case_evidence_persists_all_required_hashes(self) -> None:
        text = source("s12_sound_playground_write_case_evidence.m")
        for field in (
            "pcm_sha256",
            "wav_sha256",
            "parameter_snapshot_sha256",
            "scenario_sha256",
            "model_sha256_before",
            "model_sha256_after",
            "metrics_json_sha256",
        ):
            self.assertIn(field, text)
        self.assertIn("simulink_qualification.pcm", text)

    def test_idle_failure_stops_later_cases_and_writes_failed_summary(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        self.assertIn("finishFailed", text)
        self.assertIn("CONTROLLED_FLOW_FAILED", text)
        self.assertIn("failed_stage", text)
        self.assertIn(
            "return", text[text.index("idle_simulation") : text.index("cruise_simulation")]
        )

    def test_repeatability_uses_two_independent_output_directories_and_full_evidence(self) -> None:
        text = source("s12_sound_playground_repeatability_gate.m")
        self.assertIn("repeatability_a", text)
        self.assertIn("repeatability_b", text)
        for field in (
            "pcm_sha256",
            "wav_sha256",
            "parameter_snapshot_sha256",
            "frame_count",
            "model_sha256",
        ):
            self.assertIn(field, text)
        self.assertNotIn("Placeholder", text)

    def test_sensitivity_is_one_variable_per_pair(self) -> None:
        text = source("s12_sound_playground_sensitivity_gate.m")
        for pair in ("rpm_800_vs_3000", "load_02_vs_08", "acceleration_0_vs_positive"):
            self.assertIn(pair, text)
        self.assertIn("dominant_order_frequency", text)
        self.assertIn("order2_to_order1", text)
        self.assertIn("transient", text)
        self.assertIn("same_reset_state", text)

    def test_final_state_machine_has_only_v5_top_level_states(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        for state in (
            "PLAN_ONLY_NOT_EXECUTED",
            "CONTROLLED_FLOW_RUNNING",
            "CONTROLLED_FLOW_FAILED",
            "CONTROLLED_FLOW_PASSED",
        ):
            self.assertIn(state, text)
        self.assertNotIn("CONTROLLED_FLOW_COMPLETED_REQUIRES_INDEPENDENT_RUNTIME_REVIEW", text)
        self.assertIn("qualification_report.json", text)
        self.assertIn("completion_receipt.json", text)

    def test_device_skip_is_an_incomplete_direct_listening_gate(self) -> None:
        text = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        self.assertIn("SKIPPED_NOT_AUTHORIZED", text)
        self.assertIn("INCOMPLETE", text)
        self.assertNotIn("SKIPPED_UNAUTHORIZED_OPTIONAL_OPERATION", text)

    def test_close_helper_returns_observable_cleanup_result(self) -> None:
        text = source("s12_sound_playground_close_owned_model_without_save.m")
        self.assertIn("function result =", text)
        for status in ("CLOSED", "ALREADY_CALLER_OWNED", "CLEANUP_FAILED"):
            self.assertIn(status, text)
        self.assertIn("cleanup_error_path", text)

    def test_stateflow_size_parser_is_numeric_and_rejects_dynamic_shapes(self) -> None:
        parser = source("s12_sound_playground_parse_fixed_size.m")
        for example in ("[18,1]", "[18 1]", "18,1"):
            self.assertIn(example, parser)
        self.assertIn("DynamicSize", parser)
        interface = source("s12_sound_playground_configure_function_interfaces.m")
        self.assertIn("s12_sound_playground_parse_fixed_size", interface)
        self.assertNotIn("actual.size ~= expected.size", interface)

    def test_promotion_is_explicitly_unqualified_and_failure_is_durable(self) -> None:
        promotion = source("s12_sound_playground_promote_temp.m")
        finalizer = source("s12_sound_playground_finalize_formal_qualification.m")
        canonical = source("s12_sound_playground_canonical_path_plan.m")
        self.assertIn("PROMOTED_UNQUALIFIED_CANDIDATE", promotion)
        self.assertIn("FAILED_QUALIFICATION", finalizer)
        self.assertIn("canonical_migration", finalizer)
        self.assertIn("qualification manifest", canonical)

    def test_product_claims_keep_dashboard_and_app_boundaries(self) -> None:
        dashboard = source("s12_sound_playground_dashboard_contract.m")
        self.assertIn("SCRIPT_CONFIGURED_SIMULINK_AUDITION_CANDIDATE", dashboard)
        self.assertIn("NOT_A_VALIDATED_DASHBOARD_PLAYGROUND", dashboard)
        self.assertIn("APP_IMPORT_CLAIM = PROHIBITED", dashboard)

    def test_v5_package_contract_and_external_audit_descriptor_are_truthful(self) -> None:
        manifest_root = ROOT / "audit_manifests"
        scope = json.loads(
            (manifest_root / "source_hash_scope_v5.json").read_text(encoding="utf-8")
        )
        descriptor = json.loads(
            (manifest_root / "external_v4_audit_reference.json").read_text(encoding="utf-8")
        )
        self.assertEqual(scope["runtime_data_location"], "OUTSIDE_SOURCE_TREE")
        self.assertEqual(descriptor["content_status"], "NOT_AVAILABLE_NOT_FABRICATED")
        self.assertIn(
            "50A1E0678E3A238DA088010DAAA4B9C584A77A6D9967FC25BCDD96C3F3905902",
            descriptor["declared_sha256"],
        )
        package_test = (Path(__file__).with_name("test_package_self_contained.py")).read_text(
            encoding="utf-8"
        )
        self.assertIn("test_s12_sound_playground_v5_static", package_test)
        self.assertIn("forbidden", package_test)


if __name__ == "__main__":
    unittest.main()
