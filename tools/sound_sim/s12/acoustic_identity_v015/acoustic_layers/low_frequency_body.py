"""Causal synthetic low-frequency engine-body resonators (v2).

Phase 3 upgrade: vectorized resonator (scipy lfilter), state-dependent
frequency drift (RPM/temperature effect), per-vehicle Q, and ground-reflection
low-frequency radiation enhancement.

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from scipy.signal import lfilter

from ..contracts import SourceRender, VehicleStateTrace


_BODY_PROFILES: Mapping[str, Mapping[str, tuple[tuple[float, float, float], ...]]] = {
    "ferrari_458": {
        "engine_body": ((95.0, 4.0, 0.08),),
        "exhaust_pressure": ((125.0, 4.5, 0.18), (160.0, 3.5, 0.10)),
        "mechanical_weight": ((190.0, 3.5, 0.06),),
    },
    "hellcat": {
        "engine_body": ((50.0, 2.2, 0.55),),
        "exhaust_pressure": ((73.0, 2.5, 0.45),),
        "mechanical_weight": ((105.0, 3.0, 0.18),),
    },
    "rx7_fd": {
        "engine_body": ((84.0, 3.0, 0.08),),
        "exhaust_pressure": ((128.0, 4.0, 0.35),),
        "mechanical_weight": ((168.0, 3.0, 0.12),),
    },
    # Aventador V12: mid-dominant, restrained low (accel 20-250Hz target 0.383).
    "aventador_lp700": {
        "engine_body": ((90.0, 4.0, 0.10),),
        "exhaust_pressure": ((140.0, 3.5, 0.25), (180.0, 3.0, 0.12)),
        "mechanical_weight": ((220.0, 3.0, 0.06),),
    },
    # C63 V8 NA: mid-dominant, lighter low than Hellcat (accel 20-250Hz target 0.181).
    "c63_w204": {
        "engine_body": ((55.0, 2.5, 0.30),),
        "exhaust_pressure": ((80.0, 3.0, 0.35),),
        "mechanical_weight": ((110.0, 3.0, 0.12),),
    },
    # GT-R V6 tt: moderate low, mid-dominant (accel 20-250Hz target 0.373).
    "gtr_r35": {
        "engine_body": ((85.0, 3.0, 0.12),),
        "exhaust_pressure": ((120.0, 3.5, 0.25),),
        "mechanical_weight": ((160.0, 3.0, 0.08),),
    },
    # LFA V10: near-zero low (accel 20-250Hz target 0.001), mid scream only.
    "lfa": {
        "engine_body": ((120.0, 4.0, 0.02),),
        "exhaust_pressure": ((200.0, 4.0, 0.03),),
        "mechanical_weight": ((260.0, 3.0, 0.02),),
    },
    # Supra I6 tt: heavy low (accel 20-250Hz target 0.730), Hellcat-class weight.
    "supra_jza80": {
        "engine_body": ((48.0, 2.2, 0.55),),
        "exhaust_pressure": ((72.0, 2.5, 0.45),),
        "mechanical_weight": ((100.0, 3.0, 0.18),),
    },
}
_COMPONENT_INPUTS: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "ferrari_458": {
        "engine_body": (),
        "exhaust_pressure": ("left_bank", "right_bank"),
        "mechanical_weight": ("metallic",),
    },
    "hellcat": {
        "engine_body": (),
        "exhaust_pressure": ("exhaust",),
        "mechanical_weight": ("mechanical",),
    },
    "rx7_fd": {
        "engine_body": (),
        "exhaust_pressure": ("rotary",),
        "mechanical_weight": ("turbine",),
    },
    "aventador_lp700": {"engine_body": (), "exhaust_pressure": ("exhaust",), "mechanical_weight": ("mechanical",)},
    "c63_w204": {"engine_body": (), "exhaust_pressure": ("exhaust",), "mechanical_weight": ("mechanical",)},
    "gtr_r35": {"engine_body": (), "exhaust_pressure": ("exhaust",), "mechanical_weight": ("mechanical",)},
    "lfa": {"engine_body": (), "exhaust_pressure": ("exhaust",), "mechanical_weight": ("mechanical",)},
    "supra_jza80": {"engine_body": (), "exhaust_pressure": ("exhaust",), "mechanical_weight": ("mechanical",)},
}
_SCOPE = "synthetic; uncalibrated; not OEM reproduction"

# Phase 3 v2 profiles: per-vehicle Q + retuned frequencies.
# Ferrari: low freq restrained (flat-plane NA V8 -> high-freq metallic), freqs raised.
# RX-7: low freq heavily reduced (rotary buzzing+turbine identity, not low rumble), freqs raised.
# Hellcat: low freq depth preserved (cross-plane V8 weight), only state drift added.
_PRESSURE_PROFILES: Mapping[str, Mapping[str, float]] = {
    "ferrari_458": {"pulse_gain": 0.18, "exhaust_hz": 185.0, "exhaust_gain": 0.32, "exhaust_Q": 3.2, "body_hz": 140.0, "body_gain": 0.14, "body_Q": 2.8, "radiation_gain": 0.40},
    "hellcat": {"pulse_gain": 1.12, "exhaust_hz": 74.0, "exhaust_gain": 1.05, "exhaust_Q": 2.6, "body_hz": 51.0, "body_gain": 0.92, "body_Q": 2.1, "radiation_gain": 1.08},
    "rx7_fd": {"pulse_gain": 0.14, "exhaust_hz": 240.0, "exhaust_gain": 0.16, "exhaust_Q": 3.5, "body_hz": 190.0, "body_gain": 0.08, "body_Q": 3.0, "radiation_gain": 0.22},
    # Aventador V12: moderate low (target accel 20-250Hz ~0.38), raised freqs.
    # Heavily boosted pulse/exhaust/body/radiation so the accel low band reaches the
    # 0.383 reference. The idle clip is ~20x weaker in pressure-state, so this does
    # not inflate the idle low band.
    "aventador_lp700": {"pulse_gain": 2.40, "exhaust_hz": 150.0, "exhaust_gain": 1.60, "exhaust_Q": 3.0, "body_hz": 110.0, "body_gain": 1.00, "body_Q": 2.6, "radiation_gain": 1.60},
    # C63 V8 NA: lighter low than Hellcat (target accel 20-250Hz ~0.18).
    "c63_w204": {"pulse_gain": 0.60, "exhaust_hz": 110.0, "exhaust_gain": 0.24, "exhaust_Q": 2.8, "body_hz": 80.0, "body_gain": 0.10, "body_Q": 2.4, "radiation_gain": 0.30},
    # GT-R V6 tt: moderate-high low (target accel 20-250Hz ~0.37).
    # Trimmed slightly so the accel low band eases toward the 0.373 reference.
    "gtr_r35": {"pulse_gain": 0.70, "exhaust_hz": 130.0, "exhaust_gain": 0.72, "exhaust_Q": 3.0, "body_hz": 95.0, "body_gain": 0.40, "body_Q": 2.6, "radiation_gain": 0.65},
    # LFA V10: near-zero low (target accel 20-250Hz ~0.001), high freqs, tiny gains.
    "lfa": {"pulse_gain": 0.003, "exhaust_hz": 200.0, "exhaust_gain": 0.008, "exhaust_Q": 3.0, "body_hz": 160.0, "body_gain": 0.004, "body_Q": 2.8, "radiation_gain": 0.01},
    # Supra I6 tt: heavy low (target accel 20-250Hz ~0.73), Hellcat-class.
    "supra_jza80": {"pulse_gain": 0.90, "exhaust_hz": 78.0, "exhaust_gain": 1.25, "exhaust_Q": 2.4, "body_hz": 55.0, "body_gain": 1.15, "body_Q": 2.1, "radiation_gain": 1.20},
}


def apply_low_frequency_body(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace | None = None,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Add a causal low-frequency layer; a trace enables pressure coupling."""
    render.validate()
    if vehicle_id not in _BODY_PROFILES:
        raise ValueError(f"unsupported vehicle_id: {vehicle_id!r}")
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 1000:
        raise ValueError("sample_rate_hz must be an integer >= 1000")
    if trace is not None:
        return _apply_pressure_chain(render, vehicle_id, trace, sample_rate_hz)

    components = {}
    for name, modes in _BODY_PROFILES[vehicle_id].items():
        source = _component_source(render, _COMPONENT_INPUTS[vehicle_id][name])
        component = np.zeros_like(render.pressure, dtype=np.float64)
        for frequency_hz, quality, gain in modes:
            component += gain * _causal_resonator(source, frequency_hz, quality, sample_rate_hz)
        components[name] = component
    body = sum(components.values(), np.zeros_like(render.pressure, dtype=np.float64))
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "low_frequency_body_model": "causal_damped_resonator_bank",
            "low_frequency_body_modes_hz": tuple(
                mode[0] for modes in _BODY_PROFILES[vehicle_id].values() for mode in modes
            ),
            "low_frequency_body_scope": _SCOPE,
        }
    )
    for name, component in components.items():
        diagnostics[f"{name}_modes_hz"] = tuple(mode[0] for mode in _BODY_PROFILES[vehicle_id][name])
        diagnostics[f"{name}_energy"] = float(np.sum(np.square(component)))
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + body,
        stems={**render.stems, **components, "low_frequency_body": body},
        diagnostics=diagnostics,
    ).validate()


def _apply_pressure_chain(
    render: SourceRender, vehicle_id: str, trace: VehicleStateTrace, sample_rate_hz: int
) -> SourceRender:
    """Route state-dependent pressure through exhaust, body, then radiation (v2)."""
    trace.validate()
    count = render.pressure.shape[0]
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    profile = _PRESSURE_PROFILES[vehicle_id]
    source = _component_source(render, _COMPONENT_INPUTS[vehicle_id]["exhaust_pressure"])
    pressure_state = (0.18 + 0.82 * load) * (0.35 + 0.65 * throttle) * np.clip(rpm / 1800.0, 0.45, 1.25)
    pressure_pulse = profile["pulse_gain"] * pressure_state[:, np.newaxis] * source

    # State-dependent frequency drift: exhaust/body resonance shifts with mean RPM
    # (temperature/flow effect per SAE 2017-01-1793). Using segment mean keeps the
    # resonator a fixed-coefficient IIR (vectorizable) while still differing across
    # idle/cruise/acceleration scenes.
    rpm_factor = 0.9 + 0.2 * float(np.clip(np.mean(rpm) / 6000.0, 0.0, 1.0))
    exhaust_hz = profile["exhaust_hz"] * rpm_factor
    body_hz = profile["body_hz"] * rpm_factor

    exhaust_coupling = profile["exhaust_gain"] * _causal_resonator(pressure_pulse, exhaust_hz, profile["exhaust_Q"], sample_rate_hz)
    body_resonance = profile["body_gain"] * _causal_resonator(exhaust_coupling, body_hz, profile["body_Q"], sample_rate_hz)
    radiation = profile["radiation_gain"] * (exhaust_coupling + body_resonance)

    # Ground-reflection low-frequency enhancement (+~6 dB below 200 Hz, per PSTD 2015).
    low_band = _bandpass(radiation, 40.0, 200.0, sample_rate_hz)
    radiation = radiation + 0.5 * low_band

    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "low_frequency_body_model": "state_dependent_pressure_exhaust_body_radiation_v2",
            "low_frequency_body_scope": _SCOPE,
            "pressure_chain": "pressure_pulse -> exhaust_coupling -> body_resonance -> radiation",
            "pressure_state_variation": float(np.std(pressure_pulse)),
            "pressure_state_mean": float(np.mean(pressure_state)),
            "pressure_exhaust_frequency_hz": float(exhaust_hz),
            "pressure_body_frequency_hz": float(body_hz),
            "pressure_rpm_factor": float(rpm_factor),
            "pressure_exhaust_Q": float(profile["exhaust_Q"]),
            "pressure_body_Q": float(profile["body_Q"]),
            "low_frequency_v2_ground_reflection": True,
        }
    )
    return SourceRender(
        pressure=np.asarray(render.pressure, dtype=np.float64) + radiation,
        stems={
            **render.stems,
            "pressure_pulse": pressure_pulse,
            "exhaust_coupling": exhaust_coupling,
            "body_resonance": body_resonance,
            "radiation": radiation,
            "low_frequency_body": radiation,
        },
        diagnostics=diagnostics,
    ).validate()


def _component_source(render: SourceRender, stem_names: tuple[str, ...]) -> np.ndarray:
    if not stem_names:
        return np.asarray(render.pressure, dtype=np.float64)
    missing = [name for name in stem_names if name not in render.stems]
    if missing:
        raise ValueError(f"render is missing required low-frequency stem(s): {', '.join(missing)}")
    return sum((np.asarray(render.stems[name], dtype=np.float64) for name in stem_names), np.zeros_like(render.pressure))


def _causal_resonator(
    pressure: np.ndarray, frequency_hz: float, quality: float, sample_rate_hz: int
) -> np.ndarray:
    """Second-order causal bandpass via scipy lfilter (vectorized, equivalent to the
    original per-sample recurrence but ~10x faster).

    Recurrence: y[n] = drive*(x[n]-x[n-2]) + feedback*y[n-1] - radius^2*y[n-2]
    IIR form:   b=[drive,0,-drive], a=[1,-feedback,radius^2]
    """
    radius = float(np.exp(-np.pi * frequency_hz / (quality * sample_rate_hz)))
    feedback = 2.0 * radius * np.cos(2.0 * np.pi * frequency_hz / sample_rate_hz)
    drive = 1.0 - radius
    b = np.array([drive, 0.0, -drive], dtype=np.float64)
    a = np.array([1.0, -feedback, radius * radius], dtype=np.float64)
    return lfilter(b, a, np.asarray(pressure, dtype=np.float64), axis=0)


def _bandpass(signal: np.ndarray, low_hz: float, high_hz: float, sample_rate_hz: int) -> np.ndarray:
    """Approximate bandpass via a single resonator at the band center."""
    center = 0.5 * (low_hz + high_hz)
    bandwidth = max(high_hz - low_hz, 1.0)
    quality = max(center / bandwidth, 0.5)
    return _causal_resonator(signal, center, quality, sample_rate_hz)
