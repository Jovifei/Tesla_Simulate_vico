"""Synthetic, uncalibrated S12 operating-point amplitudes (not OEM data)."""

from __future__ import annotations

from dataclasses import dataclass


RPM_GRID = (800.0, 1200.0, 2000.0, 4000.0, 6000.0)
LOAD_GRID = (0.00, 0.25, 0.60, 1.00)
PRESSURE_AMPLITUDE_PA = (
    (0.50, 0.80, 2.00, 4.00),
    (0.60, 0.90, 2.50, 4.50),
    (0.80, 1.50, 3.50, 6.00),
    (1.00, 2.00, 4.50, 7.00),
    (1.20, 2.50, 5.00, 8.00),
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
    if not RPM_GRID[0] <= rpm <= RPM_GRID[-1] or not LOAD_GRID[0] <= load <= LOAD_GRID[-1]:
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
