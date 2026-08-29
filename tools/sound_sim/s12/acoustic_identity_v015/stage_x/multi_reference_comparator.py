"""Stage X multi-reference comparator.

Raw-dynamic metrics run on unaltered signals. Timbre metrics run on
RMS-matched signals. Every scenario is compared against its own bound
reference; order metrics are NOT_QUALIFIED without an RPM trace. Output is
a twelve-dimension relative table, never an OEM similarity percentage.
"""

from __future__ import annotations

from typing import Any

import numpy as np

COMPARATOR_SCHEMA = "s12.stage_x.multi_reference_comparison.v1"

FINE_BAND_EDGES_HZ = (20.0, 60.0, 120.0, 250.0, 400.0, 1000.0, 4000.0, 5500.0, 11000.0)
CANONICAL_BAND_EDGES_HZ = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))
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
    "idle_life": ("hot_idle",),
    "acceleration_continuity": ("full_pull",),
    "shift_transient": ("shift",),
    "afterfire_naturalness": ("lift", "afterfire"),
}


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """Collapse stereo/multi-channel PCM to mono for metric comparison."""
    array = np.asarray(audio, dtype=np.float64)
    if array.ndim == 1:
        return array
    if array.ndim == 2:
        return np.mean(array, axis=1)
    return array.reshape(array.shape[0], -1).mean(axis=1)


def loudness_match_rms(signal: np.ndarray, target_rms: float) -> np.ndarray:
    """Equal-power RMS match to a target; deterministic, gain-only."""
    rms = float(np.sqrt(np.mean(np.square(signal)))) if signal.size else 0.0
    if rms <= 1e-9 or target_rms <= 0.0:
        return signal.copy()
    return signal * (target_rms / rms)


def _band_powers(spectrum: np.ndarray, freqs: np.ndarray, edges: tuple[float, ...]) -> list[float]:
    result = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (freqs >= lo) & (freqs < hi)
        result.append(float(np.sum(spectrum[mask] ** 2)))
    total = float(np.sum(spectrum[(freqs >= edges[0]) & (freqs <= edges[-1])] ** 2)) + 1e-15
    return [value / total for value in result]


def _spectra(audio: np.ndarray, sample_rate: int, frame: int = 4096, hop: int = 1024) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(frame)
    count = max(2, 1 + (audio.size - frame) // hop)
    spectra = np.stack([np.abs(np.fft.rfft(audio[i * hop : i * hop + frame] * window)) for i in range(count)])
    freqs = np.fft.rfftfreq(frame, 1.0 / sample_rate)
    return spectra, freqs


def raw_dynamic_metrics(audio: np.ndarray, sample_rate: int) -> dict[str, float]:
    """Level and impact metrics on the unaltered signal."""
    audio = _to_mono(audio)
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    frame = 2048
    energies = np.array([float(np.mean(np.square(audio[i : i + frame]))) for i in range(0, max(audio.size - frame, 1), frame)])
    if energies.size:
        quiet = float(np.percentile(energies, 10))
        loud = float(np.percentile(energies, 95))
        dynamic_range_db = 10.0 * np.log10(max(loud, 1e-12) / max(quiet, 1e-12))
    else:
        dynamic_range_db = 0.0
    threshold = peak * 0.25 if peak > 0 else 1.0
    crossings = np.flatnonzero((np.abs(audio[:-1]) < threshold) & (np.abs(audio[1:]) >= threshold))
    duration_s = max(audio.size / sample_rate, 1e-9)
    return {
        "rms_dbfs": 20.0 * np.log10(max(rms, 1e-9)),
        "peak_dbfs": 20.0 * np.log10(max(peak, 1e-9)),
        "crest_db": 20.0 * np.log10(max(peak, 1e-9) / max(rms, 1e-9)),
        "dynamic_range_db": float(dynamic_range_db),
        "transient_event_density_per_s": float(crossings.size / duration_s),
        "note": "rms_dbfs is an uncalibrated LUFS proxy; no absolute loudness claim",
    }


def timbre_metrics(audio: np.ndarray, sample_rate: int) -> dict[str, Any]:
    """Timbre metrics on the RMS-matched signal (match before calling)."""
    audio = _to_mono(audio)
    spectra, freqs = _spectra(audio, sample_rate)
    mean_spectrum = np.mean(spectra, axis=0)
    fine_shares = _band_powers(mean_spectrum, freqs, FINE_BAND_EDGES_HZ)
    canonical_shares = _band_powers(mean_spectrum, freqs, tuple(edge for pair in CANONICAL_BAND_EDGES_HZ for edge in pair))
    total_power = float(np.sum(mean_spectrum**2)) + 1e-15
    centroid = float(np.sum(freqs * mean_spectrum**2) / total_power)
    frame_powers = np.mean(spectra**2, axis=1)
    flux = float(np.mean(np.abs(np.diff(frame_powers)) / (frame_powers[:-1] + 1e-15)))
    # roughness proxy: modulation energy of band envelopes in 20-200 Hz
    envelopes = np.sqrt(np.mean(spectra**2, axis=0) + 1e-15)
    envelope_fft = np.abs(np.fft.rfft((envelopes - np.mean(envelopes)) * np.hanning(envelopes.size)))
    mod_freqs = np.fft.rfftfreq(envelopes.size, d=4096 / sample_rate)
    roughness = float(np.sum(envelope_fft[(mod_freqs >= 20) & (mod_freqs <= 200)] ** 2) / (np.sum(envelope_fft**2) + 1e-15))
    # sharpness proxy: weighted high-frequency energy
    high_mask = freqs > 2000.0
    sharpness = float(np.sum(mean_spectrum[high_mask] ** 2 * (freqs[high_mask] / 1000.0) ** 0.5) / (total_power * 4.0))
    # tonality proxy: spectral peak prominence
    if mean_spectrum.size > 3:
        peaks = mean_spectrum[1:-1]
        prominence = peaks - 0.5 * (mean_spectrum[:-2] + mean_spectrum[2:])
        tonality = float(np.mean(np.clip(prominence / (np.mean(mean_spectrum) + 1e-15), 0.0, 5.0)))
    else:
        tonality = 0.0
    return {
        "fine_band_shares": fine_shares,
        "canonical_band_shares": canonical_shares,
        "spectral_centroid_hz": centroid,
        "spectral_flux": flux,
        "roughness_proxy": roughness,
        "sharpness_proxy": sharpness,
        "tonality_proxy": tonality,
    }


def _relative_error(candidate: float, parent: float, reference: float) -> float:
    parent_err = abs(parent - reference)
    candidate_err = abs(candidate - reference)
    if parent_err <= 1e-12:
        return 0.0 if candidate_err <= 1e-12 else 1.0
    return (candidate_err - parent_err) / parent_err


def compare_case(reference: np.ndarray, parent: np.ndarray, candidate: np.ndarray, sample_rate: int, *, candidate_id: str) -> dict[str, Any]:
    """Compare one scenario triple against one bound reference."""
    reference = _to_mono(reference)
    parent = _to_mono(parent)
    candidate = _to_mono(candidate)
    ref_rms = float(np.sqrt(np.mean(np.square(reference)))) if reference.size else 0.0
    parent_matched = loudness_match_rms(parent, ref_rms)
    candidate_matched = loudness_match_rms(candidate, ref_rms)
    raw_ref = raw_dynamic_metrics(reference, sample_rate)
    raw_parent = raw_dynamic_metrics(parent, sample_rate)
    raw_candidate = raw_dynamic_metrics(candidate, sample_rate)
    timbre_ref = timbre_metrics(parent_matched if reference.size == 0 else reference, sample_rate) if reference.size else timbre_metrics(reference, sample_rate)
    timbre_parent = timbre_metrics(parent_matched, sample_rate)
    timbre_candidate = timbre_metrics(candidate_matched, sample_rate)
    metrics: dict[str, Any] = {}
    for name, ref_value, parent_value, candidate_value in (
        ("rms_dbfs", raw_ref["rms_dbfs"], raw_parent["rms_dbfs"], raw_candidate["rms_dbfs"]),
        ("crest_db", raw_ref["crest_db"], raw_parent["crest_db"], raw_candidate["crest_db"]),
        ("dynamic_range_db", raw_ref["dynamic_range_db"], raw_parent["dynamic_range_db"], raw_candidate["dynamic_range_db"]),
        ("transient_event_density_per_s", raw_ref["transient_event_density_per_s"], raw_parent["transient_event_density_per_s"], raw_candidate["transient_event_density_per_s"]),
        ("spectral_centroid_hz", timbre_ref["spectral_centroid_hz"], timbre_parent["spectral_centroid_hz"], timbre_candidate["spectral_centroid_hz"]),
        ("spectral_flux", timbre_ref["spectral_flux"], timbre_parent["spectral_flux"], timbre_candidate["spectral_flux"]),
        ("roughness_proxy", timbre_ref["roughness_proxy"], timbre_parent["roughness_proxy"], timbre_candidate["roughness_proxy"]),
        ("sharpness_proxy", timbre_ref["sharpness_proxy"], timbre_parent["sharpness_proxy"], timbre_candidate["sharpness_proxy"]),
        ("tonality_proxy", timbre_ref["tonality_proxy"], timbre_parent["tonality_proxy"], timbre_candidate["tonality_proxy"]),
    ) + tuple(
        (f"band_share_{int(lo)}_{int(hi)}", ref_share, parent_share, candidate_share)
        for (lo, hi), ref_share, parent_share, candidate_share in zip(
            tuple(zip(FINE_BAND_EDGES_HZ[:-1], FINE_BAND_EDGES_HZ[1:])),
            timbre_ref["fine_band_shares"],
            timbre_parent["fine_band_shares"],
            timbre_candidate["fine_band_shares"],
        )
    ):
        metrics[name] = {
            "reference": ref_value,
            "parent": parent_value,
            "candidate": candidate_value,
            "candidate_vs_parent_rel": _relative_error(candidate_value, parent_value, ref_value),
        }
    return {
        "candidate_id": candidate_id,
        "order_metrics": "NOT_QUALIFIED_NO_RPM_TRACE",
        "raw_signal": "unaltered",
        "timbre_signal": "rms_matched_to_reference",
        "metrics": metrics,
    }


_DIMENSION_MEMBERS = {
    "low_frequency_body": ("band_share_20_60", "band_share_60_120"),
    "120_400_pressure_attack": ("band_share_120_250", "band_share_250_400"),
    "mid_band_congestion": ("band_share_400_1000", "band_share_1000_4000"),
    "mechanical_texture": ("roughness_proxy", "spectral_flux"),
    "forced_induction_identity": ("tonality_proxy", "sharpness_proxy"),
    "synthetic_artifact": ("tonality_proxy", "sharpness_proxy"),
    "dynamic_range": ("dynamic_range_db", "crest_db"),
}


def aggregate_dimensions(case_comparison: dict[str, Any], scenario: str, render_seconds: float | None = None) -> dict[str, float]:
    """Map case metrics to the twelve contract dimensions (negative = closer to reference)."""
    metrics = case_comparison["metrics"]
    result: dict[str, float] = {}
    for dimension, members in _DIMENSION_MEMBERS.items():
        values = [metrics[name]["candidate_vs_parent_rel"] for name in members if name in metrics]
        result[dimension] = float(np.mean(values)) if values else 0.0
    for dimension, scenarios in SCENARIO_SCOPED.items():
        if scenario in scenarios:
            values = [metrics[name]["candidate_vs_parent_rel"] for name in ("transient_event_density_per_s", "crest_db") if name in metrics]
            result[dimension] = float(np.mean(values)) if values else 0.0
        else:
            result[dimension] = float("nan")
    result["runtime_cost"] = float("inf") if render_seconds is None else float(render_seconds)
    return result


def compare_multi_reference(
    scenario_comparisons: dict[str, list[dict[str, Any]]],
    *,
    candidate_id: str,
) -> dict[str, Any]:
    """Median dimension improvement across every bound reference case."""
    dimension_values: dict[str, list[float]] = {name: [] for name in DIMENSIONS}
    for scenario, cases in scenario_comparisons.items():
        for case in cases:
            for dimension, value in case["dimensions"].items():
                if np.isfinite(value) and dimension != "runtime_cost":
                    dimension_values[dimension].append(value)
    medians = {name: float(np.median(values)) if values else float("nan") for name, values in dimension_values.items()}
    finite = [value for name, value in medians.items() if name != "runtime_cost" and np.isfinite(value)]
    objective = float(np.mean(finite)) if finite else None
    return {
        "schema": COMPARATOR_SCHEMA,
        "candidate_id": candidate_id,
        "scenario_case_counts": {scenario: len(cases) for scenario, cases in scenario_comparisons.items()},
        "dimension_median_relative_error": medians,
        "multi_reference_median_objective": objective,
        "improvement_fraction": (-objective) if objective is not None else None,
        "interpretation": "negative relative error = candidate closer to reference than parent; improvement_fraction > 0 = candidate better",
        "forbidden_outputs": ["oem_similarity_percentage", "human_pass", "approved_profile"],
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }


__all__ = [
    "CANONICAL_BAND_EDGES_HZ",
    "DIMENSIONS",
    "FINE_BAND_EDGES_HZ",
    "COMPARATOR_SCHEMA",
    "aggregate_dimensions",
    "compare_case",
    "compare_multi_reference",
    "loudness_match_rms",
    "raw_dynamic_metrics",
    "timbre_metrics",
]
