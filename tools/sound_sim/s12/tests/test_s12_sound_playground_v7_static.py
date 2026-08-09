"""Offline v7 closeout gates; source inspection and synthetic-source math only.

This test never imports, launches, or connects to MATLAB, Simulink, or MCP.
It does not claim that a generated SLX, PCM stream, or audio device was run.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "playground"
TESTS = ROOT.parent / "tests"
EXPECTED_STAGES = [
    "environment_preflight",
    "global_lock_acquire",
    "authorization_verification",
    "evidence_sha_verification",
    "temporary_build",
    "post_build_port_contract",
    "cold_reload_compile",
    "promote_repaired_candidate",
    "idle_simulation",
    "cruise_simulation",
    "acceleration_simulation",
    "pcm_validation",
    "rpm_sensitivity",
    "load_sensitivity",
    "acceleration_sensitivity",
    "repeatability",
    "optional_device_smoke_skipped",
    "formal_qualification",
    "qualification_report",
    "global_lock_release",
    "completion_receipt",
]


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def source_equivalent_excitation(
    rpm: float, load: float, acceleration: float, *, blocks: int = 20
) -> list[float]:
    """Mirror the frozen synthetic excitation equations without MATLAB execution."""
    sample_rate = 48_000
    frame_samples = 960
    rpm = min(max(rpm, 800.0), 7000.0)
    load = min(max(load, 0.0), 1.0)
    acceleration = min(max(acceleration, -2.0), 5.0)
    throttle = 0.35
    order_gain = (1.0, 0.7, 0.4, 0.25)
    load_balance = (1.0, 0.5 + 0.5 * load, 0.2 + 0.8 * load, 0.1 + 0.9 * load)
    cylinder_color = (1.0, 0.92, 1.06, 0.88)
    firing_order = (1, 3, 4, 2)
    phase = [0.0] * 5
    transient = 0.0
    last_throttle = throttle
    output: list[float] = []
    base_frequency = rpm / 60.0
    for _ in range(blocks):
        frame: list[float] = []
        for index in range(frame_samples):
            value = 0.0
            for order in range(1, 5):
                omega = 2.0 * math.pi * base_frequency * order / sample_rate
                value += (
                    order_gain[order - 1]
                    * load_balance[order - 1]
                    * math.sin(phase[order - 1] + omega * index)
                )
            firing_omega = 2.0 * math.pi * base_frequency * 2.0 / sample_rate
            for cylinder, color in enumerate(cylinder_color):
                phase_offset = 2.0 * math.pi * (firing_order[cylinder] - 1) / 4.0
                value += 0.08 * color * math.sin(phase[4] + phase_offset + firing_omega * index)
            frame.append(0.12 * value)
        for order in range(1, 5):
            omega = 2.0 * math.pi * base_frequency * order / sample_rate
            phase[order - 1] = (phase[order - 1] + omega * frame_samples) % (2.0 * math.pi)
        firing_omega = 2.0 * math.pi * base_frequency * 2.0 / sample_rate
        phase[4] = (phase[4] + firing_omega * frame_samples) % (2.0 * math.pi)
        throttle_step = max(throttle - last_throttle, 0.0)
        last_throttle = throttle
        target = (
            0.08 * max(acceleration, 0.0) / 5.0
            + 0.05 * max(-acceleration, 0.0) / 2.0
            + 0.10 * throttle_step
        )
        transient = 0.88 * transient + 0.12 * target
        for index in range(frame_samples):
            frame[index] += transient * math.sin(
                phase[1] + 2.0 * math.pi * base_frequency * 2.0 * index / sample_rate
            )
        output.extend(frame)
    return output


def projected_energy(samples: list[float], sample_rate: int, frequency_hz: float) -> float:
    real = sum(
        value * math.cos(2.0 * math.pi * frequency_hz * index / sample_rate)
        for index, value in enumerate(samples)
    )
    imaginary = sum(
        value * math.sin(2.0 * math.pi * frequency_hz * index / sample_rate)
        for index, value in enumerate(samples)
    )
    return real * real + imaginary * imaginary


class V7OfflineCloseoutTests(unittest.TestCase):
    def test_v7_tests_are_immutable_canonical_members(self) -> None:
        tree = source("s12_sound_playground_source_tree_sha256.m")
        self.assertIn("test_s12_sound_playground_v7_static.py", tree)
        self.assertIn("test_s12_sound_playground_v7_contract.m", tree)

    def test_authorization_is_schema_bound_and_binds_external_report_package_and_source_identity(
        self,
    ) -> None:
        authorization = source("s12_sound_playground_controlled_rebuild_authorization.m")
        self.assertIn("s12.playground.controlled-rebuild-authorization.v1", authorization)
        self.assertNotIn('"audit_version"', authorization)
        self.assertNotIn("sixthAuditReportSha256", authorization)
        self.assertIn('"READY_FOR_CONTROLLED_REBUILD"', authorization)
        self.assertIn("s12_sound_playground_verify_audit_zip_source_identity", authorization)
        self.assertIn("reviewed_source_tree_sha256", authorization)
        self.assertIn("approving_audit_report_sha256", authorization)

    def test_authorization_negative_contracts_reject_stale_future_unknown_and_mismatched_evidence(
        self,
    ) -> None:
        contract_test = (TESTS / "test_s12_sound_playground_v7_contract.m").read_text(
            encoding="utf-8"
        )
        for label in (
            "test_pending_external_authorization_is_rejected",
            "test_wrong_schema_is_rejected_without_review_ordinal_logic",
            "test_package_source_identity_mismatch_is_rejected",
        ):
            self.assertIn(label, contract_test)

    def test_template_is_external_pending_not_a_fabricated_authorization(self) -> None:
        template = json.loads(
            (ROOT / "audit_manifests/controlled_rebuild_authorization_template.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            template["authorization_schema_version"],
            "s12.playground.controlled-rebuild-authorization.v1",
        )
        self.assertEqual(template["decision"], "PENDING_EXTERNAL_INDEPENDENT_APPROVAL")
        self.assertNotIn("audit_version", template)
        self.assertEqual(template["status"], "TEMPLATE_ONLY_NOT_AN_AUTHORIZATION")

    def test_signal_specification_is_exact_fixed_size_contract_with_five_readbacks(self) -> None:
        builder = source("s12_sound_playground_build_temp.m")
        inspector = source("s12_sound_playground_inspect_model.m")
        self.assertIn('"Dimensions", "[18 1]", "VarSizeSig", "No"', builder)
        self.assertNotIn("DimensionsMode", builder)
        for name in (
            "Interactive Configuration [18x1]",
            "Qualification Configuration [18x1]",
            "Selected Configuration [18x1]",
            "Vehicle State Fixed Packed [18x1]",
            "Engine Excitation Fixed Packed [18x1]",
        ):
            self.assertIn(name, builder)
            self.assertIn(name, inspector)
        for property_name in ("Dimensions", "VarSizeSig", "OutDataTypeStr"):
            self.assertIn(f'get_param(path, "{property_name}")', inspector)

    def test_order_metrics_use_rpm_centered_one_sided_bands_and_no_half_spectrum_proxy(
        self,
    ) -> None:
        metrics = source("s12_sound_playground_case_order_metrics.m")
        contract = source("s12_sound_playground_sensitivity_contract.m")
        self.assertIn(
            "function metrics = s12_sound_playground_case_order_metrics(pcmPath, rpm)", metrics
        )
        self.assertIn("center_hz", metrics)
        self.assertIn("half_bandwidth_hz", metrics)
        self.assertIn("order2_to_order1_energy_ratio", metrics)
        self.assertIn("oneSidedEnergy", metrics)
        self.assertNotRegex(metrics, r"half\s*/\s*8|lowEnd|harmonic_order_energy_ratio")
        for field in (
            "order_band_orders",
            "order_band_half_bandwidth_hz",
            "order_energy_window",
            "minimum_load_rms_change",
            "minimum_order2_to_order1_energy_ratio_change",
        ):
            self.assertIn(field, contract)

    def test_source_equivalent_load_pair_meets_frozen_rms_and_order_ratio_contract(self) -> None:
        low = source_equivalent_excitation(6000.0, 0.2, 0.0)
        high = source_equivalent_excitation(6000.0, 0.8, 0.0)
        rms_low = math.sqrt(sum(value * value for value in low) / len(low))
        rms_high = math.sqrt(sum(value * value for value in high) / len(high))
        ratio_low = projected_energy(low, 48_000, 200.0) / max(
            projected_energy(low, 48_000, 100.0), 1e-30
        )
        ratio_high = projected_energy(high, 48_000, 200.0) / max(
            projected_energy(high, 48_000, 100.0), 1e-30
        )
        self.assertGreater(rms_high - rms_low, 1e-4)
        self.assertGreater(ratio_high - ratio_low, 1e-4)

    def test_acceleration_uses_delta_pcm_not_global_waveform_growth(self) -> None:
        gate = source("s12_sound_playground_sensitivity_gate.m")
        delta = source("s12_sound_playground_delta_pcm_metrics.m")
        self.assertIn("s12_sound_playground_delta_pcm_metrics", gate)
        self.assertNotIn("varied.transient_window_energy - base.transient_window_energy", gate)
        self.assertNotIn("varied.transient_peak - base.transient_peak", gate)
        for field in ("delta_pcm", "delta_energy", "delta_rms", "delta_peak"):
            self.assertIn(field, delta)

    def test_source_equivalent_acceleration_pair_meets_delta_contract(self) -> None:
        base = source_equivalent_excitation(6000.0, 0.5, 0.0)
        varied = source_equivalent_excitation(6000.0, 0.5, 2.0)
        window = int(0.2 * 48_000)
        delta = [right - left for left, right in zip(base[:window], varied[:window])]
        energy = sum(value * value for value in delta)
        peak = max(abs(value) for value in delta)
        self.assertGreater(energy, 1e-6)
        self.assertGreater(peak, 1e-5)

    def test_qualification_report_precedes_release_and_completion_follows_release(self) -> None:
        orchestrator = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        formal = orchestrator.index('"formal_qualification"')
        report = orchestrator.index("writeQualificationReport")
        release = orchestrator.index("releaseLockAndRecord")
        completion = orchestrator.index("writeCompletionReceipt")
        self.assertLess(formal, report)
        self.assertLess(report, release)
        self.assertLess(release, completion)
        self.assertIn(
            "formal_qualification", source("s12_sound_playground_finalize_formal_qualification.m")
        )

    def test_final_report_contract_includes_formal_identity_lock_and_all_stage_records(
        self,
    ) -> None:
        orchestrator = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        for field in (
            "formal_qualification",
            "formal_candidate_sha256",
            "qualification_status",
            "direct_listening_gate",
            "global_lock_status",
            "qualification_report_sha256",
            "release_receipt_sha256",
            "overall_completion_status",
            "progress",
        ):
            self.assertIn(field, orchestrator)

    def test_expected_stage_manifest_is_exact_and_device_is_skipped_not_completed(self) -> None:
        manifest = json.loads(
            (ROOT / "audit_manifests/expected_stage_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["ordering"], EXPECTED_STAGES)
        self.assertEqual(
            manifest["allowed_statuses"], ["COMPLETED", "FAILED", "SKIPPED_NOT_AUTHORIZED"]
        )
        self.assertIn("optional_device_smoke_skipped", manifest["ordering"])
        self.assertNotIn("optional_device_smoke", manifest["ordering"])

    def test_builder_cleanup_is_explicit_observable_and_does_not_swallow_exceptions(self) -> None:
        builder = source("s12_sound_playground_build_temp.m")
        closer = source("s12_sound_playground_close_owned_model_without_save.m")
        self.assertNotIn("function safeCleanup", builder)
        self.assertNotRegex(builder, r"catch\s*\n\s*end")
        self.assertIn("s12_sound_playground_close_owned_model_without_save", builder)
        self.assertIn("S12:Playground:BuilderCleanup", builder)
        self.assertIn("CLEANUP_FAILED", closer)
        self.assertIn("CLEANUP_FAILURE_EVIDENCE_WRITE_FAILED", closer)
        self.assertIn("model_cleanup_failure.json", builder)
        self.assertIn("library_cleanup_failure.json", builder)

    def test_slx_evidence_identity_is_unchanged(self) -> None:
        manifest = json.loads(
            (ROOT / "audit_manifests/evidence_identity_manifest.json").read_text(encoding="utf-8")
        )
        expected = {
            "historical_pre_repair_invalid": "FA91F46A2F8F6D78586FAE407E795BCEB99AD529F76925A4AF806F9AC73595C0",
            "workspace_unvalidated_intermediate": "43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5",
        }
        self.assertEqual({name: manifest[name]["sha256"] for name in expected}, expected)

    def test_static_suite_has_no_runtime_launcher_or_mcp_operation(self) -> None:
        text = Path(__file__).read_text(encoding="utf-8").lower()
        for prohibited in (
            "import " + "subprocess",
            "from " + "subprocess",
            "matlab -" + "batch",
            "matlab." + "engine",
            "os." + "system(",
        ):
            self.assertNotIn(prohibited, text)


if __name__ == "__main__":
    unittest.main()
