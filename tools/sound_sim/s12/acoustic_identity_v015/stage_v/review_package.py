"""Chinese Stage-V review package with separate raw/monitor and blind B/C paths."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np

from .io import read_pcm24_wav, sha256_file, write_json
from .scenarios import STAGE_V_SCENARIOS

_SCOPE = "synthetic; uncalibrated; not OEM reproduction"


def _package_files(root: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in {"package_manifest.json", "blind_key_external.json"}:
            files.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)})
    return files


def build_stage_v_review_package(source_root: str | Path, output_root: str | Path) -> dict[str, object]:
    source = Path(source_root)
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty review package: {root}")
    root.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    package: dict[str, Any] = {
        "schema_version": "s12.stage_v.review_package.v1",
        "status": "WAITING_FOR_JOVI_HELLCAT_REVIEW",
        "reference_status": "REFERENCE_POINTER_ONLY",
        "scope": _SCOPE,
        "vehicle_id": "hellcat_v1",
        "source_manifest_sha256": sha256_file(source / "manifest.json"),
        "human_pass": False,
        "profile_freeze_ready": False,
        "scenarios": {},
    }
    blind_key: dict[str, str] = {}
    blind_trials: dict[str, dict[str, object]] = {}
    for scenario in STAGE_V_SCENARIOS:
        source_case = source / scenario
        case = root / "vehicles" / "hellcat_v1" / scenario
        case.mkdir(parents=True, exist_ok=True)
        copied: dict[str, str] = {}
        for name in ("legacy_parent_raw.wav", "event_candidate_raw.wav", "event_candidate_monitor.wav", "metrics.json", "reference_pointer.json"):
            destination = case / name
            shutil.copy2(source_case / name, destination)
            copied[name] = destination.relative_to(root).as_posix()
        blind_case = root / "blind" / scenario
        blind_case.mkdir(parents=True, exist_ok=True)
        order = ("B", "C") if int(hashlib.sha256(scenario.encode("utf-8")).hexdigest()[-1], 16) % 2 == 0 else ("C", "B")
        blind_paths: dict[str, str] = {}
        for index, label in enumerate(order, start=1):
            source_name = "legacy_parent_raw.wav" if label == "B" else "event_candidate_raw.wav"
            destination = blind_case / f"stimulus_{index:02d}.wav"
            shutil.copy2(source_case / source_name, destination)
            blind_paths[f"stimulus_{index:02d}"] = destination.relative_to(root).as_posix()
            blind_key[f"{scenario}:stimulus_{index:02d}"] = label
        blind_trials[scenario] = {"stimuli": blind_paths, "labels_hidden": True}
        package["scenarios"][scenario] = {
            "vehicle_id": "hellcat_v1",
            "scenario": scenario,
            "source_model": "event_domain_v1",
            "reference": copied["reference_pointer.json"],
            "legacy_parent": copied["legacy_parent_raw.wav"],
            "event_candidate_raw": copied["event_candidate_raw.wav"],
            "event_candidate_monitor": copied["event_candidate_monitor.wav"],
            "metrics": copied["metrics.json"],
            "parameter_changes": source_manifest.get("scenarios", {}).get(scenario, {}),
        }
    write_json(root / "blind_manifest.json", {"schema_version": "s12.stage_v.blind_manifest.v1", "status": "WAITING_FOR_JOVI_HELLCAT_REVIEW", "trials": blind_trials})
    write_json(root / "blind_key_external.json", {"warning": "Keep this file outside the listener-facing package.", "mapping": blind_key})
    (root / "README_ZH.md").write_text(
        "# S12 Stage V Hellcat 中文盲听包\n\n"
        "状态：`WAITING_FOR_JOVI_HELLCAT_REVIEW`。\n\n"
        "本包包含 Legacy Parent、Event-Domain Candidate Raw 和 Candidate Monitor。\n"
        "Reference 目前只有外部指针，没有复制原始录音；因此不能产生 R1、OEM 或 Profile Freeze 结论。\n\n"
        "试听时记录播放设备、Windows 音量、输出端点和听感备注。Raw 用于分析，Monitor 只用于试听，二者不可混用。\n",
        encoding="utf-8",
        newline="\n",
    )
    package["files"] = _package_files(root)
    write_json(root / "package_manifest.json", package)
    errors = validate_stage_v_review_package(root)
    if errors:
        raise ValueError("review package validation failed: " + "; ".join(errors))
    return package


def validate_stage_v_review_package(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / "package_manifest.json"
    if not manifest_path.is_file():
        return ["package_manifest.json is missing"]
    try:
        package = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"package manifest unreadable: {exc}"]
    if package.get("reference_status") != "REFERENCE_POINTER_ONLY":
        errors.append("reference status mismatch")
    if not (root / "README_ZH.md").is_file() or not (root / "blind_manifest.json").is_file():
        errors.append("review instructions or blind manifest missing")
    if not (root / "blind_key_external.json").is_file():
        errors.append("external blind key missing")
    for scenario in STAGE_V_SCENARIOS:
        record = package.get("scenarios", {}).get(scenario)
        if not record:
            errors.append(f"scenario missing: {scenario}")
            continue
        for field in ("legacy_parent", "event_candidate_raw", "event_candidate_monitor", "metrics", "reference"):
            path = root / str(record.get(field, ""))
            if not path.is_file():
                errors.append(f"{scenario}: {field} missing")
        try:
            parent, parent_meta = read_pcm24_wav(root / str(record["legacy_parent"]))
            candidate, candidate_meta = read_pcm24_wav(root / str(record["event_candidate_raw"]))
            monitor, monitor_meta = read_pcm24_wav(root / str(record["event_candidate_monitor"]))
            if parent_meta["sha256"] == candidate_meta["sha256"] or (parent == candidate).all():
                errors.append(f"{scenario}: Parent/Candidate identical")
            if (candidate == monitor).all():
                errors.append(f"{scenario}: monitor is not separate")
            if max(parent_meta["clipping"], candidate_meta["clipping"], monitor_meta["clipping"]) != 0:
                errors.append(f"{scenario}: clipping detected")
        except (OSError, ValueError, KeyError) as exc:
            errors.append(f"{scenario}: WAV validation failed: {exc}")
    for item in package.get("files", []):
        path = root / str(item.get("path", ""))
        if not path.is_file():
            errors.append(f"package file missing: {item.get('path')}")
        elif sha256_file(path) != str(item.get("sha256", "")):
            errors.append(f"package SHA mismatch: {item.get('path')}")
    return errors


def build_three_vehicle_review_package(source_root: str | Path, output_root: str | Path) -> dict[str, object]:
    """Build one listener package for all three current Event-Domain vehicles."""

    source = Path(source_root)
    root = Path(output_root)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty review package: {root}")
    root.mkdir(parents=True, exist_ok=True)
    vehicles = ("hellcat_v1", "ferrari_458_v1", "rx7_fd_v1")
    package: dict[str, Any] = {
        "schema_version": "s12.stage_v.three_vehicle_review_package.v1",
        "status": "WAITING_FOR_JOVI_THREE_VEHICLE_REVIEW",
        "reference_status": "REFERENCE_POINTER_ONLY",
        "scope": _SCOPE,
        "human_pass": False,
        "profile_freeze_ready": False,
        "vehicles": {},
    }
    blind_key: dict[str, str] = {}
    blind_trials: dict[str, dict[str, object]] = {}
    for vehicle_id in vehicles:
        vehicle_source = source / vehicle_id
        package["vehicles"][vehicle_id] = {"scenarios": {}}
        for scenario in STAGE_V_SCENARIOS:
            source_case = vehicle_source / scenario
            case = root / "vehicles" / vehicle_id / scenario
            case.mkdir(parents=True, exist_ok=True)
            copied: dict[str, str] = {}
            for name in ("legacy_parent_raw.wav", "event_candidate_raw.wav", "event_candidate_monitor.wav", "metrics.json", "reference_pointer.json"):
                destination = case / name
                shutil.copy2(source_case / name, destination)
                copied[name] = destination.relative_to(root).as_posix()
            blind_case = root / "blind" / vehicle_id / scenario
            blind_case.mkdir(parents=True, exist_ok=True)
            order = ("B", "C") if int(hashlib.sha256(f"{vehicle_id}:{scenario}".encode("utf-8")).hexdigest()[-1], 16) % 2 == 0 else ("C", "B")
            stimuli: dict[str, str] = {}
            for index, label in enumerate(order, start=1):
                source_name = "legacy_parent_raw.wav" if label == "B" else "event_candidate_raw.wav"
                destination = blind_case / f"stimulus_{index:02d}.wav"
                shutil.copy2(source_case / source_name, destination)
                key = f"{vehicle_id}:{scenario}:stimulus_{index:02d}"
                blind_key[key] = label
                stimuli[f"stimulus_{index:02d}"] = destination.relative_to(root).as_posix()
            blind_trials[f"{vehicle_id}:{scenario}"] = {"stimuli": stimuli, "labels_hidden": True}
            package["vehicles"][vehicle_id]["scenarios"][scenario] = {
                "legacy_parent": copied["legacy_parent_raw.wav"],
                "event_candidate_raw": copied["event_candidate_raw.wav"],
                "event_candidate_monitor": copied["event_candidate_monitor.wav"],
                "metrics": copied["metrics.json"],
                "reference": copied["reference_pointer.json"],
                "source_model": "event_domain_v1",
            }
    write_json(root / "blind_manifest.json", {"schema_version": "s12.stage_v.three_vehicle_blind_manifest.v1", "status": package["status"], "trials": blind_trials})
    write_json(root / "blind_key_external.json", {"warning": "Keep this file outside the listener-facing package.", "mapping": blind_key})
    (root / "README_ZH.md").write_text(
        "# S12 Stage V 三车型中文盲听包\n\n"
        "状态：`WAITING_FOR_JOVI_THREE_VEHICLE_REVIEW`。\n\n"
        "包含 Hellcat、Ferrari 458、RX-7 FD 的 Legacy Parent、Event Candidate Raw 和 Candidate Monitor。\n"
        "Reference 仅保留外部指针，没有复制原始录音；不能据此宣称 R1、OEM、校准或 Profile Freeze。\n",
        encoding="utf-8", newline="\n")
    package["files"] = _package_files(root)
    write_json(root / "package_manifest.json", package)
    errors = validate_three_vehicle_review_package(root)
    if errors:
        raise ValueError("three-vehicle review package validation failed: " + "; ".join(errors))
    return package


def validate_three_vehicle_review_package(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / "package_manifest.json"
    if not manifest_path.is_file():
        return ["package_manifest.json is missing"]
    try:
        package = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"package manifest unreadable: {exc}"]
    if package.get("reference_status") != "REFERENCE_POINTER_ONLY":
        errors.append("reference status mismatch")
    if not (root / "README_ZH.md").is_file() or not (root / "blind_manifest.json").is_file() or not (root / "blind_key_external.json").is_file():
        errors.append("review package support files missing")
    for vehicle_id in ("hellcat_v1", "ferrari_458_v1", "rx7_fd_v1"):
        for scenario in STAGE_V_SCENARIOS:
            record = package.get("vehicles", {}).get(vehicle_id, {}).get("scenarios", {}).get(scenario)
            if not record:
                errors.append(f"missing record: {vehicle_id}/{scenario}")
                continue
            try:
                parent, parent_meta = read_pcm24_wav(root / str(record["legacy_parent"]))
                candidate, candidate_meta = read_pcm24_wav(root / str(record["event_candidate_raw"]))
                monitor, monitor_meta = read_pcm24_wav(root / str(record["event_candidate_monitor"]))
                if parent_meta["sha256"] == candidate_meta["sha256"] or np.array_equal(parent, candidate):
                    errors.append(f"{vehicle_id}/{scenario}: Parent/Candidate identical")
                if np.array_equal(candidate, monitor):
                    errors.append(f"{vehicle_id}/{scenario}: monitor is not separate")
                if max(parent_meta["clipping"], candidate_meta["clipping"], monitor_meta["clipping"]) != 0:
                    errors.append(f"{vehicle_id}/{scenario}: clipping detected")
            except (OSError, ValueError, KeyError) as exc:
                errors.append(f"{vehicle_id}/{scenario}: WAV validation failed: {exc}")
    for item in package.get("files", []):
        path = root / str(item.get("path", ""))
        if not path.is_file():
            errors.append(f"package file missing: {item.get('path')}")
        elif sha256_file(path) != str(item.get("sha256", "")):
            errors.append(f"package SHA mismatch: {item.get('path')}")
    return errors


__all__ = [
    "build_stage_v_review_package",
    "build_three_vehicle_review_package",
    "validate_stage_v_review_package",
    "validate_three_vehicle_review_package",
]
