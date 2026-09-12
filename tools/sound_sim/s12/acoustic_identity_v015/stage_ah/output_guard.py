"""Versioned output-peak policies for Stage AH.

The linked soft ceiling is applied to float stereo immediately before the
renderer converts to int16.  It is deliberately separate from source
variants so C0 can measure output-policy changes independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


LEGACY_CLIP_V1 = "legacy_clip_v1"
LINKED_SOFT_CEILING_V1 = "linked_soft_ceiling_v1"
OUTPUT_GUARD_RECEIPT_SCHEMA = "s12.stage_ah.output_guard_receipt.v2"


@dataclass(frozen=True)
class GuardConfig:
    policy_id: str = LINKED_SOFT_CEILING_V1
    knee: float = 0.90
    ceiling: float = 0.94

    def validate(self) -> None:
        if self.policy_id != LINKED_SOFT_CEILING_V1:
            raise ValueError(f"unsupported output policy: {self.policy_id}")
        if not (np.isfinite(self.knee) and np.isfinite(self.ceiling)):
            raise ValueError("knee and ceiling must be finite")
        if not 0.0 < self.knee < self.ceiling < 1.0:
            raise ValueError("expected 0 < knee < ceiling < 1")


def _longest_run(mask: np.ndarray, sample_rate: int) -> dict[str, Any]:
    best = {
        "samples": 0, "seconds": 0.0, "channel": None,
        "start_sample": None, "end_sample_exclusive": None,
        "start_time_s": None, "end_time_s": None,
    }
    for channel in range(mask.shape[1]):
        indices = np.flatnonzero(mask[:, channel])
        if not len(indices):
            continue
        for run in np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1):
            start, end = int(run[0]), int(run[-1] + 1)
            length = end - start
            if length > best["samples"]:
                best = {
                    "samples": length,
                    "seconds": length / float(sample_rate),
                    "channel": channel,
                    "start_sample": start,
                    "end_sample_exclusive": end,
                    "start_time_s": start / float(sample_rate),
                    "end_time_s": end / float(sample_rate),
                }
    return best


def ceiling_run_metrics(values: np.ndarray, *, ceiling: float = .94,
                        sample_rate: int = 48_000) -> dict[str, Any]:
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or not np.all(np.isfinite(x)):
        raise ValueError("expected finite stereo values")
    mask = np.abs(x) > ceiling + 1e-12
    return {
        "ceiling_input_exceedance_samples": int(np.count_nonzero(mask)),
        "exceedance_longest_run": _longest_run(mask, sample_rate),
    }


def linked_soft_ceiling(
    values: np.ndarray, config: GuardConfig = GuardConfig(), *,
    sample_rate: int = 48_000,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply one common, memoryless gain to every channel in each frame."""
    config.validate()
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] == 0 or x.shape[1] == 0:
        raise ValueError("expected a nonempty (frames, channels) array")
    if not np.all(np.isfinite(x)):
        raise ValueError("non-finite signal; do not repair it silently")

    k, c = float(config.knee), float(config.ceiling)
    peak = np.max(np.abs(x), axis=1)
    active = peak > k
    gain = np.ones(len(peak), dtype=np.float64)
    if np.any(active):
        with np.errstate(over="ignore", invalid="raise"):
            z = (peak[active] - k) / (c - k)
            target = k + (c - k) * np.tanh(z)
        # Keep the finite result one ULP inside the declared ceiling.  This is
        # a floating-point guard, not an additional hard limiter policy.
        target = np.minimum(target, np.nextafter(c, 0.0))
        gain[active] = target / peak[active]

    soft_output = x.copy()
    soft_output[active] = x[active] * gain[active, None]
    emergency_mask = np.abs(soft_output) > c + 1e-12
    emergency_output = np.clip(soft_output, -c, c)
    emergency_error = soft_output - emergency_output
    output = emergency_output if np.any(emergency_mask) else soft_output
    if not np.all(np.isfinite(output)):
        raise ArithmeticError("output guard produced non-finite samples")

    delta = output - x
    min_gain = float(np.min(gain))
    old_exceedance = ceiling_run_metrics(x, ceiling=c, sample_rate=sample_rate)
    return output, {
        "receipt_schema": OUTPUT_GUARD_RECEIPT_SCHEMA,
        "output_policy": config.policy_id,
        "knee_linear": k,
        "ceiling_linear": c,
        "stereo_link": "instantaneous_frame_peak_common_gain",
        "parent_denominator_policy": "caller_supplied_fixed_parent_peak",
        "frame_count": int(len(x)),
        "legacy_ceiling_input_exceedance_samples": old_exceedance[
            "ceiling_input_exceedance_samples"
        ],
        "legacy_transfer_pre_guard_peak": float(np.max(np.abs(x))),
        "pre_guard_exceedance_longest_run": old_exceedance["exceedance_longest_run"],
        "pre_guard_peak": float(np.max(np.abs(x))),
        "soft_guard_active_frames": int(np.count_nonzero(active)),
        "soft_guard_active_frame_ratio": float(np.mean(active)),
        "soft_guard_min_gain": min_gain,
        "soft_guard_max_attenuation_db": float(-20.0 * np.log10(min_gain)),
        "soft_guard_delta_peak": float(np.max(np.abs(delta))),
        "soft_guard_delta_rms": float(np.sqrt(np.mean(delta * delta))),
        "post_guard_peak": float(np.max(np.abs(output))),
        "post_guard_ceiling_exceedance_samples": int(
            np.count_nonzero(np.abs(output) > c + 1e-12)
        ),
        "emergency_clip_count": int(np.count_nonzero(emergency_mask)),
        "emergency_clip_error": float(np.max(np.abs(emergency_error))),
        "emergency_clip_error_rms": float(np.sqrt(np.mean(emergency_error * emergency_error))),
    }
