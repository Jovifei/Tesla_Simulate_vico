"""Scoped RX-7 startup-boundary repair for the AI-4B candidate path."""
from __future__ import annotations

from typing import Any

import numpy as np

RX7_BOUNDARY_POLICY_V1 = "rx7_start_boundary_fade_v1"
RX7_BOUNDARY_FADE_FRAMES = 24


def apply_rx7_boundary_repair(
    values: np.ndarray,
    *,
    policy: str | None = RX7_BOUNDARY_POLICY_V1,
    fade_frames: int = RX7_BOUNDARY_FADE_FRAMES,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply a short start-only ramp to the RX-7 boundary candidate.

    The ramp is applied to both channels with the same scalar and never mutates
    the input. ``None`` is an explicit no-op for the legacy/default path.
    """
    audio = np.asarray(values, dtype=np.float64)
    if audio.ndim != 2 or audio.shape[1] != 2 or audio.shape[0] < 2:
        raise ValueError("expected finite stereo audio with at least two frames")
    if not np.all(np.isfinite(audio)):
        raise ValueError("boundary repair requires finite stereo audio")
    if policy is None:
        return audio.copy(), {
            "policy_id": None,
            "scope": "disabled",
            "fade_frames": 0,
            "modified_frames": 0,
            "delta_peak": 0.0,
            "delta_rms": 0.0,
            "stereo_link": "none",
        }
    if policy != RX7_BOUNDARY_POLICY_V1:
        raise ValueError(f"unsupported boundary policy: {policy}")
    if isinstance(fade_frames, bool) or not isinstance(fade_frames, (int, np.integer)):
        raise ValueError("fade_frames must be a positive integer")
    if fade_frames < 2:
        raise ValueError("fade_frames must be at least two")
    count = min(int(fade_frames), audio.shape[0])
    repaired = audio.copy()
    ramp = np.linspace(0.0, 1.0, count, dtype=np.float64)[:, None]
    repaired[:count] *= ramp
    delta = repaired - audio
    return repaired, {
        "policy_id": policy,
        "scope": "rx7_start_boundary_only",
        "fade_frames": count,
        "modified_frames": count,
        "delta_peak": float(np.max(np.abs(delta))),
        "delta_rms": float(np.sqrt(np.mean(delta * delta))),
        "stereo_link": "common_frame_ramp",
    }


__all__ = (
    "RX7_BOUNDARY_POLICY_V1",
    "RX7_BOUNDARY_FADE_FRAMES",
    "apply_rx7_boundary_repair",
)
