"""Hellcat-only, shared-clock afterfire contributor for Stage-L Round-2.

The implementation is intentionally source driven: it does not synthesize a
fixed pitch or schedule events at wall-clock intervals.  Events are selected
on the shared crank clock and their short templates are taken from the actual
HEMI stems immediately before throttle closure.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from .crank_clock import HellcatCrankClock, build_hellcat_crank_clock


_PARAMETERS = (
    "minimum_rpm", "residual_energy_gain", "event_energy_threshold",
    "body_mix", "bright_mix", "decay_90_10_s",
)


def render_hellcat_afterfire_v1(
    render: SourceRender,
    trace: VehicleStateTrace,
    clock: HellcatCrankClock,
    parameters: Mapping[str, float],
    sample_rate_hz: int = 48000,
    oxygen_proxy: np.ndarray | None = None,
) -> SourceRender:
    """Return ``render`` plus one deterministic ``afterfire`` contributor."""

    render.validate()
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    if set(parameters) != set(_PARAMETERS):
        raise ValueError("afterfire parameters must match the v9 six-field contract")
    values = {name: float(parameters[name]) for name in _PARAMETERS}
    if not all(np.isfinite(value) for value in values.values()):
        raise ValueError("afterfire parameters must be finite")
    if values["minimum_rpm"] <= 0.0 or values["decay_90_10_s"] <= 0.0:
        raise ValueError("minimum_rpm and decay_90_10_s must be positive")
    if not all(0.0 <= values[name] <= 2.0 for name in ("body_mix", "bright_mix", "event_energy_threshold")):
        raise ValueError("afterfire mix and threshold parameters are out of range")

    count = render.pressure.shape[0]
    expected_clock = build_hellcat_crank_clock(trace, sample_rate_hz)
    if not isinstance(clock, HellcatCrankClock):
        raise ValueError("shared crank clock is required")
    if len(clock.firing_event_gate) != count or len(clock.event_sample_indices) != len(expected_clock.event_sample_indices):
        raise ValueError("shared crank clock length must match SourceRender")
    if not np.allclose(clock.engine_phase_cycles, expected_clock.engine_phase_cycles, atol=1.0e-12, rtol=0.0):
        raise ValueError("shared crank clock does not match trace")
    if oxygen_proxy is not None:
        oxygen = np.asarray(oxygen_proxy, dtype=np.float64)
        if oxygen.shape != (count,) or not np.all(np.isfinite(oxygen)):
            raise ValueError("oxygen_proxy must be a finite one-dimensional array matching render")
        oxygen = np.clip(oxygen, 0.0, 1.0)
    else:
        oxygen = None
    if "afterfire" in render.stems and np.any(np.abs(np.asarray(render.stems["afterfire"], dtype=np.float64)) > 1.0e-15):
        raise ValueError("Hellcat afterfire may only be applied once")
    if len(clock.firing_event_gate) != count:
        raise ValueError("shared crank clock length must match SourceRender")
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    left = _required(render.stems, "hemi_exhaust_left", render.pressure.shape)
    right = _required(render.stems, "hemi_exhaust_right", render.pressure.shape)
    body = _required(render.stems, "hemi_blowdown_body", render.pressure.shape)
    structure = _required(render.stems, "hemi_structure_shock", render.pressure.shape)
    torque = _required(render.stems, "hemi_mechanical_torque_ripple", render.pressure.shape)

    # A one-pole thermal memory gives hot history a real time constant.  The
    # closure memory is only seeded by an actual throttle-close edge.
    hot_signal = np.clip((rpm - 2400.0) / 3600.0, 0.0, 1.0) * load
    thermal = _one_pole(hot_signal, 0.35, sample_rate_hz)
    close_edge = np.r_[False, (throttle[:-1] > 0.30) & (throttle[1:] <= 0.12)]
    close_memory = _decaying_memory(close_edge, sample_rate_hz, 0.90)
    residual = _one_pole(np.mean(np.abs(left + right + body), axis=1), 0.20, sample_rate_hz)
    if oxygen is None:
        oxygen = np.clip((0.22 - throttle) / 0.22, 0.0, 1.0) * (0.35 + 0.65 * load)

    events: list[int] = []
    qualification_rows: list[dict[str, object]] = []
    event_scores: dict[int, float] = {}
    for index in clock.event_sample_indices:
        if index >= count:
            continue
        score = (
            0.30 * thermal[index]
            + 0.20 * close_memory[index]
            + 0.20 * np.clip((rpm[index] - values["minimum_rpm"]) / 2600.0, 0.0, 1.0)
            + 0.15 * np.clip(values["residual_energy_gain"] * residual[index] / 0.20, 0.0, 1.0)
            + 0.15 * oxygen[index]
        )
        hot_ok = bool(thermal[index] >= 0.08)
        rpm_ok = bool(rpm[index] >= values["minimum_rpm"])
        throttle_ok = bool(close_memory[index] > 0.0)
        residual_ok = bool(residual[index] > 1.0e-5)
        oxygen_ok = bool(oxygen[index] > 0.0)
        row = {
            "sample_index": int(index), "hot_history": hot_ok, "rpm": rpm_ok,
            "throttle_close": throttle_ok, "residual_energy": residual_ok,
            "oxygen_proxy": oxygen_ok,
        }
        if throttle_ok and hot_ok and rpm_ok and residual_ok and oxygen_ok and score >= values["event_energy_threshold"]:
            events.append(int(index))
            event_scores[int(index)] = float(score)
            qualification_rows.append(row)
            break

    afterfire = np.zeros_like(render.pressure, dtype=np.float64)
    if events:
        template_len = max(8, int(round(0.060 * sample_rate_hz)))
        decay_len = max(template_len, int(round(0.40 * sample_rate_hz)))
        for event in events:
            start = max(0, event - template_len)
            stop = event
            if stop - start < 4:
                continue
            source_body = body[start:stop]
            source_structure = structure[start:stop]
            source_torque = torque[start:stop]
            # Repeat the measured pre-lift template without time-stretching it;
            # stretching would move the source's actual spectral content into
            # an artificial low-frequency pulse.
            body_template = _tile_template(np.mean(source_body, axis=1), decay_len)
            bright_template = _tile_template(np.mean(source_structure + source_torque, axis=1), decay_len)
            body_template = _normalize(body_template)
            bright_template = _normalize(bright_template)
            x = np.linspace(0.0, 1.0, decay_len, dtype=np.float64)
            envelope = np.exp(-x * (6.907755278982137 / max(values["decay_90_10_s"], 1.0e-4)) * 0.045)
            amp = float(np.clip(event_scores[event], 0.0, 1.0))
            # Re-evaluate local energy so each event is driven by its own
            # crank-aligned template rather than a repeated fixed pulse.
            local = float(np.clip(
                0.30 * thermal[event]
                + 0.20 * close_memory[event]
                + 0.20 * np.clip((rpm[event] - values["minimum_rpm"]) / 2600.0, 0.0, 1.0)
                + 0.15 * np.clip(values["residual_energy_gain"] * residual[event] / 0.20, 0.0, 1.0)
                + 0.15 * oxygen[event], 0.0, 1.0,
            ))
            amp = max(amp, local)
            mono = envelope * amp * (
                values["body_mix"] * body_template + values["bright_mix"] * bright_template
            )
            end = min(count, event + mono.size)
            if end > event:
                bank = clock.bank_labels[clock.event_sample_indices.index(event)]
                if bank == "left":
                    afterfire[event:end, 0] += mono[: end - event]
                    afterfire[event:end, 1] += 0.55 * mono[: end - event]
                else:
                    afterfire[event:end, 0] += 0.55 * mono[: end - event]
                    afterfire[event:end, 1] += mono[: end - event]

    contributors = list(render.diagnostics.get("pressure_stem_contract", {}).get("contributors", render.stems.keys()))
    if "afterfire" not in contributors:
        contributors.append("afterfire")
    stems = dict(render.stems)
    stems["afterfire"] = afterfire
    diagnostics = dict(render.diagnostics)
    diagnostics.update({
        "afterfire_model": "hellcat_afterfire_v1_shared_clock_template",
        "afterfire_event_count": len(events),
        "afterfire_event_sample_indices": tuple(events),
        "afterfire_bank_labels": tuple(clock.bank_labels[clock.event_sample_indices.index(event)] for event in events),
        "afterfire_template_provenance": {
            "kind": "actual_pre_lift_hemi_arrays",
            "source_stems": ("hemi_blowdown_body", "hemi_structure_shock", "hemi_mechanical_torque_ripple"),
        },
        "fixed_80_700_hz_oscillators_used": False,
        "fixed_tone_injection": False,
        "afterfire_contributor_count": 1,
        "afterfire_qualification": qualification_rows,
        "candidate_parameter_usage": _usage(values, bool(events)),
        "pressure_stem_contract": {"contributors": contributors, "diagnostic_aggregates": []},
    })
    pressure = sum((np.asarray(stems[name], dtype=np.float64) for name in contributors), np.zeros_like(render.pressure))
    return SourceRender(pressure, stems, diagnostics).validate()


def _required(stems: Mapping[str, np.ndarray], name: str, shape: tuple[int, int]) -> np.ndarray:
    value = np.asarray(stems.get(name), dtype=np.float64) if name in stems else None
    if value is None or value.shape != shape or not np.all(np.isfinite(value)):
        raise ValueError(f"required afterfire template stem {name!r} is missing or invalid")
    return value


def _one_pole(values: np.ndarray, time_constant_s: float, sample_rate_hz: int) -> np.ndarray:
    alpha = 1.0 - np.exp(-1.0 / (time_constant_s * sample_rate_hz))
    output = np.zeros_like(values, dtype=np.float64)
    for index, value in enumerate(values):
        output[index] = alpha * value + (1.0 - alpha) * (output[index - 1] if index else 0.0)
    return output


def _decaying_memory(edges: np.ndarray, sample_rate_hz: int, decay_s: float) -> np.ndarray:
    output = np.zeros(edges.size, dtype=np.float64)
    decay = np.exp(-1.0 / (decay_s * sample_rate_hz))
    for index, edge in enumerate(edges):
        output[index] = 1.0 if edge else (decay * output[index - 1] if index else 0.0)
    return output


def _resample_mono(values: np.ndarray, length: int) -> np.ndarray:
    if values.size == length:
        return np.asarray(values, dtype=np.float64).copy()
    return np.interp(np.linspace(0.0, 1.0, length), np.linspace(0.0, 1.0, values.size), values)


def _tile_template(values: np.ndarray, length: int) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return np.zeros(length, dtype=np.float64)
    return np.resize(values, length)


def _normalize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    scale = float(np.sqrt(np.mean(np.square(values))))
    return values / scale if scale > 1.0e-12 else np.zeros_like(values)


def _usage(values: Mapping[str, float], active: bool) -> dict[str, list[str]]:
    keys = [f"afterfire.{name}" for name in values]
    return {
        "requested": keys, "read": keys, "configured": keys,
        "active": keys if active else [], "inactive": [] if active else keys, "unused": [],
    }


__all__ = ("render_hellcat_afterfire_v1",)
