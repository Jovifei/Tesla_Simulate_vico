"""One shared deterministic four-stroke crank clock for Stage-L Hellcat work."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..contracts import VehicleStateTrace


HELLCAT_FIRING_ORDER = (1, 8, 4, 3, 6, 5, 7, 2)
HELLCAT_BANK_PATTERN = ("left", "right", "left", "right", "right", "left", "right", "left")


@dataclass(frozen=True)
class HellcatCrankClock:
    engine_phase_cycles: np.ndarray
    cycle_phase_cycles: np.ndarray
    firing_event_gate: np.ndarray
    left_bank_event_gate: np.ndarray
    right_bank_event_gate: np.ndarray
    torque_ripple_envelope: np.ndarray
    event_sample_indices: tuple[int, ...]
    bank_labels: tuple[str, ...]


def build_hellcat_crank_clock(trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> HellcatCrankClock:
    trace.validate()
    if not isinstance(sample_rate_hz, int) or isinstance(sample_rate_hz, bool) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    increments = 0.5 * (rpm[:-1] + rpm[1:]) / (60.0 * sample_rate_hz)
    phase = np.r_[0.0, np.cumsum(increments, dtype=np.float64)]
    event_id = np.floor(phase * 4.0 + 1.0e-12).astype(np.int64)
    indices = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    firing = np.zeros(count, dtype=np.float64)
    firing[indices] = 1.0
    labels = tuple(HELLCAT_BANK_PATTERN[int(event_id[index]) % len(HELLCAT_BANK_PATTERN)] for index in indices)
    left = np.zeros(count, dtype=np.float64)
    right = np.zeros(count, dtype=np.float64)
    for index, label in zip(indices, labels, strict=True):
        (left if label == "left" else right)[index] = 1.0
    decay = float(np.exp(-1.0 / (0.018 * sample_rate_hz)))
    ripple = np.zeros(count, dtype=np.float64)
    for index in range(count):
        ripple[index] = firing[index] + (decay * ripple[index - 1] if index else 0.0)
    peak = float(np.max(ripple))
    if peak > 0.0:
        ripple /= peak
    arrays = (phase, np.mod(phase / 2.0, 1.0), firing, left, right, ripple)
    for value in arrays:
        value.setflags(write=False)
    return HellcatCrankClock(*arrays, tuple(int(index) for index in indices), labels)


__all__ = ("HELLCAT_BANK_PATTERN", "HELLCAT_FIRING_ORDER", "HellcatCrankClock", "build_hellcat_crank_clock")
