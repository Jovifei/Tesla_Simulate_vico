"""Fit a fixture HarmonicTimbreMap from synthetic Hellcat cycles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..stage_w.timbre_map import TimbreMap4D

MAP_SCHEMA = "s12.stage_y.harmonic_timbre_map.v1"
MAP_BOUNDARY = {
    "fixture_scope": "FIXTURE_ONLY",
    "oem_status": "NOT_OEM",
    "tuning_authority": "NOT_TUNING_AUTHORITY",
}
MAP_PATH = Path(__file__).resolve().parent / "data" / "hellcat_fixture_timbre_map.json"
_MAP_KEYS = {
    "schema", "vehicle_id", "source", "rpm_axis", "load_axis", "boost_axis",
    "order_axis", "amplitude", "fixture_sha256", "created_from_commit", "boundary",
}


def _fixture_sha256(bank: dict[str, Any], rpm_axis: np.ndarray) -> str:
    return hashlib.sha256(
        b"".join(np.asarray(bank["cycles"][float(rpm)], dtype=np.float64).tobytes() for rpm in rpm_axis)
    ).hexdigest()


def _strict_axis(payload: dict[str, Any], name: str) -> np.ndarray:
    value = payload.get(name)
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a JSON array")
    try:
        axis = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must contain finite numbers") from None
    if axis.ndim != 1 or axis.size < 2 or not np.all(np.isfinite(axis)) or np.any(np.diff(axis) <= 0.0):
        raise ValueError(f"{name} must be finite and strictly increasing")
    return axis


def validate_fitted_timbre_map(payload: Any) -> TimbreMap4D:
    """Validate the committed synthetic-only map and return its interpolation table."""
    if not isinstance(payload, dict) or set(payload) != _MAP_KEYS:
        raise ValueError("invalid fitted HarmonicTimbreMap inventory")
    if payload["schema"] != MAP_SCHEMA or payload["vehicle_id"] != "hellcat" or payload["source"] != "synthetic_fixture":
        raise ValueError("unsupported fitted HarmonicTimbreMap identity")
    if payload["boundary"] != MAP_BOUNDARY:
        raise ValueError("fitted HarmonicTimbreMap boundary metadata is invalid")
    fixture_sha = payload["fixture_sha256"]
    source_commit = payload["created_from_commit"]
    if not isinstance(fixture_sha, str) or len(fixture_sha) != 64 or any(char not in "0123456789abcdef" for char in fixture_sha):
        raise ValueError("fixture_sha256 must be a lowercase SHA-256")
    if not isinstance(source_commit, str) or len(source_commit) != 40 or any(char not in "0123456789abcdef" for char in source_commit):
        raise ValueError("created_from_commit must be a lowercase commit SHA")
    axes = tuple(_strict_axis(payload, name) for name in ("rpm_axis", "load_axis", "boost_axis", "order_axis"))
    try:
        amplitude = np.asarray(payload["amplitude"], dtype=np.float64)
    except (TypeError, ValueError):
        raise ValueError("amplitude must be a finite numeric array") from None
    if amplitude.shape != tuple(axis.size for axis in axes) or not np.all(np.isfinite(amplitude)) or np.any(amplitude < 0.0):
        raise ValueError("amplitude must match axes and be finite/nonnegative")
    return TimbreMap4D(*axes, amplitude)


def fit_harmonic_map(bank: dict, vehicle_id: str = "hellcat") -> dict:
    sample_rate = int(bank["sample_rate_hz"])
    rpm_axis = np.array(sorted(bank["cycles"].keys()), dtype=np.float64)
    load_axis = np.array([0.2, 0.6, 1.0], dtype=np.float64)
    boost_axis = np.array([0.0, 0.5, 1.0], dtype=np.float64)
    order_axis = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
    amplitude = np.zeros((rpm_axis.size, load_axis.size, boost_axis.size, order_axis.size), dtype=np.float64)
    for rpm_index, rpm in enumerate(rpm_axis):
        cycle = np.asarray(bank["cycles"][float(rpm)], dtype=np.float64)
        mono = cycle.mean(axis=1)
        spectrum = np.abs(np.fft.rfft(mono))
        freqs = np.fft.rfftfreq(mono.size, 1.0 / sample_rate)
        firing_hz = float(rpm) / 60.0 * 4.0
        for order_index, order in enumerate(order_axis):
            target = firing_hz * float(order)
            bin_index = int(np.argmin(np.abs(freqs - target)))
            base = float(spectrum[bin_index])
            for load_index, load in enumerate(load_axis):
                for boost_index, boost in enumerate(boost_axis):
                    amplitude[rpm_index, load_index, boost_index, order_index] = base * (0.4 + 0.6 * load) * (0.5 + 0.5 * boost)
    fixture_sha = _fixture_sha256(bank, rpm_axis)
    return {
        "schema": MAP_SCHEMA,
        "vehicle_id": vehicle_id,
        "source": "synthetic_fixture",
        "rpm_axis": rpm_axis.tolist(),
        "load_axis": load_axis.tolist(),
        "boost_axis": boost_axis.tolist(),
        "order_axis": order_axis.tolist(),
        "amplitude": amplitude.tolist(),
        "fixture_sha256": fixture_sha,
    }


def build_committed_fixture_timbre_map(path: str | Path = MAP_PATH, *, created_from_commit: str) -> dict[str, Any]:
    """Fit and serialize the compact synthetic fixture map without embedding PCM."""
    if not isinstance(created_from_commit, str) or len(created_from_commit) != 40 or any(char not in "0123456789abcdef" for char in created_from_commit):
        raise ValueError("created_from_commit must be a lowercase commit SHA")
    from .fixture_cycles import synthesize_hellcat_cycle_bank

    mapped = fit_harmonic_map(synthesize_hellcat_cycle_bank(), vehicle_id="hellcat")
    payload = {
        **mapped,
        "created_from_commit": created_from_commit,
        "boundary": dict(MAP_BOUNDARY),
    }
    validate_fitted_timbre_map(payload)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    return payload


def load_committed_fixture_timbre_map(path: str | Path = MAP_PATH) -> tuple[dict[str, Any], TimbreMap4D]:
    """Load the committed map fail-closed; malformed or missing files always raise."""
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load fitted HarmonicTimbreMap: {target}") from exc
    table = validate_fitted_timbre_map(payload)
    from .fixture_cycles import synthesize_hellcat_cycle_bank
    expected_fixture_sha = _fixture_sha256(synthesize_hellcat_cycle_bank(), table.rpm_axis)
    if payload["fixture_sha256"] != expected_fixture_sha:
        raise ValueError("fitted HarmonicTimbreMap fixture SHA differs from deterministic source")
    return payload, table


__all__ = [
    "MAP_BOUNDARY", "MAP_PATH", "MAP_SCHEMA", "build_committed_fixture_timbre_map",
    "fit_harmonic_map", "load_committed_fixture_timbre_map", "validate_fitted_timbre_map",
]
