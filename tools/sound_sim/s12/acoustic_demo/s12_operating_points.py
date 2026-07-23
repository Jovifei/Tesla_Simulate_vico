"""Synthetic, uncalibrated S12 operating-point amplitudes."""

from __future__ import annotations

from dataclasses import dataclass


RPM_GRID = (2000.0, 4000.0, 6000.0)
LOAD_GRID = (0.25, 0.60, 1.00)
PRESSURE_AMPLITUDE_PA = (
    (1.5, 3.5, 6.0),
    (2.0, 4.5, 7.0),
    (2.5, 5.0, 8.0),
)


@dataclass(frozen=True)
class OperatingPoint:
    rpm: float
    load: float
    pressure_amplitude_pa: float


def _enclosing(grid: tuple[float, ...], value: float) -> tuple[float, float]:
    if value in grid:
        return value, value
    for lower, upper in zip(grid, grid[1:]):
        if lower <= value <= upper:
            return lower, upper
    raise ValueError("value is outside the documented synthetic grid")


def _grid_value(rpm: float, load: float) -> float:
    return PRESSURE_AMPLITUDE_PA[RPM_GRID.index(rpm)][LOAD_GRID.index(load)]


def lookup_operating_point(rpm: float, load: float) -> OperatingPoint:
    """Return the exact or bilinearly interpolated synthetic amplitude."""
    if not 2000.0 <= rpm <= 6000.0 or not 0.25 <= load <= 1.00:
        raise ValueError("RPM/load is outside the documented synthetic grid")

    lower_rpm, upper_rpm = _enclosing(RPM_GRID, rpm)
    lower_load, upper_load = _enclosing(LOAD_GRID, load)
    rpm_fraction = (
        0.0
        if lower_rpm == upper_rpm
        else (rpm - lower_rpm) / (upper_rpm - lower_rpm)
    )
    load_fraction = (
        0.0
        if lower_load == upper_load
        else (load - lower_load) / (upper_load - lower_load)
    )
    low = (
        (1.0 - load_fraction) * _grid_value(lower_rpm, lower_load)
        + load_fraction * _grid_value(lower_rpm, upper_load)
    )
    high = (
        (1.0 - load_fraction) * _grid_value(upper_rpm, lower_load)
        + load_fraction * _grid_value(upper_rpm, upper_load)
    )
    return OperatingPoint(
        rpm=rpm,
        load=load,
        pressure_amplitude_pa=(1.0 - rpm_fraction) * low + rpm_fraction * high,
    )
