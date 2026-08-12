"""Static named-stem peak budgeting for Stage-L Hellcat transients."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from .candidate_profiles import StageLCandidateProfile


NAMED_PEAK_STEMS = (
    "afterfire", "hellcat_shift_reengagement", "hellcat_sc_drive_transient",
    "hellcat_tip_in_blowdown",
)


def apply_hellcat_named_peak_budget(
    render: SourceRender,
    trace: VehicleStateTrace,
    candidate: StageLCandidateProfile,
    sample_rate_hz: int = 48_000,
) -> SourceRender:
    """Attenuate isolated peaks by one fixed factor per named transient stem."""
    render.validate()
    trace.validate()
    if not isinstance(candidate, StageLCandidateProfile) or candidate.vehicle_id != "hellcat":
        raise ValueError("candidate must be a validated Stage-L Hellcat profile")
    if not isinstance(sample_rate_hz, int) or isinstance(sample_rate_hz, bool) or sample_rate_hz < 8_000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    missing = sorted(set(NAMED_PEAK_STEMS) - set(render.stems))
    if missing:
        raise ValueError(f"named peak-budget stems are missing: {missing}")

    stems = {name: np.asarray(stem, dtype=np.float64).copy() for name, stem in render.stems.items()}
    pressure = np.asarray(render.pressure, dtype=np.float64).copy()
    gains: dict[str, float] = {}
    evidence: dict[str, dict[str, object]] = {}
    for name in NAMED_PEAK_STEMS:
        old = stems[name]
        peak = float(np.max(np.abs(old)))
        rms = float(np.sqrt(np.mean(np.square(old))))
        target = max(0.25 * peak, 8.0 * rms)
        gain = 1.0 if peak <= 1.0e-30 else min(1.0, target / peak)
        new = old * gain
        stems[name] = new
        pressure += new - old
        gains[name] = gain
        evidence[name] = {
            "before_peak": peak,
            "after_peak": float(np.max(np.abs(new))),
            "before_rms": rms,
            "after_rms": float(np.sqrt(np.mean(np.square(new)))),
            "gain": gain,
            "status": (
                "INACTIVE_ZERO" if peak <= 1.0e-30
                else "REDUCED_ISOLATED_PEAK" if gain < 1.0
                else "HEADROOM_ALREADY_SATISFIED"
            ),
        }
    diagnostics = dict(render.diagnostics)
    diagnostics.update({
        "peak_budget_model": "one_static_gain_per_named_transient_stem",
        "peak_budget_named_stems": NAMED_PEAK_STEMS,
        "peak_budget_stem_gains": gains,
        "peak_budget_stem_evidence": evidence,
        "whole_pressure_processed": False,
        "compressor_or_limiter_used": False,
        "pre_ptr_named_peak_budget": True,
    })
    return replace(render, pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def make_stage_l_comfort_copy(
    audio: np.ndarray,
    *,
    requested_gain_db: float = 1.9382,
    peak_limit_dbfs: float = -1.5,
) -> tuple[np.ndarray, dict[str, object]]:
    """Apply one peak-safe static review-copy gain without altering formal PCM."""
    value = np.asarray(audio, dtype=np.float64)
    if value.ndim != 2 or value.shape[1] != 2 or not np.all(np.isfinite(value)):
        raise ValueError("audio must be finite stereo")
    if not np.isfinite(requested_gain_db) or requested_gain_db < 0.0 or requested_gain_db > 1.9382:
        raise ValueError("requested_gain_db must be finite and in [0, 1.9382]")
    if not np.isfinite(peak_limit_dbfs) or peak_limit_dbfs >= 0.0:
        raise ValueError("peak_limit_dbfs must be finite and < 0")
    requested = float(10.0 ** (requested_gain_db / 20.0))
    peak = float(np.max(np.abs(value)))
    peak_limit = float(10.0 ** (peak_limit_dbfs / 20.0))
    headroom_gain = requested if peak <= 1.0e-30 else peak_limit / peak
    actual = min(requested, headroom_gain)
    output = value * actual
    return output, {
        "requested_gain_db": float(requested_gain_db),
        "actual_gain_db": float(20.0 * np.log10(max(actual, 1.0e-30))),
        "headroom_limited": bool(actual < requested - 1.0e-12),
        "peak_limit_dbfs": float(peak_limit_dbfs),
        "static_whole_copy_gain_only": True,
        "compressor_or_limiter_used": False,
    }


def make_stage_l_formal_copy(audio: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    """Return an unprocessed formal-comparison copy with explicit policy evidence."""
    value = np.asarray(audio, dtype=np.float64)
    if value.ndim != 2 or value.shape[1] != 2 or not np.all(np.isfinite(value)):
        raise ValueError("audio must be finite stereo")
    return value.copy(), {
        "gain_db": 0.0,
        "static_whole_copy_gain_only": True,
        "compressor_or_limiter_used": False,
        "per_section_agc_used": False,
    }


__all__ = (
    "NAMED_PEAK_STEMS", "apply_hellcat_named_peak_budget", "make_stage_l_comfort_copy",
    "make_stage_l_formal_copy",
)
