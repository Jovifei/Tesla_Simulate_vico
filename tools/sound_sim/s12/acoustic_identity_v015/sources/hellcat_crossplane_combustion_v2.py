"""Deterministic Stage-L cross-plane HEMI combustion and blowdown source.

This is a C-level synthetic model.  It consumes the shared Stage-L crank
clock directly; it is not an OEM pressure trace or calibration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from ..contracts import SourceRender
if TYPE_CHECKING:
    from ..stage_l.crank_clock import HellcatCrankClock


_PARAMETERS = {
    "cylinder_strength_variation",
    "bank_amplitude_asymmetry",
    "blowdown_attack_ms",
    "blowdown_fast_decay_ms",
    "blowdown_slow_decay_ms",
    "blowdown_slow_weight",
    "low_frequency_blowdown_gain",
    "structure_shock_mix",
    "torque_ripple_modulation_depth",
    "xpipe_cross_coupling",
    "xpipe_delay_ms",
}
_CONTRIBUTORS = (
    "hemi_exhaust_left",
    "hemi_exhaust_right",
    "hemi_blowdown_body",
    "hemi_structure_shock",
    "hemi_mechanical_torque_ripple",
)
_AGGREGATES = ("hemi_exhaust", "hemi_combustion_and_blowdown")
_CYLINDER_PATTERN = np.asarray((-1.0, -0.42, 0.68, 0.15, -0.75, 0.92, -0.16, 0.48))


def render_hellcat_crossplane_combustion_v2(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    clock: "HellcatCrankClock",
    sample_rate_hz: int,
    overrides: Mapping[str, float],
) -> SourceRender:
    """Render event-driven bank exhaust, blowdown body and structure pressure."""
    from ..stage_l.crank_clock import HELLCAT_BANK_PATTERN, HELLCAT_FIRING_ORDER

    rpm, load, throttle = _validate_inputs(rpm, load, throttle, clock, sample_rate_hz)
    values = _validate_overrides(overrides)
    count = rpm.size
    event_indices = np.asarray(clock.event_sample_indices, dtype=np.int64)
    event_count = event_indices.size
    cylinder_variation = values["cylinder_strength_variation"]
    cylinder_pattern = 1.0 + cylinder_variation * _CYLINDER_PATTERN
    event_strengths = cylinder_pattern[np.arange(event_count) % cylinder_pattern.size]
    pressure_rise = (
        (0.28 + 0.72 * load[event_indices])
        * (0.25 + 0.75 * throttle[event_indices])
    )
    event_amplitudes = 0.075 * pressure_rise * event_strengths

    all_impulses = np.zeros(count, dtype=np.float64)
    all_impulses[event_indices] = event_amplitudes
    left_impulses = np.zeros(count, dtype=np.float64)
    right_impulses = np.zeros(count, dtype=np.float64)
    asymmetry = values["bank_amplitude_asymmetry"]
    for ordinal, (index, label) in enumerate(zip(event_indices, clock.bank_labels, strict=True)):
        if label == "left":
            left_impulses[index] = event_amplitudes[ordinal] * (1.0 + asymmetry)
        else:
            right_impulses[index] = event_amplitudes[ordinal] * (1.0 - asymmetry)

    kernel, kernel_diagnostics = _blowdown_kernel(sample_rate_hz, values)
    left_local = _finite_convolve(left_impulses, kernel)
    right_local = _finite_convolve(right_impulses, kernel)
    delay_samples = max(1, int(round(values["xpipe_delay_ms"] * sample_rate_hz / 1000.0)))
    cross = values["xpipe_cross_coupling"]
    left_pressure = left_local + cross * _delay(right_local, delay_samples)
    right_pressure = right_local + cross * _delay(left_local, delay_samples)
    exhaust_left = np.column_stack((left_pressure, 0.34 * left_pressure))
    exhaust_right = np.column_stack((0.34 * right_pressure, right_pressure))

    body_kernel = _body_kernel(sample_rate_hz, values)
    body_mono = values["low_frequency_blowdown_gain"] * _finite_convolve(all_impulses, body_kernel)
    blowdown_body = np.column_stack((0.62 * body_mono, 0.62 * body_mono))

    shock_kernel = _structure_kernel(sample_rate_hz)
    shock_mono = values["structure_shock_mix"] * _finite_convolve(all_impulses, shock_kernel)
    structure_shock = np.column_stack((shock_mono, 0.82 * shock_mono))

    torque_kernel = _torque_kernel(sample_rate_hz)
    torque_events = _finite_convolve(all_impulses, torque_kernel)
    torque_mono = values["torque_ripple_modulation_depth"] * torque_events
    mechanical_torque = np.column_stack((0.88 * torque_mono, torque_mono))

    stems = {
        "hemi_exhaust_left": exhaust_left,
        "hemi_exhaust_right": exhaust_right,
        "hemi_blowdown_body": blowdown_body,
        "hemi_structure_shock": structure_shock,
        "hemi_mechanical_torque_ripple": mechanical_torque,
    }
    pressure = sum((stems[name] for name in _CONTRIBUTORS), np.zeros((count, 2)))
    stems["hemi_exhaust"] = exhaust_left + exhaust_right
    stems["hemi_combustion_and_blowdown"] = pressure.copy()
    requested = sorted(values)
    diagnostics: dict[str, object] = {
        "vehicle_id": "hellcat",
        "scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        "clock_object_id": id(clock),
        "event_gates_consumed": True,
        "event_sample_indices_consumed": True,
        "bank_labels_consumed": True,
        "event_sample_indices": clock.event_sample_indices,
        "bank_labels": clock.bank_labels,
        "event_count": int(event_count),
        "firing_order": HELLCAT_FIRING_ORDER,
        "cylinder_sequence": tuple(HELLCAT_FIRING_ORDER[i % 8] for i in range(event_count)),
        "cylinder_strength_pattern": tuple(float(value) for value in cylinder_pattern),
        "event_strengths": tuple(float(value) for value in event_strengths),
        "event_phase_max_error_samples": 0.0,
        "merged_firing_order": "uniform_4EO",
        "merged_firing_ridge_hz": float(np.mean(rpm) * 4.0 / 60.0),
        "bank_interval_ratio_multisets": _bank_interval_ratio_multisets(HELLCAT_BANK_PATTERN),
        "bank_response_model": "independent_bank_pulses_with_delayed_coherent_xpipe_crossfeed",
        "excitation_model": "event_driven_pressure_pulses",
        "static_low_shelf_used": False,
        "resonance_model": "broad_event_kernel_no_high_q_peak",
        "white_noise_used": False,
        "randomness_used": False,
        "pressure_stem_contract": {
            "contributors": list(_CONTRIBUTORS),
            "diagnostic_aggregates": list(_AGGREGATES),
        },
        "candidate_parameter_usage": {
            "requested": requested,
            "read": requested,
            "configured": requested,
            "active": requested,
            "inactive": [],
            "unused": [],
        },
        "xpipe_delay_samples": delay_samples,
        **kernel_diagnostics,
    }
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def _validate_inputs(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    clock: "HellcatCrankClock",
    sample_rate_hz: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from ..stage_l.crank_clock import HellcatCrankClock

    if not isinstance(clock, HellcatCrankClock):
        raise TypeError("clock must be a HellcatCrankClock")
    if not isinstance(sample_rate_hz, int) or isinstance(sample_rate_hz, bool) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    arrays = tuple(np.asarray(value, dtype=np.float64) for value in (rpm, load, throttle))
    count = clock.engine_phase_cycles.size
    if any(value.ndim != 1 or value.size != count for value in arrays):
        raise ValueError("rpm/load/throttle must be one-dimensional and match the shared clock")
    if any(not np.all(np.isfinite(value)) for value in arrays):
        raise ValueError("rpm/load/throttle must be finite")
    if np.any(arrays[0] < 0.0) or np.any((arrays[1] < 0.0) | (arrays[1] > 1.0)) or np.any((arrays[2] < 0.0) | (arrays[2] > 1.0)):
        raise ValueError("rpm/load/throttle values are outside their contracts")
    increments = 0.5 * (arrays[0][:-1] + arrays[0][1:]) / (60.0 * sample_rate_hz)
    if not np.allclose(np.diff(clock.engine_phase_cycles), increments, rtol=0.0, atol=1.0e-12):
        raise ValueError("shared crank clock does not match rpm/sample-rate input")
    event_indices = np.asarray(clock.event_sample_indices, dtype=np.int64)
    if not np.array_equal(event_indices, np.flatnonzero(clock.firing_event_gate)):
        raise ValueError("shared crank clock event gate/index contract is inconsistent")
    for index, label in zip(event_indices, clock.bank_labels, strict=True):
        gate = clock.left_bank_event_gate if label == "left" else clock.right_bank_event_gate
        other = clock.right_bank_event_gate if label == "left" else clock.left_bank_event_gate
        if gate[index] != 1.0 or other[index] != 0.0:
            raise ValueError("shared crank clock bank label/gate contract is inconsistent")
    return arrays


def _validate_overrides(overrides: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(overrides, Mapping) or set(overrides) != _PARAMETERS:
        raise ValueError("combustion/blowdown overrides must contain the exact public parameter set")
    values = {name: float(value) for name, value in overrides.items()}
    if any(not np.isfinite(value) for value in values.values()):
        raise ValueError("combustion/blowdown override values must be finite")
    return values


def _blowdown_kernel(sample_rate_hz: int, values: Mapping[str, float]) -> tuple[np.ndarray, dict[str, object]]:
    attack_s = values["blowdown_attack_ms"] / 1000.0
    fast_s = values["blowdown_fast_decay_ms"] / 1000.0
    slow_s = values["blowdown_slow_decay_ms"] / 1000.0
    slow_weight = values["blowdown_slow_weight"]
    length = max(8, int(np.ceil(6.0 * slow_s * sample_rate_hz)))
    time_s = np.arange(length, dtype=np.float64) / sample_rate_hz
    rise = 1.0 - np.exp(-time_s / max(attack_s, 1.0 / sample_rate_hz))
    fast = rise * np.exp(-time_s / max(fast_s, 1.0 / sample_rate_hz))
    slow = rise * np.exp(-time_s / max(slow_s, 1.0 / sample_rate_hz))
    kernel = (1.0 - slow_weight) * fast + slow_weight * slow
    peak = max(float(np.max(kernel)), 1.0e-30)
    kernel /= peak
    fast_energy = float(np.sum(np.square((1.0 - slow_weight) * fast)))
    slow_energy = float(np.sum(np.square(slow_weight * slow)))
    return kernel, {
        "measured_attack_samples": int(np.argmax(kernel)),
        "measured_fast_decay_samples": float(fast_s * sample_rate_hz),
        "measured_slow_decay_samples": float(slow_s * sample_rate_hz),
        "slow_tail_energy_ratio": slow_energy / max(fast_energy + slow_energy, 1.0e-30),
        "blowdown_kernel_peak": float(np.max(kernel)),
        "blowdown_kernel_area": float(np.sum(kernel)),
    }


def _body_kernel(sample_rate_hz: int, values: Mapping[str, float]) -> np.ndarray:
    attack_s = values["blowdown_attack_ms"] / 1000.0
    fast_s = values["blowdown_fast_decay_ms"] / 1000.0
    slow_s = values["blowdown_slow_decay_ms"] / 1000.0
    slow_weight = values["blowdown_slow_weight"]
    length = max(8, int(np.ceil(7.0 * slow_s * sample_rate_hz)))
    time_s = np.arange(length, dtype=np.float64) / sample_rate_hz
    rise = 1.0 - np.exp(-time_s / max(attack_s, 1.0 / sample_rate_hz))
    kernel = rise * (
        0.35 * (1.0 - slow_weight) * np.exp(-time_s / max(2.2 * fast_s, 1.0 / sample_rate_hz))
        + slow_weight * np.exp(-time_s / max(1.7 * slow_s, 1.0 / sample_rate_hz))
    )
    return kernel / max(float(np.max(kernel)), 1.0e-30)


def _structure_kernel(sample_rate_hz: int) -> np.ndarray:
    length = max(8, int(round(0.010 * sample_rate_hz)))
    time_s = np.arange(length, dtype=np.float64) / sample_rate_hz
    return (1.0 - np.exp(-time_s / 0.0008)) * np.exp(-time_s / 0.0028)


def _torque_kernel(sample_rate_hz: int) -> np.ndarray:
    length = max(8, int(round(0.016 * sample_rate_hz)))
    time_s = np.arange(length, dtype=np.float64) / sample_rate_hz
    return (1.0 - np.exp(-time_s / 0.0015)) * np.exp(-time_s / 0.006)


def _finite_convolve(impulses: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    return np.convolve(impulses, kernel, mode="full")[: impulses.size]


def _delay(value: np.ndarray, samples: int) -> np.ndarray:
    delayed = np.zeros_like(value)
    delayed[samples:] = value[:-samples]
    return delayed


def _bank_interval_ratio_multisets(
    bank_pattern: tuple[str, ...],
) -> dict[str, tuple[int, ...]]:
    result: dict[str, tuple[int, ...]] = {}
    for bank in ("left", "right"):
        positions = np.asarray([i for i, label in enumerate(bank_pattern) if label == bank])
        intervals = np.diff(np.r_[positions, positions[0] + len(bank_pattern)])
        result[bank] = tuple(int(value) for value in np.sort(intervals))
    return result


__all__ = ("render_hellcat_crossplane_combustion_v2",)
