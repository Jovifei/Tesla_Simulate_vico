"""Self-contained tamper coverage for the strict Stage-W bake-off validator."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_v.io import sha256_file
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import (
    run_hellcat_bakeoff,
    validate_bakeoff_manifest,
)


CASE_FILES = (
    "raw_source.wav",
    "post_ptr_raw.wav",
    "monitor.wav",
    "state_trace.json",
    "phase_trace.json",
    "event_trace.json",
    "path_trace.json",
    "gain_trace.json",
    "metrics.json",
    "cpu_memory_latency.json",
    "sha256_manifest.json",
)


@pytest.fixture(scope="module")
def bakeoff_fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("stage_w_validator") / "bakeoff"
    run_hellcat_bakeoff(root, duration_s=0.20)
    return root


def _copy_fixture(source: Path, tmp_path: Path) -> Path:
    target = tmp_path / "bakeoff"
    shutil.copytree(source, target)
    return target


def _write_json(path: Path, payload: object, *, allow_nan: bool = False) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=allow_nan) + "\n",
        encoding="utf-8",
    )


def _rebind_case(root: Path, architecture: str, scene: str) -> None:
    case = root / architecture / scene
    inner_path = case / "sha256_manifest.json"
    inner = json.loads(inner_path.read_text(encoding="utf-8"))
    for name in CASE_FILES[:-1]:
        inner[name] = sha256_file(case / name)
    _write_json(inner_path, inner)
    outer_path = root / "bakeoff_manifest.json"
    outer = json.loads(outer_path.read_text(encoding="utf-8"))
    outer["files"][f"{architecture}/{scene}/sha256_manifest.json"] = sha256_file(inner_path)
    for name in CASE_FILES[:-1]:
        outer["files"][f"{architecture}/{scene}/{name}"] = sha256_file(case / name)
    _write_json(outer_path, outer)


def _rebind_root_file(root: Path, relative: str) -> None:
    manifest_path = root / "bakeoff_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][relative] = sha256_file(root / relative)
    _write_json(manifest_path, manifest)


def test_validator_rejects_extra_outer_manifest_entries(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    extra = root / "unexpected.json"
    extra.write_text("{}\n", encoding="utf-8")
    manifest = json.loads((root / "bakeoff_manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["unexpected.json"] = sha256_file(extra)
    _write_json(root / "bakeoff_manifest.json", manifest)

    assert any("outer_manifest_extra:unexpected.json" in error for error in validate_bakeoff_manifest(root))


def test_validator_rejects_nonfinite_values_in_any_required_trace(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "P2H" / "steady_1200rpm" / "phase_trace.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["phase_rad"][0] = float("nan")
    _write_json(path, payload, allow_nan=True)
    _rebind_case(root, "P2H", "steady_1200rpm")

    assert any("nonfinite:phase_trace:P2H/steady_1200rpm" in error for error in validate_bakeoff_manifest(root))


def test_validator_rejects_invalid_cpu_memory_latency_values(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "P3" / "steady_2000rpm" / "cpu_memory_latency.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["render_seconds"] = -1.0
    _write_json(path, payload)
    _rebind_case(root, "P3", "steady_2000rpm")

    assert any("cpu_memory_latency:P3/steady_2000rpm" in error for error in validate_bakeoff_manifest(root))


def test_validator_recomputes_saved_audio_metrics(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "P5" / "gear_shift" / "metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["raw_metrics"]["peak"] += 0.1
    _write_json(path, payload)
    _rebind_case(root, "P5", "gear_shift")

    assert any("audio_metrics:P5/gear_shift" in error for error in validate_bakeoff_manifest(root))


def test_validator_requires_afterfire_count_and_rejects_ineligible_events(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    missing_path = root / "P2H" / "afterfire_eligible" / "event_trace.json"
    missing = json.loads(missing_path.read_text(encoding="utf-8"))
    missing.pop("afterfire_event_count")
    _write_json(missing_path, missing)
    _rebind_case(root, "P2H", "afterfire_eligible")
    assert any("afterfire_event_count_missing:P2H/afterfire_eligible" in error for error in validate_bakeoff_manifest(root))

    wrong_path = root / "P1" / "afterfire_ineligible" / "event_trace.json"
    wrong = json.loads(wrong_path.read_text(encoding="utf-8"))
    wrong["afterfire_event_count"] = [0, 1]
    _write_json(wrong_path, wrong)
    _rebind_case(root, "P1", "afterfire_ineligible")
    assert any("afterfire_wrong_condition:P1/afterfire_ineligible" in error for error in validate_bakeoff_manifest(root))


def test_validator_cross_checks_parameter_and_geometry_flags(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "P2H" / "steady_3000rpm" / "metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["diagnostics"]["parameter_consumption"]["crankpin_geometry"] = False
    _write_json(path, payload)
    _rebind_case(root, "P2H", "steady_3000rpm")

    assert any("parameter_consumption:P2H/steady_3000rpm" in error for error in validate_bakeoff_manifest(root))


def test_validator_cross_checks_summary_hashes_and_ablation_truth(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    parent_path = root / "parent_candidate_metrics.json"
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    parent["parent"]["steady_1200rpm"]["raw_sha256"] = "0" * 64
    _write_json(parent_path, parent)
    _rebind_root_file(root, "parent_candidate_metrics.json")
    assert any("parent_candidate_hash:P1/steady_1200rpm/raw_sha256" in error for error in validate_bakeoff_manifest(root))

    ablation_path = root / "ablation_results.json"
    ablation = json.loads(ablation_path.read_text(encoding="utf-8"))
    ablation["ablations"]["P2_to_P2H_waveguide"]["steady_1200rpm"]["post_ptr_sha256_different"] = False
    _write_json(ablation_path, ablation)
    _rebind_root_file(root, "ablation_results.json")
    assert any("ablation_truth:P2_to_P2H_waveguide/steady_1200rpm/post_ptr_sha256_different" in error for error in validate_bakeoff_manifest(root))
