"""Deterministic, offline synthetic four-stroke S12 pressure source."""

from __future__ import annotations

from dataclasses import dataclass
import math

from s12_acoustic_audition import PressureTrace
from s12_operating_points import lookup_operating_point


SYNTHETIC_PROVENANCE = (
    "synthetic",
    "uncalibrated",
    "offline",
    "not_realtime_qualified",
)


@dataclass(frozen=True)
class EngineSourceConfig:
    rpm: float
    load: float
    cylinder_count: int = 4
    firing_order: tuple[int, ...] = (1, 3, 4, 2)
    cycle_revolutions: int = 2
    sample_rate_hz: int = 48000
    pulse_sharpness: float = 4.0


def _firing_phases(config: EngineSourceConfig) -> tuple[float, ...]:
    if (
        config.cylinder_count <= 0
        or len(config.firing_order) != config.cylinder_count
        or set(config.firing_order) != set(range(1, config.cylinder_count + 1))
    ):
        raise ValueError("firing order must contain each cylinder exactly once")
    return tuple(
        2.0 * math.pi * index / config.cylinder_count
        for index, _cylinder in enumerate(config.firing_order)
    )


def synthesize_four_stroke(
    config: EngineSourceConfig, duration_s: float
) -> PressureTrace:
    """Synthesize a repeatable zero-mean pulse train from a synthetic grid."""
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    if config.cycle_revolutions <= 0 or config.sample_rate_hz <= 0:
        raise ValueError("cycle revolutions and sample rate must be positive")

    firing_phases = _firing_phases(config)
    frame_count = round(duration_s * config.sample_rate_hz)
    if frame_count <= 0:
        raise ValueError("duration_s is too short for the configured sample rate")
    firing_frequency_hz = (
        config.cylinder_count * config.rpm / (config.cycle_revolutions * 60.0)
    )
    if not math.isfinite(firing_frequency_hz) or firing_frequency_hz <= 0:
        raise ValueError("RPM must produce a positive finite firing frequency")

    pulses = [
        sum(
            math.exp(
                config.pulse_sharpness
                * (math.cos(2.0 * math.pi * firing_frequency_hz * index / config.sample_rate_hz - event_phase) - 1.0)
            )
            for event_phase in firing_phases
        )
        for index in range(frame_count)
    ]
    mean = sum(pulses) / len(pulses)
    centered = [sample - mean for sample in pulses]
    amplitude = lookup_operating_point(config.rpm, config.load).pressure_amplitude_pa
    peak = max(max(abs(value) for value in centered), 1e-12)
    scaled = [sample * amplitude / peak for sample in centered]
    return PressureTrace.uniform(
        "synthetic_four_stroke.v1",
        scaled,
        config.sample_rate_hz,
        firing_frequency_hz,
        "engine_exhaust_port",
        SYNTHETIC_PROVENANCE,
    )
