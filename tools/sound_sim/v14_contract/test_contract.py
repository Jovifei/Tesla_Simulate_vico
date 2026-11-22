import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import contract


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = contract.read_json(contract.HERE / "vehicle-registry.json")

    def test_registry_is_closed_and_has_ten_planned_packages(self):
        contract.validate_registry(self.registry)
        self.assertEqual(len(self.registry["vehicles"]), 9)
        self.assertEqual(sum(len(v["sound_packages"]) for v in self.registry["vehicles"]), 10)
        matrix = contract.planned_matrix(self.registry)
        self.assertEqual(len(matrix["formal_cases"]), 50)
        self.assertEqual(len(matrix["h_cases_outside_formal_matrix"]), 10)
        self.assertTrue(all(c["capture_status"] == "NOT_RUN" for c in matrix["formal_cases"]))
        for v in self.registry["vehicles"]:
            for p in v["sound_packages"]:
                self.assertFalse(contract.playable(self.registry, v["vehicle_id"], p["route_id"], p["package_id"], "a" * 64))

    def test_package_and_evidence_binding(self):
        v = self.registry["vehicles"][0]
        v["catalog_status"] = "TARGET_LOCKED"
        v["template_id"] = "synthetic_template"
        v["readiness_status"] = "ACOUSTIC_CALIBRATED"
        p = v["sound_packages"][0]
        p["package_sha256"] = "a" * 64
        p["owner_audition"] = {"status": "PASS", "route_id": p["route_id"], "package_id": p["package_id"], "package_sha256": "a" * 64, "evidence_ref": "signed-attestation"}
        args = (self.registry, v["vehicle_id"], p["route_id"], p["package_id"], "a" * 64)
        self.assertFalse(contract.playable(*args))
        self.assertTrue(contract.playable(*args, verified_owner_audition=True))
        self.assertFalse(contract.playable(*args[:-1], "b" * 64, verified_owner_audition=True))
        p["owner_audition"]["package_sha256"] = "c" * 64
        with self.assertRaises(ValueError):
            contract.playable(*args, verified_owner_audition=True)

    def test_invalid_or_ambiguous_registry_rejected(self):
        for mutate in (lambda d: d["vehicles"][0].update(readiness_status="MODEL_READY"),
                       lambda d: d["vehicles"][0].update(verification_status="PASS"),
                       lambda d: d["vehicles"][0].update(catalog_status="TARGET_LOCKED"),
                       lambda d: d["vehicles"][1].update(legacy_key=d["vehicles"][0]["legacy_key"])):
            doc = copy.deepcopy(self.registry)
            mutate(doc)
            with self.assertRaises(ValueError):
                contract.validate_registry(doc)

    def test_readiness_transitions_require_evidence_and_audit(self):
        self.assertFalse(contract.valid_transition("SPEC_UNVERIFIED", "MODEL_INCOMPLETE", evidence_verified=True))
        self.assertFalse(contract.valid_transition("MODEL_INCOMPLETE", "MODEL_VALIDATED"))
        self.assertTrue(contract.valid_transition("MODEL_INCOMPLETE", "MODEL_VALIDATED", evidence_verified=True))
        self.assertFalse(contract.valid_transition("ACOUSTIC_CALIBRATED", "SPEC_UNVERIFIED"))
        self.assertTrue(contract.valid_transition("ACOUSTIC_CALIBRATED", "SPEC_UNVERIFIED", audited_regression=True))
        self.assertFalse(contract.valid_transition("SPEC_UNVERIFIED", "MODEL_VALIDATED", evidence_verified=True))

    def test_frozen_pinset_readonly_and_negative_cases(self):
        self.assertEqual(contract.verify_frozen()["status"], "BLOCKED")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {"schema_version": "1.0", "source_commit": "a" * 40, "files": {}}
            for n in range(1, 5):
                data = f"synthetic trajectory {n}".encode()
                (root / f"t{n}.json").write_bytes(data)
                manifest["files"][f"T{n}"] = {"path": f"t{n}.json", "sha256": hashlib.sha256(data).hexdigest()}
            path = root / "manifest.json"
            def save(doc):
                data = json.dumps(doc, sort_keys=True).encode()
                path.write_bytes(data)
                return hashlib.sha256(data).hexdigest()
            pin = save(manifest)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            result = contract.verify_frozen(root, path, pin, "a" * 40)
            self.assertEqual(result["status"], "VERIFIED_PINSET")
            self.assertEqual(result["official_authority"], "NOT_VERIFIED")
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            for pinned, commit in (("b" * 64, "a" * 40), (pin, "b" * 40)):
                with self.assertRaises(ValueError):
                    contract.verify_frozen(root, path, pinned, commit)
            for mutation in (lambda d: d["files"]["T1"].update(path="../outside"),
                             lambda d: d["files"]["T1"].update(path="C:/outside"),
                             lambda d: d["files"]["T2"].update(path="t1.json"),
                             lambda d: d["files"]["T1"].update(sha256="b" * 64),
                             lambda d: d["files"].pop("T4")):
                bad = copy.deepcopy(manifest)
                mutation(bad)
                with self.assertRaises(ValueError):
                    contract.verify_frozen(root, path, save(bad), "a" * 40)

    def test_explicit_cold_and_hot_and_no_overwrite(self):
        points = [{"time_s": 0, "rpm": 0, "load": 0.2, "throttle": 0.1, "gear": 1},
                  {"time_s": 1, "rpm": 1000, "load": 0.3, "throttle": 0.2, "gear": 2}]
        recipe = {"scenario_id": "C0", "start_mode": "START_COLD", "points": points}
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            out = contract.generate(recipe, a)
            self.assertEqual(out, Path(a) / "generated" / "C0" / "scenario_config.json")
            self.assertEqual(contract.read_json(out)["scenario_config"]["start_mode"], "START_COLD")
            self.assertEqual(out.read_bytes(), contract.generate(recipe, b).read_bytes())
            before = out.read_bytes()
            with self.assertRaises(FileExistsError):
                contract.generate(recipe, a)
            self.assertEqual(out.read_bytes(), before)
            hot = dict(recipe, scenario_id="H_rx7_fd", start_mode="HOT")
            self.assertTrue(contract.generate(hot, a).is_file())
            for bad in (dict(recipe, scenario_id="T1"), dict(recipe, scenario_id="../T1"), dict(recipe, start_mode="HOT"), dict(recipe, points=[points[1], points[0]]), dict(recipe, points=[points[0], dict(points[1], load=float("nan"))]), dict(recipe, points=[points[0], dict(points[1], gear=1.5)]), dict(recipe, points=[points[0], dict(points[1], acceleration_mps2=0)])):
                with self.assertRaises(ValueError):
                    contract.generate(bad, a)

    def test_duplicate_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            for content in ('{"a":1,"a":2}', '{"a":NaN}'):
                p.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    contract.read_json(p)


if __name__ == "__main__":
    unittest.main()
