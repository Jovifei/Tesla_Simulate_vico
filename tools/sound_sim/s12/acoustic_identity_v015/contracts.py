"""Small, strict data contracts shared by future v0.15 source modules."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class VehicleStateTrace:
    """A synchronized offline vehicle-state timeline for one source renderer."""

    time_s: np.ndarray
    rpm: np.ndarray
    load: np.ndarray
    throttle: np.ndarray
    acceleration_mps2: np.ndarray

    def validate(self) -> "VehicleStateTrace":
        arrays = {
            "time_s": self.time_s,
            "rpm": self.rpm,
            "load": self.load,
            "throttle": self.throttle,
            "acceleration_mps2": self.acceleration_mps2,
        }
        normalized = {name: np.asarray(value, dtype=np.float64) for name, value in arrays.items()}
        lengths = set()
        for name, value in normalized.items():
            if value.ndim != 1:
                raise ValueError(f"{name} must be a one-dimensional array")
            if value.size == 0:
                raise ValueError(f"{name} must not be empty")
            lengths.add(value.size)
        if len(lengths) != 1:
            raise ValueError("VehicleStateTrace arrays must have equal lengths")
        if not np.all(np.isfinite(normalized["time_s"])):
            raise ValueError("time_s must be finite")
        if not np.all(np.diff(normalized["time_s"]) > 0.0):
            raise ValueError("time_s must be strictly increasing")
        for name, value in normalized.items():
            if name != "time_s" and not np.all(np.isfinite(value)):
                raise ValueError(f"{name} must be finite")
        if np.any(normalized["rpm"] < 0.0):
            raise ValueError("rpm must be >= 0")
        for name in ("load", "throttle"):
            if np.any((normalized[name] < 0.0) | (normalized[name] > 1.0)):
                raise ValueError(f"{name} must be in [0, 1]")
        return self


@dataclass(frozen=True)
class SourceRender:
    """Finite stereo pre-PTR pressure and independently named stereo stems."""

    pressure: np.ndarray
    stems: Mapping[str, np.ndarray]
    diagnostics: Mapping[str, object]

    def validate(self) -> "SourceRender":
        pressure = np.asarray(self.pressure, dtype=np.float64)
        if pressure.ndim != 2 or pressure.shape[1:] != (2,):
            raise ValueError("pressure must have shape [N, 2]")
        if pressure.shape[0] == 0:
            raise ValueError("pressure must not be empty")
        if not np.all(np.isfinite(pressure)):
            raise ValueError("pressure must be finite")
        if not self.stems:
            raise ValueError("stems must contain at least one named stereo stem")
        for name, stem in self.stems.items():
            if not isinstance(name, str) or not name:
                raise ValueError("stems must use non-empty string names")
            stereo_stem = np.asarray(stem, dtype=np.float64)
            if stereo_stem.shape != pressure.shape:
                raise ValueError(f"stem {name!r} must have shape [N, 2] matching pressure")
            if not np.all(np.isfinite(stereo_stem)):
                raise ValueError(f"stem {name!r} must be finite")
        return self


@dataclass(frozen=True)
class ResearchDatabase:
    """Read-only v0.15 reference topology and C-level target records."""

    vehicles: Mapping[str, Mapping[str, object]]
    synthesis_targets: Mapping[str, Mapping[str, object]]


def load_research_database() -> ResearchDatabase:
    """Load the versioned research data shipped with the v0.15 package."""
    root = Path(__file__).resolve().parent
    reference_payload = _read_json(root / "reference_database" / "vehicle_records.json")
    targets_payload = _read_json(root / "targets" / "synthesis_targets.json")
    return ResearchDatabase(
        vehicles=reference_payload["vehicles"],
        synthesis_targets=targets_payload["vehicles"],
    )


def _read_json(path: Path) -> Mapping[str, object]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)
