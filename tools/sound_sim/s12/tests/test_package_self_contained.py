"""Validate an extracted v6 audit package without a repository checkout."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath


TEST_NAMES = [
    "test_s12_sound_playground.m",
    "test_s12_sound_playground_offline_repair.m",
    "test_s12_sound_playground_v3_static.py",
    "test_s12_sound_playground_v4_static.py",
    "test_s12_sound_playground_v5_static.py",
    "test_s12_sound_playground_v6_static.py",
    "test_s12_sound_playground_v6_contract.m",
    "test_s12_sound_playground_v7_static.py",
    "test_s12_sound_playground_v7_contract.m",
    "test_package_self_contained.py",
]
DECLARATION_FILES = [
    "S12_Simulink_Sound_Playground_v09_Offline_Repair_v7_Report.md",
    "reports/S12_Simulink_Sound_Playground_v09_Offline_Repair_v7_Report.md",
    "README.md",
    "DELIVERY.md",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def safe_package_path(root: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        raise AssertionError(f"unsafe package-relative path: {relative}")
    resolved = (root / Path(*candidate.parts)).resolve()
    if root.resolve() not in resolved.parents:
        raise AssertionError(f"path escapes package: {relative}")
    return resolved


def immutable_scope_hash(source_root: Path) -> tuple[str, int]:
    s12_root = source_root / "tools/sound_sim/s12"
    playground = s12_root / "playground"
    tests = s12_root / "tests"
    files = [*playground.glob("*.m"), *playground.glob("*.json"), *playground.glob("*.py")]
    files.extend((playground / "audit_manifests").glob("*.json"))
    files.extend(tests / name for name in TEST_NAMES)
    for path in files:
        assert path.is_file(), f"immutable source member missing: {path.relative_to(source_root)}"
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(s12_root).as_posix()):
        digest.update((path.relative_to(s12_root).as_posix() + "\n").encode())
        digest.update((sha256(path) + "\n").encode())
    return digest.hexdigest().upper(), len(files)


def assert_no_forbidden_artifacts(package_root: Path) -> None:
    forbidden_suffixes = {".wav", ".pcm"}
    forbidden_parts = {"slprj", "cache", "__pycache__", ".git"}
    forbidden = []
    for path in package_root.rglob("*"):
        relative = path.relative_to(package_root)
        lower_parts = {part.lower() for part in relative.parts}
        if path.suffix.lower() in forbidden_suffixes or lower_parts & forbidden_parts:
            forbidden.append(relative.as_posix())
        if any(part.startswith(".s12_playground_") for part in relative.parts):
            forbidden.append(relative.as_posix())
    if forbidden:
        raise AssertionError(f"forbidden audit-package artifacts: {sorted(set(forbidden))}")


def assert_canonical_source_paths(package_root: Path, source_root: Path) -> None:
    orphans = [
        path.name
        for path in package_root.iterdir()
        if path.is_file() and (path.suffix.lower() == ".m" or path.name.startswith("test_"))
    ]
    assert not orphans, f"root-level source/test copies are forbidden: {sorted(orphans)}"
    s12_root = source_root / "tools/sound_sim/s12"
    source_files = [
        *s12_root.joinpath("playground").glob("*.m"),
        *s12_root.joinpath("playground").glob("*.py"),
        *s12_root.joinpath("tests").glob("*.m"),
        *s12_root.joinpath("tests").glob("*.py"),
    ]
    duplicates = [
        name for name, count in Counter(path.name for path in source_files).items() if count > 1
    ]
    assert not duplicates, f"duplicate canonical source/test basenames: {sorted(duplicates)}"
    for path in package_root.rglob("*"):
        if path.is_file() and (path.suffix.lower() == ".m" or path.name.startswith("test_")):
            assert source_root in path.parents, (
                f"source/test outside canonical source/: {path.relative_to(package_root)}"
            )


def assert_evidence(package_root: Path, source_root: Path) -> None:
    manifest_path = (
        source_root
        / "tools/sound_sim/s12/playground/audit_manifests/evidence_identity_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in ("historical_pre_repair_invalid", "workspace_unvalidated_intermediate"):
        role = manifest[name]
        evidence = safe_package_path(package_root, role["package_relative_path"])
        assert evidence.is_file(), f"missing evidence: {name}"
        assert sha256(evidence) == role["sha256"], f"SHA mismatch: {name}"


def declared_sha(text: str, label: str) -> str:
    match = re.search(r"Immutable source SHA-256:\s*([A-F0-9]{64})", text)
    if not match:
        raise AssertionError(f"missing immutable source SHA declaration in {label}")
    return match.group(1)


def assert_identity_declarations(package_root: Path, actual_sha: str, actual_count: int) -> None:
    identity = json.loads(
        (package_root / "metadata/source_identity_manifest_v7.json").read_text(encoding="utf-8")
    )
    assert identity["immutable_source_sha256"] == actual_sha
    assert identity["immutable_file_count"] == actual_count
    declared = [identity["immutable_source_sha256"]]
    for relative in DECLARATION_FILES:
        path = safe_package_path(package_root, relative)
        assert path.is_file(), f"missing SHA declaration: {relative}"
        declared.append(declared_sha(path.read_text(encoding="utf-8"), relative))
    assert set(declared) == {actual_sha}, f"source SHA declarations disagree: {declared}"


def assert_packaging_metadata(package_root: Path) -> None:
    metadata = json.loads((package_root / "metadata/packaging_v7.json").read_text(encoding="utf-8"))
    assert metadata["packaging_os"] == "Windows PowerShell"
    assert metadata["zip_entry_separator"] == "/"
    assert metadata["fresh_extract_command"].startswith("Expand-Archive")
    assert metadata["fresh_extract_result"] == "PASS"
    entries = metadata["zip_entries"]
    assert entries and all("\\" not in entry for entry in entries)


def assert_sixth_audit_truth(package_root: Path) -> None:
    report = package_root / "reports/S12_Simulink_Playground_v09_Offline_Audit_v6_ChatGPT.md"
    descriptor = (
        package_root / "reports/S12_Simulink_Playground_v09_Offline_Audit_v6_availability.json"
    )
    if report.is_file():
        assert sha256(report) == "35647E7EFD473A49008D9E7A79A6DAF024CF39686DE59598F5FC0A78296219FC"
    else:
        state = json.loads(descriptor.read_text(encoding="utf-8"))
        assert (
            state["declared_sha256"]
            == "35647E7EFD473A49008D9E7A79A6DAF024CF39686DE59598F5FC0A78296219FC"
        )
        assert state["content_status"] == "EXTERNAL_BYTES_NOT_AVAILABLE_NOT_FABRICATED"


def main(package_root: Path) -> None:
    source_root = package_root / "source"
    assert source_root.is_dir(), "missing canonical source/"
    assert_no_forbidden_artifacts(package_root)
    assert_canonical_source_paths(package_root, source_root)
    assert_evidence(package_root, source_root)
    actual_sha, actual_count = immutable_scope_hash(source_root)
    assert_identity_declarations(package_root, actual_sha, actual_count)
    assert_packaging_metadata(package_root)
    assert_sixth_audit_truth(package_root)
    command = [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "tools.sound_sim.s12.tests.test_s12_sound_playground_v3_static",
        "tools.sound_sim.s12.tests.test_s12_sound_playground_v4_static",
        "tools.sound_sim.s12.tests.test_s12_sound_playground_v5_static",
        "tools.sound_sim.s12.tests.test_s12_sound_playground_v6_static",
        "tools.sound_sim.s12.tests.test_s12_sound_playground_v7_static",
        "-v",
    ]
    completed = subprocess.run(command, cwd=source_root, text=True, capture_output=True)
    if completed.returncode != 0:
        raise AssertionError(completed.stdout + completed.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python test_package_self_contained.py <unzipped-root>")
    main(Path(sys.argv[1]))
