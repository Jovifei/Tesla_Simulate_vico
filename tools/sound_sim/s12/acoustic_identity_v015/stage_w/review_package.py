"""Local, source-free Stage-W architecture review package."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np

from ..stage_v.io import read_pcm24_wav, sha256_file, write_json
from .bakeoff import SCENES

_EXECUTABLE = ("P1", "P2", "P2H", "P3", "P5")
_CASE_FILES = (
    "raw_source.wav", "post_ptr_raw.wav", "monitor.wav",
    "state_trace.json", "phase_trace.json", "event_trace.json",
    "path_trace.json", "gain_trace.json", "metrics.json",
    "cpu_memory_latency.json", "sha256_manifest.json",
)


def _files(root: Path) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "package_manifest.json"
    ]


def build_stage_w_review_package(source_root: str | Path, output_root: str | Path) -> dict[str, Any]:
    """Copy only local synthetic bake-off evidence into a human-review package."""
    source = Path(source_root)
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty review package: {root}")
    bakeoff = json.loads((source / "bakeoff_results.json").read_text(encoding="utf-8"))
    if bakeoff.get("selected_architecture") is not None:
        raise ValueError("Stage-W package builder accepts only an unselected bake-off")
    if bakeoff.get("status") == "REFERENCE_TARGET_MISSING" or bakeoff.get("reference_status") == "REFERENCE_POINTER_ONLY":
        raise ValueError("review package prohibited until candidate selection and R1 qualification")
    root.mkdir(parents=True, exist_ok=True)
    package: dict[str, Any] = {
        "schema_version": "s12.stage_w.review_package.v1",
        "status": "WAITING_FOR_JOVI_ARCHITECTURE_REVIEW",
        "reference_status": "REFERENCE_POINTER_ONLY",
        "selected_architecture": None,
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction; NOT_R1_QUALIFIED; NOT_PROFILE_FREEZE_READY",
        "source_bakeoff_manifest_sha256": sha256_file(source / "bakeoff_manifest.json"),
        "requested_duration_s": bakeoff["requested_duration_s"],
        "long_window": bakeoff.get("long_window", False),
        "scene_duration_s": bakeoff.get("scene_duration_s", {}),
        "block_aligned_duration_s": bakeoff["block_aligned_duration_s"],
        "vehicles": {"hellcat": {"architectures": {}}},
    }
    for architecture in _EXECUTABLE:
        records: dict[str, Any] = {}
        for scene in SCENES:
            source_case = source / architecture / scene
            destination = root / "vehicles" / "hellcat" / architecture / scene
            destination.mkdir(parents=True, exist_ok=True)
            copied: dict[str, str] = {}
            for name in _CASE_FILES:
                shutil.copy2(source_case / name, destination / name)
                copied[name] = (destination / name).relative_to(root).as_posix()
            records[scene] = copied
        package["vehicles"]["hellcat"]["architectures"][architecture] = records
    write_json(root / "reference_pointer.json", {
        "status": "REFERENCE_TARGET_MISSING",
        "selection_allowed": False,
        "reason": "No legal, rights-bound and RPM/state-synchronised Reference is available.",
        "scope": package["scope"],
    })
    unavailable = {name: bakeoff["architectures"][name] for name in ("P4", "P6")}
    write_json(root / "unavailable_paths.json", unavailable)
    (root / "README_ZH.md").write_text(
        "# S12 Stage W 架构试听包\n\n"
        "状态：`WAITING_FOR_JOVI_ARCHITECTURE_REVIEW`，未选择架构。\n\n"
        "包内所有 WAV 为本地 synthetic 输出。每个场景有 P1、P2、P2H、P3、P5 的 Raw、Post-PTR Raw 和 Monitor；"
        "Raw 只用于分析，Monitor 只用于试听。Reference 仅是缺失指针，P4/P6 在 `unavailable_paths.json` 中说明原因，"
        "不含第三方音频、模型或预设。\n",
        encoding="utf-8", newline="\n",
    )
    package["files"] = _files(root)
    write_json(root / "package_manifest.json", package)
    errors = validate_stage_w_review_package(root)
    if errors:
        raise ValueError("review package validation failed: " + "; ".join(errors))
    return package


def validate_stage_w_review_package(root: str | Path) -> list[str]:
    root = Path(root)
    manifest_path = root / "package_manifest.json"
    if not manifest_path.is_file():
        return ["package_manifest.json missing"]
    package = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if package.get("status") == "WAITING_FOR_JOVI_ARCHITECTURE_REVIEW" and package.get("selected_architecture") is None and package.get("reference_status") == "REFERENCE_POINTER_ONLY":
        errors.append("stale_waiting_audition")
    if package.get("status") != "WAITING_FOR_JOVI_ARCHITECTURE_REVIEW":
        errors.append("status")
    if package.get("reference_status") != "REFERENCE_POINTER_ONLY" or package.get("selected_architecture") is not None:
        errors.append("selection_gate")
    pointer_path = root / "reference_pointer.json"
    if not pointer_path.is_file():
        errors.append("reference_pointer")
    else:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer.get("status") != "REFERENCE_TARGET_MISSING" or pointer.get("selection_allowed") is not False:
            errors.append("reference_pointer_gate")
    unavailable_path = root / "unavailable_paths.json"
    if not unavailable_path.is_file():
        errors.append("unavailable_paths")
    else:
        unavailable = json.loads(unavailable_path.read_text(encoding="utf-8"))
        required = {"P4": "REFERENCE_RECORDING_RIGHTS_PENDING", "P6": "TEACHER_NOT_RUNTIME_CANDIDATE"}
        for architecture, status in required.items():
            if unavailable.get(architecture, {}).get("status") != status:
                errors.append(f"unavailable:{architecture}")
    for architecture in _EXECUTABLE:
        for scene in SCENES:
            record = package.get("vehicles", {}).get("hellcat", {}).get("architectures", {}).get(architecture, {}).get(scene)
            if not record:
                errors.append(f"record:{architecture}/{scene}")
                continue
            try:
                raw, raw_meta = read_pcm24_wav(root / record["raw_source.wav"])
                post, post_meta = read_pcm24_wav(root / record["post_ptr_raw.wav"])
                monitor, monitor_meta = read_pcm24_wav(root / record["monitor.wav"])
                if raw.shape[0] != post.shape[0] or post.shape[0] != monitor.shape[0]:
                    errors.append(f"frames:{architecture}/{scene}")
                if max(raw_meta["clipping"], post_meta["clipping"], monitor_meta["clipping"]) != 0:
                    errors.append(f"clipping:{architecture}/{scene}")
                if architecture != "P1" and np.array_equal(post, monitor):
                    errors.append(f"monitor:{architecture}/{scene}")
            except (OSError, KeyError, ValueError) as exc:
                errors.append(f"wav:{architecture}/{scene}:{exc}")
    for item in package.get("files", []):
        path = root / str(item.get("path", ""))
        if not path.is_file():
            errors.append(f"missing:{item.get('path')}")
        elif sha256_file(path) != item.get("sha256"):
            errors.append(f"sha:{item.get('path')}")
    return errors


__all__ = ["build_stage_w_review_package", "validate_stage_w_review_package"]
