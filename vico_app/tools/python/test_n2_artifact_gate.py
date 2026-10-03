"""Executable gate contracts using synthetic artifact bytes, never acoustic acceptance evidence."""
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import n2_artifact_gate as gate
import n2_hard_gate as hard

HERE = Path(__file__).resolve().parent
PREREG = HERE.parents[2] / "docs/vico-p2-n2-implementation-preregistration.md"


def synthetic_binary():
    # Independent wire-format fixture, not a CPU rendering or recalibration of N2 kernels.
    response = lambda n: (1 / math.sqrt(2),) + (0.,) * (n - 2) + (-1 / math.sqrt(2),)
    arrays = [(.52, .46, .39, .33, .27, .22, .17, .12)] + [response(4096)] * 8 + [response(12288)] * 3
    scalars = (13.728409855272066, .08, 18.2039020043, .20)
    seeds = (0x4e325f535243, 5900017, 0x4e325f525350)
    h = hashlib.sha256(b"C63_N2_CONTINUOUS_V1")
    h.update(struct.pack("<6i4d3q", 48000, 8, 4096, 12288, 48, 24, *scalars, *seeds))
    for values in arrays:
        h.update(struct.pack("<" + str(len(values)) + "d", *values))
    identity = h.hexdigest()
    binary = struct.pack(">5iH", 0x4e324250, 2, 8, 4096, 12288, 64) + identity.encode()
    binary += struct.pack(">4d3q", *scalars, *seeds)
    for values in arrays:
        binary += struct.pack(">i" + str(len(values)) + "d", len(values), *values)
    return binary, identity


class GateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "frozen.bin"
            process = subprocess.run(["java", str(HERE / "fixtures/n2/FrozenN2ArtifactFixture.java"), str(output)],
                                     capture_output=True, text=True, timeout=30)
            if process.returncode:
                raise AssertionError(process.stderr + process.stdout)
            cls.binary, cls.profile = output.read_bytes(), process.stdout.strip()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = {key: self.root / name for key, name in (
            ("ledger", "budget.json"), ("artifact", "profile.bin"),
            ("reference", "reference.json"), ("calibration", "calibration.json"))}
        self.files["preregistration"] = PREREG
        self.files["artifact"].write_bytes(self.binary)
        self.files["reference"].write_text('{"synthetic_fixture_only":true}')
        self.calibration = {
            "schema": "c63.n2.calibration.v1", "candidate": gate.CANDIDATE,
            "profile_sha256": self.profile, "artifact_sha256": hashlib.sha256(self.binary).hexdigest(),
            "calibration_profile_id": gate.UNIT_PROFILE_ID, "source_scale": gate.SOURCE_SCALE,
            "event_unit_energy": gate.LEGACY_EVENT_UNIT_ENERGY, "event_unit_l2": gate.LEGACY_EVENT_UNIT_L2,
            "pre_objective": True, "heldout_used_for_fitting": False,
        }
        self.write(self.files["calibration"], self.calibration)
        self.result_path = self.root / "result.json"
        self.trial = self.reserve("trial-1")
        self.result = {
            "schema": gate.RESULT_SCHEMA, "candidate": gate.CANDIDATE,
            "trial_id": "trial-1", "kind": "continuous", "bindings": self.trial["bindings"],
            "reservation": self.trial,
            "evidence": {"sample_count": 144000, "finite": True, "energy_finite": True},
            "partition_invariant": True, "snapshot_replay": True, "baseline_t_identity": True,
            "state_continuity": True, "heldout_used_for_fitting": False,
            "gain_changes_after_calibration": 0,
            "continuous": {"low_max_db": 1., "low_p90_db": 1., "low_median_db": 1.,
                           "mid_max_rise_db": 1., "source_rms_change_db": -1.,
                           "provenance_groups": {"fixture": {"baseline_distance": 10., "candidate_distance": 11.}}},
            "event": {"baseline_distance": 10., "candidate_distance": 8.},
        }
        self.write(self.result_path, self.result)

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, allow_nan=True))

    def reserve(self, trial_id, kind="continuous"):
        return gate.reserve(trial_id=trial_id, kind=kind, **self.files)

    def verify(self):
        self.write(self.result_path, self.result)
        return gate.verify(self.result_path, trial_id="trial-1", **self.files)

    def cli(self, command="check", trial_id="trial-1", kind="continuous", result_path=None, module=False):
        result_path = result_path or self.result_path
        if command == "artifact":
            args = [str(HERE / "n2_artifact_gate.py"), "--verify", str(result_path)]
        else:
            args = [str(HERE / "n2_hard_gate.py"), command]
            args += ["--result", str(result_path)] if command == "check" else ["--kind", kind]
        args += ["--trial-id", trial_id]
        for key, path in self.files.items():
            args += ["--" + key, str(path)]
        if module:
            args = ["-m", "vico_app.tools.python." + Path(args[0]).stem, *args[1:]]
        return subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=30, cwd=HERE.parents[2])

    def assert_rejected(self, output):
        self.assertFalse(output["feasible"], output)
        self.assertEqual("REJECTED_BEFORE_SCORING", output["status"])
        self.assertTrue(output["reasons"])

    def test_valid_actual_function_and_both_clis(self):
        self.assertTrue(self.verify()["feasible"])
        self.assertTrue(hard.check(self.result_path, trial_id="trial-1", **self.files)["feasible"])
        for command in ("check", "artifact"):
            p = self.cli(command)
            self.assertEqual(0, p.returncode, p.stderr + p.stdout)
            self.assertTrue(json.loads(p.stdout)["feasible"])

    def test_package_import_and_module_clis(self):
        from vico_app.tools.python import n2_artifact_gate as package_gate
        from vico_app.tools.python import n2_hard_gate as package_hard
        self.assertTrue(package_gate.verify(self.result_path, trial_id="trial-1", **self.files)["feasible"])
        self.assertTrue(package_hard.check(self.result_path, trial_id="trial-1", **self.files)["feasible"])
        for command in ("artifact", "check"):
            process = self.cli(command, module=True)
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertTrue(json.loads(process.stdout)["feasible"])

    def test_cli_rejection_is_nonzero_not_json_echo(self):
        self.result["state_continuity"] = False
        self.write(self.result_path, self.result)
        for command in ("check", "artifact"):
            p = self.cli(command)
            self.assertEqual(2, p.returncode, p.stderr + p.stdout)
            self.assert_rejected(json.loads(p.stdout))

    def test_missing_ledger_or_reservation(self):
        self.assert_rejected(gate.verify(self.result_path, trial_id="absent", **self.files))
        self.files["ledger"].unlink()
        self.assert_rejected(self.verify())
        self.assertFalse(self.files["ledger"].exists())

    def test_result_cannot_forge_reservation_or_identity(self):
        original = copy.deepcopy(self.result)
        for key, value in (("candidate", "HY1"), ("schema", "c63.n2.reference_result.v1"),
                           ("trial_id", "other"), ("kind", "event"), ("reservation", {}),
                           ("bindings", {})):
            with self.subTest(key=key):
                self.setUp()  # Each mutation gets a fresh candidate ledger.
                self.result[key] = value
                self.assert_rejected(self.verify())
        self.setUp()
        self.result["reservation"]["attempt"] = True
        self.assert_rejected(self.verify())

    def test_hash_shaped_lies_are_not_artifact_evidence(self):
        for key in gate.BINDING_KEYS:
            with self.subTest(key=key):
                self.setUp()
                value = self.result["bindings"][key]
                self.result["bindings"][key] = "a" * 64
                self.assert_rejected(self.verify())
                self.result["bindings"][key] = value

    def test_changed_reference_calibration_or_preregistration_rejected(self):
        for key in ("reference", "calibration", "preregistration"):
            with self.subTest(key=key):
                self.setUp()
                previous = self.files[key]
                altered = self.root / (key + ".tampered")
                altered.write_bytes(previous.read_bytes() + b" ")
                self.files[key] = altered
                self.assert_rejected(self.verify())
                with self.assertRaises(ValueError):
                    self.reserve("tampered")
                self.files[key] = previous

    def test_calibration_constants_and_identity_cannot_change(self):
        original = copy.deepcopy(self.calibration)
        for key, value in (("source_scale", 1), ("event_unit_l2", 1), ("event_unit_energy", 1),
                           ("calibration_profile_id", "a" * 64), ("profile_sha256", "a" * 64),
                           ("artifact_sha256", "a" * 64), ("pre_objective", 1),
                           ("heldout_used_for_fitting", 0), ("candidate", "HY1")):
            with self.subTest(key=key):
                self.setUp()
                self.write(self.files["calibration"], dict(original, **{key: value}))
                self.assert_rejected(self.verify())
        self.write(self.files["calibration"], original)

    def test_artifact_tamper_truncation_trailing_bytes_and_forged_identity(self):
        corrupted = bytearray(self.binary)
        corrupted[86:94] = struct.pack(">d", float("nan"))
        modified = bytearray(self.binary)
        modified[-1] ^= 1
        for data in (b"not a profile", self.binary[:-1], self.binary + b"x", bytes(corrupted),
                     bytes(modified), self.binary[:22] + b"a" * 64 + self.binary[86:]):
            with self.subTest(size=len(data)):
                self.setUp()
                self.files["artifact"].write_bytes(data)
                self.assert_rejected(self.verify())
        self.files["artifact"].write_bytes(self.binary)

    def test_self_consistent_arbitrary_bank_cannot_impersonate_frozen_profile(self):
        binary, identity = synthetic_binary()
        with self.assertRaisesRegex(ValueError, "artifact_frozen_unit_profile_identity"):
            gate._binary_identity(binary)
        self.files["artifact"].write_bytes(binary)
        self.calibration["profile_sha256"] = identity
        self.calibration["artifact_sha256"] = hashlib.sha256(binary).hexdigest()
        self.write(self.files["calibration"], self.calibration)
        self.assert_rejected(self.verify())
        with self.assertRaisesRegex(ValueError, "candidate_search_stopped"):
            self.reserve("forged-profile")

    def test_missing_or_empty_input_files_rejected(self):
        for key in ("artifact", "calibration", "reference", "preregistration"):
            with self.subTest(key=key):
                original = self.files[key]
                self.files[key] = self.root / "missing"
                self.assert_rejected(self.verify())
                self.files[key] = original
        self.files["reference"].write_bytes(b"")
        self.assert_rejected(self.verify())

    def test_registered_one_db_boundary_all_fields(self):
        for key in ("low_max_db", "low_p90_db", "low_median_db", "mid_max_rise_db", "source_rms_change_db"):
            with self.subTest(key=key):
                self.setUp()
                self.result["continuous"][key] = 1.0000001
                output = self.verify()
                self.assert_rejected(output)
                self.assertIn(key + "_gt_1db", output["reasons"])
                self.result["continuous"][key] = 1.
        self.setUp()
        self.result["continuous"]["low_p90_db"] = 1.25  # Old 1.5 dB exception must not survive.
        self.assert_rejected(self.verify())

    def test_protected_low_max_required_not_just_p90(self):
        del self.result["continuous"]["low_max_db"]
        self.assert_rejected(self.verify())

    def test_mid_rule_is_rise_not_absolute_attenuation(self):
        self.result["continuous"]["mid_max_rise_db"] = -2.
        self.assertTrue(self.verify()["feasible"])

    def test_nonfinite_bool_string_and_missing_metrics(self):
        for bad in (float("nan"), float("inf"), -float("inf"), True, "0", None):
            for section, key in (("continuous", "low_max_db"), ("event", "candidate_distance")):
                with self.subTest(section=section, bad=bad):
                    self.setUp()
                    old = self.result[section][key]
                    self.result[section][key] = bad
                    self.assert_rejected(self.verify())
                    self.result[section][key] = old

    def test_digital_state_and_fitting_evidence_required(self):
        original = copy.deepcopy(self.result)
        for key in ("evidence", "partition_invariant", "snapshot_replay", "baseline_t_identity",
                    "state_continuity", "heldout_used_for_fitting", "gain_changes_after_calibration"):
            with self.subTest(key=key):
                self.setUp()
                del self.result[key]
                self.assert_rejected(self.verify())
        for bad in (True, 0, -1, 1.5, "1"):
            self.setUp()
            self.result["evidence"]["sample_count"] = bad
            self.assert_rejected(self.verify())
        self.setUp()
        self.result["evidence"]["sample_count"] = 1
        self.result["gain_changes_after_calibration"] = False
        self.assert_rejected(self.verify())

    def test_event_and_provenance_regression_rejected(self):
        self.result["event"]["candidate_distance"] = 8.00001
        self.assert_rejected(self.verify())
        self.setUp()
        self.result["event"]["candidate_distance"] = 8.
        self.result["continuous"]["provenance_groups"]["fixture"]["candidate_distance"] = 11.001
        self.assert_rejected(self.verify())
        self.setUp()
        self.result["continuous"]["provenance_groups"] = {}
        self.assert_rejected(self.verify())

    def test_malformed_json_duplicate_keys_and_overflow_rejected(self):
        for data in ('{', '[]', 'null', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}',
                     '{"schema":"bad","schema":"good"}'):
            with self.subTest(data=data):
                self.result_path.write_text(data)
                p = self.cli()
                self.assertEqual(2, p.returncode, p.stderr)
                self.assert_rejected(json.loads(p.stdout))
        self.result_path.write_bytes(b"\xff")
        self.assertEqual(2, self.cli().returncode)

    def test_malformed_ledger_never_resets_or_changes(self):
        state = gate.load(self.files["ledger"])
        bad_states = [[], {}, dict(state, schema="c63.n2.budget.v1"), dict(state, limits={}),
                      dict(state, trials=[None]), dict(state, trials=state["trials"] * 2)]
        broken = copy.deepcopy(state)
        broken["trials"][0]["attempt"] = True
        bad_states.append(broken)
        for value in bad_states:
            with self.subTest(value=value):
                self.write(self.files["ledger"], value)
                before = self.files["ledger"].read_bytes()
                self.assert_rejected(self.verify())
                with self.assertRaises(ValueError):
                    self.reserve("new")
                self.assertEqual(before, self.files["ledger"].read_bytes())

    def test_duplicate_across_kinds_rejected_without_consuming_attempt(self):
        before = self.files["ledger"].read_bytes()
        for kind in gate.LIMITS:
            with self.assertRaisesRegex(ValueError, "duplicate"):
                self.reserve("trial-1", kind)
        self.assertEqual(before, self.files["ledger"].read_bytes())

    def test_invalid_trial_names_rejected(self):
        for value in ("", "space id", "../escape", "x" * 129, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.reserve(value)

    def test_reserved_receipt_survives_later_reservations(self):
        self.reserve("later")
        self.reserve("event-1", "event")
        self.assertTrue(self.verify()["feasible"])

    def test_process_concurrency_enforces_both_budgets_and_no_lost_updates(self):
        jobs = [("continuous", i) for i in range(55)] + [("event", i) for i in range(30)]
        def run(job):
            kind, i = job
            return kind, self.cli("reserve", kind + str(i), kind)
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(run, jobs))
        for kind, maximum in gate.LIMITS.items():
            successes = [p for k, p in results if k == kind and p.returncode == 0]
            # setUp already reserved one continuous attempt.
            self.assertEqual(maximum - (kind == "continuous"), len(successes))
        self.assertTrue(all(p.returncode in (0, 2) for _, p in results))
        state = gate.load(self.files["ledger"])
        self.assertEqual(gate.LIMITS, gate._validate_ledger(state))
        self.assertEqual(72, len({t["trial_id"] for t in state["trials"]}))
        self.assertTrue(self.verify()["feasible"])
        before = self.files["ledger"].read_bytes()
        self.assertEqual(2, self.cli("reserve", "over-budget").returncode)
        self.assertEqual(before, self.files["ledger"].read_bytes())
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_result_seal_binds_success_failure_and_idempotent_replay(self):
        for feasible in (True, False):
            with self.subTest(feasible=feasible):
                self.setUp()
                self.result["state_continuity"] = feasible
                first = self.verify()
                self.assertEqual(feasible, first["feasible"])
                self.assertEqual(first, self.verify())
                digest = hashlib.sha256(self.result_path.read_bytes()).hexdigest()
                self.assertEqual(digest, first["result_sha256"])
                self.assertEqual(self.trial, first["reservation"])
                self.assertEqual(digest, gate.load(self.files["ledger"])["results"]["trial-1"])
                self.result["event"]["candidate_distance"] = 1.
                self.assertIn("invalid_evidence:reservation_already_used_for_different_result", self.verify()["reasons"])
                self.assertEqual(1, len(gate.load(self.files["ledger"])["trials"]))

    def test_concurrent_results_cannot_reuse_one_reservation(self):
        second = copy.deepcopy(self.result)
        second["event"]["candidate_distance"] = 1.
        other = self.root / "second-result.json"
        self.write(other, second)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda path: self.cli(result_path=path), [self.result_path, other]))
        self.assertEqual([0, 2], sorted(p.returncode for p in results))
        self.assertEqual(1, len(gate.load(self.files["ledger"])["results"]))

    def test_identity_failure_persistently_stops_candidate_search(self):
        self.result["candidate"] = "HY1"
        self.assert_rejected(self.verify())
        self.assertEqual("identity_or_representation_failure", gate.load(self.files["ledger"])["stop_reason"])
        with self.assertRaisesRegex(ValueError, "candidate_search_stopped"):
            self.reserve("after-identity-failure")
        self.result["candidate"] = gate.CANDIDATE
        self.assert_rejected(self.verify())
        self.assertEqual(2, self.cli("reserve", "after-stop").returncode)

    def test_representation_failure_in_reserve_stops_existing_ledger(self):
        self.files["artifact"].write_bytes(self.binary[:-1])
        with self.assertRaisesRegex(ValueError, "artifact_size"):
            self.reserve("bad-artifact")
        self.files["artifact"].write_bytes(self.binary)
        with self.assertRaisesRegex(ValueError, "candidate_search_stopped"):
            self.reserve("after-stop")

    def test_deeply_nested_json_fails_closed_without_traceback(self):
        malformed = '{"x":' + '[' * 10000 + '0' + ']' * 10000 + '}'
        for path in (self.result_path, self.files["ledger"]):
            self.setUp()
            # Resolve to this fresh test's equivalent path.
            target = self.result_path if path.name == "result.json" else self.files["ledger"]
            target.write_text(malformed)
            process = self.cli()
            self.assertEqual(2, process.returncode)
            self.assert_rejected(json.loads(process.stdout))
            self.assertNotIn("Traceback", process.stderr)

    def test_concurrent_duplicate_is_reserved_exactly_once(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.cli("reserve", "same"), range(16)))
        self.assertEqual(1, sum(p.returncode == 0 for p in results))
        self.assertEqual(2, len(gate.load(self.files["ledger"])["trials"]))


if __name__ == "__main__":
    unittest.main()
