"""Future-App JSON ingress simulation; no server or device connection is opened."""

from __future__ import annotations

import json
import math
from typing import Mapping

from vehicle_state_runtime.stream import VehicleState


def _finite_number(payload: Mapping[str, object], name: str) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"App vehicle-state field {name!r} must be finite")
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
    speed_kmh = _finite_number(payload, "speed")
    acceleration_mps2 = _finite_number(payload, "acceleration")
    timestamp_s = _finite_number(payload, "timestamp")
    if speed_kmh < 0.0 or timestamp_s < 0.0:
        raise ValueError("App speed and timestamp must be nonnegative")
    rpm = _finite_number(payload, "rpm") if "rpm" in payload else _clamp(800.0 + speed_kmh * 20.0 + acceleration_mps2 * 100.0, 800.0, 6000.0)
    load = _finite_number(payload, "load") if "load" in payload else _clamp(0.30 + acceleration_mps2 * 0.10, 0.0, 1.0)
    throttle = _finite_number(payload, "throttle") if "throttle" in payload else load
    return VehicleState(timestamp_s, rpm, speed_kmh / 3.6, acceleration_mps2, load, throttle)
