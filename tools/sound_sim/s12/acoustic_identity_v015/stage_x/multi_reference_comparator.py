"""Stage X/Y scenario-bound multi-reference comparator.

Version 2 corrects three issues in the original proxy implementation:

* canonical band powers are evaluated from explicit ``(low, high)`` pairs;
* spectral flux compares normalized spectra bin by bin over time;
* roughness is derived from time-varying band envelopes rather than from a
  Fourier transform of the frequency axis.

The comparator remains an engineering diagnostic. It does not output an OEM
similarity percentage and order-domain metrics remain unavailable without a
synchronised RPM trace.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np

COMPARATOR_SCHEMA = "s12.stage_y.multi_reference_comparison.v2"

FINE_BAND_EDGES_HZ = (20.0, 60.0, 120.0, 250.0, 400.0, 1000.0, 4000.0, 5500.0, 11000.0)
CANONICAL_BAND_EDGES_HZ = (
    (20.0, 250.0),
    (250.0, 1000.0),
    (1000.0, 4000.0),
    (4000.0, 12000.0),
)
DIMENSIONS = (
    "low_frequency_body",
    "120_400_pressure_attack",
    "mid_band_congestion",
    "mechanical_texture",
    "forced_induction_identity",
    "idle_life",
    "acceleration_continuity",
    "shift_transient",
    "afterfire_naturalness",
    "synthetic_artifact",
    "dynamic_range",
    "runtime_cost",
)
SCENARIO_SCOPED = {
    "idle_life": ("hot_idle", "idle_return"),
    "acceleration_continuity": ("tip_in", "full_pull"),
    "shift_transient": ("shift",),
    "afterfire_naturalness": ("lift", "afterfire"),
}

_EPS = 1.0e-15


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """Collapse a finite PCM array to one mono vector."""
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        result = array
    elif array.ndim == 2:
        result = np.mean(array, axis=1)
    else:
        result = array.reshape(array.shape[0], -1).mean(axis=1)
    if not np.all(np.isfinite(result)):
        raise ValueError("audio must contain finite PCM")
    return result


def loudness_match_rms(signal: np.ndarray, target_rms: float) -> np.ndarray:
    """Apply one deterministic gain so timbre can be compared at equal RMS."""
    values = np.asarray(signal, dtype=np.float64)
    rms = float(np.sqrt(np.mean(np.square(values)))) if values.size else 0.0
    if rms <= 1.0e-12 or target_rms <= 0.0:
        return values.copy()
    return values * (float(target_rms) / rms)


def _frame_audio(audio: np.ndarray, frame: int, hop: int) -> np.ndarray:
    """Return zero-padded overlapping frames with at least two rows."""
    if frame <= 0 or hop <= 0:
        raise ValueError("frame and hop must be positive")
    values = _to_mono(audio)
    minimum = frame + hop
    if values.size < minimum:
        values = np.pad(values, (0, minimum - values.size))
    count = 1 + (values.size - frame) // hop
    indices = np.arange(frame)[None, :] + hop * np.arange(count)[:, None]
    return values[indices]


def _spectra(
    audio: np.ndarray,
    sample_rate: int,
    *,
    frame: int = 2048,
    hop: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    """Return magnitude spectra indexed as ``[time, frequency]``."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    framed = _frame_audio(audio, frame, hop)
    window = np.hanning(frame)
    spectra = np.abs(np.fft.rfft(framed * window[None, :], axis=1))
    freqs = np.fft.rfftfreq(frame, 1.0 / sample_rate)
    return spectra, freqs


def _band_shares_from_pairs(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    pairs: Iterable[tuple[float, float]],
) -> list[float]:
    """Calculate non-overlapping power shares for explicit frequency pairs."""
    power = np.square(np.asarray(spectrum, dtype=np.float64))
    pairs_tuple = tuple((float(lo), float(hi)) for lo, hi in pairs)
    if any(hi <= lo for lo, hi in pairs_tuple):
        raise ValueError("band pairs must have positive width")
    overall_lo = min(lo for lo, _ in pairs_tuple)
    overall_hi = max(hi for _, hi in pairs_tuple)
    total_mask = (freqs >= overall_lo) & (freqs < overall_hi)
    total = float(np.sum(power[total_mask])) + _EPS
    return [
        float(np.sum(power[(freqs >= lo) & (freqs < hi)])) / total
        for lo, hi in pairs_tuple
    ]


def _fine_pairs() -> tuple[tuple[float, float], ...]:
    return tuple(zip(FINE_BAND_EDGES_HZ[:-1], FINE_BAND_EDGES_HZ[1:]))


def _normalized_spectral_flux(spectra: np.ndarray) -> float:
    """Positive spectral flux over L1-normalized magnitude spectra."""
    if spectra.shape[0] < 2:
        return 0.0
    normalized = spectra / (np.sum(spectra, axis=1, keepdims=True) + _EPS)
    positive = np.maximum(np.diff(normalized, axis=0), 0.0)
    return float(np.mean(np.sqrt(np.sum(np.square(positive), axis=1))))


def _time_envelope_roughness(
    spectra: np.ndarray,
    freqs: np.ndarray,
    sample_rate: int,
    hop: int,
) -> float:
    """Modulation-energy roughness proxy on time-varying acoustic bands."""
    if spectra.shape[0] < 4:
        return 0.0
    envelope_pairs = (
        (20.0, 120.0),
        (120.0, 250.0),
        (250.0, 400.0),
        (400.0, 1000.0),
        (1000.0, 4000.0),
        (4000.0, min(11000.0, sample_rate * 0.49)),
    )
    frame_rate = sample_rate / float(hop)
    values: list[float] = []
    power = np.square(spectra)
    for lo, hi in envelope_pairs:
        mask = (freqs >= lo) & (freqs < hi)
        if not np.any(mask):
            continue
        envelope = np.sqrt(np.mean(power[:, mask], axis=1) + _EPS)
        window_len = max(3, int(round(frame_rate / 8.0)))
        kernel = np.ones(window_len, dtype=np.float64) / window_len
        trend = np.convolve(envelope, kernel, mode="same")
        mod_signal = envelope - trend
        if float(np.std(mod_signal)) <= 1.0e-12:
            values.append(0.0)
            continue
        modulation = np.abs(np.fft.rfft(mod_signal * np.hanning(mod_signal.size)))
        mod_freqs = np.fft.rfftfreq(mod_signal.size, d=1.0 / frame_rate)
        target = (mod_freqs >= 15.0) & (mod_freqs <= min(80.0, frame_rate * 0.45))
        numerator = float(np.sum(np.square(modulation[target])))
        denominator = float(np.sum(np.square(modulation))) + _EPS
        values.append(numerator / denominator)
    return float(np.mean(values)) if values else 0.0


def _tonality_and_persistence(
    spectra: np.ndarray,
    freqs: np.ndarray,
) -> tuple[float, float]:
    """Return spectral peak prominence and persistent narrow-band tone ratio."""
    region = (freqs >= 150.0) & (freqs <= 8000.0)
    selected = spectra[:, region]
    if selected.shape[1] < 5:
        return 0.0, 0.0
    padded = np.pad(selected, ((0, 0), (2, 2)), mode="edge")
    local = (
        padded[:, 0:-4]
        + padded[:, 1:-3]
        + padded[:, 3:-1]
        + padded[:, 4:]
    ) / 4.0
    prominence = np.maximum(selected - local, 0.0) / (
        np.mean(selected, axis=1, keepdims=True) + _EPS
    )
    tonality = float(np.mean(np.clip(prominence, 0.0, 8.0)))

    peak_index = np.argmax(prominence, axis=1)
    peak_strength = np.max(prominence, axis=1)
    strong = peak_strength >= 1.5
    if not np.any(strong):
        return tonality, 0.0
    histogram = np.bincount(peak_index[strong], minlength=selected.shape[1])
    persistence = float(np.max(histogram)) / float(selected.shape[0])
    return tonality, persistence


def raw_dynamic_metrics(audio: np.ndarray, sample_rate: int) -> dict[str, float | str]:
    """Level, crest, envelope range, and impact metrics on unaltered PCM."""
    values = _to_mono(audio)
    rms = float(np.sqrt(np.mean(np.square(values)))) if values.size else 0.0
    peak = float(np.max(np.abs(values))) if values.size else 0.0

    frame = max(256, int(round(sample_rate * 0.020)))
    hop = max(128, frame // 2)
    framed = _frame_audio(values, frame, hop)
    frame_rms = np.sqrt(np.mean(np.square(framed), axis=1) + _EPS)
    quiet = float(np.percentile(frame_rms, 10))
    loud = float(np.percentile(frame_rms, 95))
    dynamic_range_db = 20.0 * np.log10(max(loud, 1.0e-12) / max(quiet, 1.0e-12))

    envelope = np.max(np.abs(framed), axis=1)
    median = float(np.median(envelope))
    mad = float(np.median(np.abs(envelope - median))) + 1.0e-12
    threshold = median + 6.0 * mad
    active = envelope > threshold
    onsets = int(np.count_nonzero(active & ~np.r_[False, active[:-1]]))
    duration_s = max(values.size / float(sample_rate), 1.0e-9)

    return {
        "rms_dbfs": 20.0 * np.log10(max(rms, 1.0e-9)),
        "peak_dbfs": 20.0 * np.log10(max(peak, 1.0e-9)),
        "crest_db": 20.0 * np.log10(max(peak, 1.0e-9) / max(rms, 1.0e-9)),
        "dynamic_range_db": float(dynamic_range_db),
        "transient_event_density_per_s": float(onsets / duration_s),
        "note": "rms_dbfs is an uncalibrated digital-domain level; no SPL claim",
    }


def timbre_metrics(audio: np.ndarray, sample_rate: int) -> dict[str, Any]:
    """Corrected timbre and modulation proxies on a finite mono signal."""
    values = _to_mono(audio)
    frame = 2048
    hop = 256
    spectra, freqs = _spectra(values, sample_rate, frame=frame, hop=hop)
    mean_spectrum = np.mean(spectra, axis=0)
    fine_shares = _band_shares_from_pairs(mean_spectrum, freqs, _fine_pairs())
    canonical_shares = _band_shares_from_pairs(
        mean_spectrum,
        freqs,
        CANONICAL_BAND_EDGES_HZ,
    )

    power = np.square(mean_spectrum)
    total_power = float(np.sum(power)) + _EPS
    centroid = float(np.sum(freqs * power) / total_power)
    flux = _normalized_spectral_flux(spectra)
    roughness = _time_envelope_roughness(spectra, freqs, sample_rate, hop)

    high_mask = freqs >= 2000.0
    sharpness = float(
        np.sum(power[high_mask] * np.sqrt(np.maximum(freqs[high_mask], 1.0) / 1000.0))
        / (total_power * 4.0)
    )
    tonality, persistent_tone = _tonality_and_persistence(spectra, freqs)

    return {
        "metric_version": "s12.stage_y.timbre_metrics.v2",
        "fine_band_shares": fine_shares,
        "canonical_band_shares": canonical_shares,
        "spectral_centroid_hz": centroid,
        "spectral_flux": flux,
        "roughness_proxy": roughness,
        "sharpness_proxy": sharpness,
        "tonality_proxy": tonality,
        "persistent_tone_ratio": persistent_tone,
        "narrowband_whine_proxy": tonality * persistent_tone,
    }


def _relative_error(candidate: float, parent: float, reference: float) -> float:
    """Relative change in absolute error with a reference-scaled floor."""
    parent_err = abs(float(parent) - float(reference))
    candidate_err = abs(float(candidate) - float(reference))
    scale_floor = max(0.02 * abs(float(reference)), 1.0e-9)
    return (candidate_err - parent_err) / max(parent_err, scale_floor)


def compare_case(
    reference: np.ndarray,
    parent: np.ndarray,
    candidate: np.ndarray,
    sample_rate: int,
    *,
    candidate_id: str,
) -> dict[str, Any]:
    """Compare one scenario triple against one bound reference."""
    reference_mono = _to_mono(reference)
    parent_mono = _to_mono(parent)
    candidate_mono = _to_mono(candidate)
    length = min(reference_mono.size, parent_mono.size, candidate_mono.size)
    if length <= 0:
        raise ValueError("reference, parent and candidate must be non-empty")
    reference_mono = reference_mono[:length]
    parent_mono = parent_mono[:length]
    candidate_mono = candidate_mono[:length]

    ref_rms = float(np.sqrt(np.mean(np.square(reference_mono))))
    parent_matched = loudness_match_rms(parent_mono, ref_rms)
    candidate_matched = loudness_match_rms(candidate_mono, ref_rms)

    raw_ref = raw_dynamic_metrics(reference_mono, sample_rate)
    raw_parent = raw_dynamic_metrics(parent_mono, sample_rate)
    raw_candidate = raw_dynamic_metrics(candidate_mono, sample_rate)
    timbre_ref = timbre_metrics(reference_mono, sample_rate)
    timbre_parent = timbre_metrics(parent_matched, sample_rate)
    timbre_candidate = timbre_metrics(candidate_matched, sample_rate)

    metric_rows: list[tuple[str, float, float, float]] = [
        ("rms_dbfs", float(raw_ref["rms_dbfs"]), float(raw_parent["rms_dbfs"]), float(raw_candidate["rms_dbfs"])),
        ("crest_db", float(raw_ref["crest_db"]), float(raw_parent["crest_db"]), float(raw_candidate["crest_db"])),
        ("dynamic_range_db", float(raw_ref["dynamic_range_db"]), float(raw_parent["dynamic_range_db"]), float(raw_candidate["dynamic_range_db"])),
        ("transient_event_density_per_s", float(raw_ref["transient_event_density_per_s"]), float(raw_parent["transient_event_density_per_s"]), float(raw_candidate["transient_event_density_per_s"])),
    ]
    for name in (
        "spectral_centroid_hz",
        "spectral_flux",
        "roughness_proxy",
        "sharpness_proxy",
        "tonality_proxy",
        "persistent_tone_ratio",
        "narrowband_whine_proxy",
    ):
        metric_rows.append((name, float(timbre_ref[name]), float(timbre_parent[name]), float(timbre_candidate[name])))
    for (lo, hi), ref_share, parent_share, candidate_share in zip(
        _fine_pairs(),
        timbre_ref["fine_band_shares"],
        timbre_parent["fine_band_shares"],
        timbre_candidate["fine_band_shares"],
    ):
        metric_rows.append((f"band_share_{int(lo)}_{int(hi)}", float(ref_share), float(parent_share), float(candidate_share)))

    metrics = {
        name: {
            "reference": ref_value,
            "parent": parent_value,
            "candidate": candidate_value,
            "candidate_vs_parent_rel": _relative_error(candidate_value, parent_value, ref_value),
        }
        for name, ref_value, parent_value, candidate_value in metric_rows
    }
    return {
        "candidate_id": candidate_id,
        "metric_version": "s12.stage_y.comparator_metrics.v2",
        "order_metrics": "NOT_QUALIFIED_NO_RPM_TRACE",
        "raw_signal": "unaltered",
        "timbre_signal": "rms_matched_to_reference",
        "metrics": metrics,
    }


_DIMENSION_MEMBERS = {
    "low_frequency_body": ("band_share_20_60", "band_share_60_120"),
    "120_400_pressure_attack": ("band_share_120_250", "band_share_250_400", "transient_event_density_per_s"),
    "mid_band_congestion": ("band_share_400_1000", "band_share_1000_4000"),
    "mechanical_texture": ("roughness_proxy", "spectral_flux"),
    "forced_induction_identity": ("tonality_proxy", "sharpness_proxy", "persistent_tone_ratio"),
    "synthetic_artifact": ("narrowband_whine_proxy", "persistent_tone_ratio", "sharpness_proxy"),
    "dynamic_range": ("dynamic_range_db", "crest_db"),
}


def aggregate_dimensions(
    case_comparison: dict[str, Any],
    scenario: str,
    render_seconds: float | None = None,
) -> dict[str, float]:
    """Map case metrics to the twelve contract dimensions."""
    metrics = case_comparison["metrics"]
    result: dict[str, float] = {}
    for dimension, members in _DIMENSION_MEMBERS.items():
        values = [
            float(metrics[name]["candidate_vs_parent_rel"])
            for name in members
            if name in metrics and np.isfinite(metrics[name]["candidate_vs_parent_rel"])
        ]
        result[dimension] = float(np.median(values)) if values else float("nan")

    scenario_members = {
        "idle_life": ("roughness_proxy", "dynamic_range_db", "transient_event_density_per_s"),
        "acceleration_continuity": ("spectral_flux", "dynamic_range_db", "crest_db"),
        "shift_transient": ("transient_event_density_per_s", "crest_db"),
        "afterfire_naturalness": ("transient_event_density_per_s", "crest_db", "spectral_flux"),
    }
    for dimension, scenarios in SCENARIO_SCOPED.items():
        if scenario not in scenarios:
            result[dimension] = float("nan")
            continue
        values = [
            float(metrics[name]["candidate_vs_parent_rel"])
            for name in scenario_members[dimension]
            if name in metrics and np.isfinite(metrics[name]["candidate_vs_parent_rel"])
        ]
        result[dimension] = float(np.median(values)) if values else float("nan")
    result["runtime_cost"] = float("nan") if render_seconds is None else float(render_seconds)
    return result


def compare_multi_reference(
    scenario_comparisons: dict[str, list[dict[str, Any]]],
    *,
    candidate_id: str,
) -> dict[str, Any]:
    """Aggregate independent case dimensions with robust medians."""
    dimension_values: dict[str, list[float]] = {name: [] for name in DIMENSIONS}
    case_count = 0
    for cases in scenario_comparisons.values():
        for case in cases:
            case_count += 1
            for dimension, value in case["dimensions"].items():
                if dimension in dimension_values and np.isfinite(value):
                    dimension_values[dimension].append(float(value))

    medians = {
        name: float(np.median(values)) if values else float("nan")
        for name, values in dimension_values.items()
    }
    finite = [
        float(np.clip(value, -2.0, 2.0))
        for name, value in medians.items()
        if name != "runtime_cost" and np.isfinite(value)
    ]
    objective = float(np.median(finite)) if finite else None
    return {
        "schema": COMPARATOR_SCHEMA,
        "candidate_id": candidate_id,
        "metric_version": "s12.stage_y.comparator_metrics.v2",
        "scenario_case_counts": {scenario: len(cases) for scenario, cases in scenario_comparisons.items()},
        "case_count": case_count,
        "dimension_median_relative_error": medians,
        "multi_reference_median_objective": objective,
        "improvement_fraction": (-objective) if objective is not None else None,
        "interpretation": "negative relative error = candidate closer to reference than parent; improvement_fraction > 0 = candidate better",
        "forbidden_outputs": ["oem_similarity_percentage", "human_pass", "approved_profile"],
        "scope": "engineering diagnostic only; synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }


__all__ = [
    "CANONICAL_BAND_EDGES_HZ",
    "COMPARATOR_SCHEMA",
    "DIMENSIONS",
    "FINE_BAND_EDGES_HZ",
    "aggregate_dimensions",
    "compare_case",
    "compare_multi_reference",
    "loudness_match_rms",
    "raw_dynamic_metrics",
    "timbre_metrics",
]
