"""Deterministic, synthetic Hellcat-inspired supercharger whine source."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender


_ORDER_FAMILIES = (2.36, 11.8, 23.6)


def render_supercharger_whine_v2(
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    engine_phase: np.ndarray,
    sample_rate_hz: int,
    overrides: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render shaft/lobe/sideband/bypass stems before the shared PTR boundary.

    The drive ratio and order families are fixed architecture assumptions. All
    amplitudes and time constants are C-level synthetic candidate controls.
    No random or unrelated broadband noise is used.
    """
    overrides = {} if overrides is None else dict(overrides)
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    arrays = {"rpm": rpm, "load": load, "throttle": throttle, "engine_phase": engine_phase}
    values = {name: np.asarray(value, dtype=np.float64) for name, value in arrays.items()}
    if any(value.ndim != 1 for value in values.values()) or len({value.size for value in values.values()}) != 1:
        raise ValueError("supercharger inputs must be equal-length one-dimensional arrays")
    if any(not np.all(np.isfinite(value)) for value in values.values()):
        raise ValueError("supercharger inputs must be finite")
    rpm = np.maximum(values["rpm"], 0.0)
    load = np.clip(values["load"], 0.0, 1.0)
    throttle = np.clip(values["throttle"], 0.0, 1.0)
    engine_phase = values["engine_phase"]
    count = rpm.size

    blower_gain_scale = float(overrides.get("blower_gain_scale", 1.0))
    boost_mix = float(overrides.get("blower_boost_mix", 1.0))
    lobe_mix = float(overrides.get("lobe_family_mix", 1.0))
    upper_tilt_db = float(overrides.get("upper_family_tilt_db", 0.0))
    sideband_depth = float(overrides.get("sideband_depth", 0.10))
    attack_s = float(overrides.get("boost_attack_s", 0.075))
    release_s = float(overrides.get("boost_release_s", 0.22))
    bypass_gain = float(overrides.get("bypass_release_gain", 0.10))
    if attack_s <= 0.0 or release_s <= 0.0:
        raise ValueError("boost attack/release must be positive")
    if any(not np.isfinite(value) for value in (blower_gain_scale, boost_mix, lobe_mix, upper_tilt_db, sideband_depth, attack_s, release_s, bypass_gain)):
        raise ValueError("supercharger overrides must be finite")

    boost_target = load * throttle * np.clip((rpm - 1100.0) / 3800.0, 0.0, 1.15) * boost_mix
    boost_state = np.zeros(count, dtype=np.float64)
    bypass_state = np.zeros(count, dtype=np.float64)
    for index in range(1, count):
        tau = attack_s if boost_target[index] >= boost_state[index - 1] else release_s
        boost_state[index] = boost_state[index - 1] + (boost_target[index] - boost_state[index - 1]) / max(tau * sample_rate_hz, 1.0)
        bypass_target = (1.0 - throttle[index]) * (0.35 + 0.65 * (1.0 - boost_state[index]))
        bypass_state[index] = bypass_state[index - 1] + (bypass_target - bypass_state[index - 1]) / (0.050 * sample_rate_hz)

    shaft_phase = np.cumsum(rpm * _ORDER_FAMILIES[0]) / (60.0 * sample_rate_hz)
    phase_lobe = shaft_phase * 5.0
    phase_upper = shaft_phase * 10.0
    # The envelope is quiet at idle, rises with boost and load, and never uses
    # a whole-bundle gain as a proxy for the whine state.
    rpm_factor = np.clip((rpm - 900.0) / 5200.0, 0.0, 1.0)
    # Load/throttle are deliberately multiplicative here: a Hellcat whine is
    # masked at idle and becomes present as the compressor is loaded.  A broad
    # additive floor made the aggregate energy correlate only ~0.70 with load
    # over the complete idle/pull/lift cycle, which was not a useful identity
    # cue.  The small floor preserves a quiet cruise trace without making the
    # blower audible with zero load and zero throttle.
    load_factor = (0.12 + 0.88 * np.power(load, 1.15)) * (load > 0.0)
    throttle_factor = (0.18 + 0.82 * np.power(throttle, 1.10)) * (throttle > 0.0)
    envelope = blower_gain_scale * (0.10 + 0.90 * boost_state) * load_factor * throttle_factor * (0.25 + 0.75 * rpm_factor)
    upper_factor = 10.0 ** (upper_tilt_db / 20.0)
    shaft = 0.22 * envelope * np.sin(2.0 * np.pi * shaft_phase)
    lobe = 0.58 * envelope * lobe_mix * np.sin(2.0 * np.pi * phase_lobe)
    upper = 0.22 * envelope * upper_factor * np.sin(2.0 * np.pi * phase_upper + 0.21)
    # Four combustion events per crank revolution amplitude-modulate the rotor
    # families, producing deterministic sidebands rather than a fixed sine.
    # The four terms are intentionally normalised as a family rather than
    # treated as four unrelated tones.  The scale keeps the default C-level
    # seed in the 5--20% sideband/main energy band while preserving the
    # explicit ``sideband_depth`` control.
    sideband = envelope * (5.5 * sideband_depth) * (
        0.30 * np.sin(2.0 * np.pi * (phase_lobe + 4.0 * engine_phase))
        + 0.30 * np.sin(2.0 * np.pi * (phase_lobe - 4.0 * engine_phase))
        + 0.12 * np.sin(2.0 * np.pi * (phase_upper + 4.0 * engine_phase))
        + 0.12 * np.sin(2.0 * np.pi * (phase_upper - 4.0 * engine_phase))
    )
    closed_throttle = throttle < 0.25
    release_envelope = closed_throttle.astype(np.float64) * boost_state * bypass_state
    bypass = bypass_gain * release_envelope * (
        0.65 * np.sin(2.0 * np.pi * phase_lobe + 0.63)
        + 0.35 * np.sin(2.0 * np.pi * phase_upper + 1.1)
    )

    stems = {
        "blower_shaft": np.column_stack((0.65 * shaft, shaft)),
        "blower_lobe_family": np.column_stack((0.65 * lobe, lobe)),
        "blower_upper_family": np.column_stack((0.65 * upper, upper)),
        "blower_sidebands": np.column_stack((0.65 * sideband, sideband)),
        "blower_bypass_release": np.column_stack((0.70 * bypass, bypass)),
    }
    aggregate = sum(stems.values(), np.zeros((count, 2), dtype=np.float64))
    stems["blower"] = aggregate

    peak = float(np.max(boost_state)) if count else 0.0
    rise_index = _first_crossing(boost_state, peak * 0.63)
    fall_index = _first_fall_after(boost_state, peak * 0.37, rise_index)
    release_events = int(np.count_nonzero(np.diff(closed_throttle.astype(np.int8)) > 0))
    diagnostics = {
        "vehicle_id": "hellcat",
        "scope": "synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
        "order_families": _ORDER_FAMILIES,
        "blower_dynamic_model": "rpm_load_boost_inertia_with_rotor_sidebands_and_bypass_release",
        "boost_attack_s": attack_s,
        "boost_release_s": release_s,
        "boost_rise_time_s": float(rise_index / sample_rate_hz) if rise_index is not None else 0.0,
        "boost_fall_time_s": float((fall_index - rise_index) / sample_rate_hz) if fall_index is not None and rise_index is not None else 0.0,
        "boost_state_peak": peak,
        "bypass_event_count": release_events,
        "bypass_energy": float(np.sum(np.square(stems["blower_bypass_release"]))),
        "blower_energy": float(np.sum(np.square(aggregate))),
        "pipeline_position": "before_pre_ptr_equalization",
        "candidate_source_overrides": dict(overrides),
    }
    return SourceRender(pressure=aggregate, stems=stems, diagnostics=diagnostics).validate()


def _first_crossing(values: np.ndarray, threshold: float) -> int | None:
    if threshold <= 0.0:
        return 0
    matches = np.flatnonzero(values >= threshold)
    return int(matches[0]) if matches.size else None


def _first_fall_after(values: np.ndarray, threshold: float, start: int | None) -> int | None:
    if start is None:
        return None
    matches = np.flatnonzero(values[start:] <= threshold)
    return int(start + matches[0]) if matches.size else None


__all__ = ("render_supercharger_whine_v2",)
