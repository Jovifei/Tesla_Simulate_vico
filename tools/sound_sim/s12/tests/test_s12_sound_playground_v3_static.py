"""Offline v3 structural gates; never imports or invokes MATLAB."""

from __future__ import annotations

import re
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "playground"


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class V3OfflineStaticTests(unittest.TestCase):
    def test_required_v3_helpers_exist(self) -> None:
        required = {
            "s12_sound_playground_decode_compiled_dimensions.m",
            "s12_sound_playground_configure_pcm_sink.m",
            "s12_sound_playground_pcm_logging_contract.m",
            "s12_sound_playground_normalize_logged_pcm.m",
            "s12_sound_playground_canonical_path_plan.m",
        }
        self.assertSetEqual({path.name for path in ROOT.glob("*.m")} & required, required)

    def test_stateflow_interface_uses_named_input_output_props(self) -> None:
        text = source("s12_sound_playground_configure_function_interfaces.m")
        self.assertIn("chart.Inputs", text)
        self.assertIn("chart.Outputs", text)
        self.assertIn("Props.Array.Size", text)
        self.assertIn("Props.Array.IsDynamic", text)
        self.assertNotIn("chart.Data", text)
        self.assertIn('"reset", [1, 1]', source("s12_sound_playground_function_interfaces.m"))
        interfaces = source("s12_sound_playground_function_interfaces.m")
        self.assertIn('"input_order", ["packed", "reset"]', interfaces)
        self.assertIn('"input_order", ["excitation", "packed", "reset"]', interfaces)
        self.assertIn('"output_order", ["excitation", "packedOut"]', interfaces)
        self.assertIn('"output_order", ["pressure", "packedOut"]', interfaces)

    def test_inspector_has_only_file_level_local_functions(self) -> None:
        text = source("s12_sound_playground_inspect_model.m")
        declarations = re.findall(r"(?m)^function\s+(?:(?:\[[^]]+\]|\w+)\s*=\s+)?(\w+)", text)
        self.assertEqual(declarations[0], "s12_sound_playground_inspect_model")
        self.assertIn("inspectPorts", declarations)
        self.assertIn("portCount", declarations)
        self.assertIn("portNames", declarations)
        self.assertIn("assertTopLevelLink", declarations)
        self.assertNotIn("observed.top_level_connections = contract.top_level_connections", text)
        self.assertIn('get_param(model, "Lines")', text)
        self.assertIn('get_param(lineHandle, "SrcPortHandle")', text)
        self.assertIn('get_param(lineHandle, "DstPortHandle")', text)
        self.assertIn("assertExactTopLevelLinks", text)
        self.assertIn("s12_sound_playground_compile_and_inspect_dimensions", text)
        self.assertNotIn("CompiledPortDimensions", text)

    def test_fixed_18_element_and_frame_timing_contract(self) -> None:
        text = source("s12_sound_playground_signal_contract.m")
        self.assertIn("[18, 1]", text)
        self.assertIn("mux_input_signal_count", text)
        self.assertIn("qualification_frame_count", text)
        self.assertIn("qualification_stop_time_s", text)
        self.assertIn("qualification_audio_duration_s", text)
        self.assertNotIn('"sample_rate", 19', text)
        self.assertNotIn('"sample_rate",', text)
        self.assertNotIn("Sample Rate", source("s12_sound_playground_build_temp.m"))

    def test_mode_selection_matches_manual_switch_wiring(self) -> None:
        text = source("s12_sound_playground_modes.m")
        self.assertIn('"selected_input", 2', text)
        self.assertIn('"selected_input", 1', text)
        apply_mode = source("s12_sound_playground_apply_mode.m")
        self.assertIn("mode.switch_value", apply_mode)
        self.assertIn("Dashboard_Mode_Selector_Manual_Switch", text)

    def test_runner_normalizes_and_gates_before_wav(self) -> None:
        text = source("s12_sound_playground_run_simulink_case.m")
        self.assertIn("s12_sound_playground_normalize_logged_pcm", text)
        self.assertIn("SIMULATION_COMPLETED_AND_VALIDATED", text)
        self.assertIn("SIMULATION_FAILED_VALIDATION", text)
        self.assertNotIn("reshape(double(pcm), [], 2)", text)
        self.assertNotIn('"StopTime", "10"', text)
        self.assertIn("s12_sound_playground_measure_pcm", text)
        self.assertIn("s12_sound_playground_validate_pcm_metrics", text)
        self.assertLess(
            text.index("s12_sound_playground_validate_pcm_metrics"),
            text.index("s12_sound_playground_write_case_evidence"),
        )

    def test_pcm_reset_promotion_and_canonical_contracts_are_fail_closed(self) -> None:
        sink = source("s12_sound_playground_configure_pcm_sink.m")
        self.assertIn('"SaveFormat", contract.save_format', sink)
        self.assertIn('"Save2DSignal", contract.save_2d_signals', sink)
        self.assertIn('"MaxDataPoints", contract.max_data_points', sink)
        self.assertIn('"Decimation", contract.decimation', sink)
        self.assertIn("assertMaskValue", sink)
        self.assertIn("get_param(blockPath, parameter)", sink)
        normalizer = source("s12_sound_playground_normalize_logged_pcm.m")
        self.assertIn("isequal(size(raw), [expectedRows, signal.pcm.shape(2)])", normalizer)
        self.assertNotIn("reshape(raw", normalizer)
        reset = source("s12_sound_playground_reset_contract.m")
        self.assertIn('"internal_unit_delay_reset_pulse"', reset)
        self.assertIn('"OFF_UNTIL_CONTROLLED_RUNTIME_PROOF"', reset)
        self.assertFalse((ROOT / "s12_sound_playground_initialize_simulation.m").exists())
        promotion = source("s12_sound_playground_promote_temp.m")
        for requirement in (
            "temporary_before_sha256",
            "formal_before_sha256",
            "evidence_sha256_before",
            "manifest_sha256",
            "audit_only",
            "rollbackPromotion",
            "writePromotionError",
        ):
            self.assertIn(requirement, promotion)
        canonical = source("s12_sound_playground_canonical_path_plan.m")
        self.assertIn("S12_Sound_Playground_PRE_REPAIR_INVALID.slx", canonical)
        self.assertIn("NO_FILE_OPERATION", canonical)

    def test_pcm_gate_uses_last_to_next_first_sample(self) -> None:
        metrics = source("s12_sound_playground_measure_pcm.m")
        self.assertIn("firstSamples(2:end, :) - lastSamples(1:end - 1, :)", metrics)
        validator = source("s12_sound_playground_validate_pcm_metrics.m")
        for requirement in (
            "actual_frame_count",
            "pcm_sample_count",
            "channels",
            "clipping_count",
            "boundary_last_to_first",
            "duration_s",
        ):
            self.assertIn(requirement, validator)

    def test_workspace_binary_identity_mismatch_is_explicit(self) -> None:
        manifest = json.loads(
            (ROOT / "audit_manifests/evidence_identity_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["workspace_unvalidated_intermediate"]["sha256"],
            "43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5",
        )
        self.assertEqual(
            manifest["historical_pre_repair_invalid"]["sha256"],
            "FA91F46A2F8F6D78586FAE407E795BCEB99AD529F76925A4AF806F9AC73595C0",
        )
        evidence = source("s12_sound_playground_port_contract.m")
        self.assertIn("WORKSPACE_UNVALIDATED_INTERMEDIATE", evidence)
        self.assertIn("FA91F46A2F8F6D78586FAE407E795BCEB99AD529F76925A4AF806F9AC73595C0", evidence)

    def test_audit_manifests_are_parseable_and_runtime_honest(self) -> None:
        manifest_root = ROOT / "audit_manifests"
        expected = {
            "expected_model_manifest.json",
            "expected_dimensions_manifest.json",
            "mode_selection_manifest.json",
            "pcm_logging_manifest.json",
            "promotion_transaction_manifest.json",
            "canonical_path_manifest.json",
            "external_v2_audit_reference.json",
            "external_v3_audit_reference.json",
            "evidence_identity_manifest.json",
            "controlled_rebuild_authorization_template.json",
            "expected_stage_manifest.json",
            "v3_static_verification.json",
            "v4_static_verification.json",
        }
        self.assertTrue(expected <= {path.name for path in manifest_root.glob("*.json")})
        contents = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in manifest_root.glob("*.json")
        }
        self.assertEqual(
            contents["expected_model_manifest.json"]["readiness"],
            "NOT_READY_FOR_CONTROLLED_REBUILD",
        )
        self.assertEqual(contents["expected_dimensions_manifest.json"]["frame_count"], 500)
        self.assertEqual(
            contents["mode_selection_manifest.json"]["qualification"]["selected_input"], 2
        )
        self.assertEqual(
            contents["external_v2_audit_reference.json"]["content_status"], "NOT_FABRICATED"
        )
        self.assertEqual(
            contents["external_v3_audit_reference.json"]["content_status"], "NOT_FABRICATED"
        )
        self.assertEqual(
            contents["v3_static_verification.json"]["python_static_contract_tests"]["passed"], 10
        )
        self.assertEqual(
            contents["v4_static_verification.json"]["validation_scope"],
            "STATIC_ONLY_NO_MATLAB_OR_SIMULINK_EXECUTION",
        )
        self.assertEqual(
            contents["source_hash_scope_v5.json"]["runtime_data_location"], "OUTSIDE_SOURCE_TREE"
        )


if __name__ == "__main__":
    unittest.main()
