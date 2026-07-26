"""External v0.7 packet contract mapped to the existing runtime state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from vehicle_state_runtime.stream import VehicleState


VEHICLE_STATE_PACKET_SCHEMA_PATH = Path(__file__).with_name("vehicle_state_packet.json")
_FIELDS = ("timestamp", "rpm", "speed", "acceleration", "load", "throttle")


def _number(payload: Mapping[str, object], name: str) -> float:
    if name not in payload:
        raise ValueError(f"vehicle-state packet requires {name!r}")
    value = payload[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"vehicle-state packet field {name!r} must be numeric")
    return float(value)


@dataclass(frozen=True)
class VehicleStatePacket:
    """C/synthetic external control packet; numeric safety is handled by v0.6."""

    timestamp_s: float
    rpm: float
    speed_kmh: float
    acceleration_mps2: float
    load: float
    throttle: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "VehicleStatePacket":
        if not isinstance(payload, Mapping):
            raise ValueError("vehicle-state packet must be a JSON object")
        return cls(*(_number(payload, field) for field in _FIELDS))

    def to_runtime_state(self) -> VehicleState:
        return VehicleState(
            self.timestamp_s,
            self.rpm,
            self.speed_kmh / 3.6,
            self.acceleration_mps2,
            self.load,
            self.throttle,
        )

    def as_mapping(self) -> dict[str, float]:
        return {
            "timestamp": self.timestamp_s,
            "rpm": self.rpm,
            "speed": self.speed_kmh,
            "acceleration": self.acceleration_mps2,
            "load": self.load,
            "throttle": self.throttle,
        }
