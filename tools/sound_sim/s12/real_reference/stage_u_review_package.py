"""Build a fail-closed Stage U human review package outside the repository.

Raw audio is copied byte-for-byte to the approved external root.  Separate
48 kHz audition copies are loudness managed to -18 LUFS with a -1.5 dBFS peak
cap.  The repository receives only an HTML/JavaScript review surface and JSON
metadata; it never receives audio bytes.
"""

from __future__ import annotations

import hashlib
import http.server
import io
import json
import math
import mimetypes
import random
import shutil
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.sax.saxutils import escape

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, stft

from tools.sound_sim.s12.acoustic_identity_v015.loudness_manager import (
    LoudnessMetrics,
    manage_bundle_loudness,
    measure_loudness,
)


ALLOWED_EXTERNAL_ROOT = Path(r"E:\Claude_allow\Download")
TARGET_LUFS = -18.0
PEAK_CAP_DBFS = -1.5
AUDITION_SAMPLE_RATE_HZ = 48_000
_EXPECTED_SELECTION = ("hellcat", "hellcat_stage_u_04")
_TIMBRAL_DESCRIPTORS = {
    "hardness": "硬度",
    "depth": "深度",
    "brightness": "明亮度",
    "roughness": "粗糙度",
    "warmth": "温暖度",
    "sharpness": "锐度",
    "booming": "轰鸣感",
    "reverb": "混响感",
}


class StageUReviewPackageError(ValueError):
    """Raised when Stage U review evidence cannot pass every required gate."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _manifest_content_sha256(value: Mapping[str, Any]) -> str:
    payload = copy_mapping(value)
    payload.pop("manifest_sha256", None)
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _load_mapping(value: Mapping[str, Any] | str | Path, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return copy_mapping(value)
    path = Path(value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageUReviewPackageError(f"cannot read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise StageUReviewPackageError(f"{label} must be a JSON object")
    return payload


def copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Make a JSON-safe deep copy without retaining caller-owned references."""

    try:
        result = json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        raise StageUReviewPackageError(
            "review inputs must be JSON serializable"
        ) from exc
    if not isinstance(result, dict):
        raise StageUReviewPackageError("review input must be an object")
    return result


def _inside_allowed_external_root(path: Path) -> Path:
    allowed = ALLOWED_EXTERNAL_ROOT.resolve()
    resolved = Path(path).resolve()
    if resolved == allowed or not resolved.is_relative_to(allowed):
        raise StageUReviewPackageError(
            f"output is outside allowed external root: {resolved}"
        )
    return resolved


def _valid_sha(value: Any) -> bool:
    text = str(value or "").lower()
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def _metric_payload(metrics: LoudnessMetrics) -> dict[str, Any]:
    return {
        "integrated_lufs": float(metrics.integrated_lufs),
        "rms_dbfs": float(metrics.rms_dbfs),
        "peak_dbfs": float(metrics.peak_dbfs),
        "crest_factor_db": float(metrics.crest_factor_db),
        "clipping_count": int(metrics.clipping_count),
    }


def _read_audio(path: Path) -> tuple[np.ndarray, int]:
    try:
        audio, sample_rate_hz = sf.read(path, always_2d=True, dtype="float64")
    except (OSError, RuntimeError) as exc:
        raise StageUReviewPackageError(f"audio cannot be decoded: {path}") from exc
    if audio.size == 0 or audio.shape[0] == 0 or not np.all(np.isfinite(audio)):
        raise StageUReviewPackageError(
            f"audio must contain finite nonzero-duration samples: {path}"
        )
    if int(sample_rate_hz) <= 0:
        raise StageUReviewPackageError(f"audio sample rate is invalid: {path}")
    return np.asarray(audio, dtype=np.float64), int(sample_rate_hz)


def _read_verified_raw_copy(path: Path, expected_sha256: str) -> tuple[np.ndarray, int]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise StageUReviewPackageError(
            f"raw staging copy cannot be read: {path}"
        ) from exc
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if actual_sha256 != str(expected_sha256).lower():
        raise StageUReviewPackageError(f"raw staging SHA-256 mismatch: {path}")
    try:
        audio, sample_rate_hz = sf.read(
            io.BytesIO(payload), always_2d=True, dtype="float64"
        )
    except (OSError, RuntimeError) as exc:
        raise StageUReviewPackageError(
            f"raw staging copy cannot be decoded: {path}"
        ) from exc
    if audio.size == 0 or audio.shape[0] == 0 or not np.all(np.isfinite(audio)):
        raise StageUReviewPackageError(
            f"raw staging copy must contain finite nonzero-duration samples: {path}"
        )
    if int(sample_rate_hz) <= 0:
        raise StageUReviewPackageError(
            f"raw staging copy sample rate is invalid: {path}"
        )
    return np.asarray(audio, dtype=np.float64), int(sample_rate_hz)


def _resample_48k(audio: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    if sample_rate_hz == AUDITION_SAMPLE_RATE_HZ:
        return np.asarray(audio, dtype=np.float64)
    divisor = math.gcd(int(sample_rate_hz), AUDITION_SAMPLE_RATE_HZ)
    return np.asarray(
        resample_poly(
            audio,
            AUDITION_SAMPLE_RATE_HZ // divisor,
            int(sample_rate_hz) // divisor,
            axis=0,
        ),
        dtype=np.float64,
    )


def _selection_is_qualified(row: Mapping[str, Any]) -> bool:
    expected = int(row.get("expected_reference_count", 0) or 0)
    distinct = int(row.get("distinct_reference_count", 0) or 0)
    required = int(row.get("required_improvement_count", 0) or 0)
    improved = int(row.get("improved_reference_count", 0) or 0)
    return bool(
        row.get("professional_bound")
        and row.get("hard_gates_pass")
        and expected > 0
        and distinct >= expected
        and required > 0
        and improved >= required
        and row.get("per_reference")
    )


def _record_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("vehicle_id") or ""),
        str(row.get("reference_id") or ""),
        str(row.get("candidate_id") or ""),
    )


def _professional_index(
    professional: Mapping[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    results = professional.get("results")
    if not isinstance(results, list):
        raise StageUReviewPackageError("professional binding results are missing")
    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in results:
        if isinstance(raw, Mapping):
            indexed[_record_key(raw)] = dict(raw)
    return indexed


def _grid_index(grid: Mapping[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    candidates = grid.get("candidates")
    if not isinstance(candidates, list):
        raise StageUReviewPackageError("candidate grid results are missing")
    return {
        _record_key(row): dict(row) for row in candidates if isinstance(row, Mapping)
    }


def _validate_sha_binding(row: Mapping[str, Any], label: str) -> None:
    binding = row.get("sha_binding")
    if not isinstance(binding, Mapping):
        raise StageUReviewPackageError(f"professional binding SHA is missing: {label}")
    for role in ("reference", "parent", "candidate"):
        declared = str(row.get(f"{role}_sha256") or "").lower()
        bound = str(binding.get(role) or "").lower()
        if not _valid_sha(declared) or bound != declared:
            raise StageUReviewPackageError(
                f"professional binding SHA mismatch: {label}/{role}"
            )


def _collect_trials(
    selection: Mapping[str, Any],
    professional: Mapping[str, Any],
    grid: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if selection.get("schema_version") != "s12-stage-u-selection-v1":
        raise StageUReviewPackageError("Stage U selection schema is invalid")
    if selection.get("status") != "R2_COMPARATOR_DRIVEN_CANDIDATE_READY":
        raise StageUReviewPackageError(
            "Stage U selection status is not candidate-ready"
        )
    selected = selection.get("selected_candidates")
    if not isinstance(selected, list) or not selected:
        raise StageUReviewPackageError("no selected candidate is available for review")
    if len(selected) != 1 or not isinstance(selected[0], Mapping):
        raise StageUReviewPackageError("exactly one selected candidate is required")
    selected_candidate = selected[0]
    selected_identity = (
        str(selected_candidate.get("vehicle_id") or ""),
        str(selected_candidate.get("candidate_id") or ""),
    )
    if selected_identity != _EXPECTED_SELECTION:
        raise StageUReviewPackageError(
            "current selected truth requires hellcat/hellcat_stage_u_04"
        )
    if selected_candidate.get("status") != "R2_COMPARATOR_DRIVEN_CANDIDATE_READY":
        raise StageUReviewPackageError(
            "selected candidate status is not candidate-ready"
        )
    if not _selection_is_qualified(selected_candidate):
        raise StageUReviewPackageError(
            "no selected candidate passes qualification gates"
        )
    per_reference = selected_candidate.get("per_reference")
    declared_counts = {
        int(selected_candidate.get(name, -1) or -1)
        for name in (
            "reference_count",
            "distinct_reference_count",
            "expected_reference_count",
        )
    }
    reference_ids = {
        str(row.get("reference_id") or "")
        for row in per_reference
        if isinstance(row, Mapping)
    }
    if (
        declared_counts != {len(per_reference)}
        or len(reference_ids) != len(per_reference)
        or "" in reference_ids
    ):
        raise StageUReviewPackageError(
            "selected candidate reference coverage is inconsistent"
        )
    rejected = selection.get("rejected_candidates")
    if not isinstance(rejected, list):
        raise StageUReviewPackageError("rejected candidate truth is missing")
    for vehicle_id, expected_status in (
        ("ferrari_458", "REFERENCE_COVERAGE_NOT_QUALIFIED"),
        ("rx7_fd", "NO_MEASURABLE_IMPROVEMENT"),
    ):
        rejected_rows = [
            row
            for row in rejected
            if isinstance(row, Mapping) and row.get("vehicle_id") == vehicle_id
        ]
        if not rejected_rows or any(
            row.get("status") != expected_status for row in rejected_rows
        ):
            raise StageUReviewPackageError(
                f"current rejected truth is invalid: {vehicle_id}"
            )
    qualifying = [selected_candidate]

    professional_by_key = _professional_index(professional)
    grid_by_key = _grid_index(grid)
    trials: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in qualifying:
        vehicle_id = str(candidate.get("vehicle_id") or "")
        candidate_id = str(candidate.get("candidate_id") or "")
        for selected_row in candidate.get("per_reference", []):
            if not isinstance(selected_row, Mapping):
                raise StageUReviewPackageError(
                    "selected per-reference record must be an object"
                )
            row = dict(selected_row)
            row.setdefault("vehicle_id", vehicle_id)
            row.setdefault("candidate_id", candidate_id)
            key = _record_key(row)
            if not all(key) or key in seen:
                raise StageUReviewPackageError(
                    f"duplicate or incomplete selected trial: {key}"
                )
            seen.add(key)
            if not bool(row.get("professional_bound")) or not bool(
                row.get("hard_gates_pass")
            ):
                raise StageUReviewPackageError(
                    f"selected trial lacks professional binding: {key}"
                )
            if str(row.get("professional_binding_status")) != "ALL_COMPONENT_SHA_BOUND":
                raise StageUReviewPackageError(
                    f"selected trial lacks professional binding: {key}"
                )
            _validate_sha_binding(row, f"selected/{key}")
            parent_sha = str(row.get("parent_sha256") or "").lower()
            candidate_sha = str(row.get("candidate_sha256") or "").lower()
            if parent_sha == candidate_sha:
                raise StageUReviewPackageError(
                    f"Parent/Candidate SHA must differ: {key}"
                )

            professional_row = professional_by_key.get(key)
            if not professional_row:
                raise StageUReviewPackageError(
                    f"professional binding is missing: {key}"
                )
            if not bool(professional_row.get("professional_bound")) or not bool(
                professional_row.get("hard_gates_pass")
            ):
                raise StageUReviewPackageError(f"professional binding failed: {key}")
            if (
                str(professional_row.get("professional_binding_status"))
                != "ALL_COMPONENT_SHA_BOUND"
            ):
                raise StageUReviewPackageError(
                    f"professional binding is incomplete: {key}"
                )
            _validate_sha_binding(professional_row, f"professional/{key}")
            for role in ("reference", "parent", "candidate"):
                if (
                    str(professional_row.get(f"{role}_sha256") or "").lower()
                    != str(row.get(f"{role}_sha256") or "").lower()
                ):
                    raise StageUReviewPackageError(
                        f"professional binding SHA mismatch: {key}/{role}"
                    )
            components = professional_row.get("professional_components")
            if not isinstance(components, Mapping) or not all(
                isinstance(components.get(name), Mapping)
                for name in ("matlab", "mosqito", "audioFeatureExtractor")
            ):
                raise StageUReviewPackageError(
                    f"professional binding components are missing: {key}"
                )

            grid_row = grid_by_key.get(key)
            if not grid_row or not isinstance(
                grid_row.get("parameter_values"), Mapping
            ):
                raise StageUReviewPackageError(
                    f"candidate parameter values are missing: {key}"
                )
            if str(grid_row.get("candidate_sha256") or "").lower() != candidate_sha:
                raise StageUReviewPackageError(f"candidate grid SHA mismatch: {key}")
            row["professional_components"] = copy_mapping(components)
            row["parameter_values"] = copy_mapping(grid_row["parameter_values"])
            row["source_mapping"] = copy_mapping(grid_row.get("source_mapping") or {})
            trials.append(row)
    if not trials:
        raise StageUReviewPackageError("no selected candidate trial is available")
    return trials


def _verify_raw_sources(trials: Sequence[Mapping[str, Any]]) -> None:
    for trial in trials:
        for role in ("reference", "parent", "candidate"):
            source = Path(str(trial.get(f"{role}_path") or ""))
            if not source.is_file():
                raise StageUReviewPackageError(f"raw audio is missing: {source}")
            declared = str(trial.get(f"{role}_sha256") or "").lower()
            actual = _sha256(source)
            if not _valid_sha(declared) or actual != declared:
                raise StageUReviewPackageError(f"raw SHA-256 mismatch: {role}/{source}")


def _safe_trial_id(index: int, row: Mapping[str, Any]) -> str:
    reference = "".join(
        character if character.isalnum() else "_"
        for character in str(row["reference_id"])
    )
    return f"u7_{index:02d}_{reference}".strip("_")


def _build_media_receipt(
    *,
    role: str,
    trial_id: str,
    row: Mapping[str, Any],
    staging_root: Path,
    final_root: Path,
) -> dict[str, Any]:
    source = Path(str(row[f"{role}_path"]))
    source_sha = str(row[f"{role}_sha256"]).lower()
    raw_relative = Path("audio") / trial_id / "raw" / f"{role}{source.suffix.lower()}"
    audition_relative = (
        Path("audio") / trial_id / "audition" / f"{role}_48k_loudness_matched.wav"
    )
    raw_staging = staging_root / raw_relative
    audition_staging = staging_root / audition_relative
    raw_staging.parent.mkdir(parents=True, exist_ok=True)
    audition_staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, raw_staging)

    audio, source_rate = _read_verified_raw_copy(raw_staging, source_sha)
    resampled = _resample_48k(audio, source_rate)
    input_metrics = measure_loudness(resampled, AUDITION_SAMPLE_RATE_HZ)
    managed = manage_bundle_loudness(
        {role: resampled},
        AUDITION_SAMPLE_RATE_HZ,
        target_lufs=TARGET_LUFS,
        peak_limit_dbfs=PEAK_CAP_DBFS,
    )
    audition = np.asarray(managed.segments[role], dtype=np.float64)
    sf.write(audition_staging, audition, AUDITION_SAMPLE_RATE_HZ, subtype="PCM_24")
    reopened, reopened_rate = _read_audio(audition_staging)
    output_metrics = measure_loudness(reopened, reopened_rate)
    if (
        output_metrics.clipping_count != 0
        or output_metrics.peak_dbfs > PEAK_CAP_DBFS + 1e-6
    ):
        raise StageUReviewPackageError(f"audition peak gate failed: {trial_id}/{role}")

    raw_final = final_root / raw_relative
    audition_final = final_root / audition_relative
    return {
        "source_path": str(source),
        "source_raw_sha256": source_sha,
        "raw_copy_path": str(raw_final),
        "raw_copy_uri": raw_final.as_uri(),
        "raw_copy_sha256": source_sha,
        "audition_copy_path": str(audition_final),
        "audition_copy_uri": audition_final.as_uri(),
        "audition_sha256": _sha256(audition_staging),
        "source_sample_rate_hz": source_rate,
        "audition_sample_rate_hz": reopened_rate,
        "resampled": source_rate != AUDITION_SAMPLE_RATE_HZ,
        "duration_s": float(reopened.shape[0] / reopened_rate),
        "target_lufs": TARGET_LUFS,
        "peak_cap_dbfs": PEAK_CAP_DBFS,
        "gain_db": float(managed.gain_db),
        "gain_linear": float(managed.gain_linear),
        "headroom_limited": bool(managed.headroom_limited),
        "resampled_input_metrics": _metric_payload(input_metrics),
        "audition_metrics": _metric_payload(output_metrics),
    }


def _timbral_unavailable_receipt() -> dict[str, Any]:
    unavailable = "PROJECT_UNMAINTAINED_NOT_AVAILABLE"
    return {
        "status": unavailable,
        "hard_gate": False,
        "gate_label": "非硬门禁",
        "reason": "timbral_models 项目当前不可维护且本环境不可用；不生成或替代任何数值。",
        "descriptors": {
            descriptor_id: {
                "before": None,
                "after": None,
                "status": unavailable,
            }
            for descriptor_id in _TIMBRAL_DESCRIPTORS
        },
    }


def _residual_colour(value_db: float, limit_db: float = 24.0) -> str:
    amount = min(1.0, abs(float(value_db)) / limit_db)
    base = (25, 34, 38)
    target = (50, 216, 203) if value_db >= 0.0 else (255, 184, 77)
    rgb = tuple(
        round(start + amount * (end - start)) for start, end in zip(base, target)
    )
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _write_residual_svg(
    path: Path,
    residual_db: np.ndarray,
    frequencies_hz: np.ndarray,
    times_s: np.ndarray,
    *,
    label: str,
    reference_sha256: str,
    comparison_role: str,
    comparison_sha256: str,
    summary: Mapping[str, float],
) -> None:
    row_indices = np.linspace(
        0, residual_db.shape[0] - 1, min(48, residual_db.shape[0]), dtype=int
    )
    column_indices = np.linspace(
        0, residual_db.shape[1] - 1, min(96, residual_db.shape[1]), dtype=int
    )
    display = residual_db[np.ix_(row_indices, column_indices)]
    width, height = 960, 380
    plot_x, plot_y, plot_width, plot_height = 72, 76, 840, 230
    cell_width = plot_width / display.shape[1]
    cell_height = plot_height / display.shape[0]
    rectangles: list[str] = []
    for row_index, row in enumerate(display):
        y = plot_y + (display.shape[0] - row_index - 1) * cell_height
        for column_index, value in enumerate(row):
            x = plot_x + column_index * cell_width
            rectangles.append(
                f'<rect x="{x:.3f}" y="{y:.3f}" width="{cell_width + 0.05:.3f}" '
                f'height="{cell_height + 0.05:.3f}" fill="{_residual_colour(float(value))}"/>'
            )
    max_frequency = float(frequencies_hz[row_indices[-1]])
    max_time = float(times_s[column_indices[-1]]) if times_s.size else 0.0
    role_label = "父版本" if comparison_role == "parent" else "候选版本"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{escape(label)}</title>",
        '<rect width="960" height="380" fill="#111719"/>',
        f'<text x="36" y="35" fill="#e9f2ef" font-size="20" font-family="Microsoft YaHei UI, sans-serif">{escape(label)}</text>',
        f'<text x="36" y="58" fill="#91a6a5" font-size="12" font-family="Consolas, monospace">参考音轨 {escape(reference_sha256[:16])}… / {escape(role_label)} {escape(comparison_sha256[:16])}…</text>',
        *rectangles,
        f'<rect x="{plot_x}" y="{plot_y}" width="{plot_width}" height="{plot_height}" fill="none" stroke="#365057"/>',
        f'<text x="{plot_x}" y="330" fill="#91a6a5" font-size="12">0 秒</text>',
        f'<text x="{plot_x + plot_width - 58}" y="330" fill="#91a6a5" font-size="12">{max_time:.2f} 秒</text>',
        f'<text x="16" y="{plot_y + plot_height}" fill="#91a6a5" font-size="12">0</text>',
        f'<text x="8" y="{plot_y + 10}" fill="#91a6a5" font-size="12">{max_frequency / 1000.0:.1f}kHz</text>',
        f'<text x="72" y="360" fill="#32d8cb" font-size="13">平均绝对残差 {float(summary["mean_absolute_db"]):.3f} dB</text>',
        f'<text x="360" y="360" fill="#ffb84d" font-size="13">95% 绝对残差 {float(summary["p95_absolute_db"]):.3f} dB</text>',
        '<text x="690" y="360" fill="#91a6a5" font-size="12">青绿：高于参考 / 琥珀：低于参考</text>',
        "</svg>",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_spectrogram_residual(
    *,
    media: Mapping[str, Mapping[str, Any]],
    raw_staging_paths: Mapping[str, Path],
    comparison_role: str,
    trial_id: str,
    staging_root: Path,
    final_root: Path,
) -> dict[str, Any]:
    if comparison_role not in {"parent", "candidate"}:
        raise StageUReviewPackageError(
            f"invalid spectrogram comparison role: {comparison_role}"
        )
    reference_receipt = media["reference"]
    comparison_receipt = media[comparison_role]
    reference_audio, reference_rate = _read_verified_raw_copy(
        raw_staging_paths["reference"],
        str(reference_receipt["source_raw_sha256"]),
    )
    comparison_audio, comparison_rate = _read_verified_raw_copy(
        raw_staging_paths[comparison_role],
        str(comparison_receipt["source_raw_sha256"]),
    )
    reference = np.mean(_resample_48k(reference_audio, reference_rate), axis=1)
    comparison = np.mean(_resample_48k(comparison_audio, comparison_rate), axis=1)
    sample_count = min(reference.size, comparison.size)
    if sample_count < 128:
        raise StageUReviewPackageError(
            f"raw analysis clip is too short for spectrogram residual: {trial_id}"
        )
    reference = reference[:sample_count]
    comparison = comparison[:sample_count]
    nperseg = min(1024, sample_count)
    noverlap = min(768, nperseg - 1)
    frequencies, times, reference_stft = stft(
        reference,
        fs=AUDITION_SAMPLE_RATE_HZ,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
        padded=False,
    )
    _, _, comparison_stft = stft(
        comparison,
        fs=AUDITION_SAMPLE_RATE_HZ,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
        padded=False,
    )
    frequency_mask = frequencies <= 8_000.0
    frequencies = frequencies[frequency_mask]
    floor = 1.0e-8
    reference_db = 20.0 * np.log10(
        np.maximum(np.abs(reference_stft[frequency_mask]), floor)
    )
    comparison_db = 20.0 * np.log10(
        np.maximum(np.abs(comparison_stft[frequency_mask]), floor)
    )
    residual_db = comparison_db - reference_db
    absolute = np.abs(residual_db)
    summary = {
        "signed_mean_db": float(np.mean(residual_db)),
        "mean_absolute_db": float(np.mean(absolute)),
        "rms_db": float(np.sqrt(np.mean(np.square(residual_db)))),
        "p95_absolute_db": float(np.percentile(absolute, 95.0)),
        "max_absolute_db": float(np.max(absolute)),
        "frequency_bin_count": int(residual_db.shape[0]),
        "time_frame_count": int(residual_db.shape[1]),
        "duration_s": float(sample_count / AUDITION_SAMPLE_RATE_HZ),
    }
    phase = "before" if comparison_role == "parent" else "after"
    label = (
        "调整前频谱残差（参考对父版本）"
        if comparison_role == "parent"
        else "调整后频谱残差（参考对候选版本）"
    )
    relative = Path("visuals") / trial_id / f"{phase}.svg"
    staging_path = staging_root / relative
    final_path = final_root / relative
    _write_residual_svg(
        staging_path,
        residual_db,
        frequencies,
        times,
        label=label,
        reference_sha256=str(reference_receipt["source_raw_sha256"]),
        comparison_role=comparison_role,
        comparison_sha256=str(comparison_receipt["source_raw_sha256"]),
        summary=summary,
    )
    return {
        "status": "COMPUTED_FROM_SHA_BOUND_RAW_ANALYSIS",
        "label": label,
        "reference_role": "reference",
        "comparison_role": comparison_role,
        "reference_raw_sha256": str(reference_receipt["source_raw_sha256"]),
        "comparison_raw_sha256": str(comparison_receipt["source_raw_sha256"]),
        "svg_path": str(final_path),
        "svg_url": f"/visuals/{trial_id}/{phase}.svg",
        "svg_sha256": _sha256(staging_path),
        "summary": summary,
        "analysis": {
            "domain": "raw_sha_bound_analysis_clips",
            "sample_rate_hz": AUDITION_SAMPLE_RATE_HZ,
            "stft_window": "hann",
            "stft_frame_size": nperseg,
            "stft_overlap": noverlap,
            "frequency_max_hz": 8_000.0,
        },
    }


def _professional_metric_view(
    components: Mapping[str, Any],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for source, output_name in (
        ("matlab", "matlab"),
        ("mosqito", "mosqito"),
        ("audioFeatureExtractor", "audio_feature_extractor"),
    ):
        values = components[source]
        before = values.get("parent_distance")
        after = values.get("candidate_distance")
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            raise StageUReviewPackageError(
                f"professional distances are missing: {source}"
            )
        result[output_name] = {"before": float(before), "after": float(after)}
    return result


def _page_data(manifest: Mapping[str, Any], manifest_sha: str) -> dict[str, Any]:
    page_trials = []
    for trial in manifest["trials"]:
        page_trials.append(
            {
                "trial_id": trial["trial_id"],
                "vehicle_id": trial["vehicle_id"],
                "scenario": trial["scenario"],
                "reference_id": trial["reference_id"],
                "candidate_id": trial["candidate_id"],
                "randomized_mapping": trial["randomized_mapping"],
                "sha_bindings": {
                    role: {
                        "raw": receipt["source_raw_sha256"],
                        "audition": receipt["audition_sha256"],
                    }
                    for role, receipt in trial["media"].items()
                },
                "media": {
                    role: {
                        "url": f"/media/{trial['trial_id']}/{role}.wav",
                        "sha256": receipt["audition_sha256"],
                        "duration_s": receipt["duration_s"],
                    }
                    for role, receipt in trial["media"].items()
                },
                "professional_binding": trial["professional_binding"],
                "parent_candidate_distinct": trial["parent_candidate_distinct"],
                "professional_metrics": trial["professional_metrics"],
                "spectrogram_residuals": {
                    phase: {
                        "status": receipt["status"],
                        "label": receipt["label"],
                        "url": receipt["svg_url"],
                        "svg_sha256": receipt["svg_sha256"],
                        "reference_role": receipt["reference_role"],
                        "comparison_role": receipt["comparison_role"],
                        "reference_raw_sha256": receipt["reference_raw_sha256"],
                        "comparison_raw_sha256": receipt["comparison_raw_sha256"],
                        "summary": receipt["summary"],
                    }
                    for phase, receipt in trial["spectrogram_residuals"].items()
                },
                "timbral_descriptors": trial["timbral_descriptors"],
                "parameter_values": trial["parameter_values"],
                "parameter_uncertainty": {
                    "status": "NOT_QUANTIFIED_GRID_CANDIDATE",
                    "display": "未量化：当前值是有限网格候选点，仅由已绑定参考片段支持。",
                },
                "status_labels": {
                    "review": "等待 Jovi 人工盲听",
                    "evidence": "专业指标已绑定",
                    "order": "阶次比较未获资格",
                },
            }
        )
    return {
        "schema_version": "s12-stage-u-review-page-data-v1",
        "status": "READY_FOR_HUMAN_REVIEW",
        "manifest_sha256": manifest_sha,
        "target_lufs": TARGET_LUFS,
        "peak_cap_dbfs": PEAK_CAP_DBFS,
        "trials": page_trials,
    }


def _write_page(repository_root: Path, page_data: Mapping[str, Any]) -> None:
    if repository_root.exists() and any(repository_root.iterdir()):
        raise StageUReviewPackageError(
            f"refusing non-empty repository review root: {repository_root}"
        )
    repository_root.mkdir(parents=True, exist_ok=True)
    (repository_root / "index.html").write_text(_HTML, encoding="utf-8")
    (repository_root / "review.js").write_text(_JAVASCRIPT, encoding="utf-8")
    serialized = json.dumps(page_data, ensure_ascii=False, indent=2, sort_keys=True)
    (repository_root / "review_data.json").write_text(
        serialized + "\n", encoding="utf-8"
    )
    (repository_root / "review_data.js").write_text(
        f"window.S12_STAGE_U_REVIEW_DATA = {serialized};\n", encoding="utf-8"
    )


def build_review_package(
    selection: Mapping[str, Any] | str | Path,
    professional_metrics: Mapping[str, Any] | str | Path,
    candidate_grid: Mapping[str, Any] | str | Path,
    *,
    repository_review_root: str | Path,
    external_output_root: str | Path,
    random_seed: int | None = None,
) -> dict[str, Any]:
    """Build external audio plus a repository-only review page for selected candidates."""

    output = _inside_allowed_external_root(Path(external_output_root))
    repository_root = Path(repository_review_root).resolve()
    if output.exists():
        raise StageUReviewPackageError(
            f"refusing existing external review output: {output}"
        )
    if repository_root.exists() and any(repository_root.iterdir()):
        raise StageUReviewPackageError(
            f"refusing non-empty repository review root: {repository_root}"
        )
    selection_data = _load_mapping(selection, "selection")
    professional_data = _load_mapping(professional_metrics, "professional metrics")
    grid_data = _load_mapping(candidate_grid, "candidate grid")
    trials = _collect_trials(selection_data, professional_data, grid_data)
    _verify_raw_sources(trials)

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}-staging-", dir=output.parent)
    )
    rng = random.Random(random_seed)
    try:
        manifest_trials: list[dict[str, Any]] = []
        for index, row in enumerate(trials, start=1):
            trial_id = _safe_trial_id(index, row)
            roles = ["parent", "candidate"]
            rng.shuffle(roles)
            mapping = {"B": roles[0], "C": roles[1]}
            media = {
                role: _build_media_receipt(
                    role=role,
                    trial_id=trial_id,
                    row=row,
                    staging_root=staging,
                    final_root=output,
                )
                for role in ("reference", "parent", "candidate")
            }
            raw_staging_paths = {
                role: staging / Path(str(receipt["raw_copy_path"])).relative_to(output)
                for role, receipt in media.items()
            }
            spectrogram_residuals = {
                "before": _build_spectrogram_residual(
                    media=media,
                    raw_staging_paths=raw_staging_paths,
                    comparison_role="parent",
                    trial_id=trial_id,
                    staging_root=staging,
                    final_root=output,
                ),
                "after": _build_spectrogram_residual(
                    media=media,
                    raw_staging_paths=raw_staging_paths,
                    comparison_role="candidate",
                    trial_id=trial_id,
                    staging_root=staging,
                    final_root=output,
                ),
            }
            manifest_trials.append(
                {
                    "trial_id": trial_id,
                    "vehicle_id": row["vehicle_id"],
                    "scenario": row.get("scenario"),
                    "reference_id": row["reference_id"],
                    "candidate_id": row["candidate_id"],
                    "randomized_mapping": mapping,
                    "media": media,
                    "spectrogram_residuals": spectrogram_residuals,
                    "timbral_descriptors": _timbral_unavailable_receipt(),
                    "professional_binding": {
                        "status": "ALL_COMPONENT_SHA_BOUND",
                        "passes": True,
                        "sha_binding": copy_mapping(row["sha_binding"]),
                    },
                    "parent_candidate_distinct": media["parent"]["source_raw_sha256"]
                    != media["candidate"]["source_raw_sha256"],
                    "professional_metrics": _professional_metric_view(
                        row["professional_components"]
                    ),
                    "legacy_metrics": {
                        "before": float(row.get("parent_distance", 0.0)),
                        "after": float(row.get("candidate_distance", 0.0)),
                        "absolute_improvement": float(
                            row.get("absolute_improvement", 0.0)
                        ),
                    },
                    "parameter_values": copy_mapping(row["parameter_values"]),
                    "source_mapping": copy_mapping(row["source_mapping"]),
                    "parameter_uncertainty": {
                        "status": "NOT_QUANTIFIED_GRID_CANDIDATE",
                        "reason": "finite grid candidate; no continuous confidence interval was produced",
                    },
                }
            )
        manifest_file_payload: dict[str, Any] = {
            "schema_version": "s12-stage-u-review-package-v1",
            "status": "ABX_READY_FOR_HUMAN_REVIEW",
            "candidate_count": len(
                {
                    (trial["vehicle_id"], trial["candidate_id"])
                    for trial in manifest_trials
                }
            ),
            "trial_count": len(manifest_trials),
            "audio_policy": {
                "raw_copy": "byte-identical external copy; never loudness matched",
                "audition_copy": "separate 48 kHz loudness-managed copy",
                "target_lufs": TARGET_LUFS,
                "peak_cap_dbfs": PEAK_CAP_DBFS,
                "raw_media_in_repository": False,
            },
            "trials": manifest_trials,
            "manifest_path": str(output / "review_package_manifest.json"),
        }
        manifest_file_payload["manifest_sha256"] = _manifest_content_sha256(
            manifest_file_payload
        )
        validate_review_package(manifest_file_payload, verify_manifest_file=False)
        manifest_path = staging / "review_package_manifest.json"
        manifest_path.write_bytes(_json_bytes(manifest_file_payload))
        staging.replace(output)
        returned = copy_mapping(manifest_file_payload)
        _write_page(
            repository_root,
            _page_data(returned, str(returned["manifest_sha256"])),
        )
        return returned
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        if output.exists() and not (output / "review_package_manifest.json").is_file():
            shutil.rmtree(output)
        raise


def validate_review_package(
    manifest: Mapping[str, Any], *, verify_manifest_file: bool = True
) -> dict[str, Any]:
    """Prove the package's SHA, media, distinctness and professional gates."""

    if manifest.get("status") != "ABX_READY_FOR_HUMAN_REVIEW":
        raise StageUReviewPackageError(
            "raw-only or incomplete package must not be labelled ABX-ready"
        )
    declared_manifest_sha = str(manifest.get("manifest_sha256") or "")
    if not _valid_sha(
        declared_manifest_sha
    ) or declared_manifest_sha != _manifest_content_sha256(manifest):
        raise StageUReviewPackageError("review manifest content SHA-256 mismatch")
    trials = manifest.get("trials")
    if not isinstance(trials, list) or not trials:
        raise StageUReviewPackageError("review package has no trials")
    for trial in trials:
        if not isinstance(trial, Mapping):
            raise StageUReviewPackageError("review trial must be an object")
        media = trial.get("media")
        if not isinstance(media, Mapping) or set(media) != {
            "reference",
            "parent",
            "candidate",
        }:
            raise StageUReviewPackageError(
                "review trial must contain three media roles"
            )
        if not bool(trial.get("parent_candidate_distinct")):
            raise StageUReviewPackageError("Parent/Candidate must differ")
        if media["parent"].get("source_raw_sha256") == media["candidate"].get(
            "source_raw_sha256"
        ):
            raise StageUReviewPackageError("Parent/Candidate SHA must differ")
        professional = trial.get("professional_binding")
        if (
            not isinstance(professional, Mapping)
            or not professional.get("passes")
            or professional.get("status") != "ALL_COMPONENT_SHA_BOUND"
        ):
            raise StageUReviewPackageError("professional binding must pass")
        mapping = trial.get("randomized_mapping")
        if (
            not isinstance(mapping, Mapping)
            or set(mapping) != {"B", "C"}
            or set(mapping.values()) != {"parent", "candidate"}
        ):
            raise StageUReviewPackageError("B/C randomized mapping is invalid")
        timbral = trial.get("timbral_descriptors")
        if (
            not isinstance(timbral, Mapping)
            or timbral.get("status") != "PROJECT_UNMAINTAINED_NOT_AVAILABLE"
            or timbral.get("hard_gate") is not False
            or timbral.get("gate_label") != "非硬门禁"
            or not isinstance(timbral.get("descriptors"), Mapping)
            or set(timbral["descriptors"]) != set(_TIMBRAL_DESCRIPTORS)
        ):
            raise StageUReviewPackageError(
                "timbral descriptors must remain unavailable and non-gating"
            )
        for descriptor in timbral["descriptors"].values():
            if descriptor != {
                "before": None,
                "after": None,
                "status": "PROJECT_UNMAINTAINED_NOT_AVAILABLE",
            }:
                raise StageUReviewPackageError(
                    "timbral descriptor values must not be fabricated"
                )
        residuals = trial.get("spectrogram_residuals")
        if not isinstance(residuals, Mapping) or set(residuals) != {
            "before",
            "after",
        }:
            raise StageUReviewPackageError(
                "before/after spectrogram residual receipts are required"
            )
        for phase, expected_role in (("before", "parent"), ("after", "candidate")):
            residual = residuals[phase]
            if (
                not isinstance(residual, Mapping)
                or residual.get("status") != "COMPUTED_FROM_SHA_BOUND_RAW_ANALYSIS"
                or residual.get("reference_role") != "reference"
                or residual.get("comparison_role") != expected_role
                or residual.get("reference_raw_sha256")
                != media["reference"].get("source_raw_sha256")
                or residual.get("comparison_raw_sha256")
                != media[expected_role].get("source_raw_sha256")
            ):
                raise StageUReviewPackageError(
                    f"spectrogram residual role/SHA binding failed: {phase}"
                )
            svg_path = _inside_allowed_external_root(
                Path(str(residual.get("svg_path") or ""))
            )
            expected_svg_url = f"/visuals/{trial['trial_id']}/{phase}.svg"
            if residual.get("svg_url") != expected_svg_url:
                raise StageUReviewPackageError(
                    f"spectrogram residual URL binding failed: {phase}"
                )
            svg_sha = str(residual.get("svg_sha256") or "").lower()
            if not _valid_sha(svg_sha):
                raise StageUReviewPackageError(
                    f"spectrogram residual SHA receipt is invalid: {phase}"
                )
            if verify_manifest_file or svg_path.exists():
                if not svg_path.is_file() or _sha256(svg_path) != svg_sha:
                    raise StageUReviewPackageError(
                        f"spectrogram residual SHA mismatch: {phase}"
                    )
            summary = residual.get("summary")
            numeric_keys = {
                "signed_mean_db",
                "mean_absolute_db",
                "rms_db",
                "p95_absolute_db",
                "max_absolute_db",
                "frequency_bin_count",
                "time_frame_count",
                "duration_s",
            }
            if (
                not isinstance(summary, Mapping)
                or set(summary) != numeric_keys
                or not all(
                    isinstance(summary[key], (int, float))
                    and np.isfinite(float(summary[key]))
                    for key in numeric_keys
                )
                or float(summary["mean_absolute_db"]) < 0.0
                or float(summary["p95_absolute_db"]) < 0.0
            ):
                raise StageUReviewPackageError(
                    f"spectrogram residual numeric summary is invalid: {phase}"
                )
        for role, receipt in media.items():
            if not isinstance(receipt, Mapping):
                raise StageUReviewPackageError(f"media receipt is missing: {role}")
            raw_path = Path(str(receipt.get("raw_copy_path") or ""))
            audition_path = Path(str(receipt.get("audition_copy_path") or ""))
            expected_raw = str(receipt.get("source_raw_sha256") or "").lower()
            if expected_raw != str(receipt.get("raw_copy_sha256") or "").lower():
                raise StageUReviewPackageError(
                    f"raw copy SHA-256 receipt mismatch: {role}"
                )
            if verify_manifest_file or raw_path.exists():
                if not raw_path.is_file() or _sha256(raw_path) != expected_raw:
                    raise StageUReviewPackageError(f"raw SHA-256 mismatch: {role}")
                if (
                    not audition_path.is_file()
                    or _sha256(audition_path)
                    != str(receipt.get("audition_sha256") or "").lower()
                ):
                    raise StageUReviewPackageError(f"audition SHA-256 mismatch: {role}")
            if float(receipt.get("duration_s", 0.0) or 0.0) <= 0.0:
                raise StageUReviewPackageError(f"media duration gate failed: {role}")
            if (
                int(receipt.get("audition_sample_rate_hz", 0) or 0)
                != AUDITION_SAMPLE_RATE_HZ
            ):
                raise StageUReviewPackageError(
                    f"audition sample rate gate failed: {role}"
                )
            metrics = receipt.get("audition_metrics")
            if (
                not isinstance(metrics, Mapping)
                or float(metrics.get("peak_dbfs", 1.0)) > PEAK_CAP_DBFS + 1e-6
            ):
                raise StageUReviewPackageError(f"audition peak gate failed: {role}")
            if not isinstance(receipt.get("headroom_limited"), bool) or not isinstance(
                receipt.get("gain_db"), (int, float)
            ):
                raise StageUReviewPackageError(
                    f"audition gain/headroom receipt is missing: {role}"
                )
    if int(manifest.get("trial_count", -1)) != len(trials):
        raise StageUReviewPackageError("review trial count mismatch")
    return {"status": "PASS", "trial_count": len(trials)}


def validate_listener_submission(
    submission: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate a downloaded human submission against the exact review manifest."""

    validate_review_package(manifest)
    if submission.get("schema_version") != "s12-stage-u-listener-submission-v1":
        raise StageUReviewPackageError("listener submission schema is invalid")
    if str(submission.get("manifest_sha256") or "") != str(
        manifest.get("manifest_sha256") or ""
    ):
        raise StageUReviewPackageError("listener submission manifest SHA mismatch")
    timestamp = str(submission.get("submitted_at_utc") or "")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StageUReviewPackageError(
            "listener submission UTC timestamp is invalid"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise StageUReviewPackageError("listener submission UTC timestamp is invalid")

    responses = submission.get("responses")
    response_by_id = {
        str(row.get("trial_id")): row
        for row in responses or []
        if isinstance(row, Mapping)
    }
    media_validation = submission.get("media_validation")
    mappings = submission.get("mappings")
    sha_bindings = submission.get("sha_bindings")
    if not isinstance(media_validation, Mapping) or not isinstance(mappings, Mapping):
        raise StageUReviewPackageError(
            "listener submission media validation/mappings are missing"
        )
    if not isinstance(sha_bindings, Mapping):
        raise StageUReviewPackageError("listener submission SHA bindings are missing")
    expected_trial_ids = {str(trial["trial_id"]) for trial in manifest["trials"]}
    if (
        set(response_by_id) != expected_trial_ids
        or not isinstance(responses, list)
        or len(responses) != len(expected_trial_ids)
    ):
        raise StageUReviewPackageError(
            "listener submission responses are incomplete or duplicated"
        )
    if (
        set(media_validation) != expected_trial_ids
        or set(mappings) != expected_trial_ids
        or set(sha_bindings) != expected_trial_ids
    ):
        raise StageUReviewPackageError(
            "listener submission trial bindings are incomplete"
        )
    for trial in manifest["trials"]:
        trial_id = str(trial["trial_id"])
        response = response_by_id.get(trial_id)
        if not response or response.get("answer") not in {"B", "C"}:
            raise StageUReviewPackageError(f"ABX answer is required: {trial_id}")
        if "notes" not in response or not isinstance(response.get("notes"), str):
            raise StageUReviewPackageError(
                f"listener notes receipt is required: {trial_id}"
            )
        if mappings.get(trial_id) != trial["randomized_mapping"]:
            raise StageUReviewPackageError(f"listener mapping mismatch: {trial_id}")
        trial_validation = media_validation.get(trial_id)
        if not isinstance(trial_validation, Mapping):
            raise StageUReviewPackageError(f"media validation is missing: {trial_id}")
        expected_sha_bindings = {
            role: {
                "raw": receipt["source_raw_sha256"],
                "audition": receipt["audition_sha256"],
            }
            for role, receipt in trial["media"].items()
        }
        if sha_bindings.get(trial_id) != expected_sha_bindings:
            raise StageUReviewPackageError(
                f"listener SHA bindings mismatch: {trial_id}"
            )
        if set(trial_validation) != {"reference", "parent", "candidate"}:
            raise StageUReviewPackageError(
                f"media validation roles are incomplete: {trial_id}"
            )
        for role, receipt in trial["media"].items():
            validation = trial_validation.get(role)
            if not isinstance(validation, Mapping):
                raise StageUReviewPackageError(
                    f"media validation is missing: {trial_id}/{role}"
                )
            duration_s = float(validation.get("duration_s", 0.0) or 0.0)
            if (
                validation.get("duration") is not True
                or duration_s <= 0.0
                or abs(duration_s - float(receipt["duration_s"])) >= 0.08
                or validation.get("canplaythrough") is not True
            ):
                raise StageUReviewPackageError(
                    f"duration/canplaythrough gate failed: {trial_id}/{role}"
                )
            if (
                validation.get("sha_status") != "MATCH"
                or validation.get("sha256") != receipt["audition_sha256"]
            ):
                raise StageUReviewPackageError(f"media SHA mismatch: {trial_id}/{role}")
    return {"status": "VALID_HUMAN_SUBMISSION", "trial_count": len(manifest["trials"])}


def create_review_http_server(
    repository_review_root: str | Path,
    external_output_root: str | Path,
) -> http.server.ThreadingHTTPServer:
    """Create a loopback-only, read-only server for same-origin media hashing."""

    repository_root = Path(repository_review_root).resolve()
    external_root = _inside_allowed_external_root(Path(external_output_root))
    manifest_path = external_root / "review_package_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageUReviewPackageError(
            "external review manifest cannot be served"
        ) from exc
    validate_review_package(manifest)
    routes: dict[str, Path] = {
        "/": repository_root / "index.html",
        "/index.html": repository_root / "index.html",
        "/review.js": repository_root / "review.js",
        "/review_data.js": repository_root / "review_data.js",
        "/review_data.json": repository_root / "review_data.json",
    }
    for trial in manifest["trials"]:
        for role, receipt in trial["media"].items():
            media_path = Path(str(receipt["audition_copy_path"])).resolve()
            if not media_path.is_relative_to(external_root):
                raise StageUReviewPackageError(
                    "review media route escapes external package"
                )
            routes[f"/media/{trial['trial_id']}/{role}.wav"] = media_path
        for phase, receipt in trial["spectrogram_residuals"].items():
            visual_path = Path(str(receipt["svg_path"])).resolve()
            if not visual_path.is_relative_to(external_root):
                raise StageUReviewPackageError(
                    "review visual route escapes external package"
                )
            expected_url = f"/visuals/{trial['trial_id']}/{phase}.svg"
            if receipt.get("svg_url") != expected_url:
                raise StageUReviewPackageError(
                    "review visual route does not match its receipt"
                )
            routes[expected_url] = visual_path
    if any(not path.is_file() for path in routes.values()):
        raise StageUReviewPackageError("review server route is missing a required file")

    class ReadOnlyHandler(http.server.BaseHTTPRequestHandler):
        def _send(self, include_body: bool) -> None:
            route = urllib.parse.urlsplit(self.path).path
            path = routes.get(route)
            if path is None:
                self.send_error(404)
                return
            payload = path.read_bytes()
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if mime_type.startswith("text/") or mime_type in {
                "application/javascript",
                "application/json",
            }:
                content_type = f"{mime_type}; charset=utf-8"
            else:
                content_type = mime_type
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; media-src 'self'",
            )
            self.end_headers()
            if include_body:
                self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            self._send(True)

        def do_HEAD(self) -> None:  # noqa: N802
            self._send(False)

        def do_POST(self) -> None:  # noqa: N802
            self.send_error(405)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return http.server.ThreadingHTTPServer(("127.0.0.1", 0), ReadOnlyHandler)


_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stage U 工业声学对照台</title>
  <style>
    :root { --graphite:#111719; --panel:#192226; --panel-2:#202c30; --line:#365057; --cyan:#32d8cb; --amber:#ffb84d; --ink:#e9f2ef; --muted:#91a6a5; --danger:#ff7068; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:radial-gradient(circle at 90% 0,#20363a 0,transparent 34%),repeating-linear-gradient(0deg,rgba(255,255,255,.018) 0 1px,transparent 1px 5px),var(--graphite); font-family:"Microsoft YaHei UI","Noto Sans CJK SC","PingFang SC",sans-serif; min-height:100vh; }
    body::before { content:""; position:fixed; inset:0; pointer-events:none; background:linear-gradient(90deg,transparent 49.8%,rgba(50,216,203,.035) 50%,transparent 50.2%); }
    .shell { width:min(1240px,calc(100% - 28px)); margin:0 auto; padding:28px 0 56px; }
    header { display:grid; grid-template-columns:1fr auto; gap:24px; align-items:end; padding:22px 24px; border:1px solid var(--line); border-top:4px solid var(--cyan); background:linear-gradient(135deg,rgba(32,44,48,.96),rgba(20,29,32,.96)); box-shadow:0 18px 60px rgba(0,0,0,.28); }
    .eyebrow { color:var(--cyan); letter-spacing:.22em; font-size:.76rem; }
    h1 { margin:.35rem 0 .25rem; font-family:"SimHei","Microsoft YaHei UI",sans-serif; font-size:clamp(1.8rem,4vw,3.2rem); letter-spacing:.04em; }
    .lead,.muted { color:var(--muted); }
    .lamp { display:flex; align-items:center; gap:10px; color:var(--amber); font-weight:700; }
    .lamp::before { content:""; width:13px; height:13px; border-radius:50%; background:currentColor; box-shadow:0 0 18px currentColor; }
    .toolbar,.panel { border:1px solid var(--line); background:rgba(25,34,38,.94); }
    .toolbar { margin-top:14px; padding:14px 18px; display:flex; flex-wrap:wrap; gap:12px 24px; align-items:center; }
    select,textarea,button { font:inherit; }
    select,textarea { color:var(--ink); background:#0e1517; border:1px solid var(--line); padding:10px 12px; }
    .players { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin-top:14px; }
    .player { position:relative; padding:18px; min-height:184px; overflow:hidden; }
    .player::after { content:""; position:absolute; left:0; right:0; bottom:0; height:3px; background:var(--cyan); transform:scaleX(var(--signal,.34)); transform-origin:left; }
    .player:nth-child(n+2)::after { background:var(--amber); }
    .channel { color:var(--muted); font-size:.72rem; letter-spacing:.18em; }
    .player h2 { margin:.5rem 0 1.4rem; font-size:1.22rem; }
    audio { width:100%; filter:sepia(.12) saturate(.8) hue-rotate(125deg); }
    .sha { margin-top:14px; color:var(--muted); font-family:Consolas,monospace; font-size:.7rem; overflow-wrap:anywhere; }
    .grid { display:grid; grid-template-columns:1.15fr .85fr; gap:14px; margin-top:14px; }
    .research-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; margin-top:14px; }
    .panel { padding:20px; }
    h3 { margin:0 0 14px; color:var(--cyan); font-size:1rem; letter-spacing:.08em; }
    table { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }
    th,td { text-align:left; padding:9px 8px; border-bottom:1px solid #2c3d42; }
    th { color:var(--muted); font-size:.78rem; }
    .answers { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .choice { border:1px solid var(--line); padding:14px; cursor:pointer; background:#11191c; }
    .choice:has(input:checked) { border-color:var(--amber); box-shadow:inset 0 0 0 1px var(--amber); }
    textarea { width:100%; min-height:104px; margin-top:12px; resize:vertical; }
    .status { margin-top:14px; padding:13px 15px; border-left:4px solid var(--amber); background:#11191c; color:var(--amber); }
    button { margin-top:12px; width:100%; border:0; padding:14px 18px; color:#08201f; background:var(--cyan); font-weight:900; letter-spacing:.05em; cursor:pointer; }
    button:disabled { cursor:not-allowed; background:#3a494c; color:#839191; }
    .tag { display:inline-block; margin:0 8px 8px 0; padding:5px 8px; border:1px solid var(--line); color:var(--muted); font-size:.75rem; }
    .residual-card { margin:0; }
    .residual-card img { display:block; width:100%; min-height:180px; border:1px solid var(--line); background:#111719; }
    .trace { margin-top:10px; color:var(--muted); font-family:Consolas,monospace; font-size:.72rem; overflow-wrap:anywhere; }
    @media (max-width:850px) { header,.grid,.research-grid { grid-template-columns:1fr; } .players { grid-template-columns:1fr; } .shell { width:min(100% - 18px,680px); } }
  </style>
</head>
<body>
<main class="shell">
  <header>
    <div><div class="eyebrow">S12 / U7 / SHA-256</div><h1>工业声学对照台</h1><div class="lead">三路播放器：参考音轨、父版本与候选版本已随机映射到盲听通道 B/C。审听副本与原始副本分离。</div></div>
    <div class="lamp">等待人工审听</div>
  </header>
  <section class="toolbar"><label for="trial-select">审听片段</label><select id="trial-select" data-testid="trial-select"></select><span id="trial-meta" class="muted"></span><span id="status-labels" data-testid="status-labels"></span></section>
  <section class="players">
    <article class="player panel"><div class="channel">通道 01</div><h2>参考音轨</h2><audio controls preload="metadata" data-role="reference" data-testid="reference-player"></audio><div class="sha" data-sha="reference"></div></article>
    <article class="player panel" data-testid="parent-player"><div class="channel">通道 02</div><h2>盲听通道 B</h2><audio controls preload="metadata" data-slot="B" data-testid="blind-b-player"></audio><div class="sha" data-sha-slot="B"></div></article>
    <article class="player panel" data-testid="candidate-player"><div class="channel">通道 03</div><h2>盲听通道 C</h2><audio controls preload="metadata" data-slot="C" data-testid="blind-c-player"></audio><div class="sha" data-sha-slot="C"></div></article>
  </section>
  <section class="grid">
    <article class="panel"><h3>专业指标：调整前 / 调整后</h3><table><thead><tr><th>工具域</th><th>调整前距离</th><th>调整后距离</th></tr></thead><tbody id="metrics-body"></tbody></table><h3 style="margin-top:22px">参数值与不确定性</h3><div id="parameters"></div><p id="uncertainty" class="muted"></p></article>
    <article class="panel"><h3>哪个更接近参考音轨</h3><div class="answers"><label class="choice"><input type="radio" name="answer" value="B" data-testid="answer-b"> 盲听通道 B</label><label class="choice"><input type="radio" name="answer" value="C" data-testid="answer-c"> 盲听通道 C</label></div><textarea id="notes" data-testid="listener-notes" placeholder="记录低频压力、增压器质感、换挡冲击或其他听感依据（可选）"></textarea><div class="status" data-testid="gate-status">正在校验媒体……</div><button id="export" data-testid="export-submission" disabled>导出人工提交文件</button></article>
  </section>
  <section class="panel" data-testid="timbral-descriptors" style="margin-top:14px"><h3>音色描述符（可选研究指标）</h3><div id="timbral-status" class="status">PROJECT_UNMAINTAINED_NOT_AVAILABLE · 非硬门禁</div><p class="muted">当前项目不可维护且工具不可用；调整前与调整后均显示不可用，不以代理值代替。</p><table><thead><tr><th>描述符</th><th>调整前</th><th>调整后</th><th>状态</th></tr></thead><tbody id="timbral-body"></tbody></table></section>
  <section class="research-grid">
    <figure class="panel residual-card" data-testid="spectrogram-before"><h3>调整前频谱残差（参考对父版本）</h3><img id="spectrogram-before-image" alt="调整前频谱残差（参考对父版本）"><figcaption id="spectrogram-before-caption" class="muted"></figcaption><div id="spectrogram-before-trace" class="trace"></div></figure>
    <figure class="panel residual-card" data-testid="spectrogram-after"><h3>调整后频谱残差（参考对候选版本）</h3><img id="spectrogram-after-image" alt="调整后频谱残差（参考对候选版本）"><figcaption id="spectrogram-after-caption" class="muted"></figcaption><div id="spectrogram-after-trace" class="trace"></div></figure>
  </section>
</main>
<script src="review_data.js"></script><script src="review.js"></script>
</body>
</html>
"""


_JAVASCRIPT = r"""(() => {
  "use strict";
  const data = window.S12_STAGE_U_REVIEW_DATA;
  const roles = ["reference", "parent", "candidate"];
  const metricNames = {matlab:"MATLAB", mosqito:"MoSQITo", audio_feature_extractor:"audioFeatureExtractor"};
  const timbralNames = {hardness:"硬度", depth:"深度", brightness:"明亮度", roughness:"粗糙度", warmth:"温暖度", sharpness:"锐度", booming:"轰鸣感", reverb:"混响感"};
  const state = {current:0, answers:{}, notes:{}, media_validation:{}};
  const select = document.getElementById("trial-select");
  const exportButton = document.getElementById("export");
  const gateStatus = document.querySelector('[data-testid="gate-status"]');

  function freshMediaState(trial) {
    if (!state.media_validation[trial.trial_id]) state.media_validation[trial.trial_id] = {};
    roles.forEach(role => {
      if (!state.media_validation[trial.trial_id][role]) state.media_validation[trial.trial_id][role] = {
        duration_s:0, duration:false, canplaythrough:false, sha256:"", sha_status:"PENDING"
      };
    });
  }
  function hex(buffer) { return Array.from(new Uint8Array(buffer), byte => byte.toString(16).padStart(2,"0")).join(""); }
  async function verifySha(trial, role, url) {
    const receipt = state.media_validation[trial.trial_id][role];
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("媒体读取失败");
      receipt.sha256 = hex(await crypto.subtle.digest("SHA-256", await response.arrayBuffer()));
      receipt.sha_status = receipt.sha256 === trial.media[role].sha256 ? "MATCH" : "MISMATCH";
    } catch (_) { receipt.sha_status = "READ_ERROR"; }
    updateGate();
  }
  function bindMedia(trial, role, audio, shaNode) {
    const receipt = state.media_validation[trial.trial_id][role];
    audio.src = trial.media[role].url;
    audio.onloadedmetadata = () => {
      receipt.duration_s = Number(audio.duration);
      receipt.duration = Number.isFinite(audio.duration) && audio.duration > 0 && Math.abs(audio.duration - trial.media[role].duration_s) < 0.08;
      updateGate();
    };
    audio.oncanplaythrough = () => { receipt.canplaythrough = true; updateGate(); };
    audio.onerror = () => { receipt.canplaythrough = false; updateGate(); };
    shaNode.textContent = `SHA-256 ${trial.media[role].sha256}`;
    verifySha(trial, role, trial.media[role].url);
  }
  function renderTimbral(trial) {
    const receipt = trial.timbral_descriptors;
    document.getElementById("timbral-status").textContent = `${receipt.status} · ${receipt.gate_label}`;
    const body = document.getElementById("timbral-body"); body.replaceChildren();
    Object.entries(receipt.descriptors).forEach(([name,value]) => {
      const row = document.createElement("tr");
      [`${timbralNames[name]}（${name}）`, value.before ?? "不可用", value.after ?? "不可用", value.status].forEach(text => { const cell=document.createElement("td"); cell.textContent=String(text); row.appendChild(cell); });
      body.appendChild(row);
    });
  }
  function renderResidual(trial, phase) {
    const receipt = trial.spectrogram_residuals[phase];
    document.getElementById(`spectrogram-${phase}-image`).src = receipt.url;
    const summary = receipt.summary;
    const comparisonName = receipt.comparison_role === "parent" ? "父版本" : "候选版本";
    document.getElementById(`spectrogram-${phase}-caption`).textContent = `平均绝对残差 ${summary.mean_absolute_db.toFixed(3)} dB · 均方根残差 ${summary.rms_db.toFixed(3)} dB · 95% 绝对残差 ${summary.p95_absolute_db.toFixed(3)} dB`;
    document.getElementById(`spectrogram-${phase}-trace`).textContent = `参考音轨 SHA-256 ${receipt.reference_raw_sha256} · ${comparisonName} SHA-256 ${receipt.comparison_raw_sha256} · SVG SHA-256 ${receipt.svg_sha256}`;
  }
  function renderTrial(index) {
    state.current = index;
    const trial = data.trials[index];
    freshMediaState(trial);
    document.getElementById("trial-meta").textContent = `${trial.vehicle_id} · ${trial.scenario} · ${trial.candidate_id}`;
    const statusLabels = document.getElementById("status-labels");
    statusLabels.replaceChildren();
    Object.values(trial.status_labels).forEach(label => {
      const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = label; statusLabels.appendChild(tag);
    });
    bindMedia(trial, "reference", document.querySelector('audio[data-role="reference"]'), document.querySelector('[data-sha="reference"]'));
    ["B","C"].forEach(slot => {
      const role = trial.randomized_mapping[slot];
      bindMedia(trial, role, document.querySelector(`audio[data-slot="${slot}"]`), document.querySelector(`[data-sha-slot="${slot}"]`));
    });
    const body = document.getElementById("metrics-body");
    body.replaceChildren();
    Object.entries(trial.professional_metrics).forEach(([name,value]) => {
      const row = document.createElement("tr");
      [metricNames[name] || name, value.before.toFixed(6), value.after.toFixed(6)].forEach(text => { const cell = document.createElement("td"); cell.textContent = text; row.appendChild(cell); });
      body.appendChild(row);
    });
    const parameters = document.getElementById("parameters");
    parameters.replaceChildren();
    Object.entries(trial.parameter_values).forEach(([name,value]) => { const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = `${name} = ${value}`; parameters.appendChild(tag); });
    document.getElementById("uncertainty").textContent = trial.parameter_uncertainty.display;
    renderTimbral(trial);
    renderResidual(trial, "before");
    renderResidual(trial, "after");
    document.querySelectorAll('input[name="answer"]').forEach(input => { input.checked = state.answers[trial.trial_id] === input.value; });
    document.getElementById("notes").value = state.notes[trial.trial_id] || "";
    updateGate();
  }
  function mediaReady(trial) {
    freshMediaState(trial);
    return roles.every(role => {
      const gate = state.media_validation[trial.trial_id][role];
      return gate.duration && gate.canplaythrough && gate.sha_status === "MATCH";
    });
  }
  function trialReady(trial) {
    return mediaReady(trial) && trial.parent_candidate_distinct === true && trial.professional_binding.passes === true && ["B","C"].includes(state.answers[trial.trial_id]);
  }
  function updateGate() {
    const current = data.trials[state.current];
    const allReady = data.trials.every(trialReady);
    exportButton.disabled = !allReady;
    if (!mediaReady(current)) gateStatus.textContent = "媒体校验未通过：需要有效时长、可连续播放事件与 SHA-256 一致。";
    else if (!current.parent_candidate_distinct) gateStatus.textContent = "门禁失败：父版本与候选版本必须不同。";
    else if (!current.professional_binding.passes) gateStatus.textContent = "门禁失败：缺少专业指标绑定。";
    else if (!["B","C"].includes(state.answers[current.trial_id])) gateStatus.textContent = "媒体已通过；请选择盲听通道 B 或 C。";
    else if (!allReady) gateStatus.textContent = "当前片段已完成；仍有其他片段未通过或未作答。";
    else gateStatus.textContent = "全部门禁与人工答案已齐备，可以导出提交文件。";
  }
  function submission() {
    const mappings = {}, sha_bindings = {}, responses = [];
    data.trials.forEach(trial => {
      mappings[trial.trial_id] = trial.randomized_mapping;
      sha_bindings[trial.trial_id] = trial.sha_bindings;
      responses.push({trial_id:trial.trial_id, answer:state.answers[trial.trial_id], notes:state.notes[trial.trial_id] || ""});
    });
    return {schema_version:"s12-stage-u-listener-submission-v1", manifest_sha256:data.manifest_sha256, submitted_at_utc:new Date().toISOString(), mappings, sha_bindings, media_validation:state.media_validation, responses};
  }
  function exportSubmission() {
    updateGate();
    if (exportButton.disabled) return;
    const blob = new Blob([JSON.stringify(submission(), null, 2) + "\n"], {type:"application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob); link.download = `Jovi_Stage_U_人工提交_${new Date().toISOString().replace(/[:.]/g,"-")}.json`; link.click(); URL.revokeObjectURL(link.href);
  }
  data.trials.forEach((trial,index) => { const option=document.createElement("option"); option.value=String(index); option.textContent=`${index+1}. ${trial.vehicle_id} / ${trial.scenario}`; select.appendChild(option); freshMediaState(trial); });
  select.addEventListener("change", () => renderTrial(Number(select.value)));
  document.querySelectorAll('input[name="answer"]').forEach(input => input.addEventListener("change", () => { state.answers[data.trials[state.current].trial_id]=input.value; updateGate(); }));
  document.getElementById("notes").addEventListener("input", event => { state.notes[data.trials[state.current].trial_id]=event.target.value; });
  exportButton.addEventListener("click", exportSubmission);
  renderTrial(0);
})();
"""


__all__ = [
    "ALLOWED_EXTERNAL_ROOT",
    "StageUReviewPackageError",
    "build_review_package",
    "create_review_http_server",
    "validate_listener_submission",
    "validate_review_package",
]
