"""Load and interpolate the v0.5 synthetic operating-point library."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


LIBRARY_PATH = Path(__file__).with_name("engine_operating_point_library.json")


def _canonical_hash(payload: dict) -> str:
    canonical = dict(payload)
    canonical.pop("hash", None)
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _provenance_entries(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = [value] if "source_level" in value else []
        for child in value.values():
            entries.extend(_provenance_entries(child))
        return entries
    if isinstance(value, list):
        return [entry for child in value for entry in _provenance_entries(child)]
    return []


@dataclass(frozen=True)
class OperatingPointParameters:
    rpm: float
    load: float
    excitation_gain: float
    harmonic_gain: float
    transient_gain: float


@dataclass(frozen=True)
class OperatingPointLibrary:
    raw: dict
    rpm_grid: tuple[float, ...]
    load_grid: tuple[float, ...]
    library_hash: str
    provenance_entries: tuple[dict, ...]

    @property
    def source_level(self) -> str:
        return str(self.raw["provenance"]["source_level"])

    def canonical_hash(self) -> str:
        return _canonical_hash(self.raw)

    def evaluate(self, rpm: float, load: float) -> OperatingPointParameters:
        if not math.isfinite(rpm) or not math.isfinite(load):
            raise ValueError("RPM and load must be finite")
        if (
            not self.rpm_grid[0] <= rpm <= self.rpm_grid[-1]
            or not self.load_grid[0] <= load <= self.load_grid[-1]
        ):
            raise ValueError("RPM/load is outside the documented synthetic grid")
        rpm_low, rpm_high = _bounds(self.rpm_grid, rpm)
        load_low, load_high = _bounds(self.load_grid, load)
        return OperatingPointParameters(
            rpm,
            load,
            self._interpolate("excitation_gain", rpm_low, rpm_high, load_low, load_high, rpm, load),
            self._interpolate("harmonic_gain", rpm_low, rpm_high, load_low, load_high, rpm, load),
            self._interpolate("transient_gain", rpm_low, rpm_high, load_low, load_high, rpm, load),
        )

    def _interpolate(
        self,
        name: str,
        rpm_low: float,
        rpm_high: float,
        load_low: float,
        load_high: float,
        rpm: float,
        load: float,
    ) -> float:
        table = self.raw["excitation_parameters"][name]["values"]
        lower = _blend(
            table[self.rpm_grid.index(rpm_low)][self.load_grid.index(load_low)],
            table[self.rpm_grid.index(rpm_low)][self.load_grid.index(load_high)],
            _fraction(load_low, load_high, load),
        )
        upper = _blend(
            table[self.rpm_grid.index(rpm_high)][self.load_grid.index(load_low)],
            table[self.rpm_grid.index(rpm_high)][self.load_grid.index(load_high)],
            _fraction(load_low, load_high, load),
        )
        return _blend(lower, upper, _fraction(rpm_low, rpm_high, rpm))


def _bounds(grid: tuple[float, ...], value: float) -> tuple[float, float]:
    for lower, upper in zip(grid, grid[1:]):
        if lower <= value <= upper:
            return lower, upper
    return grid[-1], grid[-1]


def _fraction(lower: float, upper: float, value: float) -> float:
    return 0.0 if lower == upper else (value - lower) / (upper - lower)


def _blend(lower: float, upper: float, fraction: float) -> float:
    return float(lower) + (float(upper) - float(lower)) * fraction


def load_operating_point_library(path: Path = LIBRARY_PATH) -> OperatingPointLibrary:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema") != "s12.engine_operating_point_library.v01":
        raise ValueError("unsupported operating-point schema")
    entries = tuple(_provenance_entries(raw))
    if not entries or any(
        entry.get("source_level") not in {"A", "B", "C"}
        or not entry.get("source")
        or not entry.get("description")
        for entry in entries
    ):
        raise ValueError("operating-point provenance is incomplete")
    digest = _canonical_hash(raw)
    if raw.get("hash") != digest:
        raise ValueError("operating-point library hash mismatch")
    rpm_grid = tuple(float(value) for value in raw["rpm_grid"]["values"])
    load_grid = tuple(float(value) for value in raw["load_grid"]["values"])
    if (
        rpm_grid != tuple(sorted(rpm_grid))
        or load_grid != tuple(sorted(load_grid))
        or len(set(rpm_grid)) != len(rpm_grid)
        or len(set(load_grid)) != len(load_grid)
    ):
        raise ValueError("operating-point grids must be strictly increasing")
    for name in ("excitation_gain", "harmonic_gain", "transient_gain"):
        table = raw["excitation_parameters"][name]["values"]
        if len(table) != len(rpm_grid) or any(len(row) != len(load_grid) for row in table):
            raise ValueError("operating-point table dimensions do not match grids")
    return OperatingPointLibrary(raw, rpm_grid, load_grid, digest, entries)
