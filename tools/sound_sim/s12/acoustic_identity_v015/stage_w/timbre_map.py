"""Deterministic RPM x load x boost timbre-map source branch."""

from __future__ import annotations

import numpy as np

from ..event_domain.config_schema import unwrap


def render_timbre_map(phase: np.ndarray, rpm: np.ndarray, load: np.ndarray, boost: np.ndarray, throttle: np.ndarray, config: dict, sample_counter: int = 0) -> dict[str, np.ndarray]:
    phase, rpm, load, boost, throttle = [np.asarray(value, dtype=np.float64) for value in (phase, rpm, load, boost, throttle)]
    if len({value.size for value in (phase, rpm, load, boost, throttle)}) != 1 or phase.ndim != 1 or not np.all(np.isfinite(np.column_stack((phase, rpm, load, boost, throttle)))):
        raise ValueError("timbre-map inputs must be equal finite vectors")
    kind = unwrap(config, "forced_induction.type")
    gain = float(unwrap(config, "forced_induction.gain"))
    ratio = float(unwrap(config, "forced_induction.ratio"))
    load = np.clip(load, 0.0, 1.0)
    boost = np.clip(boost, 0.0, 1.0)
    throttle = np.clip(throttle, 0.0, 1.0)
    shaft = phase * max(ratio, 1.0)
    drive = gain * (0.15 + 0.85 * boost) * (0.25 + 0.75 * load)
    harmonic = drive * (0.48 * np.sin(shaft) + 0.27 * np.sin(2.0 * shaft) + 0.16 * np.sin(3.0 * shaft) + 0.09 * np.sin(5.0 * shaft))
    sideband = drive * (0.16 + 0.24 * throttle) * (np.sin(shaft * 1.015 + 0.13 * np.sin(phase * 0.5)) + 0.5 * np.sin(shaft * 0.985))
    index = np.arange(phase.size, dtype=np.float64) + float(sample_counter)
    broadband = drive * (0.12 + 0.25 * boost) * (0.55 * np.sin(index * 0.017 + phase * 0.31) + 0.35 * np.sin(index * 0.041 + phase * 0.73) + 0.10 * np.sin(index * 0.097))
    casing = drive * (0.18 + 0.20 * load) * (np.sin(phase * 4.7 + 0.4) + 0.35 * np.sin(phase * 9.3))
    intake_gain = float(unwrap(config, "intake_model"))
    intake = intake_gain * np.sqrt(np.clip(load * (0.25 + throttle), 0.0, 1.5)) * (0.7 * np.sin(phase * 3.0 + 0.35) + 0.3 * np.sin(phase * 7.0))
    if kind == "supercharger":
        blower = np.column_stack((0.58 * harmonic, harmonic))
        turbo = np.zeros_like(blower)
    elif kind == "turbo":
        turbo = np.column_stack((0.55 * harmonic, harmonic))
        blower = np.zeros_like(turbo)
    else:
        blower = np.zeros((phase.size, 2), dtype=np.float64)
        turbo = np.zeros_like(blower)
    return {
        "blower": blower,
        "turbo": turbo,
        "sidebands": np.column_stack((0.55 * sideband, sideband)),
        "broadband": np.column_stack((0.70 * broadband, broadband)),
        "casing": np.column_stack((0.72 * casing, casing)),
        "intake": np.column_stack((0.52 * intake, intake)),
        "boost_state": boost.copy(),
        "blowoff": np.zeros((phase.size, 2), dtype=np.float64),
    }


__all__ = ["render_timbre_map"]
