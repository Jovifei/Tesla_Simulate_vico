"""Deterministic C/synthetic 100 Hz external vehicle-state stream."""

from __future__ import annotations

from dataclasses import dataclass
import math

from vehicle_interface.packet import VehicleStatePacket


UPDATE_HZ = 100


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
    rpm_start: float
    rpm_end: float
    speed_start_kmh: float
    speed_end_kmh: float
    load_start: float
    load_end: float

    def sample(self, timestamp_s: float, duration_s: float) -> VehicleStatePacket:
        normalized = timestamp_s / duration_s
        fraction = (normalized - self.start) / (self.end - self.start)
        blend = _smoothstep(fraction)
        derivative = _smoothstep_derivative(fraction) / ((self.end - self.start) * duration_s)
        rpm = self.rpm_start + (self.rpm_end - self.rpm_start) * blend
        speed_kmh = self.speed_start_kmh + (self.speed_end_kmh - self.speed_start_kmh) * blend
        load = self.load_start + (self.load_end - self.load_start) * blend
        acceleration_mps2 = ((self.speed_end_kmh - self.speed_start_kmh) / 3.6) * derivative
        return VehicleStatePacket(timestamp_s, rpm, speed_kmh, acceleration_mps2, load, load)


class SyntheticVehicleStateStream:
    """Continuous idle, cruise, lift and 1500-to-6000 RPM synthetic stream."""

    def __init__(self, duration_s: float = 600.0) -> None:
        update_count = round(duration_s * UPDATE_HZ)
        if not math.isfinite(duration_s) or duration_s <= 0.0 or not math.isclose(duration_s * UPDATE_HZ, update_count, abs_tol=1.0e-9):
            raise ValueError("duration must be a positive 100 Hz multiple")
        self.duration_s = float(duration_s)
        self.update_count = update_count
        self._segments = (
            _Segment(0.00, 0.15, 800.0, 800.0, 0.0, 0.0, 0.0, 0.0),
            _Segment(0.15, 0.30, 800.0, 2200.0, 0.0, 60.0, 0.0, 0.30),
            _Segment(0.30, 0.45, 2200.0, 2200.0, 60.0, 60.0, 0.30, 0.30),
            _Segment(0.45, 0.55, 2200.0, 1500.0, 60.0, 45.0, 0.30, 0.05),
            _Segment(0.55, 0.75, 1500.0, 6000.0, 45.0, 130.0, 0.05, 0.95),
            _Segment(0.75, 0.87, 6000.0, 6000.0, 130.0, 130.0, 0.95, 0.95),
            _Segment(0.87, 1.00, 6000.0, 800.0, 130.0, 0.0, 0.95, 0.0),
        )

    def packet_at(self, timestamp_s: float) -> VehicleStatePacket:
        if not math.isfinite(timestamp_s) or not 0.0 <= timestamp_s < self.duration_s:
            raise ValueError("timestamp is outside the stream duration")
        normalized = timestamp_s / self.duration_s
        for segment in self._segments:
            if segment.start <= normalized < segment.end:
                return segment.sample(timestamp_s, self.duration_s)
        raise RuntimeError("stream segment is unavailable")

    def iter_packets(self):
        for index in range(self.update_count):
            yield self.packet_at(index / UPDATE_HZ)
