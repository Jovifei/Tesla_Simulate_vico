from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import base64

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import (
    _read_pcm24_wav,
    _write_pcm24_wav,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_i.named_review import (
    FULL_CYCLE_FILE_IDS,
    PACKAGE_FILE_LAYOUT,
    REQUIRED_SOURCE_FILE_IDS,
    WAITING_STATUS,
    _inspect_wav,
    build_stage_i_named_review,
)


_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
_METRIC_ARTIFACT_LAYOUT = {
    "order_map": "04_Metrics/order_map.png",
    "spectrogram": "04_Metrics/spectrogram.png",
    "state_ratio_map": "04_Metrics/state_ratio_map.png",
    "transient_response": "04_Metrics/transient_response.png",
    "candidate_comparison_metrics": "04_Metrics/candidate_comparison_metrics.json",
}
_DIAGNOSTIC_PACKAGE_ID = "S12_Stage_I_Unqualified_Diagnostic_v1"
_DIAGNOSTIC_STATUS = "UNQUALIFIED_DIAGNOSTIC_ONLY / PARTIAL / AUTOMATED_GATE_FAIL"


def _tone(duration_s: float, frequency_hz: float, amplitude: float) -> np.ndarray:
    frames = int(round(duration_s * 48000))
    time_s = np.arange(frames, dtype=np.float64) / 48000.0
    mono = amplitude * np.sin(2.0 * np.pi * frequency_hz * time_s)
    return np.column_stack((mono, mono))


def _source_wavs(root: Path) -> tuple[dict[str, Path], dict[str, float]]:
    root.mkdir(parents=True, exist_ok=True)
    durations: dict[str, float] = {}
    sources: dict[str, Path] = {}
    for index, file_id in enumerate(REQUIRED_SOURCE_FILE_IDS):
        if file_id in FULL_CYCLE_FILE_IDS:
            duration_s = 0.10
        elif file_id in {"stage_i_shift_dip_rebuild_12s", "stage_i_lift_bypass_12s"}:
            duration_s = 0.06
        else:
            duration_s = 0.05
        path = root / f"{file_id}.wav"
        _write_pcm24_wav(path, _tone(duration_s, 90.0 + index * 13.0, 0.08 + index * 0.002))
        sources[file_id] = path
        durations[file_id] = duration_s
    return sources, durations


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metric_artifacts(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Path] = {}
    for key, relative in _METRIC_ARTIFACT_LAYOUT.items():
        path = root / Path(relative).name
        if path.suffix == ".png":
            path.write_bytes(_PNG_1X1)
        else:
            path.write_text(
                json.dumps({"scope": "synthetic", "status": "candidate"}) + "\n",
                encoding="utf-8",
            )
        artifacts[key] = path
    return artifacts


_CANDIDATE_BINDINGS = {
    "I6-A Balanced": ("stage_i_v6_a_balanced_60s", "candidate-a"),
    "I6-B Whine Forward": ("stage_i_v6_b_whine_forward_60s", "candidate-b"),
    "I6-C Softer Mechanical": ("stage_i_v6_c_softer_mechanical_60s", "candidate-c"),
}


def _json_file(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def _qualification_inputs(
    root: Path,
    sources: dict[str, Path],
    metric_artifacts: dict[str, Path],
    *,
    all_pass: bool = True,
) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    reference = {
        "schema_version": "test-reference-1",
        "automatic_status": "PASS" if all_pass else "PARTIAL / AUTOMATED_GATE_FAIL",
        "candidates": {},
    }
    qualification_candidates: dict[str, object] = {}
    source_evidence: dict[str, object] = {}
    metric_candidates: dict[str, object] = {}
    for index, (label, (file_id, candidate_id)) in enumerate(_CANDIDATE_BINDINGS.items(), 1):
        candidate_sha = hashlib.sha256(f"{candidate_id}:canonical".encode()).hexdigest()
        profile_file_sha = hashlib.sha256(f"{candidate_id}:file".encode()).hexdigest()
        render_sha = hashlib.sha256(f"{candidate_id}:render".encode()).hexdigest()
        metrics = {
            "blower_load_correlation": 0.90 + index * 0.01,
            "sideband_to_main_ratio": 0.08 + index * 0.01,
        }
        pcm_sha = _digest(sources[file_id])
        qualification_candidates[label] = {
            "source_file_id": file_id,
            "binding": {
                "candidate_id": candidate_id,
                "candidate_sha256": candidate_sha,
                "profile_sha256": profile_file_sha,
                "render_sha256": render_sha,
                "final_pcm_sha256": pcm_sha,
            },
            "gates": {"all_pass": all_pass},
            "metrics": metrics,
        }
        source_evidence[file_id] = {
            "candidate_id": candidate_id,
            "path": str(sources[file_id].resolve()),
            "sha256": pcm_sha,
            "source_render_sha256": render_sha,
            "profile_binding": {
                "candidate_id": candidate_id,
                "profile_sha256": candidate_sha,
                "profile_file_sha256": profile_file_sha,
            },
        }
        metric_candidates[label] = {"metrics": metrics}

    for file_id, path in sources.items():
        source_evidence.setdefault(
            file_id,
            {
                "path": str(path.resolve()),
                "sha256": _digest(path),
            },
        )

    metric_artifacts["candidate_comparison_metrics"].write_text(
        json.dumps({"candidates": metric_candidates}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    qualification = {
        "schema_version": "test-qualification-1",
        "automatic_reference_status": reference["automatic_status"],
        "candidates": qualification_candidates,
        "reference_summary": reference,
    }
    source_manifest = {
        "schema_version": "test-source-manifest-1",
        "files": {file_id: str(path.resolve()) for file_id, path in sources.items()},
        "evidence": source_evidence,
        "sealed_key_read": False,
    }
    return {
        "qualification_json": _json_file(root / "qualification.json", qualification),
        "reference_distance_json": _json_file(root / "reference.json", reference),
        "source_manifest": _json_file(root / "source_manifest.json", source_manifest),
    }


def _build_review(
    output_root: Path,
    *,
    source_wavs: dict[str, Path],
    metric_artifacts: dict[str, Path],
    expected_duration_s: dict[str, float],
    audio_provider=None,
    all_pass: bool = True,
    diagnostic_mode: bool = False,
):
    evidence = _qualification_inputs(
        output_root.parent / f"{output_root.name}_qualification",
        source_wavs,
        metric_artifacts,
        all_pass=all_pass,
    )
    return build_stage_i_named_review(
        output_root,
        source_wavs=None if audio_provider is not None else source_wavs,
        audio_provider=audio_provider,
        metric_artifacts=metric_artifacts,
        expected_duration_s=expected_duration_s,
        diagnostic_mode=diagnostic_mode,
        **evidence,
    )


def test_named_stage_i_package_contains_complete_named_review_contract(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")
    result = _build_review(
        tmp_path / "named",
        source_wavs=sources,
        metric_artifacts=artifacts,
        expected_duration_s=durations,
    )
    root = Path(result["output_root"])

    assert result["status"] == WAITING_STATUS
    assert result["package_id"] == "S12_Stage_I_Named_Review_v1"
    for file_id, relative_path in PACKAGE_FILE_LAYOUT.items():
        assert (root / relative_path).is_file(), file_id

    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == WAITING_STATUS
    assert manifest["sealed_key_read"] is False
    assert manifest["engineering_stems_are_product_audio"] is False
    assert set(manifest["files"]) == set(REQUIRED_SOURCE_FILE_IDS)
    assert set(manifest["metric_artifacts"]) == set(_METRIC_ARTIFACT_LAYOUT)
    assert all(Path(item["absolute_path"]).is_absolute() for item in manifest["files"].values())
    assert all(item["health"]["pcm"] == "PCM_24" for item in manifest["files"].values())
    assert all(item["health"]["sample_rate_hz"] == 48000 for item in manifest["files"].values())
    assert all(item["health"]["channels"] == 2 for item in manifest["files"].values())
    assert all(item["health"]["finite"] is True for item in manifest["files"].values())
    assert all(item["health"]["clipping_count"] == 0 for item in manifest["files"].values())

    readme = (root / "00_OPEN_ME_FIRST.md").read_text(encoding="utf-8")
    assert WAITING_STATUS in readme
    assert "0-8 s idle" in readme
    assert "engineering diagnostic stems" in readme
    assert "not product audio" in readme
    assert str((root / PACKAGE_FILE_LAYOUT["stage_i_v6_a_balanced_60s"]).resolve()) in readme

    with (root / "05_Feedback" / "Jovi_Stage_I_Named_Feedback.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(REQUIRED_SOURCE_FILE_IDS)
    assert set(rows[0]) == {
        "file_id",
        "vehicle_id",
        "candidate_id",
        "hellcat_likeness_1_5",
        "whine_presence_1_5",
        "whine_naturalness_1_5",
        "low_frequency_weight_1_5",
        "high_frequency_harshness_1_5",
        "shift_rebuild_naturalness_1_5",
        "bypass_release_naturalness_1_5",
        "artifact_freedom_1_5",
        "preference_rank",
        "keep_or_change",
        "notes",
    }

    with zipfile.ZipFile(root / "S12_Stage_I_Named_Review.zip") as archive:
        names = archive.namelist()
    assert not any("sealed" in name.lower() for name in names)
    assert set(PACKAGE_FILE_LAYOUT.values()).issubset(set(names))
    assert set(_METRIC_ARTIFACT_LAYOUT.values()).issubset(set(names))

    sums = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    }
    assert sums["artifact_manifest.json"] == _digest(root / "artifact_manifest.json")
    assert sums["S12_Stage_I_Named_Review.zip"] == _digest(root / "S12_Stage_I_Named_Review.zip")


def test_named_stage_i_package_preserves_unchanged_anchor_bytes(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    result = _build_review(
        tmp_path / "named",
        source_wavs=sources,
        metric_artifacts=_metric_artifacts(tmp_path / "metrics"),
        expected_duration_s=durations,
    )
    root = Path(result["output_root"])

    for file_id in ("ferrari_458_stage_h_unchanged_60s", "rx7_fd_stage_h_unchanged_60s"):
        assert _digest(root / PACKAGE_FILE_LAYOUT[file_id]) == _digest(sources[file_id])


def test_named_stage_i_package_applies_common_attenuation_to_comparison_groups(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    result = _build_review(
        tmp_path / "named",
        source_wavs=sources,
        metric_artifacts=_metric_artifacts(tmp_path / "metrics"),
        expected_duration_s=durations,
    )
    root = Path(result["output_root"])
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))

    full_cycle_gains = [manifest["files"][file_id]["gain_db"] for file_id in FULL_CYCLE_FILE_IDS]
    assert all(gain <= 0.0 for gain in full_cycle_gains)
    assert max(item["loudness"]["integrated_lufs"] for key, item in manifest["files"].items() if key in FULL_CYCLE_FILE_IDS) - min(
        item["loudness"]["integrated_lufs"] for key, item in manifest["files"].items() if key in FULL_CYCLE_FILE_IDS
    ) <= 0.10


def test_named_stage_i_package_fails_closed_on_missing_source(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    missing_id = "stage_i_lift_bypass_12s"
    sources.pop(missing_id)

    with pytest.raises(ValueError, match=missing_id):
        _build_review(
            tmp_path / "named",
            source_wavs=sources,
            metric_artifacts=_metric_artifacts(tmp_path / "metrics"),
            expected_duration_s=durations,
        )


def test_named_stage_i_package_accepts_injected_audio_provider(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    calls: list[str] = []

    def provider(file_id: str) -> Path:
        calls.append(file_id)
        return sources[file_id]

    result = _build_review(
        tmp_path / "named",
        source_wavs=sources,
        audio_provider=provider,
        metric_artifacts=_metric_artifacts(tmp_path / "metrics"),
        expected_duration_s=durations,
    )

    assert result["status"] == WAITING_STATUS
    assert calls == list(REQUIRED_SOURCE_FILE_IDS)
    assert _read_pcm24_wav(Path(result["output_root"]) / PACKAGE_FILE_LAYOUT["stage_i_shift_dip_rebuild_12s"]).shape[1] == 2


def test_named_stage_i_package_requires_exact_metric_artifacts(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")
    artifacts.pop("transient_response")

    with pytest.raises(ValueError, match="metric_artifacts exact-key"):
        _build_review(
            tmp_path / "named",
            source_wavs=sources,
            metric_artifacts=artifacts,
            expected_duration_s=durations,
        )


def test_named_stage_i_package_enforces_its_own_final_peak_gate(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    frames = int(round(durations["ferrari_458_stage_h_unchanged_60s"] * 48000))
    impulse = np.zeros((frames, 2), dtype=np.float64)
    impulse[frames // 2] = 0.95
    _write_pcm24_wav(sources["ferrari_458_stage_h_unchanged_60s"], impulse)

    with pytest.raises(ValueError, match="final WAV peak exceeds -1.5 dBFS"):
        _build_review(
            tmp_path / "named",
            source_wavs=sources,
            metric_artifacts=_metric_artifacts(tmp_path / "metrics"),
            expected_duration_s=durations,
        )


def test_named_stage_i_package_preserves_blower_group_loudness_spread(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    for file_id, amplitude in zip(
        (
            "stage_h_blower_only_acceleration",
            "stage_i_a_blower_only_acceleration",
            "stage_i_b_blower_only_acceleration",
            "stage_i_c_blower_only_acceleration",
        ),
        (0.03, 0.05, 0.08, 0.12),
        strict=True,
    ):
        _write_pcm24_wav(sources[file_id], _tone(durations[file_id], 720.0, amplitude))
    result = _build_review(
        tmp_path / "named",
        source_wavs=sources,
        metric_artifacts=_metric_artifacts(tmp_path / "metrics"),
        expected_duration_s=durations,
    )
    manifest = json.loads(
        (Path(result["output_root"]) / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    blower_ids = (
        "stage_h_blower_only_acceleration",
        "stage_i_a_blower_only_acceleration",
        "stage_i_b_blower_only_acceleration",
        "stage_i_c_blower_only_acceleration",
    )
    source_lufs = [
        manifest["files"][file_id]["source_integrated_lufs"] for file_id in blower_ids
    ]
    final_lufs = [
        manifest["files"][file_id]["loudness"]["integrated_lufs"] for file_id in blower_ids
    ]
    gains = [manifest["files"][file_id]["gain_db"] for file_id in blower_ids]

    assert len({round(value, 9) for value in gains}) == 1
    assert all(value <= 0.0 for value in gains)
    assert max(final_lufs) - min(final_lufs) == pytest.approx(
        max(source_lufs) - min(source_lufs), abs=0.10
    )
    assert max(final_lufs) - min(final_lufs) > 1.0


def test_named_review_script_supports_direct_help() -> None:
    script = Path(__file__).parents[1] / "scripts" / "build_stage_i_named_review.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--qualification-json" in result.stdout
    assert "--reference-distance-json" in result.stdout
    assert "--source-manifest" in result.stdout
    assert "--unqualified-diagnostic" in result.stdout


def test_named_package_accepts_one_endpoint_sample_but_rejects_two(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    file_id = "stage_h_blower_only_acceleration"
    frames = int(round(durations[file_id] * 48000))
    _write_pcm24_wav(sources[file_id], _tone((frames + 1) / 48000.0, 720.0, 0.05))
    result = _build_review(
        tmp_path / "one_sample",
        source_wavs=sources,
        metric_artifacts=_metric_artifacts(tmp_path / "metrics_one"),
        expected_duration_s=durations,
    )
    assert result["status"] == WAITING_STATUS

    _write_pcm24_wav(sources[file_id], _tone((frames + 2) / 48000.0, 720.0, 0.05))
    with pytest.raises(ValueError, match="unexpected duration"):
        _build_review(
            tmp_path / "two_samples",
            source_wavs=sources,
            metric_artifacts=_metric_artifacts(tmp_path / "metrics_two"),
            expected_duration_s=durations,
        )


def test_duration_contract_compares_integer_frames_at_eight_seconds(tmp_path: Path) -> None:
    path = tmp_path / "endpoint.wav"
    _write_pcm24_wav(path, np.zeros((8 * 48000 + 1, 2), dtype=np.float64))
    _inspect_wav(path, 8.0)

    _write_pcm24_wav(path, np.zeros((8 * 48000 + 2, 2), dtype=np.float64))
    with pytest.raises(ValueError, match="unexpected duration"):
        _inspect_wav(path, 8.0)


def test_named_package_fails_closed_when_any_candidate_is_unqualified(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")

    output_root = tmp_path / "named"
    with pytest.raises(ValueError, match="unqualified Stage-I candidates"):
        _build_review(
            output_root,
            source_wavs=sources,
            metric_artifacts=artifacts,
            expected_duration_s=durations,
            all_pass=False,
        )
    assert not output_root.exists()


@pytest.mark.parametrize(
    "file_id",
    (
        "stage_h_v5_baseline_60s",
        "ferrari_458_stage_h_unchanged_60s",
        "stage_h_blower_only_acceleration",
    ),
)
def test_named_package_rejects_healthy_in_place_source_byte_replacement(
    tmp_path: Path,
    file_id: str,
) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")
    evidence = _qualification_inputs(tmp_path / "evidence", sources, artifacts)
    _write_pcm24_wav(
        sources[file_id],
        _tone(durations[file_id], 1337.0, 0.04),
    )

    with pytest.raises(ValueError, match=f"source manifest byte SHA mismatch: {file_id}"):
        build_stage_i_named_review(
            tmp_path / "named",
            source_wavs=sources,
            metric_artifacts=artifacts,
            expected_duration_s=durations,
            **evidence,
        )


def test_diagnostic_mode_marks_every_public_artifact_as_unqualified(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")
    result = _build_review(
        tmp_path / "named",
        source_wavs=sources,
        metric_artifacts=artifacts,
        expected_duration_s=durations,
        all_pass=False,
        diagnostic_mode=True,
    )
    root = Path(result["output_root"])
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    readme = (root / "00_OPEN_ME_FIRST.md").read_text(encoding="utf-8")

    assert result["package_id"] == _DIAGNOSTIC_PACKAGE_ID
    assert result["status"] == _DIAGNOSTIC_STATUS
    assert Path(result["zip"]).name == "S12_Stage_I_Unqualified_Diagnostic.zip"
    assert manifest["package_id"] == _DIAGNOSTIC_PACKAGE_ID
    assert manifest["status"] == _DIAGNOSTIC_STATUS
    assert manifest["qualified_for_human_gate"] is False
    assert "UNQUALIFIED_DIAGNOSTIC_ONLY" in readme
    assert "WAITING_FOR_JOVI" not in readme


def test_named_package_binds_qualification_reference_source_and_metric_hashes(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")
    evidence = _qualification_inputs(tmp_path / "evidence", sources, artifacts)
    result = build_stage_i_named_review(
        tmp_path / "named",
        source_wavs=sources,
        metric_artifacts=artifacts,
        expected_duration_s=durations,
        **evidence,
    )
    manifest = json.loads(
        (Path(result["output_root"]) / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    bindings = manifest["qualification_evidence"]

    assert bindings["qualification"]["file_sha256"] == _digest(evidence["qualification_json"])
    assert bindings["reference_distance"]["file_sha256"] == _digest(
        evidence["reference_distance_json"]
    )
    assert bindings["source_manifest"]["file_sha256"] == _digest(evidence["source_manifest"])
    for evidence_id, relative_path in {
        "qualification": "04_Metrics/stage_i_qualification.json",
        "reference_distance": "04_Metrics/stage_i_reference_distance.json",
        "source_manifest": "04_Metrics/stage_i_source_manifest.json",
    }.items():
        assert bindings[evidence_id]["packaged_sha256"] == _digest(
            Path(result["output_root"]) / relative_path
        )
    assert (
        bindings["reference_distance"]["canonical_sha256"]
        == bindings["qualification"]["embedded_reference_summary_canonical_sha256"]
    )
    assert set(bindings["candidate_bindings"]) == set(_CANDIDATE_BINDINGS)
    assert all(item["exact_binding"] is True for item in bindings["candidate_bindings"].values())
    assert all(item["metrics_exact_binding"] is True for item in bindings["candidate_bindings"].values())
    assert set(bindings["metric_artifact_sha256"]) == set(_METRIC_ARTIFACT_LAYOUT)


def test_named_package_rejects_candidate_binding_drift(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")
    evidence = _qualification_inputs(tmp_path / "evidence", sources, artifacts)
    source_manifest = json.loads(evidence["source_manifest"].read_text(encoding="utf-8"))
    source_manifest["evidence"]["stage_i_v6_a_balanced_60s"]["sha256"] = "0" * 64
    _json_file(evidence["source_manifest"], source_manifest)

    with pytest.raises(ValueError, match="candidate/source binding mismatch"):
        build_stage_i_named_review(
            tmp_path / "named",
            source_wavs=sources,
            metric_artifacts=artifacts,
            expected_duration_s=durations,
            **evidence,
        )


def test_named_package_rejects_source_manifest_that_claims_sealed_key_was_read(
    tmp_path: Path,
) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")
    evidence = _qualification_inputs(tmp_path / "evidence", sources, artifacts)
    source_manifest = json.loads(evidence["source_manifest"].read_text(encoding="utf-8"))
    source_manifest["sealed_key_read"] = True
    _json_file(evidence["source_manifest"], source_manifest)

    with pytest.raises(ValueError, match="sealed key must remain unread"):
        build_stage_i_named_review(
            tmp_path / "named",
            source_wavs=sources,
            metric_artifacts=artifacts,
            expected_duration_s=durations,
            **evidence,
        )


def test_named_package_rejects_reference_or_metric_binding_drift(tmp_path: Path) -> None:
    sources, durations = _source_wavs(tmp_path / "sources")
    artifacts = _metric_artifacts(tmp_path / "metrics")
    evidence = _qualification_inputs(tmp_path / "reference_evidence", sources, artifacts)
    reference = json.loads(evidence["reference_distance_json"].read_text(encoding="utf-8"))
    reference["automatic_status"] = "DRIFT"
    _json_file(evidence["reference_distance_json"], reference)
    with pytest.raises(ValueError, match="reference summary mismatch"):
        build_stage_i_named_review(
            tmp_path / "reference_named",
            source_wavs=sources,
            metric_artifacts=artifacts,
            expected_duration_s=durations,
            **evidence,
        )

    artifacts = _metric_artifacts(tmp_path / "metrics_drift")
    evidence = _qualification_inputs(tmp_path / "metric_evidence", sources, artifacts)
    metric_payload = json.loads(
        artifacts["candidate_comparison_metrics"].read_text(encoding="utf-8")
    )
    metric_payload["candidates"]["I6-A Balanced"]["metrics"][
        "blower_load_correlation"
    ] = 0.123
    _json_file(artifacts["candidate_comparison_metrics"], metric_payload)
    with pytest.raises(ValueError, match="candidate metrics mismatch"):
        build_stage_i_named_review(
            tmp_path / "metric_named",
            source_wavs=sources,
            metric_artifacts=artifacts,
            expected_duration_s=durations,
            **evidence,
        )
