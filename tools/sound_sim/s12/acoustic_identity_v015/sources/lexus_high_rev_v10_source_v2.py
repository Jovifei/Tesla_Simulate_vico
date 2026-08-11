"""Synthetic Stage J Lexus LFA high-rev V10 event-driven source.

The source is intentionally independent of the historical fixed-centre LFA
``scream`` path.  It derives every audible oscillator from the continuously
integrated engine phase: a 72-degree V10 firing-event train, moving 5/10/15
order clusters, event-excited intake modes, and deterministic valvetrain and
metallic textures.  It contains no random-white-noise generator.

Boundary: C/synthetic, uncalibrated, and not an OEM reproduction.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_DEFAULTS = {
    "pulse_width_scale": 1.0,
    "phase_offset_deg": 0.0,
    "order_family_mix": 1.0,
    "intake_resonance_scale": 1.0,
    "metallic_texture_scale": 1.0,
    "high_rpm_growth_scale": 1.0,
}
_OVERRIDE_RANGES = {
    "pulse_width_scale": (0.45, 2.0),
    "phase_offset_deg": (-180.0, 180.0),
    "order_family_mix": (0.10, 2.0),
    "intake_resonance_scale": (0.10, 2.5),
    "metallic_texture_scale": (0.10, 2.5),
    "high_rpm_growth_scale": (0.10, 2.5),
}


def render_lfa_v2(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render deterministic stereo, pre-PTR LFA V10 pressure and named stems.

    This is C/synthetic provenance only.  The tunable ``overrides`` map is
    deliberately closed: each accepted key changes a source stem and records
    its active numeric value in diagnostics.
    """
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    settings = _settings(overrides)
    count, time_s, rpm, load, throttle = _resample_trace(trace, sample_rate_hz)
    engine_phase = np.cumsum(rpm) / (60.0 * sample_rate_hz)
    high_rpm = np.clip((rpm - 4200.0) / 4600.0, 0.0, 1.0)
    combustion = _v10_event_train(engine_phase, load, sample_rate_hz, settings["pulse_width_scale"])

    phase_offset = settings["phase_offset_deg"] / 360.0
    fifth = np.sin(2.0 * np.pi * (5.0 * engine_phase + phase_offset))
    tenth = np.sin(2.0 * np.pi * (10.0 * engine_phase + 1.37 * phase_offset))
    fifteenth = np.sin(2.0 * np.pi * (15.0 * engine_phase + 1.91 * phase_offset))
    order_growth = 0.32 + 0.68 * high_rpm * settings["high_rpm_growth_scale"]
    order_envelope = (0.30 + 0.70 * throttle) * (0.48 + 0.52 * load)
    order_mono = (
        settings["order_family_mix"]
        * 0.040
        * order_growth
        * order_envelope
        * (0.56 * fifth + 0.31 * tenth + 0.13 * fifteenth)
    )

    exhaust_mono = 0.072 * combustion * (0.22 + 0.78 * throttle)

    # The intake modes are not a fixed resonance: both carriers are engine
    # orders and their event excitation comes from the 72-degree V10 train.
    intake_excitation = _smooth_event_envelope(combustion, sample_rate_hz, 0.0045)
    intake_carrier = (
        0.63 * np.sin(2.0 * np.pi * 10.0 * engine_phase + 0.33)
        + 0.37 * np.sin(2.0 * np.pi * 15.0 * engine_phase + 1.14)
    )
    intake_mono = (
        0.052
        * settings["intake_resonance_scale"]
        * (0.12 + 0.88 * high_rpm)
        * (0.18 + 0.82 * throttle)
        * intake_excitation
        * intake_carrier
    )

    # Deterministic mechanical texture: valve/cam orders and pulse-shaped
    # lash impacts, rather than random broadband or white noise.
    valve_pulse = _smooth_event_envelope(combustion, sample_rate_hz, 0.0018)
    mechanical_mono = 0.012 * (0.35 + 0.65 * load) * (
        0.54 * np.sin(2.0 * np.pi * 20.0 * engine_phase + 0.25)
        + 0.31 * np.sin(2.0 * np.pi * 25.0 * engine_phase + 1.82)
        + 0.15 * np.sin(2.0 * np.pi * 30.0 * engine_phase + 2.71)
    ) * (0.22 + 0.78 * valve_pulse)

    # The metallic layer is a high-order, event-gated V10 texture.  Its
    # orders move with RPM and fade rapidly after a throttle lift.
    metallic_carrier = (
        0.50 * np.sin(2.0 * np.pi * 35.0 * engine_phase + 0.67)
        + 0.32 * np.sin(2.0 * np.pi * 42.5 * engine_phase + 1.91)
        + 0.18 * np.sin(2.0 * np.pi * 50.0 * engine_phase + 2.48)
    )
    metallic_mono = (
        0.020
        * settings["metallic_texture_scale"]
        * np.square(high_rpm)
        * (0.08 + 0.92 * throttle)
        * valve_pulse
        * metallic_carrier
    )

    exhaust = _to_stereo(exhaust_mono, 0.46)
    order_family = _to_stereo(order_mono, 0.58)
    intake = _to_stereo(intake_mono, 0.39)
    mechanical = _to_stereo(mechanical_mono, 0.51)
    metallic = _to_stereo(metallic_mono, 0.43)
    stems = {
        "exhaust": exhaust,
        "order_family": order_family,
        "intake": intake,
        "mechanical": mechanical,
        "metallic": metallic,
    }
    pressure = exhaust + order_family + intake + mechanical + metallic
    diagnostics = {
        "vehicle_id": "lfa",
        "scope": "synthetic; uncalibrated; not OEM reproduction",
        "provenance": "C/synthetic",
        "engine": "1LR-GUE 4.8L naturally aspirated V10",
        "firing_event_train": "V10 even-fire 72-degree event train",
        "events_per_rev": 5.0,
        "order_families": (5.0, 10.0, 15.0),
        "order_frequency_hz": {
            "5": rpm * 5.0 / 60.0,
            "10": rpm * 10.0 / 60.0,
            "15": rpm * 15.0 / 60.0,
        },
        "fixed_center_tone": False,
        "random_white_noise": False,
        "pipeline_position": "independent_source_before_pre_ptr_equalization",
        "high_rpm_growth_mean": float(np.mean(order_growth)),
        "stem_energy": {
            name: float(np.sum(np.square(stem))) for name, stem in stems.items()
        },
        "override_metrics": {
            "pulse_width_samples": float(_pulse_width_samples(sample_rate_hz, settings["pulse_width_scale"])),
            "phase_offset_deg": settings["phase_offset_deg"],
            "order_family_mix": settings["order_family_mix"],
            "intake_resonance_scale": settings["intake_resonance_scale"],
            "metallic_texture_scale": settings["metallic_texture_scale"],
            "high_rpm_growth_scale": settings["high_rpm_growth_scale"],
        },
        "active_overrides": dict(settings),
        "synthesis": "event-driven order-tracked V10; no fixed centre tone or random white noise",
    }
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def _settings(overrides: Mapping[str, float] | None) -> dict[str, float]:
    settings = dict(_DEFAULTS)
    if overrides is None:
        return settings
    unknown = set(overrides) - set(_DEFAULTS)
    if unknown:
        raise ValueError(f"unsupported LFA v2 overrides: {sorted(unknown)}")
    for name, value in overrides.items():
        numeric = float(value)
        low, high = _OVERRIDE_RANGES[name]
        if not np.isfinite(numeric) or not low <= numeric <= high:
            raise ValueError(f"{name} must be finite and in [{low}, {high}]")
        settings[name] = numeric
    return settings


def _resample_trace(
    trace: VehicleStateTrace,
    sample_rate_hz: int,
) -> tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    count = int(round((trace.time_s[-1] - trace.time_s[0]) * sample_rate_hz)) + 1
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    return (
        count,
        time_s,
        np.interp(time_s, trace.time_s, trace.rpm),
        np.interp(time_s, trace.time_s, trace.load),
        np.interp(time_s, trace.time_s, trace.throttle),
    )


def _v10_event_train(
    engine_phase: np.ndarray,
    load: np.ndarray,
    sample_rate_hz: int,
    pulse_width_scale: float,
) -> np.ndarray:
    """Produce a 72-degree (five events/revolution) V10 pulse train."""
    event_id = np.floor(engine_phase * 5.0).astype(np.int64)
    starts = np.flatnonzero(np.r_[True, np.diff(event_id) > 0])
    impulses = np.zeros(engine_phase.size, dtype=np.float64)
    impulses[starts] = 0.26 + 0.74 * load[starts]
    width = _pulse_width_samples(sample_rate_hz, pulse_width_scale)
    onset = np.arange(width, dtype=np.float64)
    pulse = np.exp(-onset / max(width * 0.30, 1.0)) - np.exp(-onset / max(width * 0.055, 1.0))
    peak = float(np.max(np.abs(pulse))) or 1.0
    return np.convolve(impulses, pulse / peak, mode="full")[: engine_phase.size]


def _pulse_width_samples(sample_rate_hz: int, pulse_width_scale: float) -> int:
    return max(3, int(round(sample_rate_hz * 0.0028 * pulse_width_scale)))


def _smooth_event_envelope(signal: np.ndarray, sample_rate_hz: int, duration_s: float) -> np.ndarray:
    width = max(1, int(round(sample_rate_hz * duration_s)))
    kernel = np.exp(-np.arange(width, dtype=np.float64) / max(width * 0.40, 1.0))
    kernel /= float(np.sum(kernel))
    return np.convolve(np.abs(signal), kernel, mode="full")[: signal.size]


def _to_stereo(mono: np.ndarray, crossfeed: float) -> np.ndarray:
    return np.column_stack((mono, crossfeed * mono))
