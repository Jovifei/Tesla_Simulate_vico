"""Deterministic 100 Hz synthetic vehicle-state stream; no vehicle data source."""

from __future__ import annotations

from dataclasses import dataclass
import math


UPDATE_HZ = 100


@dataclass(frozen=True)
class VehicleState:
    """One normalized runtime control point in SI units except RPM."""

    timestamp_s: float
    rpm: float
    speed_mps: float
    acceleration_mps2: float
    load: float
    throttle: float

    def __post_init__(self) -> None:
        """Keep raw ingress values intact; EngineSoundRuntime owns safety fallback."""

    @classmethod
    def synthetic_idle(cls, timestamp_s: float) -> "VehicleState":
        return cls(timestamp_s, 800.0, 0.0, 0.0, 0.0, 0.0)


def _smoothstep(fraction: float) -> float:
    bounded = min(1.0, max(0.0, fraction))
    return bounded * bounded * (3.0 - 2.0 * bounded)


def _smoothstep_derivative(fraction: float) -> float:
    bounded = min(1.0, max(0.0, fraction))
    return 6.0 * bounded * (1.0 - bounded)


@dataclass(frozen=True)
class _Segment:
    start: float
    end: float
    start_rpm: float
    end_rpm: float
    start_speed_mps: float
    end_speed_mps: float
    start_load: float
    end_load: float

    def sample(self, normalized_time: float, duration_s: float) -> VehicleState:
        fraction = 0.0 if self.end == self.start else (normalized_time - self.start) / (self.end - self.start)
        blend = _smoothstep(fraction)
        derivative = _smoothstep_derivative(fraction) / ((self.end - self.start) * duration_s) if self.end > self.start else 0.0
        rpm = self.start_rpm + (self.end_rpm - self.start_rpm) * blend
        speed_mps = self.start_speed_mps + (self.end_speed_mps - self.start_speed_mps) * blend
        load = self.start_load + (self.end_load - self.start_load) * blend
        return VehicleState(
            normalized_time * duration_s,
            rpm,
            speed_mps,
            (self.end_speed_mps - self.start_speed_mps) * derivative,
            load,
            load,
        )


class RuntimeDriveCycle:
    """A continuous idle/cruise/acceleration/lift/high-load synthetic cycle."""

    def __init__(self, duration_s: float = 600.0) -> None:
        update_count = round(duration_s * UPDATE_HZ)
        if not math.isfinite(duration_s) or duration_s <= 0.0 or not math.isclose(duration_s * UPDATE_HZ, update_count, abs_tol=1.0e-9):
            raise ValueError("duration must be positive and aligned to the 100 Hz stream")
        self.duration_s = float(duration_s)
        self._update_count = update_count
        self._segments = (
            _Segment(0.00, 0.10, 800.0, 800.0, 0.0, 0.0, 0.0, 0.0),
            _Segment(0.10, 0.20, 800.0, 2000.0, 0.0, 60.0 / 3.6, 0.0, 0.30),
            _Segment(0.20, 0.40, 2000.0, 2000.0, 60.0 / 3.6, 60.0 / 3.6, 0.30, 0.30),
            _Segment(0.40, 0.58, 2000.0, 6000.0, 60.0 / 3.6, 130.0 / 3.6, 0.30, 0.95),
            _Segment(0.58, 0.68, 6000.0, 6000.0, 130.0 / 3.6, 130.0 / 3.6, 0.95, 0.95),
            _Segment(0.68, 0.80, 6000.0, 2000.0, 130.0 / 3.6, 70.0 / 3.6, 0.95, 0.05),
            _Segment(0.80, 0.90, 2000.0, 2000.0, 70.0 / 3.6, 70.0 / 3.6, 0.05, 0.30),
            _Segment(0.90, 1.00, 2000.0, 800.0, 70.0 / 3.6, 0.0, 0.30, 0.0),
        )

    def sample_at(self, timestamp_s: float) -> VehicleState:
        if not math.isfinite(timestamp_s) or not 0.0 <= timestamp_s <= self.duration_s:
            raise ValueError("timestamp is outside the drive-cycle duration")
        normalized_time = timestamp_s / self.duration_s
        for segment in self._segments:
            if segment.start <= normalized_time <= segment.end:
                return segment.sample(normalized_time, self.duration_s)
        raise ValueError("drive-cycle segment is unavailable")

    def iter_updates(self):
        for index in range(self._update_count + 1):
            yield self.sample_at(index / UPDATE_HZ)
