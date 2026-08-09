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
        2.0 * math.pi * (cylinder - 1) / config.cylinder_count
        for cylinder in config.firing_order
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
    firing_order_label = "firing_order=" + "-".join(
        str(cylinder) for cylinder in config.firing_order
    )
    frame_count = round(duration_s * config.sample_rate_hz)
    if frame_count <= 0:
        raise ValueError("duration_s is too short for the configured sample rate")
    firing_frequency_hz = (
        config.cylinder_count * config.rpm / (config.cycle_revolutions * 60.0)
    )
    crank_cycle_frequency_hz = config.rpm / (config.cycle_revolutions * 60.0)
    if (
        not math.isfinite(firing_frequency_hz)
        or firing_frequency_hz <= 0
        or not math.isfinite(crank_cycle_frequency_hz)
        or crank_cycle_frequency_hz <= 0
    ):
        raise ValueError("RPM must produce a positive finite firing frequency")

    pulses = [
        sum(
            math.exp(config.pulse_sharpness * (
                math.cos(
                    2.0 * math.pi * crank_cycle_frequency_hz * index
                    / config.sample_rate_hz - event_phase
                ) - 1.0
            ))
            # Canonical summation keeps a symmetric common-port aggregate
            # bit-identical for valid permutations of the same cylinders.
            for event_phase in sorted(firing_phases)
        )
        for index in range(frame_count)
    ]
    mean = sum(pulses) / len(pulses)
    centered = [sample - mean for sample in pulses]
    amplitude = lookup_operating_point(config.rpm, config.load).pressure_amplitude_pa
    peak = max(max(abs(value) for value in centered), 1e-12)
    scaled = [sample * amplitude / peak for sample in centered]
    return PressureTrace.uniform(
        "synthetic_four_stroke.v1:" + firing_order_label,
        scaled,
        config.sample_rate_hz,
        firing_frequency_hz,
        "engine_exhaust_port",
        SYNTHETIC_PROVENANCE + (firing_order_label,),
    )


def _profile_point(
    endpoints: tuple[EngineSourceConfig, ...], position: float, mode: str
) -> tuple[float, float]:
    if mode == "step":
        endpoint = endpoints[min(int(position * len(endpoints)), len(endpoints) - 1)]
        return endpoint.rpm, endpoint.load
    segment_position = position * (len(endpoints) - 1)
    segment = min(int(segment_position), len(endpoints) - 2)
    fraction = segment_position - segment
    start, stop = endpoints[segment], endpoints[segment + 1]
    return (
        start.rpm + (stop.rpm - start.rpm) * fraction,
        start.load + (stop.load - start.load) * fraction,
    )


def _validate_profile(
    endpoints: tuple[EngineSourceConfig, ...], frame_count: int, mode: str
) -> EngineSourceConfig:
    if len(endpoints) < 2 or frame_count < 2 or mode not in {"linear", "step"}:
        raise ValueError("profile requires two endpoints, two frames, and a supported mode")
    first = endpoints[0]
    shared = (
        "cylinder_count",
        "firing_order",
        "cycle_revolutions",
        "sample_rate_hz",
        "pulse_sharpness",
    )
    if any(
        any(getattr(endpoint, name) != getattr(first, name) for name in shared)
        for endpoint in endpoints[1:]
    ):
        raise ValueError("profile endpoints must share source geometry and sampling")
    if first.cycle_revolutions <= 0 or first.sample_rate_hz <= 0:
        raise ValueError("cycle revolutions and sample rate must be positive")
    _firing_phases(first)
    return first


def synthesize_four_stroke_profile(
    endpoints: tuple[EngineSourceConfig, ...], frame_count: int, mode: str
) -> PressureTrace:
    """Synthesize a zero-mean source across a time-varying operating profile."""
    first = _validate_profile(endpoints, frame_count, mode)
    phases = sorted(_firing_phases(first))
    crank_phase = 0.0
    raw: list[float] = []
    for index in range(frame_count):
        rpm, load = _profile_point(endpoints, index / (frame_count - 1), mode)
        crank_phase += 2.0 * math.pi * rpm / (
            first.cycle_revolutions * 60.0 * first.sample_rate_hz
        )
        pulse = sum(
            math.exp(first.pulse_sharpness * (math.cos(crank_phase - phase) - 1.0))
            for phase in phases
        )
        raw.append(pulse * lookup_operating_point(rpm, load).pressure_amplitude_pa)
    mean = sum(raw) / len(raw)
    centered = [value - mean for value in raw]
    peak = max(max(abs(value) for value in centered), 1e-12)
    amplitude = max(
        lookup_operating_point(endpoint.rpm, endpoint.load).pressure_amplitude_pa
        for endpoint in endpoints
    )
    scaled = [value * amplitude / peak for value in centered]
    return PressureTrace.uniform(
        "synthetic_four_stroke_profile.v1",
        scaled,
        first.sample_rate_hz,
        None,
        "engine_exhaust_port",
        SYNTHETIC_PROVENANCE
        + ("firing_frequency=variable", f"profile_mode={mode}"),
    )


def synthesize_four_stroke_trajectory(
    config: EngineSourceConfig,
    rpm_samples: tuple[float, ...],
    load_samples: tuple[float, ...],
) -> PressureTrace:
    """Synthesize a synthetic source from every vehicle-state RPM/load sample."""
    if (
        len(rpm_samples) < 2
        or len(rpm_samples) != len(load_samples)
        or not all(math.isfinite(value) and value > 0.0 for value in rpm_samples)
        or not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in load_samples)
    ):
        raise ValueError("vehicle-state trajectory requires aligned finite RPM/load samples")
    if config.cycle_revolutions <= 0 or config.sample_rate_hz <= 0:
        raise ValueError("cycle revolutions and sample rate must be positive")
    phases = sorted(_firing_phases(config))
    crank_phase = 0.0
    raw: list[float] = []
    for rpm, load in zip(rpm_samples, load_samples):
        crank_phase += 2.0 * math.pi * rpm / (
            config.cycle_revolutions * 60.0 * config.sample_rate_hz
        )
        pulse = sum(
            math.exp(config.pulse_sharpness * (math.cos(crank_phase - phase) - 1.0))
            for phase in phases
        )
        raw.append(pulse * lookup_operating_point(rpm, load).pressure_amplitude_pa)
    mean = sum(raw) / len(raw)
    centered = [value - mean for value in raw]
    amplitude = max(
        lookup_operating_point(rpm, load).pressure_amplitude_pa
        for rpm, load in zip(rpm_samples, load_samples)
    )
    peak = max(max(abs(value) for value in centered), 1.0e-12)
    scaled = [value * amplitude / peak for value in centered]
    return PressureTrace.uniform(
        "synthetic_four_stroke_trajectory.v1",
        scaled,
        config.sample_rate_hz,
        None,
        "engine_exhaust_port",
        SYNTHETIC_PROVENANCE + ("firing_frequency=variable", "profile_mode=vehicle_state"),
    )
