"""State-local, synthetic Hellcat whine diagnostics for Stage I.

The functions in this module measure rendered arrays.  Candidate parameter
values are never treated as measured timing evidence.  These diagnostics are
uncalibrated engineering gates, not OEM measurements or human approval.
"""

from __future__ import annotations

from collections.abc import Mapping
import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


_REQUIRED_STATES = ("idle", "acceleration", "full_pull")


def measure_step_response(
    response_envelope: np.ndarray,
    command: np.ndarray,
    sample_rate_hz: int,
) -> dict[str, float]:
    """Measure actual 10--90 rise and 90--10 fall durations.

    ``response_envelope`` is deliberately explicit: callers may obtain it from
    a named rendered stem or from a standard probe.  A configured time
    constant is not accepted as evidence of the observed response.
    """
    response, state = _validated_pair(response_envelope, command, sample_rate_hz)
    rising = np.flatnonzero((state[1:] >= 0.5) & (state[:-1] < 0.5))
    falling = np.flatnonzero((state[1:] < 0.5) & (state[:-1] >= 0.5))
    if rising.size == 0:
        return {"boost_attack_10_90_s": 0.0, "boost_release_90_10_s": 0.0}
    attack = _transition_duration(response, int(rising[0] + 1), True, sample_rate_hz, int(falling[0] + 1) if falling.size else response.size)
    release = _transition_duration(response, int(falling[0] + 1), False, sample_rate_hz, response.size) if falling.size else 0.0
    return {
        "boost_attack_10_90_s": attack,
        "boost_release_90_10_s": release,
    }


def measure_bypass_decay(
    bypass_envelope: np.ndarray,
    event_gate: np.ndarray,
    sample_rate_hz: int,
) -> dict[str, float | int]:
    """Count gated bypass releases and measure the first event 90--10 decay."""
    response, gate = _validated_pair(bypass_envelope, event_gate, sample_rate_hz)
    starts = np.flatnonzero((gate[1:] >= 0.5) & (gate[:-1] < 0.5)) + 1
    valid: list[tuple[int, int]] = []
    for index, start in enumerate(starts):
        stop = int(starts[index + 1]) if index + 1 < starts.size else response.size
        if float(np.max(response[start:stop], initial=0.0)) > 1e-12:
            valid.append((int(start), stop))
    if not valid:
        return {"bypass_event_count": 0, "bypass_decay_90_10_s": 0.0}
    start, stop = valid[0]
    window = response[start:stop]
    peak_index = int(np.argmax(window))
    tail = window[peak_index:]
    peak = float(tail[0])
    high_hit = _first_at_or_below(tail, 0.9 * peak)
    low_hit = _first_at_or_below(tail, 0.1 * peak)
    decay = max(low_hit - high_hit, 0) / sample_rate_hz if low_hit is not None and high_hit is not None else 0.0
    return {"bypass_event_count": len(valid), "bypass_decay_90_10_s": float(decay)}


def compute_stage_i_perceptual_metrics(
    render: SourceRender,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    *,
    state_masks: Mapping[str, np.ndarray] | None = None,
    response_probe: Mapping[str, object] | None = None,
) -> dict[str, float | int | str]:
    """Measure state-specific Hellcat identity and transient diagnostics."""
    render.validate()
    trace.validate()
    if sample_rate_hz != 48000:
        raise ValueError("Stage-I final-render metrics require 48 kHz")
    count = np.asarray(render.pressure).shape[0]
    rpm, load, throttle = _audio_state(trace, count, sample_rate_hz)
    masks = _validated_state_masks(state_masks, rpm, load, throttle, trace, count)

    blower = _stem(render, "blower")
    exhaust = _stem(render, "exhaust")
    shaft = _stem(render, "blower_shaft")
    lobe = _stem(render, "blower_lobe_family")
    upper = _stem(render, "blower_upper_family")
    sidebands = _stem(render, "blower_sidebands")
    bypass = _stem(render, "blower_bypass_release")
    pressure = np.asarray(render.pressure, dtype=np.float64)

    shaft_order = _weighted_order(shaft, rpm, sample_rate_hz)
    lobe_order = _weighted_order(lobe, rpm, sample_rate_hz)
    concentration, cluster_width = _order_cluster_metrics(lobe, rpm, 11.8, sample_rate_hz)
    main_energy = _energy(shaft) + _energy(lobe) + _energy(upper)
    metrics: dict[str, float | int | str] = {
        "shaft_order_error": _relative_order_error(shaft_order, 2.36),
        "lobe_order_error": _relative_order_error(lobe_order, 11.8),
        "blower_load_correlation": _state_correlation((shaft, lobe, upper, sidebands, bypass), load * throttle, sample_rate_hz),
        "blower_to_exhaust_ratio_idle_db": _masked_energy_db_ratio(blower, exhaust, masks["idle"]),
        "blower_to_exhaust_ratio_acceleration_db": _masked_energy_db_ratio(blower, exhaust, masks["acceleration"]),
        "blower_to_exhaust_ratio_full_pull_db": _masked_energy_db_ratio(blower, exhaust, masks["full_pull"]),
        "single_ridge_concentration": concentration,
        "order_cluster_width_ratio": cluster_width,
        "sideband_to_main_ratio": _energy(sidebands) / max(main_energy, 1e-18),
        "am_modulation_ratio_20_200hz": _am_band_ratio(blower, sample_rate_hz, 20.0, 200.0),
        "spectral_crest_400_3200hz": _spectral_crest(blower, sample_rate_hz, 400.0, 3200.0),
        "upper_band_share_4_12khz": _band_share(pressure[masks["acceleration"]], sample_rate_hz, 4000.0, 12000.0),
        "upper_band_short_time_peak": _short_time_band_peak(pressure[masks["acceleration"]], sample_rate_hz, 4000.0, 12000.0),
        "low_frequency_share_40_200hz": _band_share(pressure[masks["acceleration"]], sample_rate_hz, 40.0, 200.0),
        "rumble_energy": _energy(_stem(render, "exhaust_rumble")),
        "blower_energy": _energy(blower),
        "exhaust_energy": _energy(exhaust),
        "scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
    }
    metrics.update(_shift_metrics(blower, rpm, throttle, sample_rate_hz))
    if response_probe is None:
        metrics.update({
            "boost_attack_10_90_s": 0.0,
            "boost_release_90_10_s": 0.0,
            "bypass_decay_90_10_s": 0.0,
            "bypass_event_count": 0,
        })
    else:
        probe_rate = int(response_probe.get("sample_rate_hz", sample_rate_hz))
        metrics.update(measure_step_response(
            np.asarray(response_probe["boost_response"], dtype=np.float64),
            np.asarray(response_probe["boost_command"], dtype=np.float64),
            probe_rate,
        ))
        metrics.update(measure_bypass_decay(
            np.asarray(response_probe["bypass_response"], dtype=np.float64),
            np.asarray(response_probe["bypass_gate"], dtype=np.float64),
            probe_rate,
        ))
    return metrics


def _validated_pair(response: np.ndarray, command: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be a positive integer")
    response = np.asarray(response, dtype=np.float64)
    command = np.asarray(command, dtype=np.float64)
    if response.ndim != 1 or command.ndim != 1 or response.size != command.size or response.size < 3:
        raise ValueError("response and command must be equal-length one-dimensional arrays")
    if not np.all(np.isfinite(response)) or not np.all(np.isfinite(command)):
        raise ValueError("response and command must be finite")
    return np.maximum(response, 0.0), command


def _transition_duration(response: np.ndarray, start: int, rising: bool, sample_rate_hz: int, stop: int) -> float:
    pre_start = max(start - max(int(0.05 * sample_rate_hz), 1), 0)
    baseline = float(np.median(response[pre_start:start])) if start > pre_start else float(response[max(start - 1, 0)])
    window = response[start:stop]
    if window.size == 0:
        return 0.0
    steady = float(np.max(window)) if rising else float(np.min(window))
    if rising:
        low = baseline + 0.1 * (steady - baseline)
        high = baseline + 0.9 * (steady - baseline)
        first = _first_at_or_above(window, low)
        second = _first_at_or_above(window, high)
    else:
        initial = float(response[max(start - 1, 0)])
        high = steady + 0.9 * (initial - steady)
        low = steady + 0.1 * (initial - steady)
        first = _first_at_or_below(window, high)
        second = _first_at_or_below(window, low)
    if first is None or second is None:
        return 0.0
    return float(max(second - first, 0) / sample_rate_hz)


def _first_at_or_above(values: np.ndarray, threshold: float) -> int | None:
    hits = np.flatnonzero(values >= threshold)
    return int(hits[0]) if hits.size else None


def _first_at_or_below(values: np.ndarray, threshold: float) -> int | None:
    hits = np.flatnonzero(values <= threshold)
    return int(hits[0]) if hits.size else None


def _audio_state(trace: VehicleStateTrace, count: int, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    audio_time = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    return tuple(np.interp(audio_time, trace.time_s, values) for values in (trace.rpm, trace.load, trace.throttle))  # type: ignore[return-value]


def _validated_state_masks(
    provided: Mapping[str, np.ndarray] | None,
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    trace: VehicleStateTrace,
    count: int,
) -> dict[str, np.ndarray]:
    if provided is None:
        derivative = np.gradient(rpm, 1.0 / 48000.0)
        redline = max(float(np.max(rpm)), 1.0)
        masks = {
            "idle": (rpm <= 1400.0) & (load <= 0.25) & (throttle <= 0.25),
            "acceleration": (derivative > 100.0) & (load >= 0.45) & (throttle >= 0.45),
            "full_pull": (rpm >= 0.70 * redline) & (load >= 0.80) & (throttle >= 0.80),
        }
    else:
        masks = {name: np.asarray(value, dtype=bool) for name, value in provided.items()}
    for name in _REQUIRED_STATES:
        if name not in masks:
            raise ValueError(f"state_masks missing required state {name!r}")
        if masks[name].ndim != 1 or masks[name].size != count:
            raise ValueError(f"state mask {name!r} must match rendered sample count")
        if not np.any(masks[name]):
            raise ValueError(f"state mask {name!r} must select at least one sample")
    return masks


def _stem(render: SourceRender, name: str) -> np.ndarray:
    value = render.stems.get(name)
    return np.zeros_like(render.pressure, dtype=np.float64) if value is None else np.asarray(value, dtype=np.float64)


def _energy(audio: np.ndarray) -> float:
    return float(np.sum(np.square(np.asarray(audio, dtype=np.float64))))


def _masked_energy_db_ratio(numerator: np.ndarray, denominator: np.ndarray, mask: np.ndarray) -> float:
    return float(10.0 * np.log10(max(_energy(numerator[mask]), 1e-18) / max(_energy(denominator[mask]), 1e-18)))


def _analytic_phase(signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mono = np.mean(np.asarray(signal, dtype=np.float64), axis=1)
    spectrum = np.fft.fft(mono)
    mask = np.zeros(mono.size)
    if mono.size % 2 == 0:
        mask[0] = mask[mono.size // 2] = 1.0
        mask[1:mono.size // 2] = 2.0
    else:
        mask[0] = 1.0
        mask[1:(mono.size + 1) // 2] = 2.0
    analytic = np.fft.ifft(spectrum * mask)
    return np.unwrap(np.angle(analytic)), np.abs(analytic)


def _weighted_order(signal: np.ndarray, rpm: np.ndarray, sample_rate_hz: int) -> float:
    phase, amplitude = _analytic_phase(signal)
    if phase.size < 3 or not np.any(amplitude > 1e-12):
        return float("nan")
    frequency = np.diff(phase) * sample_rate_hz / (2.0 * np.pi)
    engine_hz = np.maximum(rpm[1:], 1.0) / 60.0
    valid = (amplitude[1:] > np.percentile(amplitude[1:], 40.0)) & (frequency > 0.0) & np.isfinite(frequency)
    if not np.any(valid):
        return float("nan")
    weights = amplitude[1:][valid]
    return float(np.sum(frequency[valid] / engine_hz[valid] * weights) / np.sum(weights))


def _relative_order_error(measured: float, expected: float) -> float:
    return float(abs(measured - expected) / expected) if np.isfinite(measured) else float("inf")


def _order_cluster_metrics(signal: np.ndarray, rpm: np.ndarray, expected_order: float, sample_rate_hz: int) -> tuple[float, float]:
    mono = np.mean(np.asarray(signal, dtype=np.float64), axis=1)
    frame = min(4096, mono.size)
    if frame < 256:
        return 0.0, 0.0
    hop = frame // 2
    window = np.hanning(frame)
    frequencies = np.fft.rfftfreq(frame, 1.0 / sample_rate_hz)
    concentrations: list[float] = []
    widths: list[float] = []
    for start in range(0, mono.size - frame + 1, hop):
        center = start + frame // 2
        expected_hz = expected_order * max(float(rpm[center]), 1.0) / 60.0
        band = (frequencies >= 0.95 * expected_hz) & (frequencies <= 1.05 * expected_hz)
        if np.count_nonzero(band) < 3:
            continue
        power = np.square(np.abs(np.fft.rfft(mono[start:start + frame] * window)))[band]
        local_frequencies = frequencies[band]
        total = float(np.sum(power))
        if total <= 1e-18:
            continue
        concentrations.append(float(np.max(power) / total))
        centroid = float(np.sum(local_frequencies * power) / total)
        deviation = float(np.sqrt(np.sum(np.square(local_frequencies - centroid) * power) / total))
        widths.append(deviation / expected_hz)
    return (float(np.mean(concentrations)), float(np.mean(widths))) if concentrations else (0.0, 0.0)


def _frame_energy(audio: np.ndarray, sample_rate_hz: int, frame_s: float = 0.02) -> np.ndarray:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    size = max(int(round(frame_s * sample_rate_hz)), 1)
    count = mono.size // size
    return np.asarray([np.mean(np.square(mono[index * size:(index + 1) * size])) for index in range(count)])


def _state_correlation(stems: tuple[np.ndarray, ...], state: np.ndarray, sample_rate_hz: int) -> float:
    if not stems:
        return 0.0
    energy = np.zeros(stems[0].shape[0], dtype=np.float64)
    for stem in stems:
        energy += np.mean(np.square(stem), axis=1)
    frame_s = 0.02
    framed = _frame_energy(np.sqrt(np.maximum(energy, 0.0))[:, None], sample_rate_hz, frame_s)
    size = max(int(round(frame_s * sample_rate_hz)), 1)
    framed_state = np.asarray([np.mean(state[index * size:(index + 1) * size]) for index in range(framed.size)])
    active = framed_state >= 0.20
    if np.count_nonzero(active) < 2 or np.std(framed[active]) == 0.0 or np.std(framed_state[active]) == 0.0:
        return 0.0
    return float(np.corrcoef(np.log(np.maximum(framed[active], 1e-18)), framed_state[active])[0, 1])


def _rms_envelope(audio: np.ndarray, sample_rate_hz: int, window_s: float = 0.005) -> np.ndarray:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    size = max(int(round(window_s * sample_rate_hz)), 1)
    kernel = np.ones(size, dtype=np.float64) / size
    return np.sqrt(np.maximum(np.convolve(np.square(mono), kernel, mode="same"), 0.0))


def _am_band_ratio(audio: np.ndarray, sample_rate_hz: int, low_hz: float, high_hz: float) -> float:
    envelope = _rms_envelope(audio, sample_rate_hz)
    envelope -= float(np.mean(envelope))
    power = np.square(np.abs(np.fft.rfft(envelope * np.hanning(envelope.size))))
    frequencies = np.fft.rfftfreq(envelope.size, 1.0 / sample_rate_hz)
    selected = (frequencies >= low_hz) & (frequencies <= high_hz)
    return float(np.sum(power[selected]) / max(float(np.sum(power[1:])), 1e-18))


def _spectral_crest(audio: np.ndarray, sample_rate_hz: int, low_hz: float, high_hz: float) -> float:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    power = np.square(np.abs(np.fft.rfft(mono * np.hanning(mono.size))))
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
    selected = power[(frequencies >= low_hz) & (frequencies <= high_hz)]
    return float(np.max(selected, initial=0.0) / max(float(np.mean(selected)) if selected.size else 0.0, 1e-18))


def _band_share(audio: np.ndarray, sample_rate_hz: int, low_hz: float, high_hz: float) -> float:
    if audio.shape[0] < 4:
        return 0.0
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    power = np.square(np.abs(np.fft.rfft(mono * np.hanning(mono.size))))
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
    selected = (frequencies >= low_hz) & (frequencies <= high_hz)
    return float(np.sum(power[selected]) / max(float(np.sum(power)), 1e-18))


def _short_time_band_peak(audio: np.ndarray, sample_rate_hz: int, low_hz: float, high_hz: float) -> float:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    frame = min(4096, mono.size)
    if frame < 64:
        return 0.0
    frequencies = np.fft.rfftfreq(frame, 1.0 / sample_rate_hz)
    selected = (frequencies >= low_hz) & (frequencies <= high_hz)
    peaks = []
    for start in range(0, mono.size - frame + 1, max(frame // 2, 1)):
        power = np.square(np.abs(np.fft.rfft(mono[start:start + frame] * np.hanning(frame))))
        peaks.append(float(np.sum(power[selected])))
    return float(max(peaks, default=0.0) / max(float(np.sum(np.square(mono))), 1e-18))


def _shift_metrics(blower: np.ndarray, rpm: np.ndarray, throttle: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    derivative = np.gradient(rpm, 1.0 / sample_rate_hz)
    events = np.flatnonzero((derivative < -1500.0) & (throttle > 0.30))
    if events.size == 0:
        return {"shift_whine_dip_db": 0.0, "shift_whine_rebuild_time_s": 0.0}
    center = int(events[0])
    envelope = _rms_envelope(blower, sample_rate_hz)
    span = max(int(0.08 * sample_rate_hz), 1)
    before = float(np.mean(envelope[max(center - span, 0):center]))
    after = envelope[center:min(center + int(0.35 * sample_rate_hz), envelope.size)]
    if before <= 1e-12 or after.size == 0:
        return {"shift_whine_dip_db": 0.0, "shift_whine_rebuild_time_s": 0.0}
    minimum = float(np.min(after))
    dip = float(20.0 * np.log10(max(minimum, 1e-12) / before))
    rebuilt = np.flatnonzero(after >= 0.9 * before)
    rebuild = float(rebuilt[0] / sample_rate_hz) if rebuilt.size else 0.0
    return {"shift_whine_dip_db": dip, "shift_whine_rebuild_time_s": rebuild}


__all__ = (
    "compute_stage_i_perceptual_metrics",
    "measure_bypass_decay",
    "measure_step_response",
)
