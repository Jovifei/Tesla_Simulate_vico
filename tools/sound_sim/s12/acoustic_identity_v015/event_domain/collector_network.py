"""Per-path to bank/collector routing."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .exhaust_path import apply_fractional_delay, sound_speed_mps

@dataclass(frozen=True)
class CollectorResult:
    left: np.ndarray
    right: np.ndarray
    banks: np.ndarray
    path_delays_s: np.ndarray

def route_to_collectors(paths: np.ndarray, bank_assignment: list[int] | np.ndarray, primary_lengths_m: list[float] | np.ndarray, stereo_pan: list[float] | np.ndarray, sample_rate_hz: int = 48000, temperature_c: float = 700.0, collector_length_m: float = 0.5, collector_loss: float = 0.92, per_path_attenuation: list[float] | np.ndarray | None = None) -> CollectorResult:
    paths = np.asarray(paths, dtype=np.float64)
    assignment = np.asarray(bank_assignment, dtype=np.int64)
    lengths = np.asarray(primary_lengths_m, dtype=np.float64)
    pan = np.asarray(stereo_pan, dtype=np.float64)
    attenuations = np.ones(paths.shape[0], dtype=np.float64) if per_path_attenuation is None else np.asarray(per_path_attenuation, dtype=np.float64)
    if paths.ndim != 2 or paths.shape[0] != assignment.size or assignment.size != lengths.size:
        raise ValueError("path matrix and routing arrays disagree")
    if pan.size != 2 or attenuations.size != paths.shape[0] or np.any(~np.isfinite(paths)):
        raise ValueError("invalid collector inputs")
    if np.any(lengths < 0.0) or np.any(attenuations < 0.0) or not np.all(np.isfinite(attenuations)):
        raise ValueError("path lengths and attenuation must be finite and nonnegative")
    speed = float(sound_speed_mps(temperature_c))
    path_delays = lengths / speed
    bank_count = int(np.max(assignment)) + 1 if assignment.size else 1
    banks = np.zeros((bank_count, paths.shape[1]), dtype=np.float64)
    for entity in range(paths.shape[0]):
        routed = apply_fractional_delay(paths[entity], path_delays[entity], sample_rate_hz, attenuation=attenuations[entity])
        banks[int(assignment[entity])] += routed
    collector_delay = float(collector_length_m) / speed
    left = np.zeros(paths.shape[1], dtype=np.float64)
    right = np.zeros_like(left)
    for bank_index, bank in enumerate(banks):
        routed = apply_fractional_delay(bank, collector_delay, sample_rate_hz, attenuation=collector_loss)
        weight = float(np.clip(pan[bank_index % pan.size], -1.0, 1.0))
        left += routed * (1.0 - weight) * 0.5
        right += routed * (1.0 + weight) * 0.5
    return CollectorResult(left, right, banks, path_delays)
