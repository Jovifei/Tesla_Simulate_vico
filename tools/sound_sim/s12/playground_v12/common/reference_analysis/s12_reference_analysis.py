"""Deterministic v1.2 reference inventory and acoustic-analysis contracts.

The caller supplies decoded samples. This module never opens, hashes, copies,
or stores reference media.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit

import jsonschema
import numpy as np


ORDERS = tuple(0.5 * index for index in range(1, 37))
FIXED_BANDS_HZ = (
    (20, 120),
    (120, 500),
    (500, 2000),
    (2000, 8000),
    (8000, 16000),
)
RAW_MEDIA_ROOT = r"E:\Claude_allow\Download\tesla-sound-research-v12"
SAMPLES_PER_REVOLUTION = 128
WINDOW_DURATION_S = 0.25
HOP_DURATION_S = 0.10
ENVELOPE_BLOCK_DURATION_S = 0.02
FORMANT_SMOOTHING_HZ = 100.0
FORMANT_MIN_SPACING_HZ = 100.0
FORMANT_ORDER_RIDGE_EXCLUSION_HZ = 50.0
FORMANT_PERSISTENCE_FRACTION = 0.60
SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas"
FORBIDDEN_MEDIA_FRAGMENTS = (
    "audio",
    "pcm",
    "waveform",
    "cache",
    "media_blob",
    "media_hash",
    "content_hash",
    "raw_content",
    "raw_sha",
    "file_path",
    "sample_path",
)
ANALYSIS_KEYS = frozenset(
    {
        "schema_version",
        "reference_binding",
        "analysis_method",
        "derived_metrics",
        "analysis_sha256",
    }
)
RAW_AUDIO_EXTENSION = re.compile(
    r"\.(?:wav|wave|flac|mp3|aac|ogg|m4a|raw|pcm|aiff?|opus)(?:$|[?&#])",
    re.IGNORECASE,
)
HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
WINDOW_TOLERANCE = 1e-10
METRIC_TOLERANCE = 1e-9
PHASE_TOLERANCE_RAD = 2e-6


class ReferenceContractError(ValueError):
    """Raised when provenance or derived analysis violates the v1.2 boundary."""


def canonical_json(value: object) -> str:
    """Return stable, finite JSON suitable for repeatability hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def validate_reference(reference: Mapping[str, object]) -> dict:
    """Validate and return a detached R1, R2, or R3 inventory record."""

    if not isinstance(reference, Mapping):
        raise ReferenceContractError("Reference manifest must be an object.")
    _reject_media_fields(reference)
    detached = _detached_json(reference, "Reference manifest")
    _schema_validate(detached, "reference_manifest_v12.schema.json", "reference schema")

    source = _require_mapping(detached, "source")
    url = _require_text(source, "url")
    parsed_url = urlsplit(url)
    if parsed_url.scheme.lower() != "https" or not parsed_url.netloc:
        raise ReferenceContractError("source.url must be an absolute HTTPS URL.")
    expected_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    if source["source_url_sha256"] != expected_hash:
        raise ReferenceContractError("source_url_sha256 must hash the exact source URL.")

    clip = _require_mapping(detached, "clip_window")
    start_s = _finite_number(clip["start_s"], "clip_window.start_s")
    end_s = _finite_number(clip["end_s"], "clip_window.end_s")
    if end_s <= start_s:
        raise ReferenceContractError("clip window must have start_s < end_s.")

    quality = detached["quality_class"]
    if quality == "R1":
        stock = _require_mapping(detached, "stock_evidence")
        if stock["is_stock"] is not True:
            raise ReferenceContractError("R1 requires explicit stock evidence.")
        rpm = _require_mapping(detached, "rpm_evidence")
        trace_time_s, _ = _validated_rpm_trace(
            rpm["samples"],
            minimum_samples=3 if rpm["source"] == "rpm_anchors" else 2,
        )
        tolerance = 1e-12
        if trace_time_s[0] > start_s + tolerance or trace_time_s[-1] < end_s - tolerance:
            raise ReferenceContractError("RPM evidence must cover the complete clip window.")
    return detached


def analyze_reference(
    reference: Mapping[str, object],
    pcm: object,
    sample_rate_hz: object,
    events: object = (),
) -> dict:
    """Analyze one accepted R1 clip with a dynamic crank-angle order map."""

    validated = validate_reference(reference)
    if validated["quality_class"] != "R1":
        raise ReferenceContractError("Only an R1 reference can be analyzed.")

    sample_rate = _finite_number(sample_rate_hz, "sample_rate_hz")
    if sample_rate < 32000:
        raise ReferenceContractError(
            "sample_rate_hz must be at least 32000 to measure through 16000 Hz."
        )
    if sample_rate > 768000:
        raise ReferenceContractError("sample_rate_hz exceeds the supported range.")

    mono = _mono_pcm(pcm)
    if mono.size < 64:
        raise ReferenceContractError("PCM must contain at least 64 samples.")
    clip = validated["clip_window"]
    clip_start_s = float(clip["start_s"])
    clip_end_s = float(clip["end_s"])
    clip_duration_s = clip_end_s - clip_start_s
    measured_duration_s = mono.size / sample_rate
    if abs(measured_duration_s - clip_duration_s) > (1.0 / sample_rate + 1e-12):
        raise ReferenceContractError("PCM duration must match the declared clip window.")

    rpm_evidence = validated["rpm_evidence"]
    trace_time_s, trace_rpm = _validated_rpm_trace(
        rpm_evidence["samples"],
        minimum_samples=3 if rpm_evidence["source"] == "rpm_anchors" else 2,
    )
    sample_time_s = clip_start_s + np.arange(mono.size, dtype=np.float64) / sample_rate
    sample_rpm = np.interp(sample_time_s, trace_time_s, trace_rpm)
    revolutions = np.zeros(mono.size, dtype=np.float64)
    revolution_steps = (sample_rpm[:-1] + sample_rpm[1:]) / (120.0 * sample_rate)
    revolutions[1:] = np.cumsum(revolution_steps)

    frames, global_amplitudes, global_phases = _dynamic_order_map(
        mono,
        sample_time_s,
        sample_rpm,
        revolutions,
        clip_start_s,
        clip_end_s,
    )
    frequencies_hz, spectrum, power = _global_spectrum(mono, sample_rate)
    band_energy = [
        float(np.sum(power[(frequencies_hz >= low) & (frequencies_hz < high)]))
        for low, high in FIXED_BANDS_HZ
    ]
    total_band_energy = sum(band_energy)
    band_ratios = (
        [0.0] * len(FIXED_BANDS_HZ)
        if total_band_energy <= np.finfo(np.float64).eps
        else [value / total_band_energy for value in band_energy]
    )
    validated_events = _validated_events(events, clip_start_s, clip_end_s)
    reference_binding = _reference_binding(validated)

    method = {
        "domain": "windowed_dynamic_crank_angle_order_map",
        "cycle_degrees": 720,
        "order_range": [0.5, 18.0],
        "order_step": 0.5,
        "samples_per_revolution": SAMPLES_PER_REVOLUTION,
        "ordinary_average_rpm_fft": False,
        "source_sample_rate_hz": sample_rate,
        "frequency_limit_hz": 16000,
        "window_duration_s": WINDOW_DURATION_S,
        "hop_duration_s": HOP_DURATION_S,
        "envelope_block_duration_s": ENVELOPE_BLOCK_DURATION_S,
        "formant_envelope_smoothing_hz": FORMANT_SMOOTHING_HZ,
        "formant_min_peak_spacing_hz": FORMANT_MIN_SPACING_HZ,
        "formant_order_ridge_exclusion_hz": FORMANT_ORDER_RIDGE_EXCLUSION_HZ,
        "formant_tracking": "time_windowed_local_rpm_order_ridge_exclusion",
        "formant_persistence_fraction": FORMANT_PERSISTENCE_FRACTION,
    }
    metrics = {
        "orders": list(ORDERS),
        "order_amplitudes": global_amplitudes,
        "order_phases_rad": global_phases,
        "order_map": {"orders": list(ORDERS), "frames": frames},
        "fixed_bands_hz": [list(band) for band in FIXED_BANDS_HZ],
        "band_energy_ratios": band_ratios,
        "formants_hz": _persistent_formants(
            mono,
            sample_rate,
            sample_time_s,
            sample_rpm,
            FORMANT_SMOOTHING_HZ,
            FORMANT_MIN_SPACING_HZ,
            FORMANT_ORDER_RIDGE_EXCLUSION_HZ,
            FORMANT_PERSISTENCE_FRACTION,
        ),
        "spectral_centroid_hz": _spectral_centroid(frequencies_hz, spectrum),
        "spectral_rolloff_hz": _spectral_rolloff(frequencies_hz, power),
        "spectral_flatness": _spectral_flatness(power),
        "modulation_depth": _modulation_depth(
            mono, sample_rate, ENVELOPE_BLOCK_DURATION_S
        ),
        "pulse_amplitude_cv": _pulse_amplitude_cv(
            mono, sample_rate, ENVELOPE_BLOCK_DURATION_S
        ),
        "shift_statistics": _event_statistics(
            validated_events,
            {"upshift_bark", "downshift_blip_pop"},
            clip_start_s,
        ),
        "afterfire_statistics": _event_statistics(
            validated_events,
            {"overrun_crackle"},
            clip_start_s,
        ),
    }
    body = _round_tree(
        {
            "schema_version": "s12-engine-sound-v12-analysis-1",
            "reference_binding": reference_binding,
            "analysis_method": method,
            "derived_metrics": metrics,
        }
    )
    body["analysis_sha256"] = hashlib.sha256(
        canonical_json(body).encode("utf-8")
    ).hexdigest()
    _validate_analysis(body, validated)
    return _detached_json(body, "Analysis")


def build_acoustic_target(
    reference: Mapping[str, object],
    pcm: object,
    sample_rate_hz: object,
    events: object = (),
) -> dict:
    """Recompute and bind derived metrics from one transient R1 input."""

    validated = validate_reference(reference)
    if validated["quality_class"] != "R1":
        raise ReferenceContractError("Only an R1 reference can build an acoustic target.")
    analysis = analyze_reference(validated, pcm, sample_rate_hz, events)
    target = _round_tree(
        {
            "schema_version": "s12-engine-sound-v12-acoustic-target-1",
            "vehicle_id": validated["vehicle_id"],
            "reference_id": validated["reference_id"],
            "reference_quality": "R1",
            "source_url_sha256": validated["source"]["source_url_sha256"],
            "analysis_sha256": analysis["analysis_sha256"],
            "reference_binding": analysis["reference_binding"],
            "analysis_method": analysis["analysis_method"],
            "derived_metrics": analysis["derived_metrics"],
            "scope": {
                "synthetic": True,
                "uncalibrated": True,
                "offline": True,
                "oem_clone": False,
            },
        }
    )
    _reject_media_fields(target)
    _schema_validate(target, "acoustic_target_v12.schema.json", "target schema")
    return _detached_json(target, "Acoustic target")


def _reference_binding(reference: Mapping[str, object]) -> dict:
    return {
        "reference_manifest_sha256": hashlib.sha256(
            canonical_json(reference).encode("utf-8")
        ).hexdigest(),
    }


def _dynamic_order_map(
    signal: np.ndarray,
    sample_time_s: np.ndarray,
    sample_rpm: np.ndarray,
    revolutions: np.ndarray,
    clip_start_s: float,
    clip_end_s: float,
) -> tuple[list[dict], list[float], list[float]]:
    centers = np.arange(
        clip_start_s,
        clip_end_s + HOP_DURATION_S * 0.5,
        HOP_DURATION_S,
        dtype=np.float64,
    )
    if centers.size == 0 or centers[-1] < clip_end_s - 1e-12:
        centers = np.append(centers, clip_end_s)
    else:
        centers[-1] = clip_end_s

    frame_rows: list[dict] = []
    frame_coefficients: list[np.ndarray] = []
    half_window = WINDOW_DURATION_S / 2.0
    coverage_edges = np.empty(centers.size + 1, dtype=np.float64)
    coverage_edges[0] = clip_start_s
    coverage_edges[-1] = clip_end_s
    if centers.size > 1:
        coverage_edges[1:-1] = (centers[:-1] + centers[1:]) / 2.0
    for frame_index, center_s in enumerate(centers):
        analysis_start_s = max(clip_start_s, float(center_s) - half_window)
        analysis_end_s = min(clip_end_s, float(center_s) + half_window)
        first = int(np.searchsorted(sample_time_s, analysis_start_s, side="left"))
        last = int(np.searchsorted(sample_time_s, analysis_end_s, side="right"))
        first = min(first, signal.size - 1)
        last = max(first + 2, min(last, signal.size))
        local_revolutions = revolutions[first:last] - revolutions[first]
        revolution_span = float(local_revolutions[-1])
        if revolution_span <= 0:
            raise ReferenceContractError("RPM trace produced a zero-length crank-angle frame.")
        count = max(
            64,
            int(math.floor(revolution_span * SAMPLES_PER_REVOLUTION)) + 1,
        )
        uniform_revolutions = np.linspace(0.0, revolution_span, count)
        angle_signal = np.interp(
            uniform_revolutions,
            local_revolutions,
            signal[first:last],
        )
        angle_signal -= np.mean(angle_signal)
        window = np.hanning(angle_signal.size)
        denominator = float(np.sum(window))
        coefficients = np.asarray(
            [
                2.0
                * np.sum(
                    angle_signal
                    * window
                    * np.exp(-2j * np.pi * order * uniform_revolutions)
                )
                / denominator
                for order in ORDERS
            ],
            dtype=np.complex128,
        )
        frame_coefficients.append(coefficients)
        frame_rows.append(
            {
                "start_time_s": float(coverage_edges[frame_index]),
                "center_time_s": float(center_s),
                "end_time_s": float(coverage_edges[frame_index + 1]),
                "center_rpm": float(np.interp(center_s, sample_time_s, sample_rpm)),
                "amplitudes": np.abs(coefficients).tolist(),
                "phases_rad": np.angle(coefficients).tolist(),
            }
        )
    coefficient_matrix = np.vstack(frame_coefficients)
    global_coefficients = np.mean(coefficient_matrix, axis=0)
    global_amplitudes = np.sqrt(
        np.mean(np.abs(coefficient_matrix) ** 2, axis=0)
    ).tolist()
    global_phases = np.angle(global_coefficients).tolist()
    return frame_rows, global_amplitudes, global_phases


def _global_spectrum(
    signal: np.ndarray, sample_rate: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    centered = signal - np.mean(signal)
    window = np.hanning(signal.size)
    frequencies = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate)
    spectrum = np.abs(np.fft.rfft(centered * window))
    keep = frequencies <= 16000.0
    spectrum = spectrum[keep]
    frequencies = frequencies[keep]
    return frequencies, spectrum, spectrum * spectrum


def _formant_candidates(
    frequencies: np.ndarray,
    spectrum: np.ndarray,
    smoothing_hz: float,
    minimum_spacing_hz: float,
    mean_rpm: float,
    order_ridge_exclusion_hz: float,
) -> list[float]:
    if frequencies.size < 3:
        return []
    bin_hz = max(float(frequencies[1] - frequencies[0]), np.finfo(float).eps)
    width = max(3, int(round(smoothing_hz / bin_hz)))
    if width % 2 == 0:
        width += 1
    kernel = np.ones(width, dtype=np.float64) / width
    positive_floor = max(
        float(np.max(spectrum)) * 1e-12,
        np.finfo(np.float64).tiny,
    )
    log_spectrum = np.log(np.maximum(spectrum, positive_floor))
    half_width = width // 2
    padded = np.pad(log_spectrum, (half_width, half_width), mode="edge")
    envelope = np.convolve(padded, kernel, mode="valid")
    candidates = np.flatnonzero(
        (envelope[1:-1] > envelope[:-2]) & (envelope[1:-1] >= envelope[2:])
    ) + 1
    candidates = candidates[
        (frequencies[candidates] >= 20) & (frequencies[candidates] <= 16000)
    ]
    predicted_ridges = np.asarray(ORDERS, dtype=np.float64) * mean_rpm / 60.0
    candidates = np.asarray(
        [
            index
            for index in candidates
            if np.min(np.abs(predicted_ridges - frequencies[index]))
            >= order_ridge_exclusion_hz
        ],
        dtype=np.int64,
    )
    ranked = sorted(
        candidates.tolist(),
        key=lambda index: (-envelope[index], frequencies[index]),
    )
    selected: list[int] = []
    for candidate in ranked:
        frequency = float(frequencies[candidate])
        if all(
            abs(frequency - float(frequencies[existing])) >= minimum_spacing_hz
            for existing in selected
        ):
            selected.append(candidate)
        if len(selected) == 6:
            break
    return sorted(float(frequencies[index]) for index in selected)


def _persistent_formants(
    signal: np.ndarray,
    sample_rate: float,
    sample_time_s: np.ndarray,
    sample_rpm: np.ndarray,
    smoothing_hz: float,
    minimum_spacing_hz: float,
    order_ridge_exclusion_hz: float,
    persistence_fraction: float,
) -> list[float]:
    """Keep fixed spectral modes, not transient order-ridge artefacts.

    Each time window uses its local RPM for order-ridge exclusion. A candidate
    must recur in the declared fraction of windows before it can survive the
    global envelope ranking. This is deliberately deterministic and requires
    no raw-media persistence beyond the caller-provided PCM.
    """

    window_samples = max(64, int(round(WINDOW_DURATION_S * sample_rate)))
    hop_samples = max(1, int(round(HOP_DURATION_S * sample_rate)))
    final_start = max(0, signal.size - window_samples)
    starts = list(range(0, final_start + 1, hop_samples))
    if not starts or starts[-1] != final_start:
        starts.append(final_start)

    clusters: list[dict[str, object]] = []
    for frame_index, start in enumerate(starts):
        stop = min(signal.size, start + window_samples)
        frame = signal[start:stop]
        frequencies, spectrum, _power = _global_spectrum(frame, sample_rate)
        center = min(start + frame.size // 2, sample_rpm.size - 1)
        candidates = _formant_candidates(
            frequencies,
            spectrum,
            smoothing_hz,
            minimum_spacing_hz,
            float(sample_rpm[center]),
            order_ridge_exclusion_hz,
        )
        for frequency in candidates:
            matching = [
                cluster
                for cluster in clusters
                if abs(float(cluster["center_hz"]) - frequency)
                < (minimum_spacing_hz / 2.0)
                and frame_index not in cluster["frames"]
            ]
            if matching:
                cluster = min(
                    matching,
                    key=lambda item: abs(float(item["center_hz"]) - frequency),
                )
                members = cluster["members_hz"]
                members.append(frequency)
                cluster["center_hz"] = float(np.mean(members))
                cluster["frames"].add(frame_index)
            else:
                clusters.append(
                    {
                        "center_hz": frequency,
                        "members_hz": [frequency],
                        "frames": {frame_index},
                    }
                )

    minimum_support = max(2, int(math.ceil(persistence_fraction * len(starts))))
    persistent = [
        float(cluster["center_hz"])
        for cluster in clusters
        if len(cluster["frames"]) >= minimum_support
    ]
    if not persistent:
        return []
    frequencies, spectrum, _power = _global_spectrum(signal, sample_rate)
    global_candidates = _formant_candidates(
        frequencies,
        spectrum,
        smoothing_hz,
        minimum_spacing_hz,
        float(np.mean(sample_rpm)),
        order_ridge_exclusion_hz,
    )
    return [
        frequency
        for frequency in global_candidates
        if any(
            abs(frequency - persistent_frequency) < (minimum_spacing_hz / 2.0)
            for persistent_frequency in persistent
        )
    ]


def _spectral_centroid(frequencies: np.ndarray, spectrum: np.ndarray) -> float:
    total = float(np.sum(spectrum))
    return 0.0 if total <= np.finfo(float).eps else float(
        np.dot(frequencies, spectrum) / total
    )


def _spectral_rolloff(frequencies: np.ndarray, power: np.ndarray) -> float:
    total = float(np.sum(power))
    if total <= np.finfo(float).eps:
        return 0.0
    index = min(
        int(np.searchsorted(np.cumsum(power), 0.85 * total)),
        frequencies.size - 1,
    )
    return float(frequencies[index])


def _spectral_flatness(power: np.ndarray) -> float:
    positive = power + np.finfo(float).tiny
    return float(np.exp(np.mean(np.log(positive))) / np.mean(positive))


def _block_peaks(
    signal: np.ndarray, sample_rate: float, block_duration_s: float
) -> np.ndarray:
    block_size = max(1, int(round(sample_rate * block_duration_s)))
    return np.asarray(
        [
            np.max(np.abs(signal[first:first + block_size]))
            for first in range(0, signal.size, block_size)
        ],
        dtype=np.float64,
    )


def _modulation_depth(
    signal: np.ndarray, sample_rate: float, block_duration_s: float
) -> float:
    peaks = _block_peaks(signal, sample_rate, block_duration_s)
    high = float(np.max(peaks))
    low = float(np.min(peaks))
    return 0.0 if high + low <= np.finfo(float).eps else (
        (high - low) / (high + low)
    )


def _pulse_amplitude_cv(
    signal: np.ndarray, sample_rate: float, block_duration_s: float
) -> float:
    peaks = _block_peaks(signal, sample_rate, block_duration_s)
    mean = float(np.mean(peaks))
    return 0.0 if mean <= np.finfo(float).eps else float(np.std(peaks) / mean)


def _validated_events(
    events: object, clip_start_s: float, clip_end_s: float
) -> list[dict]:
    if events is None:
        events = ()
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        raise ReferenceContractError("events must be a sequence.")
    allowed_kinds = {"upshift_bark", "downshift_blip_pop", "overrun_crackle"}
    result: list[dict] = []
    for event in events:
        if not isinstance(event, Mapping):
            raise ReferenceContractError("event entries must be objects.")
        if set(event) != {"time_s", "kind", "energy", "cluster_id"}:
            raise ReferenceContractError("event entries have an invalid shape.")
        time_s = _finite_number(event["time_s"], "event.time_s")
        energy = _finite_number(event["energy"], "event.energy")
        kind = str(event["kind"])
        cluster_id = str(event["cluster_id"]).strip()
        if kind not in allowed_kinds:
            raise ReferenceContractError("event.kind is unsupported.")
        if energy < 0:
            raise ReferenceContractError("event.energy must be nonnegative.")
        if not (clip_start_s <= time_s <= clip_end_s):
            raise ReferenceContractError("event.time_s must lie inside the clip window.")
        if not cluster_id:
            raise ReferenceContractError("event.cluster_id must be nonempty.")
        result.append(
            {
                "time_s": time_s,
                "kind": kind,
                "energy": energy,
                "cluster_id": cluster_id,
            }
        )
    return result


def _event_statistics(
    events: Sequence[Mapping[str, object]],
    kinds: set[str],
    clip_start_s: float,
) -> dict:
    selected = sorted(
        (event for event in events if event["kind"] in kinds),
        key=lambda event: (float(event["time_s"]), str(event["cluster_id"])),
    )
    times = np.asarray([float(event["time_s"]) for event in selected])
    energies = np.asarray([float(event["energy"]) for event in selected])
    intervals = np.diff(times)
    interval_mean = float(np.mean(intervals)) if intervals.size else 0.0
    cluster_events: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for event in selected:
        cluster_events[str(event["cluster_id"])].append(event)
    clusters = []
    for cluster_id in sorted(cluster_events):
        entries = cluster_events[cluster_id]
        cluster_times = [float(entry["time_s"]) for entry in entries]
        clusters.append(
            {
                "cluster_id": cluster_id,
                "event_count": len(entries),
                "total_energy": sum(float(entry["energy"]) for entry in entries),
                "start_delay_s": cluster_times[0] - clip_start_s,
                "energy_decay_ratio": (
                    float(entries[-1]["energy"]) / float(entries[0]["energy"])
                    if len(entries) > 1
                    and float(entries[0]["energy"]) > np.finfo(float).eps
                    else 0.0
                ),
                "tail_duration_s": cluster_times[-1] - cluster_times[0],
            }
        )
    return {
        "event_count": len(selected),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "first_event_delay_s": float(times[0] - clip_start_s) if times.size else 0.0,
        "total_energy": float(np.sum(energies)) if energies.size else 0.0,
        "interval_cv": (
            float(np.std(intervals) / interval_mean)
            if intervals.size and interval_mean > np.finfo(float).eps
            else 0.0
        ),
        "energy_decay_ratio": (
            float(energies[-1] / energies[0])
            if energies.size > 1 and energies[0] > np.finfo(float).eps
            else 0.0
        ),
        "tail_duration_s": float(times[-1] - times[0]) if times.size > 1 else 0.0,
    }


def _validate_analysis(
    analysis: Mapping[str, object], reference: Mapping[str, object] | None = None
) -> None:
    if not isinstance(analysis, Mapping):
        raise ReferenceContractError("Analysis must be an object.")
    _reject_media_fields(analysis)
    if set(analysis) != ANALYSIS_KEYS:
        raise ReferenceContractError("Analysis has unknown or missing fields.")
    detached = _detached_json(analysis, "Analysis")
    if detached["schema_version"] != "s12-engine-sound-v12-analysis-1":
        raise ReferenceContractError("Analysis schema_version is invalid.")
    body = {key: detached[key] for key in detached if key != "analysis_sha256"}
    expected_hash = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    if detached["analysis_sha256"] != expected_hash:
        raise ReferenceContractError("Analysis hash does not match its dynamic metrics.")
    probe_target = {
        "schema_version": "s12-engine-sound-v12-acoustic-target-1",
        "vehicle_id": "analysis-validation-probe",
        "reference_id": "analysis-validation-probe",
        "reference_quality": "R1",
        "source_url_sha256": "0" * 64,
        "analysis_sha256": detached["analysis_sha256"],
        "reference_binding": detached["reference_binding"],
        "analysis_method": detached["analysis_method"],
        "derived_metrics": detached["derived_metrics"],
        "scope": {
            "synthetic": True,
            "uncalibrated": True,
            "offline": True,
            "oem_clone": False,
        },
    }
    _schema_validate(
        probe_target,
        "acoustic_target_v12.schema.json",
        "analysis schema",
    )
    metrics = detached["derived_metrics"]
    frames = metrics["order_map"]["frames"]
    if reference is None:
        raise ReferenceContractError(
            "Analysis validation requires the originating complete R1 manifest."
        )
    validated_reference = validate_reference(reference)
    expected_binding = _reference_binding(validated_reference)
    if canonical_json(detached["reference_binding"]) != canonical_json(expected_binding):
        raise ReferenceContractError("Analysis binding does not match the complete R1 manifest.")
    binding_clip = _require_mapping(validated_reference, "clip_window")
    expected_start = float(binding_clip["start_s"])
    expected_end = float(binding_clip["end_s"])
    previous_end = expected_start
    previous_center = -math.inf
    for frame in frames:
        start_s = float(frame["start_time_s"])
        end_s = float(frame["end_time_s"])
        center_s = float(frame["center_time_s"])
        if not math.isclose(
            start_s, previous_end, rel_tol=0.0, abs_tol=WINDOW_TOLERANCE
        ):
            raise ReferenceContractError(
                "Dynamic order-map frames must cover the clip without gap or overlap."
            )
        if not (
            start_s <= center_s <= end_s
        ):
            raise ReferenceContractError("Dynamic order-map frame times are invalid.")
        if end_s <= start_s:
            raise ReferenceContractError("Dynamic order-map frame duration is invalid.")
        if center_s <= previous_center:
            raise ReferenceContractError("Dynamic order-map frame times must increase.")
        previous_center = center_s
        previous_end = end_s
    if not math.isclose(
        previous_end, expected_end, rel_tol=0.0, abs_tol=WINDOW_TOLERANCE
    ):
        raise ReferenceContractError(
            "Dynamic order-map frames must cover the exact reference clip."
        )

    amplitude_matrix = np.asarray(
        [frame["amplitudes"] for frame in frames], dtype=np.float64
    )
    phase_matrix = np.asarray(
        [frame["phases_rad"] for frame in frames], dtype=np.float64
    )
    expected_amplitudes = np.sqrt(np.mean(amplitude_matrix**2, axis=0))
    expected_phases = np.angle(
        np.mean(amplitude_matrix * np.exp(1j * phase_matrix), axis=0)
    )
    if not np.allclose(
        metrics["order_amplitudes"],
        expected_amplitudes,
        rtol=METRIC_TOLERANCE,
        atol=METRIC_TOLERANCE,
    ):
        raise ReferenceContractError(
            "Global order amplitudes do not aggregate the dynamic frames."
        )
    phase_error = np.angle(
        np.exp(1j * (np.asarray(metrics["order_phases_rad"]) - expected_phases))
    )
    if not np.allclose(
        phase_error, 0.0, rtol=0.0, atol=PHASE_TOLERANCE_RAD
    ):
        raise ReferenceContractError(
            "Global order phases do not aggregate the dynamic frames."
        )

    band_ratios = np.asarray(metrics["band_energy_ratios"], dtype=np.float64)
    ratio_sum = float(np.sum(band_ratios))
    if not (
        math.isclose(ratio_sum, 0.0, abs_tol=METRIC_TOLERANCE)
        or math.isclose(ratio_sum, 1.0, abs_tol=METRIC_TOLERANCE)
    ):
        raise ReferenceContractError("Band energy ratios must be normalized.")

    formants = [float(value) for value in metrics["formants_hz"]]
    minimum_spacing = float(
        detached["analysis_method"]["formant_min_peak_spacing_hz"]
    )
    if any(
        right - left < minimum_spacing - METRIC_TOLERANCE
        for left, right in zip(formants, formants[1:])
    ):
        raise ReferenceContractError(
            "Formants must be ascending with the declared minimum spacing."
        )
    clip_duration_s = expected_end - expected_start
    _validate_event_statistics(metrics["shift_statistics"], "shift", clip_duration_s)
    _validate_event_statistics(metrics["afterfire_statistics"], "afterfire", clip_duration_s)


def _validate_event_statistics(
    statistics: Mapping[str, object], label: str, clip_duration_s: float
) -> None:
    clusters = statistics["clusters"]
    cluster_count = len(clusters)
    if int(statistics["cluster_count"]) != cluster_count:
        raise ReferenceContractError(f"{label} cluster count is inconsistent.")
    cluster_ids = [str(cluster["cluster_id"]) for cluster in clusters]
    if len(set(cluster_ids)) != len(cluster_ids):
        raise ReferenceContractError(f"{label} cluster identifiers must be unique.")

    event_count = sum(int(cluster["event_count"]) for cluster in clusters)
    if int(statistics["event_count"]) != event_count:
        raise ReferenceContractError(f"{label} event count is inconsistent.")
    total_energy = sum(float(cluster["total_energy"]) for cluster in clusters)
    if not math.isclose(
        float(statistics["total_energy"]),
        total_energy,
        rel_tol=METRIC_TOLERANCE,
        abs_tol=METRIC_TOLERANCE,
    ):
        raise ReferenceContractError(f"{label} cluster energy is inconsistent.")

    for cluster in clusters:
        count = int(cluster["event_count"])
        decay = float(cluster["energy_decay_ratio"])
        tail = float(cluster["tail_duration_s"])
        start = float(cluster["start_delay_s"])
        if start < 0 or tail < 0 or start + tail > clip_duration_s + WINDOW_TOLERANCE:
            raise ReferenceContractError(f"{label} cluster must remain inside the reference clip.")
        if count == 1 and (
            not math.isclose(decay, 0.0, abs_tol=METRIC_TOLERANCE)
            or not math.isclose(tail, 0.0, abs_tol=METRIC_TOLERANCE)
        ):
            raise ReferenceContractError(
                f"{label} single-event cluster statistics are inconsistent."
            )

    if not clusters:
        for key in (
            "first_event_delay_s",
            "total_energy",
            "energy_decay_ratio",
            "tail_duration_s",
        ):
            if not math.isclose(
                float(statistics[key]), 0.0, abs_tol=METRIC_TOLERANCE
            ):
                raise ReferenceContractError(f"{label} empty statistics are inconsistent.")
        return

    first_delay = min(float(cluster["start_delay_s"]) for cluster in clusters)
    final_delay = max(
        float(cluster["start_delay_s"]) + float(cluster["tail_duration_s"])
        for cluster in clusters
    )
    if not math.isclose(
        float(statistics["first_event_delay_s"]),
        first_delay,
        rel_tol=METRIC_TOLERANCE,
        abs_tol=METRIC_TOLERANCE,
    ):
        raise ReferenceContractError(f"{label} first-event delay is inconsistent.")
    if not math.isclose(
        float(statistics["tail_duration_s"]),
        final_delay - first_delay,
        rel_tol=METRIC_TOLERANCE,
        abs_tol=METRIC_TOLERANCE,
    ):
        raise ReferenceContractError(f"{label} tail duration is inconsistent.")


@lru_cache(maxsize=2)
def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMA_ROOT / filename).read_text(encoding="utf-8"))


def _schema_validate(value: object, filename: str, label: str) -> None:
    validator = jsonschema.Draft202012Validator(
        _load_schema(filename),
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path) or "<root>"
        raise ReferenceContractError(f"{label} violation at {path}: {first.message}")


def _require_mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    result = value.get(key)
    if not isinstance(result, Mapping):
        raise ReferenceContractError(f"{key} must be an object.")
    return result


def _require_text(value: Mapping[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ReferenceContractError(f"{key} must be nonempty text.")
    return result


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise ReferenceContractError(f"{label} must be finite numeric data.")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ReferenceContractError(f"{label} must be finite numeric data.") from error
    if not math.isfinite(result):
        raise ReferenceContractError(f"{label} must be finite numeric data.")
    return result


def _validated_rpm_trace(
    samples: object, minimum_samples: int
) -> tuple[np.ndarray, np.ndarray]:
    if (
        not isinstance(samples, Sequence)
        or isinstance(samples, (str, bytes))
        or len(samples) < minimum_samples
    ):
        raise ReferenceContractError(
            f"RPM evidence requires at least {minimum_samples} samples."
        )
    times: list[float] = []
    rpms: list[float] = []
    for sample in samples:
        if not isinstance(sample, Mapping) or set(sample) != {"time_s", "rpm"}:
            raise ReferenceContractError("RPM evidence samples have an invalid shape.")
        times.append(_finite_number(sample["time_s"], "RPM evidence time_s"))
        rpms.append(_finite_number(sample["rpm"], "RPM evidence rpm"))
    if times[0] < 0 or any(
        right <= left for left, right in zip(times, times[1:])
    ):
        raise ReferenceContractError("RPM evidence time_s must be strictly increasing.")
    if any(rpm <= 0 or rpm > 30000 for rpm in rpms):
        raise ReferenceContractError("RPM evidence values are outside the valid range.")
    return np.asarray(times), np.asarray(rpms)


def _mono_pcm(pcm: object) -> np.ndarray:
    try:
        values = np.asarray(pcm, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise ReferenceContractError(
            "PCM must be a finite vector or sample-by-channel matrix."
        ) from error
    if values.ndim == 2:
        values = np.mean(values, axis=1)
    if (
        values.ndim != 1
        or values.size == 0
        or not np.all(np.isfinite(values))
    ):
        raise ReferenceContractError(
            "PCM must be a finite vector or sample-by-channel matrix."
        )
    return values


def _reject_media_fields(value: object, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            allowed_policy_key = (
                (normalized == "raw_media_root" and path == ("research_boundary",))
                or (
                normalized == "source_url_sha256"
                and path in {(), ("source",), ("reference_binding",)}
            )
            or (
                normalized == "reference_manifest_sha256"
                and path == ("reference_binding",)
            )
            or (normalized == "analysis_sha256" and path == ())
                or (
                    normalized == "rpm_evidence_sha256"
                    and path == ("reference_binding",)
                )
            )
            if not allowed_policy_key and any(
                fragment in normalized for fragment in FORBIDDEN_MEDIA_FRAGMENTS
            ):
                raise ReferenceContractError(
                    f"Repository payload cannot contain media-bearing field: {key}"
                )
            if (
                ("sha256" in normalized or normalized.endswith("_hash"))
                and not allowed_policy_key
            ):
                raise ReferenceContractError(
                    f"Repository payload cannot contain raw content hash field: {key}"
                )
            _reject_media_fields(child, path + (normalized,))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            _reject_media_fields(child, path)
    elif isinstance(value, str):
        _reject_unsafe_string_value(value, path)


def _reject_unsafe_string_value(value: str, path: tuple[str, ...]) -> None:
    if path == ("research_boundary", "raw_media_root"):
        if value != RAW_MEDIA_ROOT:
            raise ReferenceContractError(
                "research_boundary.raw_media_root must use the declared external root."
            )
        return

    allowed_digest_paths = {
        ("source", "source_url_sha256"),
        ("source_url_sha256",),
        ("reference_binding", "source_url_sha256"),
        ("reference_binding", "reference_manifest_sha256"),
        ("reference_binding", "rpm_evidence_sha256"),
        ("analysis_sha256",),
    }
    stripped = value.strip()
    lowered = stripped.lower()
    if HEX_SHA256.fullmatch(stripped) and path not in allowed_digest_paths:
        raise ReferenceContractError(
            "Repository payload cannot contain an unapproved content hash value."
        )
    if lowered.startswith(("file:", "data:")):
        raise ReferenceContractError(
            "Repository payload cannot contain file or data URI values."
        )

    decoded = unquote(stripped)
    parsed = urlsplit(decoded)
    allowed_url_paths = {
        ("source", "url"),
        ("stock_evidence", "evidence_url"),
    }
    if path in allowed_url_paths and (
        parsed.scheme.lower() != "https" or not parsed.netloc
    ):
        raise ReferenceContractError(
            "Reference URLs must be absolute HTTPS URLs."
        )
    if parsed.scheme:
        if path not in allowed_url_paths:
            raise ReferenceContractError(
                "Repository payload cannot contain URI values outside declared reference URLs."
            )
        url_payload = f"{parsed.path}?{parsed.query}"
        if RAW_AUDIO_EXTENSION.search(url_payload):
            raise ReferenceContractError(
                "Repository payload cannot contain a raw media path or URL extension."
            )
        if ".." in parsed.path or ".." in parsed.query or "/cache/" in url_payload.lower():
            raise ReferenceContractError(
                "Repository payload cannot contain a cache location or path traversal."
            )
        return

    is_local_path = (
        bool(re.match(r"^[a-zA-Z]:[\\/]", decoded))
        or decoded.startswith(("\\\\", "/", "./", "../", ".\\", "..\\"))
        or "/" in decoded
        or "\\" in decoded
    )
    if is_local_path or RAW_AUDIO_EXTENSION.search(decoded):
        raise ReferenceContractError(
            "Repository payload cannot contain a filesystem or raw media path value."
        )


def _detached_json(value: object, label: str) -> dict:
    try:
        return json.loads(canonical_json(value))
    except (TypeError, ValueError) as error:
        raise ReferenceContractError(f"{label} must contain finite JSON data.") from error


def _round_tree(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _round_tree(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_round_tree(child) for child in value]
    if isinstance(value, tuple):
        return [_round_tree(child) for child in value]
    if isinstance(value, (float, np.floating)):
        result = float(value)
        if not math.isfinite(result):
            raise ReferenceContractError("Derived metrics must be finite.")
        return round(result, 12)
    if isinstance(value, np.integer):
        return int(value)
    return value
