"""Deterministic 100 Hz Vehicle-State traces for the Stage-V source slice."""

from __future__ import annotations

from typing import Final

import numpy as np

from ..contracts import VehicleStateTrace

STATE_RATE_HZ: Final[int] = 100
STAGE_V_SCENARIOS: Final[tuple[str, ...]] = (
    "hot_idle_20s",
    "steady_1500_2500rpm",
    "full_load_acceleration",
    "high_rpm_lift_to_idle",
    "afterfire_eligible_lift",
)

_PROFILES: dict[str, tuple[float, float]] = {
    "hellcat_v1": (850.0, 6500.0),
    "ferrari_458_v1": (1050.0, 9000.0),
    "rx7_fd_v1": (900.0, 8000.0),
}


def build_stage_v_scenario_trace(
    vehicle_id: str,
    scenario_id: str,
    duration_s: float | None = None,
) -> VehicleStateTrace:
    """Build one state-bound scenario; audio rendering interpolates this at 48 kHz."""

    if vehicle_id not in _PROFILES:
        raise ValueError(f"unsupported Stage-V vehicle: {vehicle_id!r}")
    if scenario_id not in STAGE_V_SCENARIOS:
        raise ValueError(f"unsupported Stage-V scenario: {scenario_id!r}")
    default_duration = 20.0 if scenario_id == "hot_idle_20s" else 8.0
    duration = default_duration if duration_s is None else float(duration_s)
    if not np.isfinite(duration) or duration < 0.2:
        raise ValueError("duration_s must be finite and >= 0.2")
    idle_rpm, redline_rpm = _PROFILES[vehicle_id]
    count = max(2, int(round(duration * STATE_RATE_HZ)) + 1)
    time_s = np.linspace(0.0, duration, count, dtype=np.float64)
    phase = time_s / duration

    if scenario_id == "hot_idle_20s":
        ripple = 4.0 * np.sin(2.0 * np.pi * 2.7 * time_s) + 1.5 * np.sin(2.0 * np.pi * 5.1 * time_s + 0.4)
        rpm = idle_rpm + ripple
        load = np.full(count, 0.18)
        throttle = np.full(count, 0.18)
    elif scenario_id == "steady_1500_2500rpm":
        rpm = np.linspace(1500.0, 2500.0, count)
        load = np.full(count, 0.34)
        throttle = np.full(count, 0.36)
    elif scenario_id == "full_load_acceleration":
        rpm = np.linspace(max(1500.0, 0.28 * redline_rpm), 0.94 * redline_rpm, count)
        load = np.linspace(0.42, 0.96, count)
        throttle = np.clip(load + 0.04, 0.0, 1.0)
    elif scenario_id == "high_rpm_lift_to_idle":
        high = 0.88 * redline_rpm
        close = phase >= 0.40
        rpm = np.where(close, np.linspace(high, idle_rpm, count), high)
        load = np.where(close, 0.10, 0.86)
        throttle = np.where(close, 0.02, 0.92)
    else:
        high = 0.88 * redline_rpm
        close = phase >= 0.40
        late = phase >= 0.62
        rpm = np.where(close, np.linspace(high, idle_rpm, count), high)
        load = np.where(close, np.where(late, 0.12, 0.55), 0.86)
        throttle = np.where(close, 0.02, 0.92)

    acceleration = np.gradient(rpm / 60.0, time_s)
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


__all__ = ["STATE_RATE_HZ", "STAGE_V_SCENARIOS", "build_stage_v_scenario_trace"]
