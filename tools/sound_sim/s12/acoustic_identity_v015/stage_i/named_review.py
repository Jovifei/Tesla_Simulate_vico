"""Assemble the named Stage-I engineering review from already rendered WAVs.

The builder deliberately does not import a candidate renderer.  A caller may
provide either existing WAV paths or an injected provider returning such paths.
This keeps packaging independent from candidate search and, importantly, never
opens the anonymous Stage-G sealed key.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Callable, Mapping
import zipfile

import numpy as np

from ..loudness_manager import measure_loudness
from ..render_identity_v02 import _health, _read_pcm24_wav, _write_pcm24_wav


PACKAGE_ID = "S12_Stage_I_Named_Review_v1"
WAITING_STATUS = "WAITING_FOR_JOVI_STAGE_I_NAMED_REVIEW"
DIAGNOSTIC_PACKAGE_ID = "S12_Stage_I_Unqualified_Diagnostic_v1"
DIAGNOSTIC_STATUS = "UNQUALIFIED_DIAGNOSTIC_ONLY / PARTIAL / AUTOMATED_GATE_FAIL"
PROVENANCE = "synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction"
METRIC_ARTIFACT_LAYOUT: dict[str, str] = {
    "order_map": "04_Metrics/order_map.png",
    "spectrogram": "04_Metrics/spectrogram.png",
    "state_ratio_map": "04_Metrics/state_ratio_map.png",
    "transient_response": "04_Metrics/transient_response.png",
    "candidate_comparison_metrics": "04_Metrics/candidate_comparison_metrics.json",
}
QUALIFICATION_EVIDENCE_LAYOUT: dict[str, str] = {
    "qualification": "04_Metrics/stage_i_qualification.json",
    "reference_distance": "04_Metrics/stage_i_reference_distance.json",
    "source_manifest": "04_Metrics/stage_i_source_manifest.json",
}

PACKAGE_FILE_LAYOUT: dict[str, str] = {
    "stage_h_v5_baseline_60s": "01_Hellcat_60s/01_StageH_v5_Baseline_60s.wav",
    "stage_i_v6_a_balanced_60s": "01_Hellcat_60s/02_StageI_v6_A_Balanced_60s.wav",
    "stage_i_v6_b_whine_forward_60s": "01_Hellcat_60s/03_StageI_v6_B_WhineForward_60s.wav",
    "stage_i_v6_c_softer_mechanical_60s": "01_Hellcat_60s/04_StageI_v6_C_SofterMechanical_60s.wav",
    "stage_h_blower_only_acceleration": "02_Hellcat_Diagnostics/StageH_BlowerOnly_Acceleration.wav",
    "stage_i_a_blower_only_acceleration": "02_Hellcat_Diagnostics/StageI_A_BlowerOnly_Acceleration.wav",
    "stage_i_b_blower_only_acceleration": "02_Hellcat_Diagnostics/StageI_B_BlowerOnly_Acceleration.wav",
    "stage_i_c_blower_only_acceleration": "02_Hellcat_Diagnostics/StageI_C_BlowerOnly_Acceleration.wav",
    "stage_i_shift_dip_rebuild_12s": "02_Hellcat_Diagnostics/StageI_Shift_Dip_Rebuild_12s.wav",
    "stage_i_lift_bypass_12s": "02_Hellcat_Diagnostics/StageI_Lift_Bypass_12s.wav",
    "stage_i_exhaust_only_acceleration": "02_Hellcat_Diagnostics/StageI_ExhaustOnly_Acceleration.wav",
    "ferrari_458_stage_h_unchanged_60s": "03_Anchor_Mapping/Ferrari_458_StageH_Unchanged_60s.wav",
    "rx7_fd_stage_h_unchanged_60s": "03_Anchor_Mapping/RX7_FD_StageH_Unchanged_60s.wav",
}
REQUIRED_SOURCE_FILE_IDS = tuple(PACKAGE_FILE_LAYOUT)
FULL_CYCLE_FILE_IDS = REQUIRED_SOURCE_FILE_IDS[:4]
_BLOWER_GROUP = REQUIRED_SOURCE_FILE_IDS[4:8]
_UNCHANGED_ANCHORS = REQUIRED_SOURCE_FILE_IDS[-2:]
_DIAGNOSTIC_IDS = frozenset(REQUIRED_SOURCE_FILE_IDS[4:11])

_VEHICLES = {
    **{file_id: "hellcat" for file_id in REQUIRED_SOURCE_FILE_IDS[:-2]},
    "ferrari_458_stage_h_unchanged_60s": "ferrari_458",
    "rx7_fd_stage_h_unchanged_60s": "rx7_fd",
}
_CANDIDATES = {
    "stage_h_v5_baseline_60s": "Hellcat_candidate_v5",
    "stage_i_v6_a_balanced_60s": "I6-A Balanced",
    "stage_i_v6_b_whine_forward_60s": "I6-B Whine Forward",
    "stage_i_v6_c_softer_mechanical_60s": "I6-C Softer Mechanical",
    "stage_h_blower_only_acceleration": "Hellcat_candidate_v5",
    "stage_i_a_blower_only_acceleration": "I6-A Balanced",
    "stage_i_b_blower_only_acceleration": "I6-B Whine Forward",
    "stage_i_c_blower_only_acceleration": "I6-C Softer Mechanical",
    "stage_i_shift_dip_rebuild_12s": "Stage I selected diagnostic",
    "stage_i_lift_bypass_12s": "Stage I selected diagnostic",
    "stage_i_exhaust_only_acceleration": "Stage I selected diagnostic",
    "ferrari_458_stage_h_unchanged_60s": "Stage H unchanged",
    "rx7_fd_stage_h_unchanged_60s": "Stage H unchanged",
}
_QUALIFICATION_CANDIDATE_SOURCE_IDS = {
    "I6-A Balanced": "stage_i_v6_a_balanced_60s",
    "I6-B Whine Forward": "stage_i_v6_b_whine_forward_60s",
    "I6-C Softer Mechanical": "stage_i_v6_c_softer_mechanical_60s",
}
_DEFAULT_DURATION_S = {
    **{file_id: 60.0 for file_id in FULL_CYCLE_FILE_IDS},
    **{file_id: 8.0 for file_id in (*_BLOWER_GROUP, "stage_i_exhaust_only_acceleration")},
    "stage_i_shift_dip_rebuild_12s": 12.0,
    "stage_i_lift_bypass_12s": 12.0,
    "ferrari_458_stage_h_unchanged_60s": 60.0,
    "rx7_fd_stage_h_unchanged_60s": 60.0,
}

AudioProvider = Callable[[str], str | Path]
JsonEvidence = str | Path | Mapping[str, object]


def build_stage_i_named_review(
    output_root: str | Path,
    *,
    source_wavs: Mapping[str, str | Path] | None = None,
    audio_provider: AudioProvider | None = None,
    metric_artifacts: Mapping[str, str | Path],
    qualification_json: JsonEvidence,
    reference_distance_json: JsonEvidence,
    source_manifest: JsonEvidence,
    expected_duration_s: Mapping[str, float] | None = None,
    diagnostic_mode: bool = False,
) -> dict[str, object]:
    """Build a complete named review without touching an anonymous sealed key."""
    qualification, qualification_record = _load_json_evidence(
        qualification_json, "qualification JSON"
    )
    reference_distance, reference_record = _load_json_evidence(
        reference_distance_json, "reference-distance JSON"
    )
    source_manifest_payload, source_manifest_record = _load_json_evidence(
        source_manifest, "source manifest"
    )
    metrics = _validated_metric_artifacts(metric_artifacts)
    metric_payload = json.loads(
        metrics["candidate_comparison_metrics"].read_text(encoding="utf-8")
    )
    candidate_bindings, all_candidates_pass = _validate_qualification_bindings(
        qualification,
        reference_distance,
        source_manifest_payload,
        metric_payload,
    )
    if not all_candidates_pass and not diagnostic_mode:
        raise ValueError(
            "unqualified Stage-I candidates: use diagnostic_mode=True only for an "
            "UNQUALIFIED_DIAGNOSTIC_ONLY package"
        )
    package_id = DIAGNOSTIC_PACKAGE_ID if diagnostic_mode else PACKAGE_ID
    status = DIAGNOSTIC_STATUS if diagnostic_mode else WAITING_STATUS
    zip_name = (
        "S12_Stage_I_Unqualified_Diagnostic.zip"
        if diagnostic_mode
        else "S12_Stage_I_Named_Review.zip"
    )

    manifest_files = source_manifest_payload.get("files")
    if not isinstance(manifest_files, Mapping):
        raise ValueError("source manifest must contain a files object")
    missing_manifest_files = set(REQUIRED_SOURCE_FILE_IDS) - set(manifest_files)
    unknown_manifest_files = set(manifest_files) - set(REQUIRED_SOURCE_FILE_IDS)
    if missing_manifest_files:
        raise ValueError(f"source manifest is missing file_id: {sorted(missing_manifest_files)[0]}")
    if unknown_manifest_files:
        raise ValueError(f"source manifest has unknown file_id: {sorted(unknown_manifest_files)[0]}")
    if source_wavs is None and audio_provider is None:
        source_wavs = manifest_files
    if (source_wavs is None) == (audio_provider is None):
        raise ValueError("provide exactly one of source_wavs or audio_provider")
    if source_wavs is not None:
        missing = set(REQUIRED_SOURCE_FILE_IDS) - set(source_wavs)
        unknown = set(source_wavs) - set(REQUIRED_SOURCE_FILE_IDS)
        if missing:
            raise ValueError(f"missing source file_id: {sorted(missing)[0]}")
        if unknown:
            raise ValueError(f"unknown source file_id: {sorted(unknown)[0]}")
        provider: AudioProvider = lambda file_id: source_wavs[file_id]
    else:
        assert audio_provider is not None
        provider = audio_provider

    duration_contract = dict(_DEFAULT_DURATION_S if expected_duration_s is None else expected_duration_s)
    missing_duration = set(REQUIRED_SOURCE_FILE_IDS) - set(duration_contract)
    if missing_duration:
        raise ValueError(f"missing expected duration for: {sorted(missing_duration)[0]}")

    root = Path(output_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Stage-I named output must be a new directory: {root}")
    for relative in (
        "01_Hellcat_60s",
        "02_Hellcat_Diagnostics",
        "03_Anchor_Mapping",
        "04_Metrics",
        "05_Feedback",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)

    sources: dict[str, Path] = {}
    for file_id in REQUIRED_SOURCE_FILE_IDS:
        path = Path(provider(file_id)).resolve()
        if not path.is_file():
            raise ValueError(f"source WAV does not exist for {file_id}: {path}")
        _inspect_wav(path, float(duration_contract[file_id]))
        manifest_source = manifest_files.get(file_id)
        if not isinstance(manifest_source, (str, Path)) or Path(manifest_source).resolve() != path:
            raise ValueError(f"source manifest path mismatch for {file_id}")
        sources[file_id] = path

    _validate_all_source_manifest_entries(source_manifest_payload, sources)
    _validate_candidate_source_bytes(candidate_bindings, sources)

    metric_evidence: dict[str, dict[str, object]] = {}
    for artifact_id, source in metrics.items():
        destination = root / METRIC_ARTIFACT_LAYOUT[artifact_id]
        shutil.copyfile(source, destination)
        metric_evidence[artifact_id] = {
            "relative_path": METRIC_ARTIFACT_LAYOUT[artifact_id],
            "absolute_path": str(destination.resolve()),
            "sha256": _sha256(destination),
            "source_sha256": _sha256(source),
            "bytes": destination.stat().st_size,
        }

    qualification_evidence = {
        "qualification": {
            **qualification_record,
            "relative_path": QUALIFICATION_EVIDENCE_LAYOUT["qualification"],
            "embedded_reference_summary_canonical_sha256": _canonical_json_sha256(
                qualification["reference_summary"]
            ),
        },
        "reference_distance": {
            **reference_record,
            "relative_path": QUALIFICATION_EVIDENCE_LAYOUT["reference_distance"],
        },
        "source_manifest": {
            **source_manifest_record,
            "relative_path": QUALIFICATION_EVIDENCE_LAYOUT["source_manifest"],
        },
        "candidate_bindings": candidate_bindings,
        "metric_artifact_sha256": {
            artifact_id: item["sha256"] for artifact_id, item in metric_evidence.items()
        },
        "all_candidates_pass": all_candidates_pass,
        "diagnostic_mode": bool(diagnostic_mode),
    }
    for evidence_id, payload in (
        ("qualification", qualification),
        ("reference_distance", reference_distance),
        ("source_manifest", source_manifest_payload),
    ):
        destination = root / QUALIFICATION_EVIDENCE_LAYOUT[evidence_id]
        destination.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        qualification_evidence[evidence_id]["packaged_sha256"] = _sha256(destination)

    file_evidence: dict[str, dict[str, object]] = {}
    _write_fair_group(root, sources, FULL_CYCLE_FILE_IDS, "hellcat_full_cycle", file_evidence)
    _write_fair_group(
        root,
        sources,
        _BLOWER_GROUP,
        "blower_only_acceleration",
        file_evidence,
        preserve_spread=True,
    )

    for file_id in REQUIRED_SOURCE_FILE_IDS:
        if file_id in FULL_CYCLE_FILE_IDS or file_id in _BLOWER_GROUP:
            continue
        destination = root / PACKAGE_FILE_LAYOUT[file_id]
        shutil.copyfile(sources[file_id], destination)
        file_evidence[file_id] = _file_evidence(
            file_id,
            destination,
            sources[file_id],
            gain_db=0.0,
            fairness_group=None,
        )

    (root / "04_Metrics" / "candidate_comparison.json").write_text(
        json.dumps(
            {
                "package_id": package_id,
                "status": status,
                "files": file_evidence,
                "qualification_evidence": qualification_evidence,
                "provenance": PROVENANCE,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_feedback_template(root / "05_Feedback" / "Jovi_Stage_I_Named_Feedback.csv")
    (root / "00_OPEN_ME_FIRST.md").write_text(
        _open_me_first(root, package_id=package_id, status=status, diagnostic_mode=diagnostic_mode),
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "package_id": package_id,
        "status": status,
        "qualified_for_human_gate": all_candidates_pass and not diagnostic_mode,
        "sealed_key_read": False,
        "engineering_stems_are_product_audio": False,
        "timeline": {
            "idle": "0-8 s",
            "acceleration_with_three_shifts": "8-26 s",
            "full_pull": "26-36 s",
            "lift_afterfire_bypass": "36-46 s",
            "coast": "46-52 s",
            "idle_return": "52-60 s",
        },
        "files": file_evidence,
        "metric_artifacts": metric_evidence,
        "qualification_evidence": qualification_evidence,
        "provenance": PROVENANCE,
    }
    (root / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    zip_path = root / zip_name
    _zip_tree(zip_path, root)
    _write_sha256sums(root)
    return {
        "package_id": package_id,
        "output_root": str(root),
        "status": status,
        "core_wavs": [str((root / PACKAGE_FILE_LAYOUT[file_id]).resolve()) for file_id in FULL_CYCLE_FILE_IDS],
        "zip": str(zip_path),
    }


def _write_fair_group(
    root: Path,
    sources: Mapping[str, Path],
    file_ids: tuple[str, ...],
    fairness_group: str,
    evidence: dict[str, dict[str, object]],
    preserve_spread: bool = False,
) -> None:
    audio = {file_id: _read_pcm24_wav(sources[file_id]) for file_id in file_ids}
    measured = {file_id: float(measure_loudness(value).integrated_lufs) for file_id, value in audio.items()}
    if not all(np.isfinite(value) for value in measured.values()):
        raise ValueError(f"non-finite input loudness in fairness group: {fairness_group}")
    target_lufs = min(-20.0, *measured.values())
    common_gain_db = 0.0
    if preserve_spread:
        max_peak = max(_peak_dbfs(value) for value in audio.values())
        peak_gain = -1.5 - max_peak if np.isfinite(max_peak) else 0.0
        common_gain_db = min(
            0.0,
            target_lufs - min(measured.values()),
            peak_gain,
        )
    for file_id in file_ids:
        gain_db = (
            common_gain_db
            if preserve_spread
            else min(0.0, target_lufs - measured[file_id])
        )
        destination = root / PACKAGE_FILE_LAYOUT[file_id]
        _write_pcm24_wav(destination, audio[file_id] * (10.0 ** (gain_db / 20.0)))
        evidence[file_id] = _file_evidence(
            file_id,
            destination,
            sources[file_id],
            gain_db=gain_db,
            fairness_group=fairness_group,
            source_integrated_lufs=measured[file_id],
            group_target_lufs=target_lufs,
        )


def _file_evidence(
    file_id: str,
    path: Path,
    source_path: Path,
    *,
    gain_db: float,
    fairness_group: str | None,
    source_integrated_lufs: float | None = None,
    group_target_lufs: float | None = None,
) -> dict[str, object]:
    audio = _read_pcm24_wav(path)
    health = _health(audio)
    if not bool(health["finite"]) or int(health["clipping_count"]) != 0:
        raise ValueError(f"final WAV health gate failed: {path}")
    if float(health["peak_dbfs"]) > -1.5 + 1e-6:
        raise ValueError(f"final WAV peak exceeds -1.5 dBFS: {path}")
    loudness = measure_loudness(audio)
    return {
        "relative_path": PACKAGE_FILE_LAYOUT[file_id],
        "absolute_path": str(path.resolve()),
        "sha256": _sha256(path),
        "source_sha256": _sha256(source_path),
        "vehicle_id": _VEHICLES[file_id],
        "candidate_id": _CANDIDATES[file_id],
        "engineering_diagnostic": file_id in _DIAGNOSTIC_IDS,
        "product_audio": file_id not in _DIAGNOSTIC_IDS,
        "fairness_group": fairness_group,
        "gain_db": float(gain_db),
        "source_integrated_lufs": source_integrated_lufs,
        "group_target_lufs": group_target_lufs,
        "loudness": {
            "integrated_lufs": float(loudness.integrated_lufs),
            "rms_dbfs": float(loudness.rms_dbfs),
            "peak_dbfs": float(loudness.peak_dbfs),
            "crest_factor_db": float(loudness.crest_factor_db),
            "clipping_count": int(loudness.clipping_count),
        },
        "health": health,
    }


def _peak_dbfs(audio: np.ndarray) -> float:
    peak = float(np.max(np.abs(np.asarray(audio, dtype=np.float64)), initial=0.0))
    return float(20.0 * np.log10(peak)) if peak > 0.0 else float("-inf")


def _inspect_wav(path: Path, expected_duration_s: float) -> None:
    if not np.isfinite(expected_duration_s) or expected_duration_s <= 0.0:
        raise ValueError(f"invalid expected duration for {path}")
    audio = _read_pcm24_wav(path)
    expected_frames = int(round(expected_duration_s * 48000.0))
    actual_frames = int(audio.shape[0])
    actual = actual_frames / 48000.0
    if abs(actual_frames - expected_frames) > 1:
        raise ValueError(
            f"unexpected duration for {path}: expected {expected_duration_s:.6f}, got {actual:.6f}"
        )
    health = _health(audio)
    if not bool(health["finite"]) or int(health["clipping_count"]) != 0:
        raise ValueError(f"source WAV health gate failed: {path}")


def _validated_metric_artifacts(
    provided: Mapping[str, str | Path],
) -> dict[str, Path]:
    if not isinstance(provided, Mapping) or set(provided) != set(METRIC_ARTIFACT_LAYOUT):
        raise ValueError("metric_artifacts exact-key contract mismatch")
    validated: dict[str, Path] = {}
    for artifact_id in METRIC_ARTIFACT_LAYOUT:
        path = Path(provided[artifact_id]).resolve()
        if not path.is_file():
            raise ValueError(f"metric artifact is missing: {artifact_id}")
        payload = path.read_bytes()
        if artifact_id == "candidate_comparison_metrics":
            try:
                decoded = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("candidate comparison metrics JSON is invalid") from error
            if not isinstance(decoded, Mapping) or not decoded or not _json_finite(decoded):
                raise ValueError("candidate comparison metrics JSON must be a finite object")
        elif not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"metric artifact is not a PNG: {artifact_id}")
        validated[artifact_id] = path
    return validated


def _load_json_evidence(value: JsonEvidence, label: str) -> tuple[dict[str, object], dict[str, object]]:
    if isinstance(value, Mapping):
        payload = dict(value)
        if not payload or not _json_finite(payload):
            raise ValueError(f"{label} must be a finite object")
        canonical_sha = _canonical_json_sha256(payload)
        return payload, {
            "source": "in_memory_object",
            "file_sha256": canonical_sha,
            "canonical_sha256": canonical_sha,
        }
    path = Path(value).resolve()
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid") from error
    if not isinstance(payload, dict) or not payload or not _json_finite(payload):
        raise ValueError(f"{label} must be a finite object")
    return payload, {
        "source": str(path),
        "file_sha256": _sha256(path),
        "canonical_sha256": _canonical_json_sha256(payload),
    }


def _canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_qualification_bindings(
    qualification: Mapping[str, object],
    reference_distance: Mapping[str, object],
    source_manifest: Mapping[str, object],
    metric_payload: Mapping[str, object],
) -> tuple[dict[str, dict[str, object]], bool]:
    if source_manifest.get("sealed_key_read") is not False:
        raise ValueError("source manifest sealed key must remain unread")
    embedded_reference = qualification.get("reference_summary")
    if not isinstance(embedded_reference, Mapping) or embedded_reference != reference_distance:
        raise ValueError("reference summary mismatch between qualification and reference-distance JSON")
    qualification_candidates = qualification.get("candidates")
    metric_candidates = metric_payload.get("candidates")
    source_evidence = source_manifest.get("evidence")
    required_labels = set(_QUALIFICATION_CANDIDATE_SOURCE_IDS)
    if not isinstance(qualification_candidates, Mapping) or set(qualification_candidates) != required_labels:
        raise ValueError("qualification candidates exact-key contract mismatch")
    if not isinstance(metric_candidates, Mapping) or set(metric_candidates) != required_labels:
        raise ValueError("candidate metrics exact-key contract mismatch")
    if not isinstance(source_evidence, Mapping):
        raise ValueError("source manifest must contain an evidence object")

    result: dict[str, dict[str, object]] = {}
    all_pass = True
    for label in _QUALIFICATION_CANDIDATE_SOURCE_IDS:
        qualified = qualification_candidates[label]
        metric_item = metric_candidates[label]
        if not isinstance(qualified, Mapping) or not isinstance(metric_item, Mapping):
            raise ValueError(f"candidate evidence must be an object: {label}")
        source_file_id = qualified.get("source_file_id")
        binding = qualified.get("binding")
        gates = qualified.get("gates")
        qualification_metrics = qualified.get("metrics")
        metric_values = metric_item.get("metrics")
        if (
            not isinstance(source_file_id, str)
            or source_file_id != _QUALIFICATION_CANDIDATE_SOURCE_IDS[label]
        ):
            raise ValueError(f"candidate source file_id mismatch: {label}")
        if not isinstance(binding, Mapping) or not isinstance(gates, Mapping):
            raise ValueError(f"candidate qualification is incomplete: {label}")
        gate_value = gates.get("all_pass")
        if type(gate_value) is not bool:
            raise ValueError(f"candidate all_pass gate must be a strict bool: {label}")
        all_pass = all_pass and gate_value
        source = source_evidence.get(source_file_id)
        if not isinstance(source, Mapping):
            raise ValueError(f"source evidence is missing for candidate: {label}")
        profile_binding = source.get("profile_binding")
        if not isinstance(profile_binding, Mapping):
            raise ValueError(f"source profile binding is missing for candidate: {label}")
        expected = {
            "candidate_id": binding.get("candidate_id"),
            "candidate_sha256": binding.get("candidate_sha256"),
            "profile_sha256": binding.get("profile_sha256"),
            "render_sha256": binding.get("render_sha256"),
            "final_pcm_sha256": binding.get("final_pcm_sha256"),
        }
        actual = {
            "candidate_id": source.get("candidate_id"),
            "candidate_sha256": profile_binding.get("profile_sha256"),
            "profile_sha256": profile_binding.get("profile_file_sha256"),
            "render_sha256": source.get("source_render_sha256"),
            "final_pcm_sha256": source.get("sha256"),
        }
        if any(not isinstance(value, str) or not value for value in expected.values()) or actual != expected:
            raise ValueError(f"candidate/source binding mismatch: {label}")
        if not isinstance(qualification_metrics, Mapping) or qualification_metrics != metric_values:
            raise ValueError(f"candidate metrics mismatch: {label}")
        metric_sha = _canonical_json_sha256(qualification_metrics)
        result[label] = {
            "source_file_id": source_file_id,
            **expected,
            "exact_binding": True,
            "qualification_metrics_sha256": metric_sha,
            "metric_artifact_metrics_sha256": _canonical_json_sha256(metric_values),
            "metrics_exact_binding": True,
            "all_pass": gate_value,
        }
    return result, all_pass


def _validate_candidate_source_bytes(
    candidate_bindings: Mapping[str, Mapping[str, object]],
    sources: Mapping[str, Path],
) -> None:
    for label, binding in candidate_bindings.items():
        file_id = str(binding["source_file_id"])
        if _sha256(sources[file_id]) != binding["final_pcm_sha256"]:
            raise ValueError(f"candidate/source binding mismatch: {label}")


def _validate_all_source_manifest_entries(
    source_manifest: Mapping[str, object],
    sources: Mapping[str, Path],
) -> None:
    manifest_files = source_manifest["files"]
    evidence = source_manifest.get("evidence")
    assert isinstance(manifest_files, Mapping)
    if not isinstance(evidence, Mapping):
        raise ValueError("source manifest must contain an evidence object")
    for file_id in REQUIRED_SOURCE_FILE_IDS:
        entry = evidence.get(file_id)
        if not isinstance(entry, Mapping):
            raise ValueError(f"source manifest evidence is missing: {file_id}")
        file_path = Path(str(manifest_files[file_id])).resolve()
        entry_path = entry.get("path")
        if (
            not isinstance(entry_path, str)
            or Path(entry_path).resolve() != file_path
            or file_path != sources[file_id]
        ):
            raise ValueError(f"source manifest evidence path mismatch: {file_id}")
        expected_sha = entry.get("sha256")
        if not isinstance(expected_sha, str) or re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha) is None:
            raise ValueError(f"source manifest evidence SHA must be 64 hex: {file_id}")
        if expected_sha.lower() != _sha256(sources[file_id]):
            raise ValueError(f"source manifest byte SHA mismatch: {file_id}")


def _json_finite(value: object) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _json_finite(item) for key, item in value.items())
    if isinstance(value, list):
        return all(_json_finite(item) for item in value)
    if isinstance(value, float):
        return bool(np.isfinite(value))
    return value is None or isinstance(value, (str, int, bool))


def _write_feedback_template(path: Path) -> None:
    fields = (
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
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for file_id in REQUIRED_SOURCE_FILE_IDS:
            writer.writerow(
                {
                    "file_id": file_id,
                    "vehicle_id": _VEHICLES[file_id],
                    "candidate_id": _CANDIDATES[file_id],
                }
            )


def _open_me_first(
    root: Path,
    *,
    package_id: str,
    status: str,
    diagnostic_mode: bool,
) -> str:
    lines = [
        "# S12 Stage I - Open Me First",
        "",
        f"Package: `{package_id}`",
        f"Status: `{status}`",
        "",
        "This is a named engineering calibration package. No anonymous sealed key was opened.",
        "The blower-only, exhaust-only, shift and lift files are engineering diagnostic stems; they are not product audio.",
        "",
        "## Canonical 60-second timeline",
        "",
        "0-8 s idle; 8-26 s acceleration with 3 shifts; 26-36 s full pull; 36-46 s lift/afterfire/bypass; 46-52 s coast; 52-60 s idle return.",
        "",
        "## Absolute file list",
        "",
    ]
    if diagnostic_mode:
        lines.extend(
            (
                "UNQUALIFIED_DIAGNOSTIC_ONLY: one or more candidates failed formal qualification.",
                "This package is not admitted to a human gate and cannot select or freeze a profile.",
                "",
            )
        )
    for index, file_id in enumerate(REQUIRED_SOURCE_FILE_IDS, 1):
        lines.append(f"{index}. `{(root / PACKAGE_FILE_LAYOUT[file_id]).resolve()}` ({file_id})")
    lines.extend(
        (
            "",
            "Listen to the Stage H baseline first, then Stage I A/B/C. Use the named Ferrari/RX-7 files only to bind earlier numbered feedback by explicit file_id.",
            "",
            f"All outputs are {PROVENANCE}.",
            "",
        )
    )
    return "\n".join(lines)


def _zip_tree(output: Path, root: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name in {output.name, "SHA256SUMS.txt"}:
                continue
            info = zipfile.ZipInfo(path.relative_to(root).as_posix())
            info.date_time = (2020, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _write_sha256sums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(f"{_sha256(path)}  {path.relative_to(root).as_posix()}\n")
    (root / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = (
    "DIAGNOSTIC_PACKAGE_ID",
    "DIAGNOSTIC_STATUS",
    "FULL_CYCLE_FILE_IDS",
    "METRIC_ARTIFACT_LAYOUT",
    "PACKAGE_FILE_LAYOUT",
    "PACKAGE_ID",
    "QUALIFICATION_EVIDENCE_LAYOUT",
    "REQUIRED_SOURCE_FILE_IDS",
    "WAITING_STATUS",
    "build_stage_i_named_review",
)
