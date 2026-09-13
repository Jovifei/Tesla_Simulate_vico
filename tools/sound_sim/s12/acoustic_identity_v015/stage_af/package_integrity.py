"""Contracts for Stage AF-R package identity and publication safety.

This module deliberately stays outside the audio renderer.  It hashes the
inputs and outputs surrounding the existing renderer, validates fit/reference
identity, and publishes only a fully staged package into a new directory.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parents[4]
PACKAGE_MANIFEST_SCHEMA = "s12.stage_af.package_manifest.v1"
DASHBOARD_CONTRACT_SCHEMA = "s12.stage_af.dashboard_contract.v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,95}$")


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def validate_identifier(value: str, field_name: str) -> str:
    candidate = str(value)
    if not _SAFE_ID.fullmatch(candidate):
        raise ValueError(f"invalid {field_name}: {candidate!r}")
    return candidate


def seal_payload(payload: Mapping[str, Any], schema: str) -> dict[str, Any]:
    """Return a payload with a non-recursive self-checksum field."""
    sealed = dict(payload)
    sealed.pop("contract_sha256", None)
    sealed.pop("manifest_sha256", None)
    sealed["schema"] = str(schema)
    checksum_field = "manifest_sha256" if "manifest" in str(schema) else "contract_sha256"
    sealed[checksum_field] = hashlib.sha256(canonical_json_bytes(sealed)).hexdigest()
    return sealed


def seal_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    return seal_payload(contract, DASHBOARD_CONTRACT_SCHEMA)


def artifact_record(path: str | Path, root: str | Path, role: str) -> dict[str, str]:
    file_path = Path(path).resolve()
    root_path = Path(root).resolve()
    return {
        "path": file_path.relative_to(root_path).as_posix(),
        "role": str(role),
        "sha256": sha256_file(file_path),
    }


def validate_artifacts(records: Sequence[Mapping[str, Any]], root: str | Path) -> None:
    root_path = Path(root).resolve()
    for record in records:
        relative = str(record.get("path", ""))
        path = (root_path / relative).resolve()
        if root_path not in path.parents and path != root_path:
            raise ValueError(f"artifact escapes package root: {relative}")
        actual = sha256_file(path)
        expected = str(record.get("sha256", "")).lower()
        if actual != expected:
            raise ValueError(f"artifact SHA mismatch: {relative}")


def _fingerprint_paths(paths: Sequence[Path]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        records.append(
            {
                "path": resolved.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": sha256_file(resolved),
            }
        )
    return sorted(records, key=lambda item: item["path"])


def audio_runtime_fingerprint() -> list[dict[str, str]]:
    """Files whose implementation changes can alter rendered PCM bytes."""
    return _fingerprint_paths(
        (
            PACKAGE_ROOT.parent / "stage_ad" / "engine_sim_acoustics.py",
            PACKAGE_ROOT / "partitioned_convolver.py",
        )
    )


def fit_algorithm_fingerprint() -> list[dict[str, str]]:
    """Files whose objective/search/guard changes invalidate a fit."""
    return _fingerprint_paths(
        (
            PACKAGE_ROOT / "physical_closed_loop.py",
            PACKAGE_ROOT / "spectral_guard.py",
            PACKAGE_ROOT / "fit_cli.py",
        )
    )


def package_ui_fingerprint() -> list[dict[str, str]]:
    """Dashboard/package/service files; these do not invalidate a fit."""
    return _fingerprint_paths(
        (
            PACKAGE_ROOT / "package_integrity.py",
            PACKAGE_ROOT / "build_existing_dashboards.py",
            PACKAGE_ROOT.parent / "stage_ad" / "build_unified_dashboards.py",
            PACKAGE_ROOT.parent / "stage_ad" / "audition_dashboard_template.html",
            REPOSITORY_ROOT / "review_packages" / "serve_dashboards.py",
        )
    )


def dependency_fingerprint() -> dict[str, list[dict[str, str]]]:
    """Return explicit runtime/fit/UI identity scopes."""
    return {
        "audio_runtime_fingerprint": audio_runtime_fingerprint(),
        "fit_algorithm_fingerprint": fit_algorithm_fingerprint(),
        "package_ui_fingerprint": package_ui_fingerprint(),
    }


def fit_identity_projection(identity: Mapping[str, Any]) -> dict[str, Any]:
    """Project renderer identity to fields that can invalidate a fit.

    Package UI/template/service changes are intentionally excluded so a page
    correction does not force an otherwise byte-identical fit to be rerun.
    """
    fields = (
        "vehicle",
        "sample_rate",
        "renderer",
        "source_sha256",
        "ir_source_path",
        "ir_source_sha256",
        "ir_effective_sha256",
        "ir_provenance",
        "ir_rights_status",
        "numerical_fixes",
        "audio_runtime_fingerprint",
        "fit_algorithm_fingerprint",
    )
    return {field: identity.get(field) for field in fields}


def _fit_checksum(payload: Mapping[str, Any]) -> tuple[str, str]:
    canonical = dict(payload)
    checksum = canonical.pop("fit_sha256", None)
    encoded = canonical_json_bytes(canonical)
    return str(checksum or ""), hashlib.sha256(encoded).hexdigest()


def snapshot_fit_file(source: str | Path, snapshot: str | Path) -> dict[str, str]:
    """Copy exact fit JSON bytes into an immutable package evidence path."""
    source_path = Path(source)
    snapshot_path = Path(snapshot)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = source_path.read_bytes()
    snapshot_path.write_bytes(source_bytes)
    restored = validate_fit_snapshot(snapshot_path)
    return {
        "source_path": str(source_path.resolve()),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "snapshot_path": str(snapshot_path.resolve()),
        "snapshot_sha256": restored["snapshot_sha256"],
        "schema": restored["schema"],
        "fit_sha256": restored["fit_sha256"],
    }


def validate_fit_snapshot(snapshot: str | Path) -> dict[str, str]:
    """Validate a copied fit using only its own bytes (source may be gone)."""
    snapshot_path = Path(snapshot)
    if not snapshot_path.is_file():
        raise FileNotFoundError(snapshot_path)
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"fit snapshot is not valid JSON: {snapshot_path}") from exc
    if payload.get("schema") != "s12.stage_af.physical_fit.v5":
        raise ValueError("fit snapshot schema mismatch")
    if not isinstance(payload.get("fit_identity"), Mapping):
        raise ValueError("fit snapshot identity missing")
    recorded, calculated = _fit_checksum(payload)
    if not recorded or recorded != calculated:
        raise ValueError("fit snapshot checksum mismatch")
    return {
        "snapshot_path": str(snapshot_path.resolve()),
        "snapshot_sha256": sha256_file(snapshot_path),
        "schema": str(payload["schema"]),
        "fit_sha256": recorded,
    }


def git_source_receipt(
    *,
    allow_dirty_dev: bool = False,
    additional_paths: Sequence[str | Path] = (),
) -> dict[str, Any]:
    """Capture Git provenance and enforce clean tracked sources by default."""
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    try:
        remote = git("config", "--get", "remote.origin.url")
        git_head = git("rev-parse", "HEAD")
        base_main = git("rev-parse", "origin/main")
        scopes = dependency_fingerprint()
        additional = []
        for path in additional_paths:
            resolved = Path(path).resolve()
            if not resolved.is_file():
                raise FileNotFoundError(resolved)
            additional.append(
                {
                    "path": resolved.relative_to(REPOSITORY_ROOT).as_posix(),
                    "sha256": sha256_file(resolved),
                }
            )
        scopes["additional_dependency_fingerprint"] = sorted(
            additional, key=lambda item: item["path"]
        )
        tracked_paths = sorted(
            {
                entry["path"]
                for entries in scopes.values()
                for entry in entries
            }
        )
        dirty_output = git(
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *tracked_paths,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("could not capture Git source receipt") from exc
    repository = remote
    if remote.startswith("https://github.com/"):
        repository = remote.removeprefix("https://github.com/")
    elif remote.startswith("git@github.com:"):
        repository = remote.removeprefix("git@github.com:")
    if repository.endswith(".git"):
        repository = repository[:-4]
    dependency_dirty = bool(dirty_output)
    if dependency_dirty and not allow_dirty_dev:
        raise ValueError(
            "tracked source is dirty; use --allow-dirty-dev for a non-promotable smoke"
        )
    return {
        "repository": repository,
        "git_head": git_head,
        "base_main": base_main,
        "dependency_dirty": dependency_dirty,
        "dependency_dirty_paths": [
            line[3:].strip()
            for line in dirty_output.splitlines()
            if len(line) >= 4
        ],
        "source_policy": (
            "DEV_DIRTY_SOURCE / NOT_PROMOTABLE"
            if dependency_dirty
            else "TRACKED_SOURCE_CLEAN_REQUIRED"
        ),
        "source_status": "DEV_DIRTY_SOURCE" if dependency_dirty else "SOURCE_CLEAN",
        "promotable": not dependency_dirty,
        "promotion_status": "NOT_PROMOTABLE" if dependency_dirty else "PROMOTABLE",
        "source_dependency_fingerprint": scopes,
        "source_dependency_paths": tracked_paths,
    }


def h0_oracle_cases(duration: float) -> dict[str, dict[str, Any]]:
    """Return deterministic steady/body, shift and afterfire windows."""
    duration = float(duration)
    if duration <= 0.0:
        raise ValueError("duration must be positive")
    return {
        "steady_body": {"shift_events": None, "afterfire_events": None},
        "shift": {
            "shift_events": [(duration * 0.55, min(0.12, duration * 0.1))],
            "afterfire_events": None,
        },
        "afterfire": {
            "shift_events": None,
            "afterfire_events": [(duration * 0.70, 0.40)],
        },
    }


def validate_reference_sources(
    actual: Mapping[str, Mapping[str, Any]],
    expected: Mapping[str, Mapping[str, Any]],
    *,
    required_scenes: Sequence[str] | None = None,
) -> None:
    """Require current source bytes to equal fit-recorded reference bytes."""
    required = tuple(required_scenes or expected.keys())
    for scene in required:
        expected_entry = expected.get(scene)
        actual_entry = actual.get(scene)
        if not expected_entry or not actual_entry:
            raise ValueError(f"fit reference missing: {scene}")
        expected_name = str(expected_entry.get("filename", ""))
        actual_name = str(actual_entry.get("filename", ""))
        if expected_name != actual_name:
            raise ValueError(f"fit reference filename mismatch: {scene}")
        expected_sha = str(expected_entry.get("sha256", "")).lower()
        actual_sha = str(actual_entry.get("sha256", "")).lower()
        if not expected_sha or expected_sha != actual_sha:
            raise ValueError(f"fit reference SHA mismatch: {scene}")


def publish_staged_package(staging_root: str | Path, published_root: str | Path) -> Path:
    """Atomically rename a validated fresh staging directory into publication."""
    staging = Path(staging_root)
    published = Path(published_root)
    if not staging.is_dir():
        raise FileNotFoundError(staging)
    if published.exists():
        raise FileExistsError(f"published package already exists: {published}")
    published.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(published)
    return published


def _load_legacy_module(commit: str):
    relative = "tools/sound_sim/s12/acoustic_identity_v015/stage_ad/engine_sim_acoustics.py"
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    with tempfile.TemporaryDirectory(prefix="s12-h0-legacy-") as temp_dir:
        legacy_path = Path(temp_dir) / "engine_sim_acoustics_legacy.py"
        legacy_path.write_text(result.stdout, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("s12_h0_legacy", legacy_path)
        if spec is None or spec.loader is None:
            raise ImportError("could not load legacy EngineAcoustics module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def compare_h0_with_legacy(
    legacy_commit: str,
    vehicle: str,
    rpm: np.ndarray,
    throttle: np.ndarray,
    *,
    duration: float,
    seed: int,
) -> bool:
    """Compare current empty-fix output with a fixed pre-fix Git oracle."""
    from ..stage_ad import engine_sim_acoustics as current_module

    current = current_module.EngineAcoustics(vehicle_type=vehicle, sr=48_000, numerical_fixes=())
    reference_ir = np.asarray(current.ir, dtype=np.float64).copy()
    legacy_module = _load_legacy_module(legacy_commit)
    legacy_module.load_impulse_response = lambda *args, **kwargs: reference_ir.copy()
    legacy = legacy_module.EngineAcoustics(vehicle_type=vehicle, sr=48_000)
    random_state = np.random.get_state()
    try:
        for case in h0_oracle_cases(duration).values():
            np.random.seed(seed)
            current_pcm = current.render_track(rpm, throttle, duration, **case)
            np.random.seed(seed)
            legacy_pcm = legacy.render_track(rpm, throttle, duration, **case)
            if not np.array_equal(current_pcm, legacy_pcm):
                return False
        return True
    finally:
        np.random.set_state(random_state)
