from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from tools.sound_sim.s12.real_reference.stage_u_review_package import (
    ALLOWED_EXTERNAL_ROOT,
    StageUReviewPackageError,
    build_review_package,
    create_review_http_server,
    validate_listener_submission,
    validate_review_package,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_tone(
    path: Path, sample_rate_hz: int, frequency_hz: float, amplitude: float
) -> str:
    duration_s = 0.45
    time_s = (
        np.arange(int(sample_rate_hz * duration_s), dtype=np.float64) / sample_rate_hz
    )
    audio = amplitude * np.sin(2.0 * np.pi * frequency_hz * time_s)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.column_stack((audio, audio)), sample_rate_hz, subtype="PCM_16")
    return _sha256(path)


@pytest.fixture
def external_fixture_root() -> Path:
    allowed = ALLOWED_EXTERNAL_ROOT.resolve()
    allowed.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="s12-u7-test-", dir=allowed))
    yield root
    resolved = root.resolve()
    assert resolved != allowed and resolved.is_relative_to(allowed)
    shutil.rmtree(resolved)


@pytest.fixture
def package_inputs(external_fixture_root: Path) -> dict[str, object]:
    source_root = external_fixture_root / "source"
    reference_path = source_root / "reference_44100.wav"
    parent_path = source_root / "parent_48000.wav"
    candidate_path = source_root / "candidate_32000.wav"
    reference_sha = _write_tone(reference_path, 44_100, 180.0, 0.31)
    parent_sha = _write_tone(parent_path, 48_000, 220.0, 0.12)
    candidate_sha = _write_tone(candidate_path, 32_000, 260.0, 0.16)
    reference_id = "stage_u:hellcat_fixture:reference"
    candidate_id = "hellcat_stage_u_04"
    selection = {
        "schema_version": "s12-stage-u-selection-v1",
        "status": "R2_COMPARATOR_DRIVEN_CANDIDATE_READY",
        "selected_candidates": [
            {
                "vehicle_id": "hellcat",
                "candidate_id": candidate_id,
                "reference_count": 1,
                "distinct_reference_count": 1,
                "expected_reference_count": 1,
                "required_improvement_count": 1,
                "improved_reference_count": 1,
                "professional_bound": True,
                "hard_gates_pass": True,
                "status": "R2_COMPARATOR_DRIVEN_CANDIDATE_READY",
                "per_reference": [
                    {
                        "vehicle_id": "hellcat",
                        "scenario": "idle_rev_acceleration",
                        "reference_id": reference_id,
                        "candidate_id": candidate_id,
                        "reference_path": str(reference_path),
                        "parent_path": str(parent_path),
                        "candidate_path": str(candidate_path),
                        "reference_sha256": reference_sha,
                        "parent_sha256": parent_sha,
                        "candidate_sha256": candidate_sha,
                        "parent_distance": 1.0,
                        "candidate_distance": 0.94,
                        "absolute_improvement": 0.06,
                        "professional_bound": True,
                        "hard_gates_pass": True,
                        "professional_binding_status": "ALL_COMPONENT_SHA_BOUND",
                        "sha_binding": {
                            "reference": reference_sha,
                            "parent": parent_sha,
                            "candidate": candidate_sha,
                        },
                    }
                ],
            }
        ],
        "rejected_candidates": [
            {"vehicle_id": "ferrari_458", "status": "REFERENCE_COVERAGE_NOT_QUALIFIED"},
            {"vehicle_id": "rx7_fd", "status": "NO_MEASURABLE_IMPROVEMENT"},
        ],
    }
    professional = {
        "schema_version": "s12-stage-u-professional-triad-results-v1",
        "status": "PROFESSIONAL_TRIAD_COMPARISON_COMPLETE",
        "results": [
            {
                "vehicle_id": "hellcat",
                "scenario": "idle_rev_acceleration",
                "reference_id": reference_id,
                "candidate_id": candidate_id,
                "reference_sha256": reference_sha,
                "parent_sha256": parent_sha,
                "candidate_sha256": candidate_sha,
                "professional_bound": True,
                "hard_gates_pass": True,
                "professional_binding_status": "ALL_COMPONENT_SHA_BOUND",
                "sha_binding": {
                    "reference": reference_sha,
                    "parent": parent_sha,
                    "candidate": candidate_sha,
                },
                "professional_components": {
                    "matlab": {"parent_distance": 1.8, "candidate_distance": 1.5},
                    "mosqito": {"parent_distance": 2.2, "candidate_distance": 2.0},
                    "audioFeatureExtractor": {
                        "parent_distance": 9.1,
                        "candidate_distance": 8.7,
                    },
                },
            }
        ],
    }
    grid = {
        "schema_version": "s12-stage-u-candidate-grid-results-v1",
        "status": "CANDIDATE_GRID_RENDERED",
        "candidates": [
            {
                "vehicle_id": "hellcat",
                "reference_id": reference_id,
                "candidate_id": candidate_id,
                "candidate_sha256": candidate_sha,
                "parameter_values": {
                    "blower_intake_balance": 0.25,
                    "mid_band_pressure_db": 3.0,
                    "pressure_attack_db": 3.0,
                },
                "source_mapping": {
                    "parameter_group": "pressure_attack_blower_intake_balance",
                    "source_values": {
                        "blower_intake_balance": 0.25,
                        "intake_gain_scale": 1.4125375446227544,
                        "pressure_attack_gain_scale": 1.4125375446227544,
                    },
                },
            }
        ],
    }
    return {"selection": selection, "professional": professional, "grid": grid}


def _build(
    package_inputs: dict[str, object], external_root: Path, repo_root: Path
) -> dict:
    return build_review_package(
        package_inputs["selection"],
        package_inputs["professional"],
        package_inputs["grid"],
        repository_review_root=repo_root,
        external_output_root=external_root,
        random_seed=1701,
    )


def test_review_package_refuses_output_outside_allowed_external_root(
    package_inputs: dict[str, object], tmp_path: Path
) -> None:
    with pytest.raises(StageUReviewPackageError, match="allowed external root"):
        _build(package_inputs, tmp_path / "external", tmp_path / "repo-page")


def test_review_package_refuses_nonempty_page_root_before_external_writes(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    repository_output = tmp_path / "Jovi_Reference_Parent_Candidate_Review"
    repository_output.mkdir()
    (repository_output / "owner-note.txt").write_text("preserve", encoding="utf-8")
    external_output = external_fixture_root / "must-not-exist"
    with pytest.raises(
        StageUReviewPackageError, match="non-empty repository review root"
    ):
        _build(package_inputs, external_output, repository_output)
    assert not external_output.exists()
    assert (repository_output / "owner-note.txt").read_text(
        encoding="utf-8"
    ) == "preserve"


def test_review_package_rejects_raw_sha_mismatch_before_writing(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    selection = copy.deepcopy(package_inputs["selection"])
    selection["selected_candidates"][0]["per_reference"][0]["reference_sha256"] = (
        "0" * 64
    )
    selection["selected_candidates"][0]["per_reference"][0]["sha_binding"][
        "reference"
    ] = "0" * 64
    professional = copy.deepcopy(package_inputs["professional"])
    professional["results"][0]["reference_sha256"] = "0" * 64
    professional["results"][0]["sha_binding"]["reference"] = "0" * 64
    inputs = {**package_inputs, "selection": selection, "professional": professional}
    output = external_fixture_root / "invalid-sha-package"
    with pytest.raises(StageUReviewPackageError, match="raw SHA-256 mismatch"):
        _build(inputs, output, tmp_path / "repo-page")
    assert not output.exists()


def test_review_package_rejects_parent_candidate_equality(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    selection = copy.deepcopy(package_inputs["selection"])
    row = selection["selected_candidates"][0]["per_reference"][0]
    row["candidate_path"] = row["parent_path"]
    row["candidate_sha256"] = row["parent_sha256"]
    row["sha_binding"]["candidate"] = row["parent_sha256"]
    with pytest.raises(StageUReviewPackageError, match="Parent/Candidate"):
        _build(
            {**package_inputs, "selection": selection},
            external_fixture_root / "equal",
            tmp_path / "page",
        )


def test_review_package_rejects_missing_professional_binding(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    professional = copy.deepcopy(package_inputs["professional"])
    professional["results"] = []
    with pytest.raises(StageUReviewPackageError, match="professional binding"):
        _build(
            {**package_inputs, "professional": professional},
            external_fixture_root / "no-pro",
            tmp_path / "page",
        )


def test_review_package_rejects_empty_selected_candidates(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    selection = copy.deepcopy(package_inputs["selection"])
    selection["selected_candidates"] = []
    with pytest.raises(StageUReviewPackageError, match="no selected candidate"):
        _build(
            {**package_inputs, "selection": selection},
            external_fixture_root / "none",
            tmp_path / "page",
        )


def test_review_package_locks_current_single_selected_truth(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    selection = copy.deepcopy(package_inputs["selection"])
    forged = copy.deepcopy(selection["selected_candidates"][0])
    forged["vehicle_id"] = "ferrari_458"
    forged["candidate_id"] = "ferrari_458_stage_u_01"
    forged["per_reference"][0]["vehicle_id"] = "ferrari_458"
    forged["per_reference"][0]["candidate_id"] = "ferrari_458_stage_u_01"
    selection["selected_candidates"].append(forged)
    with pytest.raises(
        StageUReviewPackageError, match="exactly one selected candidate"
    ):
        _build(
            {**package_inputs, "selection": selection},
            external_fixture_root / "multiple",
            tmp_path / "page",
        )

    selection = copy.deepcopy(package_inputs["selection"])
    selection["selected_candidates"][0]["candidate_id"] = "hellcat_stage_u_99"
    selection["selected_candidates"][0]["per_reference"][0]["candidate_id"] = (
        "hellcat_stage_u_99"
    )
    with pytest.raises(StageUReviewPackageError, match="hellcat_stage_u_04"):
        _build(
            {**package_inputs, "selection": selection},
            external_fixture_root / "forged",
            tmp_path / "page",
        )


def test_successful_package_keeps_raw_and_loudness_matched_copies_separate(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    external_output = external_fixture_root / "review-package"
    repository_output = tmp_path / "Jovi_Reference_Parent_Candidate_Review"
    manifest = _build(package_inputs, external_output, repository_output)

    assert manifest["status"] == "ABX_READY_FOR_HUMAN_REVIEW"
    assert manifest["candidate_count"] == 1
    assert manifest["trial_count"] == 1
    assert {trial["vehicle_id"] for trial in manifest["trials"]} == {"hellcat"}
    assert "ferrari_458" not in json.dumps(manifest)
    assert "rx7_fd" not in json.dumps(manifest)

    trial = manifest["trials"][0]
    assert set(trial["randomized_mapping"]) == {"B", "C"}
    assert set(trial["randomized_mapping"].values()) == {"parent", "candidate"}
    for role in ("reference", "parent", "candidate"):
        receipt = trial["media"][role]
        raw_path = Path(receipt["raw_copy_path"])
        audition_path = Path(receipt["audition_copy_path"])
        assert (
            raw_path.is_file() and audition_path.is_file() and raw_path != audition_path
        )
        assert (
            _sha256(raw_path)
            == receipt["source_raw_sha256"]
            == receipt["raw_copy_sha256"]
        )
        assert _sha256(audition_path) == receipt["audition_sha256"]
        assert receipt["audition_sample_rate_hz"] == 48_000
        assert receipt["target_lufs"] == -18.0
        assert receipt["peak_cap_dbfs"] == -1.5
        assert receipt["audition_metrics"]["peak_dbfs"] <= -1.5 + 1e-6
        assert isinstance(receipt["gain_db"], float)
        assert isinstance(receipt["headroom_limited"], bool)
        assert receipt["duration_s"] > 0.0

    assert (external_output / "review_package_manifest.json").is_file()
    assert {path.name for path in repository_output.iterdir()} == {
        "index.html",
        "review.js",
        "review_data.js",
        "review_data.json",
    }
    assert not list(repository_output.rglob("*.wav"))
    validate_review_package(manifest)
    persisted = json.loads(
        (external_output / "review_package_manifest.json").read_text(encoding="utf-8")
    )
    assert persisted["manifest_sha256"] == manifest["manifest_sha256"]
    assert persisted["manifest_path"] == manifest["manifest_path"]
    validate_review_package(persisted)


def test_repository_page_contract_is_chinese_sha_bound_and_playwright_addressable(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    repository_output = tmp_path / "Jovi_Reference_Parent_Candidate_Review"
    manifest = _build(
        package_inputs, external_fixture_root / "page-contract", repository_output
    )
    html = (repository_output / "index.html").read_text(encoding="utf-8")
    js = (repository_output / "review.js").read_text(encoding="utf-8")
    data = json.loads(
        (repository_output / "review_data.json").read_text(encoding="utf-8")
    )

    for token in (
        "工业声学对照台",
        "参考音轨",
        "父版本",
        "候选版本",
        "哪个更接近参考音轨",
        "专业指标：调整前 / 调整后",
        "参数值与不确定性",
        "导出人工提交文件",
    ):
        assert token in html + js
    for selector in (
        'data-testid="reference-player"',
        'data-testid="parent-player"',
        'data-testid="candidate-player"',
        'data-testid="answer-b"',
        'data-testid="answer-c"',
        'data-testid="export-submission"',
        'data-testid="gate-status"',
        'data-testid="status-labels"',
        'data-testid="blind-b-player"',
        'data-testid="blind-c-player"',
    ):
        assert selector in html + js
    for gate_token in (
        "duration",
        "canplaythrough",
        "sha256",
        "professional_binding",
        "parent_candidate_distinct",
    ):
        assert gate_token in js
    assert "trial.randomized_mapping[slot]" in js
    assert ".innerHTML" not in js
    assert "https://" not in html and "http://" not in html
    assert "ABX_READY" not in html
    assert data["schema_version"] == "s12-stage-u-review-page-data-v1"
    assert (
        data["trials"][0]["parameter_uncertainty"]["status"]
        == "NOT_QUANTIFIED_GRID_CANDIDATE"
    )
    assert data["trials"][0]["professional_metrics"]["matlab"] == {
        "before": 1.8,
        "after": 1.5,
    }
    persisted = json.loads(
        (
            external_fixture_root / "page-contract" / "review_package_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert data["manifest_sha256"] == persisted["manifest_sha256"]
    assert manifest["status"] == "ABX_READY_FOR_HUMAN_REVIEW"


def test_callable_validator_rejects_tampered_media_and_submission_requires_answer(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    manifest = _build(
        package_inputs, external_fixture_root / "validator", tmp_path / "page"
    )
    tampered = copy.deepcopy(manifest)
    tampered["trials"][0]["media"]["candidate"]["audition_sha256"] = "f" * 64
    canonical = copy.deepcopy(tampered)
    canonical.pop("manifest_sha256")
    tampered["manifest_sha256"] = hashlib.sha256(
        (
            json.dumps(canonical, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(StageUReviewPackageError, match="audition SHA-256 mismatch"):
        validate_review_package(tampered)

    trial = manifest["trials"][0]
    media_validation = {
        role: {
            "duration_s": receipt["duration_s"],
            "duration": True,
            "canplaythrough": True,
            "sha256": receipt["audition_sha256"],
            "sha_status": "MATCH",
        }
        for role, receipt in trial["media"].items()
    }
    missing_answer = {
        "schema_version": "s12-stage-u-listener-submission-v1",
        "manifest_sha256": manifest["manifest_sha256"],
        "submitted_at_utc": "2026-08-23T10:11:12Z",
        "responses": [{"trial_id": trial["trial_id"], "answer": "", "notes": ""}],
        "media_validation": {trial["trial_id"]: media_validation},
        "mappings": {trial["trial_id"]: trial["randomized_mapping"]},
        "sha_bindings": {
            trial["trial_id"]: {
                role: {
                    "raw": receipt["source_raw_sha256"],
                    "audition": receipt["audition_sha256"],
                }
                for role, receipt in trial["media"].items()
            }
        },
    }
    with pytest.raises(StageUReviewPackageError, match="ABX answer"):
        validate_listener_submission(missing_answer, manifest)

    valid = copy.deepcopy(missing_answer)
    valid["responses"][0] = {
        "trial_id": trial["trial_id"],
        "answer": "B",
        "notes": "B 更接近参考的低频压力感。",
    }
    persisted_manifest = json.loads(
        Path(manifest["manifest_path"]).read_text(encoding="utf-8")
    )
    result = validate_listener_submission(valid, persisted_manifest)
    assert result["status"] == "VALID_HUMAN_SUBMISSION"
    assert (
        datetime.fromisoformat(valid["submitted_at_utc"].replace("Z", "+00:00")).tzinfo
        is not None
    )

    missing_sha_receipt = copy.deepcopy(valid)
    missing_sha_receipt.pop("sha_bindings")
    with pytest.raises(StageUReviewPackageError, match="SHA bindings"):
        validate_listener_submission(missing_sha_receipt, manifest)
    wrong_duration = copy.deepcopy(valid)
    wrong_duration["media_validation"][trial["trial_id"]]["reference"][
        "duration_s"
    ] += 1.0
    with pytest.raises(StageUReviewPackageError, match="duration"):
        validate_listener_submission(wrong_duration, manifest)


def test_playwright_sees_three_players_and_fail_closed_export_gate(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    repository_output = tmp_path / "Jovi_Reference_Parent_Candidate_Review"
    external_output = external_fixture_root / "playwright"
    _build(package_inputs, external_output, repository_output)
    server = create_review_http_server(repository_output, external_output)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with playwright.sync_playwright() as runner:
        browser = runner.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("**/*.wav", lambda route: route.abort())
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        assert page.locator('[data-testid="reference-player"]').count() == 1
        assert page.locator('[data-testid="parent-player"]').count() == 1
        assert page.locator('[data-testid="candidate-player"]').count() == 1
        assert page.locator('[data-testid="blind-b-player"]').count() == 1
        assert page.locator('[data-testid="blind-c-player"]').count() == 1
        assert page.locator('[data-testid="export-submission"]').is_disabled()
        assert (
            "媒体校验未通过" in page.locator('[data-testid="gate-status"]').inner_text()
        )
        page.locator('[data-testid="answer-b"]').check()
        assert page.locator('[data-testid="export-submission"]').is_disabled()
        browser.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_playwright_positive_path_passes_sha_media_and_answer_gates(
    package_inputs: dict[str, object], external_fixture_root: Path, tmp_path: Path
) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    repository_output = tmp_path / "Jovi_Reference_Parent_Candidate_Review"
    external_output = external_fixture_root / "playwright-positive"
    manifest = _build(package_inputs, external_output, repository_output)
    server = create_review_http_server(repository_output, external_output)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with playwright.sync_playwright() as runner:
            browser = runner.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.locator('[data-testid="answer-b"]').check()
            page.locator('[data-testid="export-submission"]').wait_for(state="visible")
            page.wait_for_function(
                "!document.querySelector('[data-testid=export-submission]').disabled"
            )
            trial = manifest["trials"][0]
            expected_b_role = trial["randomized_mapping"]["B"]
            expected_c_role = trial["randomized_mapping"]["C"]
            assert expected_b_role in page.locator(
                '[data-testid="blind-b-player"]'
            ).get_attribute("src")
            assert expected_c_role in page.locator(
                '[data-testid="blind-c-player"]'
            ).get_attribute("src")
            assert (
                "全部门禁" in page.locator('[data-testid="gate-status"]').inner_text()
            )
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
