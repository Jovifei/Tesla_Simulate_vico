"""Static-only contracts for the temporary-candidate Simulink Runtime Proof."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "playground"
TESTS = ROOT.parent / "tests"
EXPECTED_STAGES = [
    "temporary_build",
    "port_contract",
    "cold_reload",
    "update_diagram",
    "active_compile_dimension_readback",
    "idle_simulation",
    "cruise_simulation",
    "acceleration_simulation",
    "pcm_validation",
    "parameter_sensitivity",
    "repeatability",
    "device_audio_smoke",
    "runtime_proof_report",
]


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class RuntimeProofStaticTests(unittest.TestCase):
    def test_runtime_proof_tests_are_named_immutable_source_members(self) -> None:
        tree = source("s12_sound_playground_source_tree_sha256.m")
        self.assertIn("test_s12_sound_playground_runtime_proof_static.py", tree)
        self.assertIn("test_s12_sound_playground_runtime_proof_contract.m", tree)
        self.assertIn("test_s12_sound_playground_atomic_write_json_runtime.m", tree)
        self.assertIn("test_s12_sound_playground_runtime_preflight.m", tree)
        self.assertIn("test_s12_sound_playground_function_scripts.m", tree)
        self.assertIn('dir(fullfile(playground, "*.m"))', tree)
        self.assertTrue((ROOT / "s12_sound_playground_runtime_proof_once.m").is_file())
        self.assertTrue((ROOT / "s12_sound_playground_runtime_proof_model_gate.m").is_file())
        self.assertNotIn("test_s12_sound_playground_v8_static.py", tree)
        self.assertNotIn("test_s12_sound_playground_v8_contract.m", tree)
        self.assertTrue((TESTS / "test_s12_sound_playground_runtime_proof_contract.m").is_file())

    def test_once_script_is_the_single_manual_entry_and_never_launches_matlab(self) -> None:
        entry = source("s12_sound_playground_runtime_proof_once.m")
        self.assertNotRegex(entry, r"(?m)^\s*function\b")
        self.assertIn("s12_sound_playground_runtime_proof(", entry)
        self.assertIn("s12_playground_runtime_proof_result", entry)
        self.assertIn("case_output_root", entry)
        for prohibited in (
            "matlab -" + "batch",
            "-nodesktop",
            "matlab." + "engine",
            "matlab-mcp-" + "server",
            "start-process",
            "retry",
        ):
            self.assertNotIn(prohibited, entry.lower())

    def test_runtime_proof_uses_exact_run_directory_and_fixed_temporary_model_name(self) -> None:
        plan = source("s12_sound_playground_runtime_proof_plan.m")
        paths = source("s12_sound_playground_runtime_paths.m")
        self.assertIn('"s12-playground-runtime-proof"', paths)
        self.assertIn("transactionRoot = runtimeRoot", paths)
        self.assertIn("temporaryRoot = runtimeRoot", paths)
        self.assertIn('"S12_Sound_Playground_RUNTIME_PROOF_TMP"', plan)
        self.assertNotIn('"S12_Sound_Playground_runtime_proof_tmp_" + runId', plan)

    def test_runtime_proof_stage_manifest_is_exact_and_runtime_truthful(self) -> None:
        manifest = json.loads(
            (ROOT / "audit_manifests/runtime_proof_stage_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["ordering"], EXPECTED_STAGES)
        self.assertEqual(manifest["initial_status"], "MANUAL_RUNTIME_REQUIRED")
        self.assertEqual(manifest["success_status"], "RUNTIME_PROOF_PASSED")
        self.assertTrue(manifest["fail_fast"])

    def test_runtime_proof_is_temporary_candidate_only(self) -> None:
        proof = source("s12_sound_playground_runtime_proof.m")
        plan = source("s12_sound_playground_runtime_proof_plan.m")
        self.assertIn(
            "function result = s12_sound_playground_runtime_proof(runId, execute, outputRoot, preflight)",
            proof,
        )
        self.assertIn("s12_sound_playground_build_temp", proof)
        self.assertIn("s12_sound_playground_inspect_model", proof)
        self.assertIn("candidate", plan)
        for prohibited in (
            "s12_sound_playground_promote_temp",
            "canonical_migration",
            "s12_sound_playground_canonical_path_plan",
            "formal_repaired_candidate",
            "controlled_rebuild_authorization",
            "audit_version",
            "audit_zip",
            "git commit",
        ):
            self.assertNotIn(prohibited, proof.lower())
            self.assertNotIn(prohibited, plan.lower())

    def test_runtime_proof_dry_run_never_builds_or_opens_a_model(self) -> None:
        proof = source("s12_sound_playground_runtime_proof.m")
        guard = proof.index("if ~execute")
        build = proof.index("s12_sound_playground_build_temp")
        self.assertLess(guard, build)
        self.assertIn('"MANUAL_RUNTIME_REQUIRED"', proof[:build])

    def test_runtime_proof_executes_each_gate_in_manifest_order(self) -> None:
        proof = source("s12_sound_playground_runtime_proof.m")
        positions = []
        for stage in EXPECTED_STAGES[:-1]:
            marker = f'runtimeStage(result, plan, "{stage}"'
            self.assertIn(marker, proof, stage)
            positions.append(proof.index(marker))
        self.assertEqual(positions, sorted(positions))
        self.assertIn("writeRuntimeProofReport", proof)
        self.assertIn("s12_sound_playground_runtime_proof_model_gate", proof)
        self.assertIn("runtimeProofParameterSensitivity", proof)

    def test_progress_starts_as_a_typed_empty_stage_record_array(self) -> None:
        proof = source("s12_sound_playground_runtime_proof.m")
        empty = source("s12_sound_playground_empty_progress.m")
        record = source("s12_sound_playground_stage_record.m")
        append = source("s12_sound_playground_append_stage_record.m")
        self.assertIn('"progress", s12_sound_playground_empty_progress()', proof)
        self.assertIn("repmat(template, 0, 1)", empty)
        self.assertNotIn("struct([])", empty)
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
            self.assertIn(f'"{field}"', record)
        self.assertIn("ProgressRecordSchema", append)

    def test_atomic_json_writer_closes_the_file_without_unsupported_flush(self) -> None:
        writer = source("s12_sound_playground_atomic_write_json.m")
        self.assertIn('fprintf(file, "%s", char(payload));', writer)
        self.assertIn("fclose(file);", writer)
        self.assertNotIn("fflush(", writer)

    def test_atomic_json_writer_has_a_closed_then_verified_publish_contract(self) -> None:
        writer = source("s12_sound_playground_atomic_write_json.m")
        self.assertIn('fopen(char(temporary), "w", "n", "UTF-8")', writer)
        self.assertIn("checkWriteCount", writer)
        self.assertIn("ferror(file)", writer)
        self.assertIn("closeOwnedFile", writer)
        self.assertIn("jsondecode(fileread(path))", writer)
        self.assertIn("ATOMIC_MOVE", writer)
        self.assertIn("REPLACE_EXISTING", writer)
        self.assertIn("verifySha256", writer)
        self.assertLess(writer.index("closeOwnedFile"), writer.index("java.nio.file.Files.move"))
        self.assertNotIn("onCleanup(", writer)
        self.assertNotIn("fclose('all')", writer)

    def test_atomic_json_writer_reserves_with_explicit_empty_java_attributes(self) -> None:
        writer = source("s12_sound_playground_atomic_write_json.m")
        self.assertIn('javaArray("java.nio.file.attribute.FileAttribute", 0)', writer)
        self.assertIn("java.nio.file.Files.createFile(toJavaPath(candidate), attributes)", writer)
        self.assertIn("matlabProcessID", writer)

    def test_sha256_contract_is_a_scalar_string_and_has_an_explicit_comparator(self) -> None:
        digest = source("s12_sound_playground_sha256.m")
        comparator = source("s12_sound_playground_sha256_equal.m")
        require = source("s12_sound_playground_require_sha256_equal.m")
        self.assertIn("lower(string(reshape(", digest)
        self.assertIn("strcmp(actual, expected)", comparator)
        self.assertIn("S12:Playground:HashScalar", require)

    def test_sha256_control_flow_uses_the_explicit_scalar_comparator(self) -> None:
        for name in (
            "s12_sound_playground_atomic_write_json.m",
            "s12_sound_playground_atomic_write_json_selftest.m",
            "s12_sound_playground_build_temp.m",
            "s12_sound_playground_controlled_rebuild_and_qualify.m",
            "s12_sound_playground_device_smoke.m",
            "s12_sound_playground_promote_temp.m",
            "s12_sound_playground_runtime_proof_model_gate.m",
            "s12_sound_playground_runtime_proof_preflight.m",
            "s12_sound_playground_run_simulink_case.m",
        ):
            self.assertTrue(
                "s12_sound_playground_sha256_equal" in source(name)
                or "s12_sound_playground_require_sha256_equal" in source(name),
                name,
            )

    def test_no_direct_sha256_equality_operators_remain(self) -> None:
        sha_names = r"(?:\b[a-zA-Z_]*sha256\b|\bactualSha(?:256)?\b|\bexpectedSha(?:256)?\b)"
        forbidden = re.compile(rf"{sha_names}[^\n]*(?:==|~=)|(?:==|~=)[^\n]*{sha_names}")
        for path in [*ROOT.glob("*.m"), *TESTS.glob("test_s12_sound_playground*.m")]:
            self.assertNotRegex(path.read_text(encoding="utf-8"), forbidden, path.name)

    def test_atomic_json_writer_uses_one_non_varargs_java_path_adapter(self) -> None:
        writer = source("s12_sound_playground_atomic_write_json.m")
        self.assertIn("function pathObject = toJavaPath(path)", writer)
        self.assertIn("java.io.File(char(path)).toPath", writer)
        self.assertIn("java.nio.file.Files.move(toJavaPath(temporary), ...", writer)
        self.assertIn("toJavaPath(path), options)", writer)
        self.assertNotIn("java.nio.file.Paths.get", writer)

    def test_atomic_json_writer_cleanup_keeps_owned_file_state_in_scope(self) -> None:
        writer = source("s12_sound_playground_atomic_write_json.m")
        self.assertNotIn("onCleanup(", writer)
        self.assertIn("catch cause", writer)
        self.assertIn("cleanupOwnedTemporary();", writer)
        self.assertIn("rethrow(cause);", writer)

    def test_atomic_json_writer_treats_reservation_and_selftest_root_as_owned_cleanup(self) -> None:
        writer = source("s12_sound_playground_atomic_write_json.m")
        selftest = source("s12_sound_playground_atomic_write_json_selftest.m")
        self.assertLess(writer.index("try"), writer.index("temporary = reserveTemporaryPath"))
        self.assertIn("if ~replaceExisting", writer)
        self.assertIn('options = javaArray("java.nio.file.CopyOption", 0);', writer)
        self.assertIn("rootCleanup = onCleanup(@() cleanupRoot(root));", selftest)

    def test_owned_temp_handle_cleanup_is_exactly_scoped(self) -> None:
        helper = source("s12_sound_playground_close_owned_json_temp_handles.m")
        self.assertIn("openedFiles", helper)
        self.assertIn("fopen(fileId)", helper)
        self.assertIn(".s12_playground_json_", helper)
        self.assertIn("transactionRoot", helper)
        self.assertIn("matched_handle_ids", helper)
        self.assertIn("closed_handle_ids", helper)
        self.assertIn("close_failures", helper)
        self.assertIn("deleted_temporary_paths", helper)
        self.assertIn("remaining_matching_handles", helper)
        self.assertNotIn("fclose('all')", helper)

    def test_atomic_writer_selftest_is_runtime_free_and_covers_failure_preservation(self) -> None:
        selftest = source("s12_sound_playground_atomic_write_json_selftest.m").lower()
        for marker in (
            "utf-8",
            "nested",
            "overwrite",
            "encoding_failure",
            "move_failure",
            "temporary_files",
            "owned_open_handles",
            "deterministic",
            "path with spaces",
        ):
            self.assertIn(marker, selftest)
        self.assertIn("initial.nested.items =", selftest)
        for prohibited in ("load_system", "new_system", "sim(", "audiodevicewriter"):
            self.assertNotIn(prohibited, selftest)

    def test_runtime_proof_preflight_runs_cleanup_selftest_and_canonical_hash_before_build(
        self,
    ) -> None:
        entry = source("s12_sound_playground_runtime_proof_once.m")
        proof = source("s12_sound_playground_runtime_proof.m")
        self.assertIn(
            "runtime_preflight = s12_sound_playground_runtime_proof_preflight(runtime_plan);", entry
        )
        self.assertLess(
            entry.index("s12_sound_playground_runtime_proof_preflight"),
            entry.index("s12_sound_playground_runtime_proof("),
        )
        self.assertIn("s12_sound_playground_runtime_proof_preflight", proof)
        self.assertLess(
            proof.index("s12_sound_playground_runtime_proof_preflight"),
            proof.index("s12_sound_playground_build_temp"),
        )
        preflight = source("s12_sound_playground_runtime_proof_preflight.m")
        for marker in (
            "s12_sound_playground_close_owned_json_temp_handles",
            "s12_sound_playground_atomic_write_json_selftest",
            "canonical_sha256_before",
            "43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5",
        ):
            self.assertIn(marker, preflight)

    def test_model_gates_separate_reload_update_and_active_compile(self) -> None:
        gate = source("s12_sound_playground_runtime_proof_model_gate.m")
        compiler = source("s12_sound_playground_compile_and_inspect_dimensions.m")
        self.assertIn('"cold_reload"', gate)
        self.assertIn('"update_diagram"', gate)
        self.assertIn('"active_compile_dimension_readback"', gate)
        self.assertIn('"SimulationCommand", "update"', gate)
        self.assertIn("s12_sound_playground_compile_and_inspect_dimensions", gate)
        self.assertIn("false", gate)
        self.assertIn("performUpdate", compiler)

    def test_runner_accepts_only_the_plan_candidate_and_preserves_model_hash(self) -> None:
        runner = source("s12_sound_playground_run_simulink_case.m")
        self.assertIn("candidate = plan.candidate", runner)
        self.assertIn("candidate.path", runner)
        self.assertIn("candidate.model_name", runner)
        self.assertNotIn("A promoted repaired candidate is required", runner)
        self.assertNotIn("caller-owned formal model", runner)
        self.assertNotIn("Formal repaired candidate changed", runner)
        self.assertIn("model_sha256_before", runner)
        self.assertIn("model_sha256_after", runner)
        self.assertIn("ScenarioWorkspaceMismatch", runner)

    def test_shared_builder_and_runner_keep_the_existing_controlled_plan_compatible(self) -> None:
        for name in (
            "s12_sound_playground_build_temp.m",
            "s12_sound_playground_run_simulink_case.m",
        ):
            text = source(name)
            self.assertIn('isfield(plan, "candidate")', text, name)
            self.assertIn('isfield(plan, "formal")', text, name)

    def test_repeatability_uses_independent_outputs_and_complete_metrics_without_scalar_rpm(
        self,
    ) -> None:
        repeatability = source("s12_sound_playground_repeatability_gate.m")
        self.assertIn('"repeatability_a"', repeatability)
        self.assertIn('"repeatability_b"', repeatability)
        for field in (
            "pcm_sha256",
            "wav_sha256",
            "scenario_sha256",
            "parameter_snapshot_sha256",
            "metrics_json_sha256",
            "model_sha256_before",
            "model_sha256_after",
            "metrics",
        ):
            self.assertIn(field, repeatability)
        self.assertNotIn("s12_sound_playground_case_order_metrics(", repeatability)

    def test_scenarios_have_one_finalization_and_workspace_round_trip(self) -> None:
        scenario = source("s12_sound_playground_scenario_source.m")
        finalizer = source("s12_sound_playground_finalize_scenario.m")
        sensitivity = source("s12_sound_playground_sensitivity_gate.m")
        controlled = source("s12_sound_playground_controlled_sensitivity_scenario.m")
        self.assertIn("s12_sound_playground_finalize_scenario(scenario)", scenario)
        self.assertIn("reshape(frames, 18, 1, frameCount)", finalizer)
        self.assertIn('"dimensions", [18, 1]', finalizer)
        self.assertIn("scenario_sha256", finalizer)
        self.assertIn("s12_sound_playground_controlled_sensitivity_scenario", sensitivity)
        self.assertIn("s12_sound_playground_finalize_scenario(scenario)", controlled)
        self.assertIn("workspaceFrames(base)", sensitivity)

    def test_device_smoke_is_bounded_and_does_not_invent_audible_confirmation(self) -> None:
        smoke = source("s12_sound_playground_device_smoke.m")
        self.assertRegex(smoke, r"durationSeconds\s*<\s*1\s*\|\|\s*durationSeconds\s*>\s*3")
        self.assertIn("Optional Device Output", smoke)
        self.assertIn('"off"', smoke)
        self.assertIn("device_playback_executed", smoke)
        self.assertIn('"pending"', smoke)
        self.assertIn("audio_device_error", smoke)
        self.assertIn("simulation = sim", smoke)
        self.assertIn("s12_sound_playground_normalize_logged_pcm", smoke)
        self.assertIn("s12_sound_playground_validate_pcm_metrics", smoke)
        self.assertIn("pcm_metrics", smoke)

    def test_runtime_proof_has_no_matlab_launcher_retry_or_mcp_bootstrap(self) -> None:
        proof = source("s12_sound_playground_runtime_proof.m").lower()
        for prohibited in (
            "matlab -" + "batch",
            "-nodesktop",
            "matlab." + "engine",
            "matlab-mcp-" + "server",
            "start-process",
            "retry",
        ):
            self.assertNotIn(prohibited, proof)

    def test_static_test_itself_cannot_launch_runtime_tools(self) -> None:
        text = Path(__file__).read_text(encoding="utf-8").lower()
        for prohibited in (
            "import " + "subprocess",
            "from " + "subprocess",
            "os." + "system(",
            "matlab -" + "batch",
        ):
            self.assertNotIn(prohibited, text)


if __name__ == "__main__":
    unittest.main()
