"""Small deterministic forced-induction and intake event layers."""
from __future__ import annotations
import numpy as np
from .config_schema import unwrap


def _optional(config: dict, path: str, default: float) -> float:
    node = config
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    if isinstance(node, dict) and "value" in node:
        return float(node["value"])
    return default

def render_forced_induction(phase_rad: np.ndarray, rpm: np.ndarray, load: np.ndarray, throttle: np.ndarray, config: dict, sample_rate_hz: int) -> dict[str, np.ndarray]:
    phase_rad, rpm, load, throttle = [np.asarray(x, dtype=np.float64) for x in (phase_rad, rpm, load, throttle)]
    kind = unwrap(config, "forced_induction.type")
    gain = float(unwrap(config, "forced_induction.gain"))
    ratio = float(unwrap(config, "forced_induction.ratio"))
    boost_target = np.clip(load * throttle * np.maximum(rpm - 900.0, 0.0) / 4800.0, 0.0, 1.0)
    state = np.zeros_like(boost_target)
    rise_tau = _optional(config, "primary_spool_tau", 0.08)
    fall_tau = _optional(config, "secondary_spool_tau", 0.25)
    for i in range(1, state.size):
        tau = rise_tau if boost_target[i] >= state[i - 1] else fall_tau
        state[i] = state[i - 1] + (boost_target[i] - state[i - 1]) / max(tau * sample_rate_hz, 1.0)
    shaft_phase = phase_rad * max(ratio, 1.0)
    if kind == "supercharger":
        carrier = gain * (0.25 + state) * (0.32 * np.sin(shaft_phase) + 0.75 * np.sin(5.0 * shaft_phase) + 0.22 * np.sin(10.0 * shaft_phase))
        blower = np.column_stack((0.58 * carrier, carrier))
        turbo = np.zeros_like(blower)
        blowoff = np.zeros_like(blower)
    elif kind == "turbo":
        carrier = gain * (0.15 + state) * (0.35 * np.sin(shaft_phase * 1.7) + 0.60 * np.sin(shaft_phase * 3.4))
        turbo = np.column_stack((0.55 * carrier, carrier))
        blower = np.zeros_like(turbo)
        drop = np.maximum(np.r_[0.0, state[:-1] - state[1:]], 0.0)
        blowoff_gain = _optional(config, "blow_off_gain", 0.08)
        blowoff_decay = _optional(config, "blow_off_decay", 0.16)
        decay_alpha = float(np.exp(-1.0 / max(blowoff_decay * sample_rate_hz, 1.0)))
        blowoff_envelope = np.zeros_like(drop)
        for i in range(1, drop.size):
            blowoff_envelope[i] = decay_alpha * blowoff_envelope[i - 1] + drop[i]
        blowoff = np.column_stack((0.45 * blowoff_gain * blowoff_envelope, blowoff_gain * blowoff_envelope))
    else:
        blower = np.zeros((phase_rad.size, 2), dtype=np.float64)
        turbo = np.zeros_like(blower)
        blowoff = np.zeros_like(blower)
    intake_gain = float(unwrap(config, "intake_model"))
    intake_carrier = intake_gain * np.sqrt(np.clip(load * (0.25 + throttle), 0.0, 1.5)) * np.sin(phase_rad * 3.0 + 0.35)
    intake = np.column_stack((0.52 * intake_carrier, intake_carrier))
    return {"blower": blower, "turbo": turbo, "blowoff": blowoff, "intake": intake, "boost_state": state}
