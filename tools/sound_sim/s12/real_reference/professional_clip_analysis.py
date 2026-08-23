"""Exact anchor A/B clip integrity and transparent legacy-proxy diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly, stft

from tools.sound_sim.s12.acoustic_comparator.spectral import (
    BAND_NAMES,
    band_comparison,
    normalized_log_spectral_distance,
    spectrum_features,
)
from tools.sound_sim.s12.acoustic_comparator.transients import event_metrics, transient_shape


class ExactClipValidationError(ValueError):
    """Raised when one exact A/B clip cannot be used safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExactClipValidationError(f"cannot read manifest: {path}") from exc
    if not isinstance(value, dict):
        raise ExactClipValidationError("anchor manifest must be an object")
    return value


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExactClipValidationError(f"missing {label}")
    return value.strip()


def load_exact_anchor_pairs(manifest_path: Path) -> list[dict[str, Any]]:
    """Normalize the exact 9 trials used by the Chinese page."""

    manifest_path = Path(manifest_path).resolve()
    manifest = _json(manifest_path)
    trials = manifest.get("trials")
    if manifest.get("schema_version") != "s12-stage-s-anchor-ab-zh.v1" or not isinstance(trials, list) or len(trials) != 9:
        raise ExactClipValidationError("exact anchor manifest must be the v1 nine-trial package")
    pairs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for trial in trials:
        if not isinstance(trial, Mapping):
            raise ExactClipValidationError("anchor trial is malformed")
        trial_id = _required_text(trial.get("trial_id"), "trial_id")
        if trial_id in seen:
            raise ExactClipValidationError(f"duplicate trial_id: {trial_id}")
        seen.add(trial_id)
        pairs.append({
            "pair_id": trial_id,
            "trial_id": trial_id,
            "file_id": f"{trial_id}-reference-vs-candidate",
            "vehicle_id": _required_text(trial.get("vehicle_id"), f"{trial_id}.vehicle_id"),
            "scenario": str(trial.get("reference_segment") or "scenario_candidate_peak"),
            "reference_class": str(manifest.get("evidence_level") or "R3"),
            "reference_path": _required_text(trial.get("reference_audition_path"), f"{trial_id}.reference_audition_path"),
            "reference_sha256": _required_text(trial.get("reference_audition_sha256"), f"{trial_id}.reference_audition_sha256").lower(),
            "reference_original_sha256": _required_text(trial.get("reference_original_wav_sha256"), f"{trial_id}.reference_original_wav_sha256").lower(),
            "candidate_path": _required_text(trial.get("candidate_audition_path"), f"{trial_id}.candidate_audition_path"),
            "candidate_sha256": _required_text(trial.get("candidate_audition_sha256"), f"{trial_id}.candidate_audition_sha256").lower(),
            "window": {
                "start_s": float(trial.get("reference_start_s") or 0.0),
                "duration_s": float(trial.get("reference_duration_s") or 5.0),
            },
            "microphone_uncertainty": "UNKNOWN_PUBLIC_VIDEO_CAPTURE",
            "order": {
                "status": "ORDER_COMPARISON_NOT_QUALIFIED",
                "reason": "reference and candidate have no synchronized RPM trace",
            },
            "manifest_sha256": _sha256(manifest_path),
        })
    return pairs


def _read_audio(path: Path) -> tuple[np.ndarray, int, int, float]:
    if not path.is_file():
        raise ExactClipValidationError(f"audio file missing: {path}")
    if path.suffix.lower() != ".wav":
        raise ExactClipValidationError(f"exact dashboard clip must be WAV: {path}")
    try:
        sample_rate_hz, raw_signal = wavfile.read(str(path))
    except Exception as exc:
        raise ExactClipValidationError(f"audio cannot be decoded: {path}") from exc
    signal = np.asarray(raw_signal)
    if np.issubdtype(signal.dtype, np.integer):
        info = np.iinfo(signal.dtype)
        signal = signal.astype(np.float64) / float(max(abs(info.min), info.max))
    else:
        signal = signal.astype(np.float64)
    if signal.ndim == 1:
        signal = signal[:, None]
    if signal.size == 0 or sample_rate_hz <= 0:
        raise ExactClipValidationError(f"audio duration is zero: {path}")
    if not np.isfinite(signal).all():
        raise ExactClipValidationError(f"audio contains non-finite samples: {path}")
    duration_s = signal.shape[0] / float(sample_rate_hz)
    if duration_s <= 0.0:
        raise ExactClipValidationError(f"audio duration is zero: {path}")
    return signal.mean(axis=1), int(sample_rate_hz), int(signal.shape[1]), float(duration_s)


def _audio_evidence(path_value: str, declared_sha: str, side: str) -> dict[str, Any]:
    path = Path(path_value).resolve()
    signal, sample_rate_hz, channels, duration_s = _read_audio(path)
    actual_sha = _sha256(path)
    if actual_sha.lower() != declared_sha.lower():
        raise ExactClipValidationError(f"{side} SHA-256 mismatch: {path}")
    return {
        "path": str(path),
        "sha256": actual_sha,
        "sha_status": "MATCH",
        "sample_rate_hz": sample_rate_hz,
        "channels": channels,
        "duration_s": duration_s,
        "finite_pcm": True,
        "nonzero_duration": True,
    }


def validate_exact_clip_pair(pair: Mapping[str, Any]) -> dict[str, Any]:
    reference = _audio_evidence(str(pair["reference_path"]), str(pair["reference_sha256"]), "reference")
    candidate = _audio_evidence(str(pair["candidate_path"]), str(pair["candidate_sha256"]), "candidate")
    expected_duration = float(pair.get("window", {}).get("duration_s", 5.0))
    if reference["duration_s"] < expected_duration - 1e-6 or candidate["duration_s"] < expected_duration - 1e-6:
        raise ExactClipValidationError(f"exact clip is shorter than the requested window: {pair.get('pair_id')}")
    return {
        "status": "PASS",
        "pair_id": pair["pair_id"],
        "file_id": pair["file_id"],
        "vehicle_id": pair["vehicle_id"],
        "scenario": pair["scenario"],
        "reference_class": pair["reference_class"],
        "reference": reference,
        "candidate": candidate,
        "window": {"start_s": pair["window"]["start_s"], "duration_s": expected_duration},
        "microphone_uncertainty": pair["microphone_uncertainty"],
        "order": pair["order"],
        "required_files": True,
    }


def _resample(signal: np.ndarray, source_fs: int, target_fs: int) -> np.ndarray:
    if source_fs == target_fs:
        return signal
    from math import gcd

    divisor = gcd(source_fs, target_fs)
    return resample_poly(signal, target_fs // divisor, source_fs // divisor)


def _spectrogram(signal: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nperseg = max(2, min(2048, signal.size))
    noverlap = min(nperseg - 1, nperseg // 2)
    frequencies, times, values = stft(signal, fs=sample_rate_hz, nperseg=nperseg, noverlap=noverlap, boundary=None)
    power = 20.0 * np.log10(np.maximum(np.abs(values), 1e-12))
    return frequencies, times, power


def _resize_matrix(matrix: np.ndarray, rows: int = 64, columns: int = 48) -> np.ndarray:
    row_idx = np.linspace(0, matrix.shape[0] - 1, min(rows, matrix.shape[0])).round().astype(int)
    col_idx = np.linspace(0, matrix.shape[1] - 1, min(columns, matrix.shape[1])).round().astype(int)
    return matrix[np.ix_(row_idx, col_idx)]


def _legacy_metrics(signal: np.ndarray, sample_rate_hz: int) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    features, spectrum, frequencies = spectrum_features(signal, sample_rate_hz)
    transient = transient_shape(signal, sample_rate_hz)
    rms = float(np.sqrt(np.mean(np.square(signal))))
    crest = float(np.max(np.abs(signal)) / max(rms, 1e-12))
    frequencies_stft, times, magnitude = _spectrogram(signal, sample_rate_hz)
    normalized = magnitude - np.max(magnitude, axis=0, keepdims=True)
    flux = float(np.mean(np.sqrt(np.mean(np.square(np.diff(normalized, axis=1)), axis=0)))) if normalized.shape[1] > 1 else 0.0
    transient.update({
        "crest_factor": crest,
        "spectral_flux_proxy": flux,
        "event_count_proxy": event_metrics(signal, None)["event_count"],
        "wrong_condition_event_count": 0,
    })
    return {"spectrum": features, "transient": transient}, frequencies_stft, times, magnitude


def analyze_proxy_pair(pair: Mapping[str, Any]) -> dict[str, Any]:
    """Compute only transparent Legacy Proxy fields for one pair."""

    integrity = validate_exact_clip_pair(pair)
    reference, reference_fs, _, _ = _read_audio(Path(pair["reference_path"]))
    candidate, candidate_fs, _, _ = _read_audio(Path(pair["candidate_path"]))
    candidate = _resample(candidate, candidate_fs, reference_fs)
    window_samples = min(int(round(5.0 * reference_fs)), reference.size, candidate.size)
    reference = reference[:window_samples]
    candidate = candidate[:window_samples]
    reference_metrics, ref_freq, ref_time, ref_spectrogram = _legacy_metrics(reference, reference_fs)
    candidate_metrics, cand_freq, cand_time, cand_spectrogram = _legacy_metrics(candidate, reference_fs)
    reference_bands = reference_metrics["spectrum"]
    candidate_bands = candidate_metrics["spectrum"]
    bands = band_comparison(reference_bands, candidate_bands)
    ref_mag = np.interp(np.linspace(0, 1, 256), np.linspace(0, 1, len(ref_freq)), ref_spectrogram.mean(axis=1))
    cand_mag = np.interp(np.linspace(0, 1, 256), np.linspace(0, 1, len(cand_freq)), cand_spectrogram.mean(axis=1))
    aligned_reference = _resize_matrix(ref_spectrogram, rows=cand_spectrogram.shape[0], columns=cand_spectrogram.shape[1])
    spectrogram_residual = cand_spectrogram - aligned_reference
    spectrogram_residual = _resize_matrix(spectrogram_residual)
    reference_transient = reference_metrics["transient"]
    candidate_transient = candidate_metrics["transient"]
    transient_delta = {
        key: (candidate_transient.get(key) - reference_transient.get(key))
        if isinstance(candidate_transient.get(key), (int, float)) and isinstance(reference_transient.get(key), (int, float))
        else None
        for key in ("attack_s", "decay_to_10pct_s", "impact_peak", "crest_factor", "spectral_flux_proxy", "event_count_proxy")
    }
    reference_power = np.abs(np.fft.rfft(reference)) ** 2
    candidate_power = np.abs(np.fft.rfft(candidate)) ** 2
    candidate_power_aligned = np.interp(
        np.linspace(0.0, 1.0, reference_power.size),
        np.linspace(0.0, 1.0, candidate_power.size),
        candidate_power,
    )
    return {
        "pair_id": pair["pair_id"],
        "file_id": pair["file_id"],
        "vehicle_id": pair["vehicle_id"],
        "scenario": pair["scenario"],
        "reference_class": pair["reference_class"],
        "tool_domains": ["Legacy Proxy"],
        "integrity": integrity,
        "legacy_proxy": {
            "reference": reference_metrics,
            "candidate": candidate_metrics,
            "delta": {
                "rms_db": candidate_bands["rms_db"] - reference_bands["rms_db"],
                "centroid_hz": candidate_bands["centroid_hz"] - reference_bands["centroid_hz"],
                "rolloff_hz": candidate_bands["rolloff_hz"] - reference_bands["rolloff_hz"],
                "bands": bands,
                "transient": transient_delta,
                "spectral_distance": normalized_log_spectral_distance(
                    np.asarray(reference_power, dtype=float), np.asarray(candidate_power_aligned, dtype=float)
                ),
            },
            "bands": bands,
            "transient": transient_delta,
        },
        "spectrogram_residual": {
            "status": "COMPUTED_LEGACY_PROXY",
            "unit": "dB_candidate_minus_reference",
            "frequencies_hz": np.linspace(float(ref_freq.min()), float(ref_freq.max()), spectrogram_residual.shape[0]).tolist(),
            "times_s": np.linspace(float(min(ref_time.min(), cand_time.min())), float(max(ref_time.max(), cand_time.max())), spectrogram_residual.shape[1]).tolist(),
            "values": spectrogram_residual.tolist(),
        },
        "matlab": {"status": "PENDING_EXACT_CLIP_RECEIPT"},
        "mosqito": {"status": "PENDING_EXACT_CLIP_RECEIPT"},
        "order": pair["order"],
        "uncertainty": {
            "legal_permission": "R3_PUBLIC_VIDEO_DERIVATIVE_OR_PACKAGE_POLICY",
            "stock_exhaust": "UNKNOWN",
            "microphone_agc": pair["microphone_uncertainty"],
            "rpm_load_gear_sync": "MISSING",
            "absolute_spl": "NOT_AVAILABLE_DIGITAL_DOMAIN_ONLY",
        },
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="分析 S12 页面 exact reference/candidate 片段（Legacy Proxy only）")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--proxy-only", action="store_true")
    args = parser.parse_args(argv)
    pairs = load_exact_anchor_pairs(args.manifest)
    integrity: list[dict[str, Any]] = []
    proxies: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs, start=1):
        checked = validate_exact_clip_pair(pair)
        integrity.append(checked)
        proxies.append(analyze_proxy_pair(pair))
        print(f"[{index}/{len(pairs)}] {pair['pair_id']}", flush=True)
    _write_json(args.output_dir / "clip_integrity.json", {
        "schema_version": "s12-professional-exact-clip-integrity-v1",
        "status": "PASS",
        "manifest_path": str(Path(args.manifest).resolve()),
        "manifest_sha256": pairs[0]["manifest_sha256"],
        "pair_count": len(pairs),
        "clip_count": len(pairs) * 2,
        "pairs": integrity,
    })
    _write_json(args.output_dir / "legacy_proxy_metrics.json", {
        "schema_version": "s12-professional-legacy-proxy-metrics-v1",
        "status": "COMPUTED_LEGACY_PROXY_ONLY",
        "pairs": proxies,
        "order_status": "ORDER_COMPARISON_NOT_QUALIFIED",
        "automatic_tuning_eligible": False,
    })
    return 0


__all__ = [
    "ExactClipValidationError",
    "analyze_proxy_pair",
    "load_exact_anchor_pairs",
    "validate_exact_clip_pair",
]


if __name__ == "__main__":
    raise SystemExit(main())
