"""Future-App JSON ingress simulation; no server or device connection is opened."""

from __future__ import annotations

import json
import math
from typing import Mapping

from vehicle_state_runtime.stream import VehicleState


def _number(payload: Mapping[str, object], name: str) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"App vehicle-state field {name!r} must be numeric")
    return float(value)


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def parse_app_vehicle_state(payload: Mapping[str, object] | str) -> VehicleState:
    """Map the documented future App payload to C/synthetic runtime controls.

    ``speed`` is km/h, acceleration is m/s², and timestamp is seconds.  RPM and
    load may be supplied directly; absent values use the documented synthetic
    fallback only for this PC simulator.
    """
    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("App vehicle-state payload must be valid JSON") from error
        if not isinstance(decoded, dict):
            raise ValueError("App vehicle-state payload must be a JSON object")
        payload = decoded
    speed_kmh = _number(payload, "speed")
    acceleration_mps2 = _number(payload, "acceleration")
    timestamp_s = _number(payload, "timestamp")
    rpm = _number(payload, "rpm") if "rpm" in payload else 800.0 + speed_kmh * 20.0 + acceleration_mps2 * 100.0
    load = _number(payload, "load") if "load" in payload else 0.30 + acceleration_mps2 * 0.10
    throttle = _number(payload, "throttle") if "throttle" in payload else load
    if all(math.isfinite(value) for value in (speed_kmh, acceleration_mps2, timestamp_s, rpm, load, throttle)):
        rpm = _clamp(rpm, 800.0, 6000.0)
        load = _clamp(load, 0.0, 1.0)
        throttle = _clamp(throttle, 0.0, 1.0)
    return VehicleState(timestamp_s, rpm, speed_kmh / 3.6, acceleration_mps2, load, throttle)
