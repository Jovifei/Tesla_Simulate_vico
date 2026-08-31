"""External v27 stage verification and atomic Hellcat bake-off publication."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
from collections.abc import Mapping
from typing import Any

from .bakeoff import (
    PLACEHOLDER_RECORDS,
    RENDERABLE_ARCHITECTURES,
    SCENES,
    STATE_RATE_HZ,
    SUMMARY_FILES,
    _ablation_results,
    _parent_candidate_metrics,
    scene_duration_s,
    validate_bakeoff_manifest,
    validate_hellcat_architecture_stage,
)
from ..stage_v.io import sha256_file, write_json


def _path_exists(path: Path) -> bool:
    """Include dangling symlinks in the absence/existence contract."""
    return os.path.lexists(os.fspath(path))


def _is_equal_or_descendant(path: Path, root: Path) -> bool:
    """Compare resolved paths without allowing string-prefix false positives."""
    path_name = os.path.normcase(os.fspath(path))
    root_name = os.path.normcase(os.fspath(root))
    try:
        return os.path.commonpath((path_name, root_name)) == root_name
    except ValueError:
        return False


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify_architecture_stage(
    stage_root: str | Path,
    architecture: str,
    duration_s: float,
    *,
    long_window: bool = False,
    parent_stage_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate one complete external architecture stage without mutating it."""
    root = Path(stage_root)
    parent = parent_stage_root if architecture != "P1" else None
    errors = validate_hellcat_architecture_stage(
        root,
        architecture,
        duration_s,
        long_window=long_window,
        parent_stage_root=parent,
    )
    if errors:
        raise ValueError(f"architecture stage is not verified ({architecture}): {errors}")
    manifest = _read_json(root / "stage_manifest.json")
    result = dict(manifest)
    result["stage_root"] = str(root)
    result["stage_manifest_path"] = str(root / "stage_manifest.json")
    return result


def _architecture_record(stage_root: Path, architecture: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    files = manifest["files"]
    scenes: dict[str, Any] = {}
    for scene in SCENES:
        case = stage_root / architecture / scene
        metrics = _read_json(case / "metrics.json")
        latency = _read_json(case / "cpu_memory_latency.json")
        scenes[scene] = {
            "raw_sha256": sha256_file(case / "raw_source.wav"),
            "post_ptr_sha256": sha256_file(case / "post_ptr_raw.wav"),
            "monitor_sha256": sha256_file(case / "monitor.wav"),
            "comparison": metrics["comparison"],
            "render_seconds": latency["render_seconds"],
        }
        # Keep the stage manifest binding live while reconstructing the result.
        for filename, field in (
            ("raw_source.wav", "raw_sha256"),
            ("post_ptr_raw.wav", "post_ptr_sha256"),
            ("monitor.wav", "monitor_sha256"),
        ):
            relative = f"{architecture}/{scene}/{filename}"
            if files.get(relative) != scenes[scene][field]:
                raise ValueError(f"stage manifest hash changed during assembly: {relative}")
    return {"status": "RENDERED", "scenes": scenes}


def _reconstruct_summaries(
    build_root: Path,
    stage_roots: Mapping[str, Path],
    manifests: Mapping[str, Mapping[str, Any]],
    duration_s: float,
    long_window: bool,
) -> dict[str, Any]:
    architectures: dict[str, Any] = {name: dict(record) for name, record in PLACEHOLDER_RECORDS.items()}
    for architecture in RENDERABLE_ARCHITECTURES:
        architectures[architecture] = _architecture_record(
            stage_roots[architecture],
            architecture,
            manifests[architecture],
        )
    scene_durations = {scene: scene_duration_s(scene, duration_s, long_window=long_window) for scene in SCENES}
    block_aligned_duration_s = max(2, int(round(max(scene_durations.values()) * STATE_RATE_HZ))) / STATE_RATE_HZ
    status = "REFERENCE_TARGET_MISSING"
    reference_status = "REFERENCE_POINTER_ONLY"
    result = {
        "schema_version": "s12.stage_w.bakeoff.v1",
        "status": status,
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
        "reference_status": reference_status,
        "requested_duration_s": float(duration_s),
        "long_window": bool(long_window),
        "scene_duration_s": scene_durations,
        "block_aligned_duration_s": block_aligned_duration_s,
        "selected_architecture": None,
        "architectures": architectures,
    }
    summaries = {
        "bakeoff_results.json": result,
        "parent_candidate_metrics.json": _parent_candidate_metrics(architectures, status, reference_status),
        "ablation_results.json": _ablation_results(architectures, status, reference_status),
        "selected_architecture.json": {"selected_architecture": None, "status": status},
        "rejected_architectures.json": {
            "status": status,
            "reference_status": reference_status,
            "selected_architecture": None,
            "rejected": ["P6"],
        },
    }
    for name in SUMMARY_FILES:
        write_json(build_root / name, summaries[name])
    return result


def assemble_v27_bakeoff(
    final_root: str | Path,
    stage_roots: Mapping[str, str | Path],
    duration_s: float = 8.0,
    *,
    long_window: bool = False,
) -> dict[str, Any]:
    """Verify five external stages, assemble, validate, and atomically publish v27."""
    final = Path(final_root)
    if _path_exists(final):
        raise FileExistsError(f"refusing to overwrite v27 final root: {final}")
    if not isinstance(stage_roots, Mapping):
        raise TypeError("stage_roots must be a mapping")
    expected = set(RENDERABLE_ARCHITECTURES)
    if set(stage_roots) != expected:
        raise ValueError(
            "stage_roots must contain exactly one stage root for each "
            + "/".join(RENDERABLE_ARCHITECTURES)
        )

    normalized: dict[str, Path] = {}
    resolved_final = final.resolve(strict=False)
    resolved_stages: dict[str, Path] = {}
    seen: dict[str, str] = {}
    for architecture in RENDERABLE_ARCHITECTURES:
        try:
            root = Path(stage_roots[architecture])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid stage root for {architecture}") from exc
        identity = os.path.normcase(os.fspath(root.resolve(strict=False)))
        if identity in seen:
            raise ValueError(f"duplicate stage root for {architecture} and {seen[identity]}")
        seen[identity] = architecture
        normalized[architecture] = root
        resolved_stages[architecture] = root.resolve(strict=False)

    for architecture in RENDERABLE_ARCHITECTURES:
        if _is_equal_or_descendant(resolved_final, resolved_stages[architecture]):
            raise ValueError(f"final root is inside or equal to stage root {architecture}: {final}")

    # Complete all trust checks before creating the external build root.
    manifests: dict[str, Mapping[str, Any]] = {}
    for architecture in RENDERABLE_ARCHITECTURES:
        manifest = verify_architecture_stage(
            normalized[architecture],
            architecture,
            duration_s,
            long_window=long_window,
            parent_stage_root=normalized["P1"] if architecture != "P1" else None,
        )
        manifests[architecture] = manifest

    final.parent.mkdir(parents=True, exist_ok=True)
    build_root = Path(tempfile.mkdtemp(prefix=f".{final.name}.v27-build-", dir=os.fspath(final.parent)))
    for architecture in RENDERABLE_ARCHITECTURES:
        shutil.copytree(
            normalized[architecture] / architecture,
            build_root / architecture,
        )
    result = _reconstruct_summaries(build_root, normalized, manifests, duration_s, long_window)
    files = {
        path.relative_to(build_root).as_posix(): sha256_file(path)
        for path in sorted(build_root.rglob("*"))
        if path.is_file() and path != build_root / "bakeoff_manifest.json"
    }
    write_json(
        build_root / "bakeoff_manifest.json",
        {
            "schema_version": "s12.stage_w.bakeoff_manifest.v1",
            "status": result["status"],
            "reference_status": result["reference_status"],
            "selected_architecture": None,
            "requested_duration_s": result["requested_duration_s"],
            "long_window": result["long_window"],
            "scene_duration_s": result["scene_duration_s"],
            "block_aligned_duration_s": result["block_aligned_duration_s"],
            "files": files,
        },
    )
    errors = validate_bakeoff_manifest(build_root)
    if errors:
        raise ValueError(f"assembled v27 build root failed strict validation: {errors}")
    if _path_exists(final):
        raise FileExistsError(f"v27 final root appeared during assembly: {final}")
    os.replace(os.fspath(build_root), os.fspath(final))
    result["final_root"] = str(final)
    return result


__all__ = ["assemble_v27_bakeoff", "verify_architecture_stage"]
