"""Continuous, deterministic vehicle-state inputs for S12 offline sound demos."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

from s12_engine_source import EngineSourceConfig


SAMPLE_RATE_HZ = 48000
SPEED_PER_RPM_MPS = 0.01
DEFAULT_CASES = ("idle", "cruise", "acceleration", "lift", "high_load")


def _finite(values: tuple[float, ...]) -> bool:
    return all(math.isfinite(value) for value in values)


@dataclass(frozen=True)
class VehicleStateSchedule:
    rpm: tuple[float, ...]
    load: tuple[float, ...]
    sample_rate_hz: int
    schedule_type: str = "vehicle_state"

    @property
    def frame_count(self) -> int:
        return len(self.rpm)

    @property
    def rpm_start(self) -> float:
        return self.rpm[0]

    def samples(self):
        return iter(zip(self.rpm, self.load))


@dataclass(frozen=True)
class VehicleStateSeries:
    case_id: str
    timestamp: tuple[float, ...]
    rpm: tuple[float, ...]
    speed: tuple[float, ...]
    acceleration: tuple[float, ...]
    load: tuple[float, ...]
    throttle: tuple[float, ...]
    sample_rate_hz: int = SAMPLE_RATE_HZ

    def validate(self) -> None:
        fields = (
            self.timestamp,
            self.rpm,
            self.speed,
            self.acceleration,
            self.load,
            self.throttle,
        )
        if (
            not self.case_id
            or self.sample_rate_hz != SAMPLE_RATE_HZ
            or len(self.timestamp) < 2
            or len({len(values) for values in fields}) != 1
            or not all(_finite(values) for values in fields)
            or min(self.rpm) <= 0.0
            or min(self.speed) < 0.0
            or any(not 0.0 <= value <= 1.0 for value in self.load + self.throttle)
        ):
            raise ValueError("vehicle state requires finite aligned 48 kHz values")
        interval_s = 1.0 / self.sample_rate_hz
        for index in range(1, len(self.timestamp)):
            if abs(self.timestamp[index] - self.timestamp[index - 1] - interval_s) > 1.0e-12:
                raise ValueError("vehicle state timestamps must be strictly uniform")
            if abs(self.load[index] - self.throttle[index]) > 1.0e-12:
                raise ValueError("synthetic load mapping requires load equal to throttle")
            expected_speed = self.rpm[index] * SPEED_PER_RPM_MPS
            if abs(self.speed[index] - expected_speed) > 1.0e-12:
                raise ValueError("speed must use the synthetic RPM mapping")
            expected_acceleration = (
                self.speed[index] - self.speed[index - 1]
            ) * self.sample_rate_hz
            if abs(self.acceleration[index] - expected_acceleration) > 1.0e-9:
                raise ValueError("acceleration must match the speed derivative")
        if abs(self.speed[0] - self.rpm[0] * SPEED_PER_RPM_MPS) > 1.0e-12:
            raise ValueError("speed must use the synthetic RPM mapping")
        if abs(self.acceleration[0] - self.acceleration[1]) > 1.0e-9:
            raise ValueError("first acceleration sample must be continuous")

    def to_order_schedule(self) -> VehicleStateSchedule:
        self.validate()
        return VehicleStateSchedule(self.rpm, self.load, self.sample_rate_hz)

    def source_config(self) -> EngineSourceConfig:
        self.validate()
        return EngineSourceConfig(self.rpm[0], self.load[0], sample_rate_hz=self.sample_rate_hz)

    def source_endpoints(self) -> tuple[EngineSourceConfig, EngineSourceConfig]:
        self.validate()
        return (
            EngineSourceConfig(self.rpm[0], self.load[0], sample_rate_hz=self.sample_rate_hz),
            EngineSourceConfig(self.rpm[-1], self.load[-1], sample_rate_hz=self.sample_rate_hz),
        )


def _linear_state(
    case_id: str,
    rpm_start: float,
    rpm_end: float,
    load_start: float,
    load_end: float,
    duration_s: float,
) -> VehicleStateSeries:
    frame_count = round(duration_s * SAMPLE_RATE_HZ)
    if frame_count < 2:
        raise ValueError("vehicle-state duration must contain two frames")
    denominator = frame_count - 1
    rpm = tuple(
        rpm_start + (rpm_end - rpm_start) * index / denominator for index in range(frame_count)
    )
    load = tuple(
        load_start + (load_end - load_start) * index / denominator for index in range(frame_count)
    )
    speed = tuple(value * SPEED_PER_RPM_MPS for value in rpm)
    acceleration_value = (speed[1] - speed[0]) * SAMPLE_RATE_HZ
    state = VehicleStateSeries(
        case_id,
        tuple(index / SAMPLE_RATE_HZ for index in range(frame_count)),
        rpm,
        speed,
        tuple(acceleration_value for _ in range(frame_count)),
        load,
        load,
    )
    state.validate()
    return state


def build_default_vehicle_state_cases() -> dict[str, VehicleStateSeries]:
    """Return the five bounded, synthetic operating trajectories for v0.3."""
    cases = {
        "idle": _linear_state("idle", 1000.0, 1000.0, 0.10, 0.10, 0.5),
        "cruise": _linear_state("cruise", 1800.0, 2600.0, 0.35, 0.50, 0.5),
        "acceleration": _linear_state("acceleration", 1000.0, 6000.0, 0.25, 0.95, 1.0),
        "lift": _linear_state("lift", 5000.0, 1800.0, 0.80, 0.10, 0.5),
        "high_load": _linear_state("high_load", 6000.0, 6000.0, 1.00, 1.00, 0.5),
    }
    if tuple(cases) != DEFAULT_CASES:
        raise RuntimeError("default vehicle-state cases changed")
    return cases


def build_load_mapping_cases() -> dict[str, VehicleStateSeries]:
    """Return fixed-RPM synthetic load comparisons for low/mid/high WAVs."""
    return {
        "low_load": _linear_state("low_load", 3000.0, 3000.0, 0.0, 0.0, 0.25),
        "mid_load": _linear_state("mid_load", 3000.0, 3000.0, 0.5, 0.5, 0.25),
        "high_load": _linear_state("high_load", 3000.0, 3000.0, 1.0, 1.0, 0.25),
    }


def _payload(cases: dict[str, VehicleStateSeries]) -> dict:
    if tuple(cases) != DEFAULT_CASES:
        raise ValueError("vehicle-state bundle requires the five default cases")
    for state in cases.values():
        state.validate()
    primary = cases["acceleration"]
    return {
        "acceleration": list(primary.acceleration),
        "case_id": primary.case_id,
        "cases": {
            name: {
                "timestamp": list(state.timestamp),
                "rpm": list(state.rpm),
                "speed": list(state.speed),
                "acceleration": list(state.acceleration),
                "load": list(state.load),
                "throttle": list(state.throttle),
            }
            for name, state in cases.items()
        },
        "load": list(primary.load),
        "rpm": list(primary.rpm),
        "schema": "s12.vehicle_state.v1",
        "speed": list(primary.speed),
        "synthetic_speed_mapping_mps_per_rpm": SPEED_PER_RPM_MPS,
        "throttle": list(primary.throttle),
        "timestamp": list(primary.timestamp),
    }


def write_vehicle_state_bundle(path: Path, cases: dict[str, VehicleStateSeries]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_payload(cases), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_vehicle_state_bundle(path: Path) -> dict[str, VehicleStateSeries]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        data.get("schema") != "s12.vehicle_state.v1"
        or data.get("synthetic_speed_mapping_mps_per_rpm") != SPEED_PER_RPM_MPS
        or not isinstance(data.get("cases"), dict)
        or set(data["cases"]) != set(DEFAULT_CASES)
        or data.get("case_id") != "acceleration"
        or not all(
            isinstance(data.get(field), list)
            for field in ("timestamp", "rpm", "speed", "acceleration", "load", "throttle")
        )
    ):
        raise ValueError("unsupported vehicle-state bundle")
    cases = {}
    for name in DEFAULT_CASES:
        values = data["cases"][name]
        if not isinstance(values, dict) or set(values) != {
            "timestamp",
            "rpm",
            "speed",
            "acceleration",
            "load",
            "throttle",
        }:
            raise ValueError("vehicle-state case has an invalid schema")
        state = VehicleStateSeries(
            name,
            *(
                tuple(float(value) for value in values[field])
                for field in ("timestamp", "rpm", "speed", "acceleration", "load", "throttle")
            ),
        )
        state.validate()
        cases[name] = state
    primary = VehicleStateSeries(
        data["case_id"],
        *(
            tuple(float(value) for value in data[field])
            for field in ("timestamp", "rpm", "speed", "acceleration", "load", "throttle")
        ),
    )
    primary.validate()
    if primary != cases["acceleration"]:
        raise ValueError("top-level vehicle-state interface disagrees with its named case")
    return cases
