"""Deterministic RPM x load x boost timbre-map source branch."""

from __future__ import annotations

import numpy as np

from ..event_domain.config_schema import unwrap


class TimbreMap4D:
    """Bounded RPM × load × boost × order table with deterministic interpolation."""

    def __init__(self, rpm_axis: np.ndarray, load_axis: np.ndarray, boost_axis: np.ndarray, order_axis: np.ndarray, values: np.ndarray) -> None:
        axes = (rpm_axis, load_axis, boost_axis, order_axis)
        if any(axis.ndim != 1 or axis.size < 2 or not np.all(np.isfinite(axis)) or np.any(np.diff(axis) <= 0.0) for axis in axes):
            raise ValueError("timbre-map axes must be finite and strictly increasing")
        expected = tuple(axis.size for axis in axes)
        if values.shape != expected or not np.all(np.isfinite(values)):
            raise ValueError("timbre-map values must match all four axes")
        self.rpm_axis, self.load_axis, self.boost_axis, self.order_axis = tuple(np.asarray(axis, dtype=np.float64) for axis in axes)
        self.values = np.asarray(values, dtype=np.float64)

    @classmethod
    def default(cls) -> "TimbreMap4D":
        axes = (np.array([800.0, 2400.0, 5200.0, 7600.0]), np.array([0.0, 0.5, 1.0]), np.array([0.0, 0.5, 1.0]), np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
        rpm, load, boost, order = np.meshgrid(*axes, indexing="ij")
        values = (0.22 + 0.000055 * rpm) * (0.35 + 0.65 * load) * (0.55 + 0.45 * boost) / np.sqrt(order)
        return cls(*axes, values)

    @classmethod
    def from_config(cls, config: dict | None) -> "TimbreMap4D":
        if not config:
            return cls.default()
        axes = tuple(np.asarray(config[name], dtype=np.float64) for name in ("rpm_axis", "load_axis", "boost_axis", "order_axis"))
        values = np.asarray(config["values"], dtype=np.float64)
        return cls(*axes, values)

    def sample(self, rpm: float, load: float, boost: float, order: float) -> float:
        point = [float(np.clip(rpm, self.rpm_axis[0], self.rpm_axis[-1])), float(np.clip(load, self.load_axis[0], self.load_axis[-1])), float(np.clip(boost, self.boost_axis[0], self.boost_axis[-1])), float(np.clip(order, self.order_axis[0], self.order_axis[-1]))]
        result = self.values
        # Sequential 1-D interpolation is multilinear and bounded.
        for axis, coordinate in reversed(list(zip((self.rpm_axis, self.load_axis, self.boost_axis, self.order_axis), point))):
            result = np.apply_along_axis(lambda row: np.interp(coordinate, axis, row), -1, result)
        return float(np.asarray(result))


def render_timbre_map(phase: np.ndarray, rpm: np.ndarray, load: np.ndarray, boost: np.ndarray, throttle: np.ndarray, config: dict, sample_counter: int = 0, inertia_state: float = 0.0) -> dict[str, np.ndarray]:
    phase, rpm, load, boost, throttle = [np.asarray(value, dtype=np.float64) for value in (phase, rpm, load, boost, throttle)]
    if len({value.size for value in (phase, rpm, load, boost, throttle)}) != 1 or phase.ndim != 1 or not np.all(np.isfinite(np.column_stack((phase, rpm, load, boost, throttle)))):
        raise ValueError("timbre-map inputs must be equal finite vectors")
    kind = unwrap(config, "forced_induction.type")
    gain = float(unwrap(config, "forced_induction.gain"))
    ratio = float(unwrap(config, "forced_induction.ratio"))
    load = np.clip(load, 0.0, 1.0)
    boost = np.clip(boost, 0.0, 1.0)
    throttle = np.clip(throttle, 0.0, 1.0)
    bypass_gain = np.clip(0.25 + 0.75 * throttle / 0.20, 0.25, 1.0) if kind in {"supercharger", "turbo"} else np.ones_like(throttle)
    shaft = phase * max(ratio, 1.0)
    table = TimbreMap4D.from_config(config.get("timbre_map"))
    rpm_factor = np.clip(rpm / 5200.0, 0.2, 1.6)
    order_gains = np.column_stack([np.array([table.sample(r, l, b, order) for r, l, b in zip(rpm, load, boost)]) for order in (1.0, 2.0, 3.0, 5.0)]) * gain
    harmonic = bypass_gain * (0.75 + 0.25 * np.clip(inertia_state, 0.0, 1.0)) * (order_gains[:, 0] * np.sin(shaft) + order_gains[:, 1] * np.sin(2.0 * shaft) + order_gains[:, 2] * np.sin(3.0 * shaft) + order_gains[:, 3] * np.sin(5.0 * shaft))
    sideband = bypass_gain * (0.16 + 0.24 * throttle) * order_gains[:, 1] * (np.sin(shaft * (1.0 + 0.015 * rpm_factor) + 0.13 * np.sin(phase * 0.5)) + 0.5 * np.sin(shaft * (1.0 - 0.015 * rpm_factor)))
    index = np.arange(phase.size, dtype=np.float64) + float(sample_counter)
    broadband = bypass_gain[:, None] * order_gains[:, 2, None] * (0.55 * np.sin(index[:, None] * 0.017 + phase[:, None] * 0.31) + 0.35 * np.sin(index[:, None] * 0.041 + phase[:, None] * 0.73) + 0.10 * np.sin(index[:, None] * 0.097))
    casing = bypass_gain[:, None] * order_gains[:, 0, None] * (0.18 + 0.20 * load)[:, None] * (np.sin(phase[:, None] * 4.7 + 0.4) + 0.35 * np.sin(phase[:, None] * 9.3))
    intake_gain = float(unwrap(config, "intake_model"))
    intake = bypass_gain * intake_gain * np.sqrt(np.clip(load * (0.25 + throttle), 0.0, 1.5)) * rpm_factor * (0.7 * np.sin(phase * 3.0 + 0.35) + 0.3 * np.sin(phase * 7.0))
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


__all__ = ["TimbreMap4D", "render_timbre_map"]
