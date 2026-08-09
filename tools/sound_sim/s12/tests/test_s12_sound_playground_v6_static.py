"""Offline v6 closeout gates; source inspection only, never invokes MATLAB."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "playground"
TESTS = ROOT.parent / "tests"


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def immutable_scope_hash(playground: Path) -> str:
    s12_root = playground.parent
    test_names = [
        "test_s12_sound_playground.m",
        "test_s12_sound_playground_offline_repair.m",
        "test_s12_sound_playground_v3_static.py",
        "test_s12_sound_playground_v4_static.py",
        "test_s12_sound_playground_v5_static.py",
        "test_s12_sound_playground_v6_static.py",
        "test_s12_sound_playground_v6_contract.m",
        "test_package_self_contained.py",
    ]
    files = [*playground.glob("*.m"), *playground.glob("*.json"), *playground.glob("*.py")]
    files.extend((playground / "audit_manifests").glob("*.json"))
    files.extend(s12_root / "tests" / name for name in test_names)
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(s12_root).as_posix()):
        digest.update((path.relative_to(s12_root).as_posix() + "\n").encode())
        digest.update((hashlib.sha256(path.read_bytes()).hexdigest().upper() + "\n").encode())
    return digest.hexdigest().upper()


class V6OfflineCloseoutTests(unittest.TestCase):
    def test_v6_tests_are_immutable_canonical_members(self) -> None:
        tree = source("s12_sound_playground_source_tree_sha256.m")
        self.assertIn("test_s12_sound_playground_v6_static.py", tree)
        self.assertIn("test_s12_sound_playground_v6_contract.m", tree)
        self.assertTrue((TESTS / "test_s12_sound_playground_v6_contract.m").is_file())

    def test_canonical_preflight_rejects_newer_or_invalid_crash_time_and_retains_flag_gate(
        self,
    ) -> None:
        verifier = source("s12_sound_playground_verify_environment_preflight.m")
        self.assertIn("crash_dump_latest_time", verifier)
        self.assertIn("crashDumpAt > capturedAt", verifier)
        self.assertIn("crash dump timestamp is newer than preflight capture", verifier)
        self.assertIn("invalid timestamp", verifier)
        self.assertIn("logical(evidence.new_crash_detected)", verifier)
        self.assertIn("active run lock or new crash evidence detected", verifier)

    def test_global_lock_helpers_are_exclusive_and_owner_scoped(self) -> None:
        acquire = source("s12_sound_playground_acquire_global_run_lock.m")
        release = source("s12_sound_playground_release_global_run_lock.m")
        for field in (
            "run_id",
            "authorization_id",
            "desktop_pid",
            "source_tree_sha256",
            "audit_zip_sha256",
            "start_time",
            "owner_process",
        ):
            self.assertIn(field, acquire)
        self.assertIn(
            "s12_sound_playground_atomic_write_json(lockPath, lockRecord, false)", acquire
        )
        self.assertIn("isfile(lockPath)", acquire)
        self.assertIn("ACTIVE_RUN_LOCKED", acquire)
        self.assertIn("run_id", release)
        self.assertIn("authorization_id", release)
        self.assertIn("RELEASE_IN_PROGRESS", release)
        self.assertIn("LockOwnerMismatch", release)

    def test_orchestrator_acquires_lock_after_preflight_before_transaction_or_authorization(
        self,
    ) -> None:
        orchestrator = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        preflight = orchestrator.index("s12_sound_playground_verify_environment_preflight")
        lock = orchestrator.index("s12_sound_playground_acquire_global_run_lock")
        transaction = orchestrator.index("mkdir(transactionRoot)")
        authorization = orchestrator.index("authorizeAndClaim")
        self.assertLess(preflight, lock)
        self.assertLess(lock, transaction)
        self.assertLess(lock, authorization)
        self.assertIn("ACTIVE_RUN_LOCKED", orchestrator)
        self.assertIn("release_global_run_lock", orchestrator)

    def test_pcm_validation_returns_an_artifact_and_void_stage_has_explicit_semantics(self) -> None:
        orchestrator = source("s12_sound_playground_controlled_rebuild_and_qualify.m")
        self.assertIn("function result = requireValidated", orchestrator)
        self.assertIn("PCM_VALIDATION_PASSED", orchestrator)
        self.assertIn("pcm_validation", orchestrator)
        self.assertIn('runArtifactStage(result, transactionRoot, "pcm_validation"', orchestrator)

    def test_sensitivity_contract_has_numeric_frequency_error_and_delta_thresholds(self) -> None:
        contract = source("s12_sound_playground_sensitivity_contract.m")
        gate = source("s12_sound_playground_sensitivity_gate.m")
        for field in (
            "selected_order",
            "frequency_absolute_tolerance_hz",
            "frequency_relative_tolerance",
            "minimum_load_rms_change",
            "minimum_order2_to_order1_energy_ratio_change",
            "transient_window_s",
            "minimum_delta_pcm_energy",
            "minimum_delta_pcm_peak",
        ):
            self.assertIn(field, contract)
        self.assertIn("double(baseValue) / 60 * contract.selected_order", gate)
        for field in (
            "expected_frequency_hz",
            "measured_frequency_hz",
            "absolute_error_hz",
            "relative_error",
            "allowed_absolute_error_hz",
            "allowed_relative_error",
        ):
            self.assertIn(field, gate)
        self.assertNotIn("isequal(base.rms, varied.rms)", gate)
        self.assertIn("frequencyComparison", gate)

    def test_v6_contract_test_covers_required_future_runtime_cases(self) -> None:
        contract_test = (TESTS / "test_s12_sound_playground_v6_contract.m").read_text(
            encoding="utf-8"
        )
        for label in (
            "crash_before_capture",
            "crash_after_capture",
            "invalid_crash_timestamp",
            "empty_crash_timestamp",
            "run_a_acquires_lock",
            "run_b_is_locked",
            "run_a_reentry_is_locked",
            "wrong_owner_cannot_release",
            "cleanup_failure_visible",
            "output_operation",
            "void_operation",
            "operation_throws",
            "pcm_validation_pass",
            "pcm_validation_fail",
            "failure_stops_sensitivity",
        ):
            self.assertIn(label, contract_test)

    def test_source_hash_is_stable_for_external_runtime_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied_s12 = Path(temporary) / "s12"
            shutil.copytree(ROOT, copied_s12 / "playground")
            shutil.copytree(TESTS, copied_s12 / "tests")
            before = immutable_scope_hash(copied_s12 / "playground")
            runtime = Path(temporary) / "runtime"
            runtime.mkdir()
            (runtime / "ACTIVE_RUN_LOCK.json").write_text('{"run_id":"a"}\n', encoding="utf-8")
            self.assertEqual(before, immutable_scope_hash(copied_s12 / "playground"))


if __name__ == "__main__":
    unittest.main()
