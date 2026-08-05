"""Shared primitives for S12 engine acoustic source models (v2).

These helpers back the Phase 3 low-frequency-body realism work for the
remaining vehicle models (Aventador V12, C63 V8 NA, GT-R V6 tt, LFA V10,
Supra I6 tt). They are vectorized (scipy ``lfilter``) equivalents of the
per-sample recurrence used by the original three sources, so renders stay
reproducible and ~10x faster.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Optional

import numpy as np
from scipy.signal import lfilter


def combustion_impulse_train(
    trace,
    sample_rate_hz: int,
    events_per_rev: float,
    bank_pattern: Optional[tuple[int, ...]] = None,
    pressure_exp: float = 1.25,
    max_comp: float = 2.0,
    min_rpm: float = 850.0,
    timing_jitter: float = 0.0,
    amp_variation: float = 0.0,
) -> dict:
    """Build the combustion event impulse train(s) for an engine.

    Returns a dict with:
      count, time_s, rpm, load, throttle, phase, event_id, starts,
      impulses (single, load-weighted), and, when ``bank_pattern`` is given,
      left_impulses / right_impulses split by firing bank.
    """
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    pressure_compensation = np.power(3000.0 / np.maximum(rpm, min_rpm), pressure_exp)
    event_pressure = np.minimum(pressure_compensation, max_comp)
    event_id = np.floor(phase * events_per_rev).astype(np.int64)
    starts = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    impulses = np.zeros(count, dtype=np.float64)
    for sample in starts:
        impulses[sample] = event_pressure[sample] * (0.45 + 0.55 * load[sample])

    # Optional always-on cycle irregularity. Real engines are not perfectly
    # periodic; a small timing jitter + amplitude variation smears the harmonic
    # comb so energy does not pile into 1-4 kHz at high rpm (where the event
    # rate itself lands in the kHz range). Seeded/deterministic. Off by default
    # so the three reviewed core sources (which pass timing_jitter=0) are
    # byte-for-byte unchanged.
    if timing_jitter > 0.0 or amp_variation > 0.0:
        rng = np.random.default_rng(int(abs(events_per_rev * 1000.0 + min_rpm)) % (2**32))
        jittered = np.zeros(count, dtype=np.float64)
        for sample in starts:
            local_rate = max(rpm[sample] / 60.0 * events_per_rev, 1e-3)
            spacing = max(sample_rate_hz / local_rate, 1.0)
            offset = 0
            if timing_jitter > 0.0:
                offset = int(round(rng.normal(0.0, timing_jitter * spacing)))
            target = min(max(sample + offset, 0), count - 1)
            amp = 1.0
            if amp_variation > 0.0:
                amp = float(np.clip(1.0 + rng.normal(0.0, amp_variation), 0.5, 1.6))
            jittered[target] += impulses[sample] * amp
        impulses = jittered
        starts = np.flatnonzero(impulses > 0.0)

    result: dict = {
        "count": count,
        "time_s": time_s,
        "rpm": rpm,
        "load": load,
        "throttle": throttle,
        "phase": phase,
        "event_id": event_id,
        "starts": starts,
        "event_pressure": event_pressure,
        "impulses": impulses,
    }
    if bank_pattern is not None:
        bp = np.asarray(bank_pattern, dtype=np.int64)
        left = np.zeros(count, dtype=np.float64)
        right = np.zeros(count, dtype=np.float64)
        for sample in starts:
            target = left if bp[event_id[sample] % bp.size] == 0 else right
            target[sample] = impulses[sample]
        result["left_impulses"] = left
        result["right_impulses"] = right
    return result


def decaying_tone(
    impulses: np.ndarray, frequency_hz: float, decay_s: float, sample_rate_hz: int
) -> np.ndarray:
    """Vectorized second-order damped sinusoid driven by ``impulses``.

    Exact lfilter equivalent of ``idle_dynamics._ring``:
      y[n] = 2r cos(w) y[n-1] - r^2 y[n-2] + sin(w) * x[n],  w = 2*pi*f/sr
    """
    radius = float(np.exp(-1.0 / (decay_s * sample_rate_hz)))
    w = 2.0 * np.pi * frequency_hz / sample_rate_hz
    feedback = 2.0 * radius * np.cos(w)
    b = np.array([np.sin(w), 0.0, 0.0], dtype=np.float64)
    a = np.array([1.0, -feedback, radius * radius], dtype=np.float64)
    return lfilter(b, a, np.asarray(impulses, dtype=np.float64), axis=0)


def mechanical_texture(count: int, sample_rate_hz: int, strength: float, seed: float) -> np.ndarray:
    """Deterministic broadband mechanical friction texture (belt/pump drag)."""
    if strength <= 0.0 or count < 1:
        return np.zeros(count, dtype=np.float64)
    rng = np.random.default_rng(int(abs(seed * 1e6)) % (2**32))
    samples = rng.uniform(-1.0, 1.0, size=count)
    cutoff = max(int(sample_rate_hz / 60), 1)
    kernel = np.ones(cutoff) / cutoff
    filtered = np.convolve(samples, kernel, mode="same")
    peak = float(np.max(np.abs(filtered))) or 1.0
    return filtered / peak


def first_order_lag(target: np.ndarray, tau_s: float, sample_rate_hz: int) -> np.ndarray:
    """Vectorized first-order low-pass (state-follow) of ``target``."""
    alpha = min(1.0, 1.0 / max(tau_s * sample_rate_hz, 1.0))
    b = np.array([alpha], dtype=np.float64)
    a = np.array([1.0, -(1.0 - alpha)], dtype=np.float64)
    return lfilter(b, a, np.asarray(target, dtype=np.float64), axis=0)


def turbo_layer(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    sample_rate_hz: int,
    shaft_ratio_base: float = 2.0,
    orders: tuple[float, ...] = (1.0, 5.0, 10.0),
    order_weights: tuple[float, ...] = (0.34, 0.94, 0.38),
    boost_tau_attack: float = 0.09,
    boost_tau_release: float = 0.22,
    bypass: bool = False,
) -> dict:
    """State-dependent turbo whine + spool.

    Returns whine_mono, boost_state, shaft_phase. ``boost_state`` is the
    inertia-smoothed boost level (attack/release asymmetric, like a real
    turbo).
    """
    boost_target = load * throttle * np.clip((rpm - 1100.0) / 3800.0, 0.0, 1.15)
    boost_state = np.zeros_like(boost_target)
    for n in range(1, boost_target.size):
        tau = boost_tau_attack if boost_target[n] >= boost_state[n - 1] else boost_tau_release
        boost_state[n] = boost_state[n - 1] + (boost_target[n] - boost_state[n - 1]) / (tau * sample_rate_hz)
    shaft_ratio = shaft_ratio_base * (0.93 + 0.16 * boost_state)
    shaft_phase = np.cumsum(rpm * shaft_ratio) / (60.0 * sample_rate_hz)
    whine = np.zeros_like(boost_target)
    for order, weight in zip(orders, order_weights):
        whine = whine + weight * np.sin(2.0 * np.pi * shaft_phase * order)
    whine_mono = whine * boost_state
    result = {"whine_mono": whine_mono, "boost_state": boost_state, "shaft_phase": shaft_phase, "shaft_ratio": shaft_ratio}
    if bypass:
        bypass_target = (1.0 - throttle) * (0.35 + 0.65 * (1.0 - boost_state))
        result["bypass_state"] = first_order_lag(bypass_target, 0.05, sample_rate_hz)
    return result


def to_stereo(mono: np.ndarray, crossfeed: float = 0.0) -> np.ndarray:
    """Mono -> stereo with optional crossfeed (right gets ``crossfeed`` * left)."""
    if crossfeed <= 0.0:
        return np.column_stack((mono, mono))
    return np.column_stack((mono, crossfeed * mono))
