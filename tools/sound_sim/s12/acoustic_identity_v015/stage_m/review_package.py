"""Build a local, non-Git Stage-M listening package without fabricating R2 audio."""
from __future__ import annotations

import hashlib
import io
import json
import wave
import zipfile
from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_comparator.cli import _pcm24
from tools.sound_sim.s12.acoustic_comparator.listening import loudness_matched_audition


CSV_COLUMNS = [
    "listener_id", "playback_device", "windows_volume", "playback_endpoint", "vehicle_id", "scenario", "baseline_file", "candidate_file", "candidate_sha256",
    "identity_score", "realism_score", "low_frequency_score", "mechanical_score", "shift_score", "afterfire_score", "artifact_score", "preference", "notes",
]


def _write_pcm24(path: Path, signal: np.ndarray, sample_rate_hz: int) -> None:
    value = np.clip(np.asarray(signal, dtype=np.float64), -1.0, 1.0 - 1.0 / (1 << 23))
    if value.ndim == 1:
        value = np.column_stack((value, value))
    integers = np.rint(value * (1 << 23)).astype(np.int32).reshape(-1)
    packed = np.empty((integers.size, 3), dtype=np.uint8)
    packed[:, 0] = integers & 0xFF
    packed[:, 1] = (integers >> 8) & 0xFF
    packed[:, 2] = (integers >> 16) & 0xFF
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(packed.tobytes())


def _clip(signal: np.ndarray, sample_rate_hz: int, seconds: float = 12.0) -> np.ndarray:
    return signal[: min(signal.shape[0], round(sample_rate_hz * seconds))]


def _extract_stage_k(root: Path) -> dict[str, tuple[bytes, bytes, str, str]]:
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    result: dict[str, tuple[bytes, bytes, str, str]] = {}
    with zipfile.ZipFile(next(root.glob("*.zip"))) as archive:
        for vehicle_id, record in manifest["vehicles"].items():
            formal = record["formal"]
            parent = formal.get("parent", formal["baseline"])
            candidate = formal["candidate"]
            result[vehicle_id] = (
                archive.read(parent["path"].replace("\\", "/")),
                archive.read(candidate["path"].replace("\\", "/")),
                str(parent["path"]),
                str(candidate["path"]),
            )
    return result


def _extract_hellcat(root: Path) -> tuple[bytes, bytes, str, str]:
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    parent_path = next(path for path in artifacts if "StageK_Parent" in path)
    candidate_path = next(path for path in artifacts if "StageL_v9_Candidate" in path and "Comfort" not in path)
    return ((root / parent_path).read_bytes(), (root / candidate_path).read_bytes(), parent_path, candidate_path)


def build_local_review_package(
    output: Path,
    comparator_results: dict[str, object],
    *,
    stage_k_three: Path,
    stage_k_remaining: Path,
    stage_l_hellcat: Path,
) -> dict[str, object]:
    """Create a new local package; a populated destination is never overwritten."""

    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing review package: {output}")
    output.mkdir(parents=True, exist_ok=True)
    source = {**_extract_stage_k(stage_k_three), **_extract_stage_k(stage_k_remaining), "hellcat": _extract_hellcat(stage_l_hellcat)}
    manifest: dict[str, object] = {"schema_version": "s12-stage-m-local-review-package-1", "status": "AUTOMATED_CLOSURE_COMPLETE / WAITING_FOR_JOVI_NAMED_REVIEW / NOT_PROFILE_FREEZE_READY", "copyright_boundary": "No external reference recording is included. Each vehicle has an external-reference pointer only.", "vehicles": {}}
    rows = [",".join(CSV_COLUMNS)]
    yaml_trials = []
    for index, vehicle_id in enumerate(sorted(source), start=1):
        anonymous_id = f"V{index:02d}"
        parent_raw, candidate_raw, parent_path, candidate_path = source[vehicle_id]
        parent, sample_rate_hz = _pcm24(parent_raw)
        candidate, candidate_rate_hz = _pcm24(candidate_raw)
        if sample_rate_hz != candidate_rate_hz:
            raise ValueError(f"sample-rate mismatch for {vehicle_id}")
        folder = output / "vehicles" / anonymous_id
        audition = folder / "audition"
        metadata = folder / "metadata"
        audition.mkdir(parents=True)
        metadata.mkdir()
        parent_clip, parent_note = loudness_matched_audition(_clip(parent, sample_rate_hz))
        candidate_clip, candidate_note = loudness_matched_audition(_clip(candidate, sample_rate_hz))
        anchor = np.repeat(candidate_clip[::4], 4, axis=0)[: candidate_clip.shape[0]]
        _write_pcm24(audition / "A_stage_k_parent_audition.wav", parent_clip, sample_rate_hz)
        _write_pcm24(audition / "B_stage_m_r1_upstream_candidate_audition.wav", candidate_clip, sample_rate_hz)
        _write_pcm24(audition / "X_low_quality_synthetic_anchor.wav", anchor, sample_rate_hz)
        external_pointer = {
            "status": "NOT_AVAILABLE", "reason": "No legally usable, provenance-bound external recording was supplied; no reference excerpt is bundled.",
            "required_before_real_reference_comparison": ["source/license", "raw SHA-256", "scenario", "RPM/load trace", "analysis window", "microphone/processing contract"],
        }
        pointer = {
            "vehicle_id": vehicle_id, "anonymous_id": anonymous_id, "analysis_signal": "unaltered_analysis_signal",
            "stage_k_parent": {"source_path": parent_path, "full_wav_sha256": hashlib.sha256(parent_raw).hexdigest()},
            "stage_m_r1": {"meaning": "upstream Round-2 candidate re-export; not a new calibration", "source_path": candidate_path, "full_wav_sha256": hashlib.sha256(candidate_raw).hexdigest()},
            "stage_m_r2": {"status": "NOT_GENERATED", "reason": "automatic calibration withheld: external target unavailable"},
            "audition": {"analysis_signal": "separate from audition", "parent": parent_note, "r1": candidate_note},
        }
        (metadata / "raw_analysis_pointers.json").write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        (metadata / "external_reference_pointer.json").write_text(json.dumps(external_pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        (metadata / "stage_m_r2_NOT_GENERATED.txt").write_text("No Stage-M R2 waveform exists. Do not substitute a duplicate, placeholder, or review-gain copy.\n", encoding="utf-8", newline="\n")
        metric = comparator_results["vehicles"][vehicle_id]
        (metadata / "metrics.json").write_text(json.dumps(metric, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        manifest["vehicles"][anonymous_id] = {"vehicle_id": vehicle_id, "source_paths": [parent_path, candidate_path], "candidate_sha256": hashlib.sha256(candidate_raw).hexdigest(), "r2": "NOT_GENERATED", "metrics": f"vehicles/{anonymous_id}/metadata/metrics.json"}
        rows.append(",".join(["", "", "", "", vehicle_id, "full_cycle", f"vehicles/{anonymous_id}/audition/A_stage_k_parent_audition.wav", f"vehicles/{anonymous_id}/audition/B_stage_m_r1_upstream_candidate_audition.wav", hashlib.sha256(candidate_raw).hexdigest(), "", "", "", "", "", "", "", "", ""])
        )
        yaml_trials.append(f"  - id: {anonymous_id}\n    reference: unavailable_external_pointer\n    stimuli:\n      parent: vehicles/{anonymous_id}/audition/A_stage_k_parent_audition.wav\n      stage_m_r1: vehicles/{anonymous_id}/audition/B_stage_m_r1_upstream_candidate_audition.wav\n      anchor: vehicles/{anonymous_id}/audition/X_low_quality_synthetic_anchor.wav\n      stage_m_r2: NOT_GENERATED")
    (output / "human_feedback_template.csv").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    (output / "webmushra-config.yaml").write_text("testName: S12 Stage M local comparison\nreference: unavailable; no hidden-reference score\ntrials:\n" + "\n".join(yaml_trials) + "\n", encoding="utf-8", newline="\n")
    (output / "ab-review.html").write_text("<!doctype html><title>S12 Stage M A/B</title><h1>S12 Stage M local A/B review</h1><p>Use headphones or a documented endpoint. This is an internal synthetic comparison, not a real-reference identity test. Each trial has Parent, Stage-M R1 (an upstream candidate re-export), and a clearly artificial low-quality anchor. Stage-M R2 was not generated because no lawful state/RPM-bound reference target exists.</p><p>Record your named response in <code>human_feedback_template.csv</code>; do not alter the anonymous mapping.</p>\n", encoding="utf-8", newline="\n")
    (output / "README.md").write_text("# S12 Stage M local listening package\n\nNo copyrighted external reference audio is included. `raw_analysis_pointers.json` preserves unaltered full-PCM SHA/pointers; files under `audition/` are separately loudness-matched 12-second listening clips. Do not use audition copies for analysis. Follow `ab-review.html` or import `webmushra-config.yaml` into a local webMUSHRA setup. Stage-M R2 is intentionally absent; no placeholder may be treated as a calibration result.\n", encoding="utf-8", newline="\n")
    (output / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return manifest
