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


def dependency_fingerprint() -> list[dict[str, str]]:
    """Hash every source file that can affect Stage AF-R rendered bytes."""
    paths = (
        PACKAGE_ROOT.parent / "stage_ad" / "engine_sim_acoustics.py",
        PACKAGE_ROOT / "physical_closed_loop.py",
        PACKAGE_ROOT / "partitioned_convolver.py",
        PACKAGE_ROOT / "spectral_guard.py",
        PACKAGE_ROOT / "build_existing_dashboards.py",
        PACKAGE_ROOT.parent / "stage_ad" / "build_unified_dashboards.py",
        PACKAGE_ROOT.parent / "stage_ad" / "audition_dashboard_template.html",
    )
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
    kwargs = {
        "shift_events": [(duration * 0.55, min(0.12, duration * 0.1))],
        "afterfire_events": [(duration * 0.70, 0.40)],
    }
    np.random.seed(seed)
    current_pcm = current.render_track(rpm, throttle, duration, **kwargs)
    np.random.seed(seed)
    legacy_pcm = legacy.render_track(rpm, throttle, duration, **kwargs)
    return bool(np.array_equal(current_pcm, legacy_pcm))
