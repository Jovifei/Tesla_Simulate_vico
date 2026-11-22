"""Standalone v1.4 research contract; no audio engine or product integration."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
ID = re.compile(r"^[a-z0-9_]+$")
SHA = re.compile(r"^[0-9a-f]{64}$")
READINESS = {"SPEC_UNVERIFIED", "SPEC_VERIFIED", "MODEL_INCOMPLETE", "MODEL_VALIDATED", "ACOUSTIC_CALIBRATED"}


def parse_json(text):
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=reject_duplicates, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return parse_json(stream.read())


def exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{where}: unexpected or missing keys")


def identifier(value):
    return isinstance(value, str) and bool(ID.fullmatch(value))


def digest(value):
    return isinstance(value, str) and bool(SHA.fullmatch(value))


def validate_registry(doc):
    exact(doc, ("schema_version", "vehicles"), "registry")
    if doc["schema_version"] != "1.0" or not isinstance(doc["vehicles"], list):
        raise ValueError("invalid registry version or vehicles")
    ids, legacy, packages = set(), set(), set()
    for v in doc["vehicles"]:
        exact(v, ("vehicle_id", "display_name", "catalog_status", "readiness_status", "template_id", "legacy_key", "sound_packages"), "vehicle")
        if not identifier(v["vehicle_id"]) or v["vehicle_id"] in ids or not isinstance(v["display_name"], str) or not v["display_name"].strip():
            raise ValueError("invalid or duplicate vehicle identity")
        ids.add(v["vehicle_id"])
        if v["catalog_status"] not in {None, "TARGET_LOCKED", "TEMPLATE_RESERVED"}:
            raise ValueError("invalid catalog status")
        if v["catalog_status"] == "TARGET_LOCKED" and v["template_id"] is None:
            raise ValueError("locked target requires a template mapping")
        if v["readiness_status"] not in READINESS and not (v["catalog_status"] == "TEMPLATE_RESERVED" and v["readiness_status"] is None):
            raise ValueError("invalid readiness")
        for key in ("template_id", "legacy_key"):
            if v[key] is not None and not identifier(v[key]):
                raise ValueError(f"invalid {key}")
        if v["legacy_key"] is not None:
            if v["legacy_key"] in legacy:
                raise ValueError("ambiguous legacy key")
            legacy.add(v["legacy_key"])
        if not isinstance(v["sound_packages"], list):
            raise ValueError("invalid packages")
        for p in v["sound_packages"]:
            exact(p, ("route_id", "package_id", "package_sha256", "owner_audition"), "package")
            if not identifier(p["route_id"]) or not identifier(p["package_id"]) or (p["package_sha256"] is not None and not digest(p["package_sha256"])):
                raise ValueError("invalid package identity")
            key = (v["vehicle_id"], p["route_id"], p["package_id"])
            if key in packages:
                raise ValueError("duplicate package")
            packages.add(key)
            a = p["owner_audition"]
            exact(a, ("status", "route_id", "package_id", "package_sha256", "evidence_ref"), "owner audition")
            if a["status"] not in {"NOT_RUN", "PASS", "FAIL"}:
                raise ValueError("invalid audition status")
            if a["status"] == "PASS" and not (p["package_sha256"] and a["route_id"] == p["route_id"] and a["package_id"] == p["package_id"] and a["package_sha256"] == p["package_sha256"] and isinstance(a["evidence_ref"], str) and a["evidence_ref"].strip()):
                raise ValueError("PASS evidence does not bind exact package")
            if a["status"] != "PASS" and any(a[k] is not None for k in ("route_id", "package_id", "package_sha256", "evidence_ref")):
                raise ValueError("non-PASS evidence fields must be null")
    return doc


def playable(registry, vehicle_id, route_id, package_id, actual_sha256, verified_owner_audition=False):
    validate_registry(registry)
    # The caller must independently authenticate owner evidence for these bytes.
    if verified_owner_audition is not True or not digest(actual_sha256):
        return False
    for v in registry["vehicles"]:
        if v["vehicle_id"] != vehicle_id or v["catalog_status"] != "TARGET_LOCKED" or v["readiness_status"] != "ACOUSTIC_CALIBRATED":
            continue
        for p in v["sound_packages"]:
            if p["route_id"] == route_id and p["package_id"] == package_id and p["package_sha256"] == actual_sha256 and p["owner_audition"]["status"] == "PASS":
                return True
    return False


def valid_transition(before, after, evidence_verified=False, audited_regression=False):
    if before not in READINESS or after not in READINESS:
        return False
    if before == after:
        return True
    forward = {("SPEC_UNVERIFIED", "SPEC_VERIFIED"), ("SPEC_VERIFIED", "MODEL_INCOMPLETE"), ("SPEC_VERIFIED", "MODEL_VALIDATED"), ("MODEL_INCOMPLETE", "MODEL_VALIDATED"), ("MODEL_VALIDATED", "ACOUSTIC_CALIBRATED")}
    if (before, after) in forward:
        return evidence_verified is True
    ranks = {"SPEC_UNVERIFIED": 0, "SPEC_VERIFIED": 1, "MODEL_INCOMPLETE": 2, "MODEL_VALIDATED": 3, "ACOUSTIC_CALIBRATED": 4}
    return ranks[after] < ranks[before] and audited_regression is True


def verify_frozen(root=None, manifest_path=None, manifest_sha256=None, source_commit=None):
    if all(value is None for value in (root, manifest_path, manifest_sha256, source_commit)):
        return {"status": "BLOCKED", "reason": "authoritative T1-T4 paths and declared SHA-256 unavailable"}
    if any(value is None for value in (root, manifest_path, manifest_sha256, source_commit)) or not digest(manifest_sha256) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("root, manifest, SHA-256 pin and 40-digit source commit are all required")
    data = Path(manifest_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest_sha256:
        raise ValueError("manifest SHA-256 pin mismatch")
    manifest = parse_json(data.decode("utf-8"))
    exact(manifest, ("schema_version", "source_commit", "files"), "frozen manifest")
    if manifest["schema_version"] != "1.0" or manifest["source_commit"] != source_commit:
        raise ValueError("manifest version or source commit mismatch")
    exact(manifest["files"], ("T1", "T2", "T3", "T4"), "frozen files")
    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise ValueError("root must be a directory")
    seen, observed = set(), {}
    for name in ("T1", "T2", "T3", "T4"):
        entry = manifest["files"][name]
        exact(entry, ("path", "sha256"), name)
        relative = entry["path"]
        if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
            raise ValueError("unsafe relative path")
        posix = PurePosixPath(relative)
        if posix.is_absolute() or relative != posix.as_posix() or any(part in (".", "..") for part in posix.parts) or not digest(entry["sha256"]):
            raise ValueError("unsafe path or invalid hash")
        path = root_path.joinpath(*posix.parts).resolve(strict=True)
        if not path.is_relative_to(root_path) or not path.is_file() or path in seen:
            raise ValueError("outside root, missing, or duplicate path")
        seen.add(path)
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != entry["sha256"]:
            raise ValueError(f"{name} SHA-256 mismatch")
        observed[name] = {"path": relative, "sha256": h.hexdigest()}
    return {"status": "VERIFIED_PINSET", "scope": "CALLER_SUPPLIED_PINSET_ONLY", "official_authority": "NOT_VERIFIED", "source_commit": source_commit, "manifest_sha256": manifest_sha256, "files": observed}


def planned_matrix(registry):
    validate_registry(registry)
    cases, h_cases = [], []
    for vehicle in registry["vehicles"]:
        for package in vehicle["sound_packages"]:
            identity = {"vehicle_id": vehicle["vehicle_id"], "route_id": package["route_id"], "package_id": package["package_id"]}
            for scenario in ("T1", "T2", "T3", "T4", "C0"):
                cases.append({**identity, "scenario_id": scenario, "capture_status": "NOT_RUN"})
            h_cases.append({**identity, "scenario_id": "H_" + vehicle["vehicle_id"], "capture_status": "NOT_RUN"})
    return {"schema_version": "1.0", "kind": "PLAN_NOT_EVIDENCE", "formal_cases": cases, "h_cases_outside_formal_matrix": h_cases, "gates": {"owner_audition": "NOT_RUN", "speaker": "NOT_RUN", "static_cabin": "NOT_RUN", "dynamic_vehicle": "NOT_RUN"}}


def number(x):
    return type(x) is int or (type(x) is float and math.isfinite(x))


def generate(recipe, output_root):
    exact(recipe, ("scenario_id", "start_mode", "points"), "recipe")
    name, mode, points = recipe["scenario_id"], recipe["start_mode"], recipe["points"]
    if not isinstance(name, str) or not re.fullmatch(r"(?:C0(?:_[a-z0-9_]+)?|H_[a-z0-9_]+)", name):
        raise ValueError("only C0, C0_<vehicleId> and H_<vehicleId> are accepted")
    if mode != ("START_COLD" if name.startswith("C0") else "HOT"):
        raise ValueError("scenario start mode mismatch")
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("at least two explicitly prescribed points required")
    previous = -1
    for p in points:
        exact(p, ("time_s", "rpm", "load", "throttle", "gear"), "point")
        if not all(number(x) for x in p.values()) or type(p["gear"]) is not int or p["time_s"] <= previous or p["rpm"] < 0 or not 0 <= p["load"] <= 1 or not 0 <= p["throttle"] <= 1:
            raise ValueError("invalid point, range or time ordering")
        previous = p["time_s"]
    if points[0]["time_s"] != 0:
        raise ValueError("time must begin at zero")
    out = {"schema_version": "1.0", "source_status": "EXPLICIT_UNVERIFIED_PRESCRIPTION", "scenario_config": {"scenario_id": name, "start_mode": mode}, "points": points}
    target_dir = Path(output_root) / "generated" / name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "scenario_config.json"
    data = (json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with open(target, "xb") as stream:
        try:
            if stream.write(data) != len(data):
                raise OSError("short write")
        except BaseException:
            stream.close()
            target.unlink()
            raise
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-registry")
    check.add_argument("path", nargs="?", default=str(HERE / "vehicle-registry.json"))
    matrix = sub.add_parser("matrix")
    matrix.add_argument("path", nargs="?", default=str(HERE / "vehicle-registry.json"))
    frozen = sub.add_parser("check-frozen")
    frozen.add_argument("--root")
    frozen.add_argument("--manifest")
    frozen.add_argument("--manifest-sha256")
    frozen.add_argument("--source-commit")
    gen = sub.add_parser("generate")
    gen.add_argument("recipe")
    gen.add_argument("output_root")
    args = parser.parse_args()
    try:
        if args.command == "check-registry":
            validate_registry(read_json(args.path))
            print(json.dumps({"status": "PASS", "scope": "registry structure only"}))
            return 0
        if args.command == "check-frozen":
            result = verify_frozen(args.root, args.manifest, args.manifest_sha256, args.source_commit)
            print(json.dumps(result, ensure_ascii=False))
            return 2 if result["status"] == "BLOCKED" else 0
        if args.command == "matrix":
            print(json.dumps(planned_matrix(read_json(args.path)), ensure_ascii=False, indent=2))
            return 0
        print(generate(read_json(args.recipe), args.output_root))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
