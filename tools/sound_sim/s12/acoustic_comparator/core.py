"""Fail-closed, dependency-light acoustic comparison core.

This module provides relative digital-domain evidence. It never converts a
synthetic parent/candidate comparison into a real-recording identity result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .alignment import bounded_cross_correlation
from .order import order_metrics, rpm_compatible
from .preprocessing import to_mono_dc_free
from .psychoacoustics import proxy_metrics
from .spectral import BANDS, BAND_NAMES, band_comparison, normalized_log_spectral_distance, spectrum_features
from .transients import event_metrics, require_trace_gated_events


@dataclass(frozen=True)
class ComparisonCase:
    vehicle_id: str
    scenario: str
    reference_id: str | None
    candidate_id: str
    sample_rate_hz: int
    reference_rpm: tuple[float, float]
    candidate_rpm: tuple[float, float]
    reference_load: tuple[float, float]
    candidate_load: tuple[float, float]
    analysis_domain: str
    reference_kind: Literal["external_recording", "synthetic_parent"] = "external_recording"


def _base_result(case: ComparisonCase, candidate: np.ndarray, eligible_event_mask: np.ndarray | None) -> dict[str, object]:
    candidate_features, _, _ = spectrum_features(candidate, case.sample_rate_hz)
    events = event_metrics(candidate, eligible_event_mask)
    return {
        "case": case.__dict__,
        "preprocessing": {
            "analysis_signal": "unaltered_analysis_signal",
            "operations": ["channel_fold_down", "dc_removal"],
            "loudness_matched_audition_signal_used": False,
        },
        "order": {
            "rpm_compatible": rpm_compatible(case.reference_rpm, case.candidate_rpm),
            "candidate": order_metrics(candidate, case.sample_rate_hz, case.candidate_rpm),
        },
        "candidate_features": candidate_features,
        "events": {
            "candidate_event_count": events["event_count"],
            "wrong_condition_event_count": events["wrong_condition_event_count"],
        },
    }


def compare_signals(
    reference: np.ndarray | None,
    candidate: np.ndarray,
    case: ComparisonCase,
    *,
    candidate_scenario: str | None = None,
    candidate_domain: str = "unaltered_analysis_signal",
    eligible_event_mask: np.ndarray | None = None,
) -> dict[str, object]:
    """Compare a trace/scenario-bound pair, preserving reference uncertainty.

    ``reference_kind='synthetic_parent'`` permits an internal regression delta
    but explicitly marks real-recording identity evaluation unavailable.
    """

    if case.analysis_domain != "unaltered_analysis_signal" or candidate_domain != "unaltered_analysis_signal":
        raise ValueError("review-gain copy is forbidden for raw analysis")
    if candidate_scenario is not None and candidate_scenario != case.scenario:
        raise ValueError("scenario mismatch")
    candidate_mono = to_mono_dc_free(candidate)
    if eligible_event_mask is not None:
        require_trace_gated_events(candidate_mono, eligible_event_mask)
    result = _base_result(case, candidate_mono, eligible_event_mask)
    if reference is None or case.reference_id is None:
        result.update(
            {
                "uncertainty": {
                    "reference_missing": True,
                    "external_reference_missing": True,
                    "digital_domain_relative_only": True,
                    "identity_score_available": False,
                },
                "spectral": {"log_distance": None},
                "bands": {},
            }
        )
        return result

    reference_mono = to_mono_dc_free(reference)
    candidate_aligned, shift = bounded_cross_correlation(reference_mono, candidate_mono)
    reference_mono = reference_mono[: candidate_aligned.size]
    reference_features, reference_spectrum, _ = spectrum_features(reference_mono, case.sample_rate_hz)
    candidate_features, candidate_spectrum, _ = spectrum_features(candidate_aligned, case.sample_rate_hz)
    reference_psycho = proxy_metrics(reference_mono, case.sample_rate_hz, reference_features["centroid_hz"])
    candidate_psycho = proxy_metrics(candidate_aligned, case.sample_rate_hz, candidate_features["centroid_hz"])
    external = case.reference_kind == "external_recording"
    result.update(
        {
            "uncertainty": {
                "reference_missing": False,
                "external_reference_missing": not external,
                "digital_domain_relative_only": not external,
                "identity_score_available": external,
                "reference_kind": case.reference_kind,
            },
            "alignment": {"method": "bounded_cross_correlation", "applied_shift_samples": shift, "max_shift_samples": 4096},
            "spectral": {
                "log_distance": normalized_log_spectral_distance(reference_spectrum, candidate_spectrum),
                "centroid_delta_hz": candidate_features["centroid_hz"] - reference_features["centroid_hz"],
                "rolloff_delta_hz": candidate_features["rolloff_hz"] - reference_features["rolloff_hz"],
                "contrast_delta_db": candidate_features["spectral_contrast_db"] - reference_features["spectral_contrast_db"],
                "tristimulus_delta": [
                    candidate_features["tristimulus_low"] - reference_features["tristimulus_low"],
                    candidate_features["tristimulus_mid"] - reference_features["tristimulus_mid"],
                    candidate_features["tristimulus_high"] - reference_features["tristimulus_high"],
                ],
                "harmonic_percussive_proxy": {
                    "reference_harmonic_share": order_metrics(reference_mono, case.sample_rate_hz, case.reference_rpm)["harmonic_energy_share"],
                    "candidate_harmonic_share": order_metrics(candidate_aligned, case.sample_rate_hz, case.candidate_rpm)["harmonic_energy_share"],
                    "percussive_proxy": candidate_psycho["crest_factor"] - reference_psycho["crest_factor"],
                },
            },
            "bands": band_comparison(reference_features, candidate_features),
            "loudness": {"delta_db": candidate_features["rms_db"] - reference_features["rms_db"]},
            "psychoacoustics": {
                "sharpness_proxy_delta": candidate_psycho["sharpness_proxy_hz"] - reference_psycho["sharpness_proxy_hz"],
                "roughness_proxy_delta": candidate_psycho["roughness_proxy"] - reference_psycho["roughness_proxy"],
                "fluctuation_proxy_delta": candidate_psycho["fluctuation_proxy"] - reference_psycho["fluctuation_proxy"],
            },
            "scenario_metrics": {
                "idle": "not_evaluated_without_idle_window",
                "acceleration": "not_evaluated_without_rpm_load_window",
                "shift": "not_evaluated_without_shift_window",
                "lift_afterfire": "not_evaluated_without_lift_window",
            },
        }
    )
    return result


__all__ = ["BANDS", "BAND_NAMES", "ComparisonCase", "compare_signals"]
