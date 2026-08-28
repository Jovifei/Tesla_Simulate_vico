"""Self-contained tamper coverage for the strict Stage-W bake-off validator."""

from __future__ import annotations

import json
import shutil
import wave
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


def _set_identity_pair(root: Path, status: str, reference_status: str) -> None:
    manifest_path = root / "bakeoff_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = status
    manifest["reference_status"] = reference_status
    manifest["selected_architecture"] = None
    _write_json(manifest_path, manifest)
    for name in ("bakeoff_results.json", "parent_candidate_metrics.json", "ablation_results.json", "rejected_architectures.json"):
        path = root / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["status"] = status
        payload["reference_status"] = reference_status
        payload["selected_architecture"] = None
        _write_json(path, payload)
        _rebind_root_file(root, name)
    selected = root / "selected_architecture.json"
    payload = json.loads(selected.read_text(encoding="utf-8"))
    payload["status"] = status
    payload["selected_architecture"] = None
    _write_json(selected, payload)
    _rebind_root_file(root, "selected_architecture.json")
    for architecture in ("P1", "P2", "P2H", "P3", "P5"):
        for scene in ("hot_idle_20s", "steady_1200rpm", "steady_2000rpm", "steady_3000rpm", "throttle_tip_in", "full_load_acceleration", "gear_shift", "high_rpm_lift", "afterfire_eligible", "afterfire_ineligible", "idle_return", "complete_cycle_60s"):
            metrics_path = root / architecture / scene / "metrics.json"
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            metrics["status"] = status
            metrics["reference_status"] = reference_status
            metrics["selected_architecture"] = None
            _write_json(metrics_path, metrics)
            _rebind_case(root, architecture, scene)


def _tamper_pcm24_first_sample(path: Path) -> None:
    with wave.open(str(path), "rb") as stream:
        params = stream.getparams()
        frames = stream.readframes(stream.getnframes())
    tampered = b"\x00\x00\x80" + frames[3:]
    with wave.open(str(path), "wb") as stream:
        stream.setparams(params)
        stream.writeframes(tampered)


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


def test_validator_rejects_missing_required_case_file(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    (root / "P1" / "steady_1200rpm" / "phase_trace.json").unlink()

    assert any("missing_required:P1/steady_1200rpm/phase_trace.json" in error for error in validate_bakeoff_manifest(root))


def test_validator_rejects_outer_sha_tamper(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    manifest_path = root / "bakeoff_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["P1/steady_1200rpm/raw_source.wav"] = "0" * 64
    _write_json(manifest_path, manifest)

    assert any("sha:P1/steady_1200rpm/raw_source.wav" in error for error in validate_bakeoff_manifest(root))


def test_validator_rejects_per_case_sha_tamper(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    case = root / "P2" / "steady_1200rpm"
    inner_path = case / "sha256_manifest.json"
    inner = json.loads(inner_path.read_text(encoding="utf-8"))
    inner["monitor.wav"] = "0" * 64
    _write_json(inner_path, inner)
    _rebind_root_file(root, "P2/steady_1200rpm/sha256_manifest.json")

    assert any("case_manifest_sha:P2/steady_1200rpm" in error for error in validate_bakeoff_manifest(root))


def test_validator_rejects_wav_clipping(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    case = root / "P3" / "gear_shift"
    _tamper_pcm24_first_sample(case / "raw_source.wav")
    _rebind_case(root, "P3", "gear_shift")

    assert any("clipping:P3/gear_shift" in error for error in validate_bakeoff_manifest(root))


def test_validator_rejects_raw_monitor_separation_tamper(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    case = root / "P5" / "full_load_acceleration"
    shutil.copyfile(case / "raw_source.wav", case / "monitor.wav")
    _rebind_case(root, "P5", "full_load_acceleration")

    assert any("separation:P5/full_load_acceleration" in error for error in validate_bakeoff_manifest(root))


def test_validator_accepts_exact_r2_identity_pair(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    _set_identity_pair(root, "R2_DIAGNOSTIC_READY", "EXTERNAL_R2_POINTER")

    assert validate_bakeoff_manifest(root) == []


def test_validator_rejects_case_status_reference_mismatch(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "P2" / "steady_1200rpm" / "metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = "R2_DIAGNOSTIC_READY"
    payload["reference_status"] = "EXTERNAL_R2_POINTER"
    _write_json(path, payload)
    _rebind_case(root, "P2", "steady_1200rpm")

    assert any("identity_gate:P2/steady_1200rpm" in error for error in validate_bakeoff_manifest(root))


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("bakeoff_manifest.json", "selection_missing:manifest"),
        ("parent_candidate_metrics.json", "selection_missing:parent_candidate_metrics.json"),
        ("P2/steady_1200rpm/metrics.json", "selection_missing:P2/steady_1200rpm"),
    ],
)
def test_validator_rejects_missing_selection_fields(
    bakeoff_fixture: Path, tmp_path: Path, relative: str, expected: str
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / relative
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("selected_architecture", None)
    _write_json(path, payload)
    if "/" in relative:
        architecture, scene, _ = relative.split("/")
        _rebind_case(root, architecture, scene)
    elif relative != "bakeoff_manifest.json":
        _rebind_root_file(root, relative)

    assert any(expected in error for error in validate_bakeoff_manifest(root))


def test_validator_rejects_nonnull_selection_field(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "P2" / "steady_1200rpm" / "metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["selected_architecture"] = "P2"
    _write_json(path, payload)
    _rebind_case(root, "P2", "steady_1200rpm")

    assert any("selection:P2/steady_1200rpm" in error for error in validate_bakeoff_manifest(root))


@pytest.mark.parametrize(
    ("field", "expected"),
    [("architecture", "nested_architecture_inventory"), ("scene", "nested_scene_inventory:P2")],
)
def test_validator_rejects_nested_inventory_tamper(
    bakeoff_fixture: Path, tmp_path: Path, field: str, expected: str
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "bakeoff_results.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if field == "architecture":
        payload["architectures"].pop("P4")
    else:
        payload["architectures"]["P2"]["scenes"].pop("steady_1200rpm")
    _write_json(path, payload)
    _rebind_root_file(root, "bakeoff_results.json")

    assert any(expected in error for error in validate_bakeoff_manifest(root))


@pytest.mark.parametrize("mode", ["missing", "null", "different"])
def test_validator_rejects_invalid_parent_candidate_difference(
    bakeoff_fixture: Path, tmp_path: Path, mode: str
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    result_path = root / "bakeoff_results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    candidate_result = result["architectures"]["P2"]["scenes"]["steady_1200rpm"]["comparison"]
    candidate_path = root / "parent_candidate_metrics.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_record = candidate["architectures"]["P2"]["steady_1200rpm"]
    if mode == "missing":
        candidate_result.pop("parent_candidate_difference_rms")
    elif mode == "null":
        candidate_result["parent_candidate_difference_rms"] = None
    else:
        candidate_result["parent_candidate_difference_rms"] = float(candidate_record["parent_candidate_difference_rms"]) + 1.0
    _write_json(result_path, result)
    _rebind_root_file(root, "bakeoff_results.json")

    expected = "parent_candidate_difference_invalid:P2/steady_1200rpm" if mode != "different" else "parent_candidate_difference:P2/steady_1200rpm"
    assert any(expected in error for error in validate_bakeoff_manifest(root))


def test_validator_rejects_missing_candidate_difference_summary(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "parent_candidate_metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["architectures"]["P2"]["steady_1200rpm"].pop("parent_candidate_difference_rms")
    _write_json(path, payload)
    _rebind_root_file(root, "parent_candidate_metrics.json")

    assert any("parent_candidate_difference_missing:P2/steady_1200rpm" in error for error in validate_bakeoff_manifest(root))



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


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("P1/steady_1200rpm/raw_source.wav", "missing_required:P1/steady_1200rpm/raw_source.wav"),
        ("P2/steady_1200rpm/metrics.json", "missing_required:P2/steady_1200rpm/metrics.json"),
        ("P3/steady_1200rpm/sha256_manifest.json", "missing_required:P3/steady_1200rpm/sha256_manifest.json"),
    ],
)
def test_validator_reports_missing_late_artifacts_without_raising(
    bakeoff_fixture: Path, tmp_path: Path, relative: str, expected: str
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    (root / relative).unlink()
    manifest_path = root / "bakeoff_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].pop(relative, None)
    _write_json(manifest_path, manifest)

    errors = validate_bakeoff_manifest(root)

    assert isinstance(errors, list)
    assert expected in errors


def test_validator_recomputes_parent_candidate_difference_from_reopened_pcm(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    case = root / "P2" / "steady_1200rpm"
    with wave.open(str(case / "post_ptr_raw.wav"), "rb") as stream:
        params = stream.getparams()
        frames = stream.readframes(stream.getnframes())
    tampered = bytearray(frames)
    tampered[40 * 6 : 40 * 6 + 6] = b"\x00\x00\x40\x00\x00\x40"
    with wave.open(str(case / "post_ptr_raw.wav"), "wb") as stream:
        stream.setparams(params)
        stream.writeframes(bytes(tampered))
    _rebind_case(root, "P2", "steady_1200rpm")

    errors = validate_bakeoff_manifest(root)

    assert any("parent_candidate_difference_pcm:P2/steady_1200rpm" in error for error in errors)


def test_validator_rejects_dual_rebound_parent_candidate_difference_tamper(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    result_path = root / "bakeoff_results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["architectures"]["P2"]["scenes"]["steady_1200rpm"]["comparison"]["parent_candidate_difference_rms"] = 9.0
    _write_json(result_path, result)
    _rebind_root_file(root, "bakeoff_results.json")
    summary_path = root / "parent_candidate_metrics.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["architectures"]["P2"]["steady_1200rpm"]["parent_candidate_difference_rms"] = 9.0
    _write_json(summary_path, summary)
    _rebind_root_file(root, "parent_candidate_metrics.json")

    errors = validate_bakeoff_manifest(root)

    assert any("parent_candidate_difference_pcm:P2/steady_1200rpm" in error for error in errors)


@pytest.mark.parametrize("architecture", ["P4", "P6"])
def test_validator_requires_exact_placeholder_records(
    bakeoff_fixture: Path, tmp_path: Path, architecture: str
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "bakeoff_results.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["architectures"][architecture]["reason"] = "tampered"
    _write_json(path, payload)
    _rebind_root_file(root, "bakeoff_results.json")

    errors = validate_bakeoff_manifest(root)

    assert any(f"placeholder_reason:{architecture}" in error for error in errors)


def test_validator_requires_placeholder_selection_boundary(
    bakeoff_fixture: Path, tmp_path: Path
) -> None:
    root = _copy_fixture(bakeoff_fixture, tmp_path)
    path = root / "bakeoff_results.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["architectures"]["P4"]["selected_architecture"] = "P4"
    _write_json(path, payload)
    _rebind_root_file(root, "bakeoff_results.json")

    errors = validate_bakeoff_manifest(root)

    assert any("placeholder_selected_architecture:P4" in error for error in errors)
