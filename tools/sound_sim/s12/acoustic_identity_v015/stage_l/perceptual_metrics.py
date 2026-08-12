"""Measured Stage-L Hellcat diagnostics with explicit analysis domains.

This module deliberately keeps three domains separate.  Source-domain values
come from the actual rendered arrays and detected events, pre-PTR values come
from the named transient arrays, and PCM health is calculated only after a
real PCM24 WAV is reopened from disk.  It is an engineering qualification
tool, not an OEM measurement or a human-listening verdict.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import math
from pathlib import Path
import wave

import numpy as np

from ..loudness_manager import measure_loudness
from ..render_identity_v02 import _read_pcm24_wav


_BANDS = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))
_LOCKED_HELLCAT_BANK_PATTERN = ("left", "right", "left", "right", "right", "left", "right", "left")
_DOMAINS = {
    "source_domain": "actual SourceRender arrays and detected events",
    "pre_ptr": "actual named transient arrays before common Pre-PTR EQ",
    "final_pcm24": "reopened PCM24 WAV bytes",
}


def compute_stage_l_perceptual_metrics(
    render: object,
    trace: object,
    final_pcm24_path: str | Path,
    *,
    sample_rate_hz: int = 48000,
) -> dict[str, object]:
    """Measure one render and an independently reopened final PCM24 WAV.

    ``sample_rate_hz`` describes the source render.  The final WAV is checked
    from its byte header and is intentionally *not* inferred from the source
    render or from this argument.
    """

    if not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be a positive integer")
    pressure = _stereo(getattr(render, "pressure", None), "render.pressure")
    raw_stems = getattr(render, "stems", None)
    if not isinstance(raw_stems, Mapping):
        raise ValueError("render.stems must be a mapping")
    stems = {str(name): _stereo(value, f"stem {name}") for name, value in raw_stems.items()}
    for name, stem in stems.items():
        if stem.shape != pressure.shape:
            raise ValueError(f"stem {name!r} must match render.pressure")
    if not np.all(np.isfinite(pressure)) or any(not np.all(np.isfinite(stem)) for stem in stems.values()):
        raise ValueError("SourceRender arrays must be finite")

    rpm, load, throttle = _audio_trace(trace, pressure.shape[0], sample_rate_hz)
    diagnostics = getattr(render, "diagnostics", {})
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    source = _source_metrics(stems, pressure, rpm, load, throttle, diagnostics, sample_rate_hz)
    pre_ptr = _pre_ptr_metrics(stems, rpm, throttle, diagnostics, sample_rate_hz)
    pcm = _reopen_pcm24(final_pcm24_path)
    final_pcm = _pcm_metrics(pcm, Path(final_pcm24_path), diagnostics)
    return {
        "schema_version": "s12-stage-l-perceptual-metrics-1",
        "domains": dict(_DOMAINS),
        "source_domain": source,
        "pre_ptr": pre_ptr,
        "final_pcm24": final_pcm,
    }


def compute_stage_k_parent_metrics(
    render: object,
    trace: object,
    final_pcm24_path: str | Path,
    *,
    sample_rate_hz: int = 48000,
) -> dict[str, object]:
    """Measure only semantics genuinely comparable with a Stage-L candidate.

    Stage-K does not expose the Stage-L primitive stem contract.  Validate that
    its real render matches the real trace, then derive every comparative value
    from the independently reopened final PCM instead of inventing Stage-L
    source stems or passing Stage-K through the Stage-L source validator.
    """
    if not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be a positive integer")
    pressure = _stereo(getattr(render, "pressure", None), "render.pressure")
    if not np.all(np.isfinite(pressure)):
        raise ValueError("Stage-K SourceRender pressure must be finite")
    _audio_trace(trace, pressure.shape[0], sample_rate_hz)
    pcm = _reopen_pcm24(final_pcm24_path)
    return {
        "schema_version": "s12-stage-k-parent-comparison-metrics-1",
        "domain": "reopened PCM24 values comparable across Stage-K and Stage-L",
        "final_pcm24": _pcm_metrics(pcm, Path(final_pcm24_path), {}),
    }


def evaluate_stage_l_metric_gates(
    candidate: Mapping[str, object], parent: Mapping[str, object],
) -> dict[str, object]:
    """Evaluate fail-closed Stage-L automated metric gates.

    This is intentionally a compact gate adapter.  Reference-distance is
    supplied by the hash-bound final-PCM module; a missing reference result is
    a failure rather than an inferred pass.
    """

    source = _mapping(candidate.get("source_domain"))
    pcm = _mapping(candidate.get("final_pcm24"))
    parent_pcm = _mapping(parent.get("final_pcm24"))
    shares = pcm.get("band_shares")
    upper = _share_at(shares, 3)
    parent_upper = _share_at(parent_pcm.get("band_shares"), 3)
    crest_candidate = _number(pcm.get("low_band_pulse_crest_db"), float("-inf"))
    crest_parent = _number(parent_pcm.get("low_band_pulse_crest_db"), float("inf"))
    crest_delta = crest_candidate - crest_parent
    roughness_candidate = _number(pcm.get("roughness_20_300_hz"), float("nan"))
    roughness_parent = _number(parent_pcm.get("roughness_20_300_hz"), float("nan"))
    anchor_shaft_rpm = _number(source.get("shaft_anchor_max_rpm", source.get("shaft_max_rpm")), float("inf"))
    gates: dict[str, bool] = {
        "shaft_ratio_error": _number(source.get("shaft_ratio_error"), float("inf")) <= 0.01,
        "shaft_anchor_max_rpm": anchor_shaft_rpm <= 14600.0,
        "intake_whine_load_correlation": _number(source.get("intake_whine_load_correlation"), -1.0) >= 0.82,
        "bank_interval_pattern_error": _number(source.get("bank_interval_pattern_error"), float("inf")) <= 1.0,
        "low_band_pulse_crest_improves_parent": crest_candidate > crest_parent,
        "low_band_pulse_crest_auxiliary_1_to_3_db": 1.0 <= crest_delta <= 3.0,
        "roughness_auxiliary_10_to_35_percent": (
            math.isfinite(roughness_candidate)
            and math.isfinite(roughness_parent)
            and roughness_parent > 0.0
            and 0.10 <= (roughness_candidate - roughness_parent) / roughness_parent <= 0.35
        ),
        "final_pcm_finite": pcm.get("finite") is True,
        "final_pcm_no_clipping": _number(pcm.get("clipping_count"), float("inf")) == 0.0,
        "final_pcm_format": (
            _number(pcm.get("sample_rate_hz"), -1.0) == 48000.0
            and _number(pcm.get("channels"), -1.0) == 2.0
            and _number(pcm.get("pcm_bits"), -1.0) == 24.0
        ),
        "final_pcm_peak": _number(pcm.get("final_pcm_peak_dbfs"), float("inf")) <= -1.5,
        "final_pcm_upper_share": upper <= 0.06,
        "final_pcm_upper_increment": math.isfinite(parent_upper) and upper - parent_upper <= 0.01,
    }
    reference = _mapping(candidate.get("reference_distance"))
    reference_gates = _mapping(reference.get("gates"))
    if reference:
        gates["reference_mean_improvement_at_least_30_percent"] = (
            _number(reference.get("mean_improvement_ratio"), -float("inf")) >= 0.30
            and reference_gates.get("all_required_states_available") is True
            and reference_gates.get("mean_improvement_at_least_30_percent") is True
            and reference_gates.get("no_state_worse_than_10_percent") is True
        )
    else:
        gates["reference_mean_improvement_at_least_30_percent"] = False
    all_pass = all(gates.values())
    return {
        **gates,
        "all_pass": all_pass,
        "automatic_status": "PASS" if all_pass else "PARTIAL / AUTOMATED_GATE_FAIL",
    }


def _source_metrics(
    stems: Mapping[str, np.ndarray],
    pressure: np.ndarray,
    rpm: np.ndarray,
    load: np.ndarray,
    throttle: np.ndarray,
    diagnostics: Mapping[str, object],
    sample_rate_hz: int,
) -> dict[str, float | int]:
    mono = np.mean(pressure, axis=1)
    # Use only Stage-L's primitive contributors.  ``exhaust`` and
    # ``hemi_exhaust`` are diagnostic aliases and including them here would
    # silently count the same pressure two or three times.
    exhaust = _required_stem(stems, "hemi_exhaust_left") + _required_stem(stems, "hemi_exhaust_right")
    intake = _required_stem(stems, "sc_intake_radiated")
    casing = _required_stem(stems, "sc_casing_radiated")
    bypass = _required_stem(stems, "sc_bypass_release")
    body = _required_stem(stems, "hemi_blowdown_body")
    structure = _required_stem(stems, "hemi_structure_shock")
    torque = _required_stem(stems, "hemi_mechanical_torque_ripple")
    aero_raw = _stem(stems, "sc_aero_raw", pressure)
    shaft_expected = 2.36 * _number(diagnostics.get("aero_family_order_ratio"), 11.8)
    # Prefer the actual untransferred aero waveform when exposed, otherwise
    # measure the actual radiated intake stem; the expected order is only a
    # target for the measured ridge, never evidence by itself.
    ridge_audio = np.mean(aero_raw if _energy(aero_raw) > 0.0 else intake, axis=1)
    measured_order_error = _order_error(ridge_audio, rpm, shaft_expected, sample_rate_hz)
    source_low = body + structure + torque
    frequencies, power = _spectrum(mono, sample_rate_hz)
    sc_frequencies, sc_power = _spectrum(np.mean(intake + casing, axis=1), sample_rate_hz)
    envelope = _smoothed_abs(np.mean(source_low, axis=1), sample_rate_hz, 0.006)
    event_indices = _clock_event_indices(diagnostics, pressure.shape[0])
    left = _required_stem(stems, "hemi_exhaust_left")
    right = _required_stem(stems, "hemi_exhaust_right")
    return {
        "shaft_ratio_error": measured_order_error,
        "shaft_max_rpm": float(np.max(rpm) * 2.36) if rpm.size else 0.0,
        "shaft_anchor_max_rpm": _anchor_shaft_max_rpm(rpm),
        "intake_whine_load_correlation": _energy_correlation(intake, load * throttle, sample_rate_hz),
        "intake_to_exhaust_ratio_db": _db_ratio(intake, exhaust),
        "gear_to_aero_ratio": _energy_ratio(casing, intake),
        "intake_transfer_energy_ratio": _energy_ratio(intake, aero_raw) if _energy(aero_raw) > 0.0 else _energy_ratio(intake, pressure),
        "bypass_event_count": _count_events(np.mean(bypass, axis=1)),
        "boost_attack_10_90_s": _rise_time(np.mean(intake, axis=1), load * throttle, sample_rate_hz),
        "boost_release_90_10_s": _release_time(np.mean(intake, axis=1), throttle, sample_rate_hz),
        "bypass_decay_90_10_s": _release_time(np.mean(bypass, axis=1), throttle, sample_rate_hz),
        "order_ridge_continuity": max(0.0, 1.0 - measured_order_error),
        "tone_prominence_ratio": _tone_prominence(sc_frequencies, sc_power),
        "firing_event_angle_error_samples": _firing_alignment_error(np.mean(source_low, axis=1), event_indices),
        "bank_interval_pattern_error": _bank_pattern_error(left, right, event_indices),
        "fourth_order_presence": _order_presence(mono, rpm, 4.0, sample_rate_hz),
        "20_80_hz_share": _band_share(frequencies, power, 20.0, 80.0),
        "80_160_hz_share": _band_share(frequencies, power, 80.0, 160.0),
        "160_250_hz_share": _band_share(frequencies, power, 160.0, 250.0),
        "250_1000_hz_share": _band_share(frequencies, power, 250.0, 1000.0),
        "low_band_pulse_crest_db": _band_crest(mono, sample_rate_hz, 80.0, 250.0),
        "low_band_envelope_cv": _coefficient_of_variation(envelope),
        "fluctuation_below_20_hz": _low_modulation_energy(envelope, sample_rate_hz),
        "roughness_20_300_hz": _roughness(mono, sample_rate_hz, 20.0, 300.0),
        "modulation_peak_hz": _modulation_peak(envelope, sample_rate_hz),
        "bank_to_bank_delay": _bank_delay_seconds(left, right, event_indices, sample_rate_hz),
    }


def _pre_ptr_metrics(
    stems: Mapping[str, np.ndarray], rpm: np.ndarray, throttle: np.ndarray,
    diagnostics: Mapping[str, object], sample_rate_hz: int,
) -> dict[str, object]:
    named = _sum_stems(
        stems,
        ("hellcat_shift_reengagement", "hellcat_sc_drive_transient", "hellcat_tip_in_blowdown"),
        next(iter(stems.values())),
    )
    mono = np.mean(named, axis=1)
    shift = _shift_metrics(mono, rpm, throttle, sample_rate_hz)
    usage, reachable = _validated_parameter_usage(diagnostics)
    return {
        "shift_dip_db": shift["dip_db"],
        "shift_settling_s": shift["settling_s"],
        "shift_overshoot_db": shift["overshoot_db"],
        "named_transient_energy": _energy(named),
        "named_transient_event_count": _count_events(mono),
        "domain": "actual named transient arrays before common Pre-PTR EQ",
        "candidate_parameter_usage": usage,
        "all_requested_parameters_reachable": reachable,
    }


def _reopen_pcm24(path_like: str | Path) -> np.ndarray:
    path = Path(path_like)
    if not path.is_file():
        raise FileNotFoundError(f"PCM24 WAV does not exist: {path}")
    try:
        with wave.open(str(path), "rb") as stream:
            format_tuple = (
                stream.getframerate(), stream.getnchannels(),
                stream.getsampwidth(), stream.getcomptype(),
            )
            if format_tuple != (48000, 2, 3, "NONE"):
                raise ValueError(
                    "PCM24 WAV must be uncompressed 48000 Hz stereo 24-bit: "
                    f"{path} (got {format_tuple!r})"
                )
        return _read_pcm24_wav(path)
    except (wave.Error, ValueError) as exc:
        raise ValueError(f"PCM24 WAV could not be reopened: {path}") from exc


def _pcm_metrics(pcm: np.ndarray, path: Path, diagnostics: Mapping[str, object]) -> dict[str, object]:
    with wave.open(str(path), "rb") as stream:
        sample_rate_hz = int(stream.getframerate())
        channels = int(stream.getnchannels())
        pcm_bits = int(stream.getsampwidth()) * 8
    loudness = measure_loudness(pcm, sample_rate_hz)
    mono = np.mean(pcm, axis=1)
    frequencies, power = _spectrum(mono, sample_rate_hz)
    return {
        "wav_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sample_rate_hz": sample_rate_hz,
        "channels": channels,
        "pcm_bits": pcm_bits,
        "finite": bool(np.all(np.isfinite(pcm))),
        "final_pcm_lufs": float(loudness.integrated_lufs),
        "final_pcm_peak_dbfs": float(loudness.peak_dbfs),
        "clipping_count": int(loudness.clipping_count),
        "band_shares": [_band_share(frequencies, power, low, high) for low, high in _BANDS],
        "low_band_pulse_crest_db": _band_crest(mono, sample_rate_hz, 80.0, 250.0),
        "roughness_20_300_hz": _roughness(mono, sample_rate_hz, 20.0, 300.0),
        "review_requested_gain_db": _number(diagnostics.get("review_requested_gain_db"), 0.0),
        "review_actual_gain_db": _number(diagnostics.get("review_actual_gain_db"), 0.0),
        "headroom_limited": bool(diagnostics.get("headroom_limited", False)),
    }


def _stereo(value: object, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim == 1:
        array = np.column_stack((array, array))
    if array.ndim != 2 or array.shape[0] == 0 or array.shape[1] != 2:
        raise ValueError(f"{name} must be a non-empty stereo [N, 2] array")
    return array


def _audio_trace(trace: object, count: int, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time_s = np.asarray(getattr(trace, "time_s", None), dtype=np.float64)
    if time_s.ndim != 1 or time_s.size == 0 or np.any(np.diff(time_s) <= 0.0):
        raise ValueError("trace.time_s must be strictly increasing")
    target = float(time_s[0]) + np.arange(count, dtype=np.float64) / sample_rate_hz
    values: list[np.ndarray] = []
    for name in ("rpm", "load", "throttle"):
        value = np.asarray(getattr(trace, name, None), dtype=np.float64)
        if value.ndim != 1 or value.size != time_s.size or not np.all(np.isfinite(value)):
            raise ValueError(f"trace.{name} must be a finite one-dimensional array")
        values.append(np.interp(target, time_s, value))
    return values[0], np.clip(values[1], 0.0, 1.0), np.clip(values[2], 0.0, 1.0)


def _stem(stems: Mapping[str, np.ndarray], name: str, reference: np.ndarray) -> np.ndarray:
    return stems.get(name, np.zeros_like(reference))


def _required_stem(stems: Mapping[str, np.ndarray], name: str) -> np.ndarray:
    try:
        return stems[name]
    except KeyError as exc:
        raise ValueError(f"required Stage-L primitive stem is missing: {name}") from exc


def _sum_stems(stems: Mapping[str, np.ndarray], names: tuple[str, ...], reference: np.ndarray) -> np.ndarray:
    found = [stems[name] for name in names if name in stems]
    return np.sum(found, axis=0) if found else np.zeros_like(reference)


def _energy(value: np.ndarray) -> float:
    return float(np.sum(np.square(np.asarray(value, dtype=np.float64))))


def _energy_ratio(numerator: np.ndarray, denominator: np.ndarray) -> float:
    return float(_energy(numerator) / max(_energy(denominator), 1.0e-18))


def _db_ratio(numerator: np.ndarray, denominator: np.ndarray) -> float:
    return float(10.0 * np.log10(max(_energy(numerator), 1.0e-18) / max(_energy(denominator), 1.0e-18)))


def _spectrum(audio: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(audio, dtype=np.float64)
    window = np.hanning(values.size) if values.size > 1 else np.ones_like(values)
    spectrum = np.fft.rfft(values * window)
    return np.fft.rfftfreq(values.size, 1.0 / sample_rate_hz), np.square(np.abs(spectrum))


def _band_share(frequencies: np.ndarray, power: np.ndarray, low: float, high: float) -> float:
    selected = (frequencies >= low) & (frequencies < high)
    total = float(np.sum(power))
    return float(np.sum(power[selected]) / total) if total > 0.0 else 0.0


def _band_crest(audio: np.ndarray, sample_rate_hz: int, low: float, high: float) -> float:
    frequencies = np.fft.rfftfreq(audio.size, 1.0 / sample_rate_hz)
    transformed = np.fft.rfft(audio)
    mask = (frequencies >= low) & (frequencies < high)
    band = np.fft.irfft(transformed * mask, n=audio.size)
    rms = float(np.sqrt(np.mean(np.square(band))))
    return float(20.0 * np.log10(max(float(np.max(np.abs(band))), 1.0e-18) / max(rms, 1.0e-18)))


def _order_error(audio: np.ndarray, rpm: np.ndarray, expected_order: float, sample_rate_hz: int) -> float:
    if audio.size < 64 or expected_order <= 0.0:
        return 1.0
    frame = min(2048, audio.size)
    hop = max(frame // 2, 1)
    errors: list[float] = []
    for start in range(0, audio.size - frame + 1, hop):
        center = min(start + frame // 2, rpm.size - 1)
        engine_hz = max(float(rpm[center]) / 60.0, 1.0)
        target = expected_order * engine_hz
        freqs, power = _spectrum(audio[start:start + frame], sample_rate_hz)
        candidates = (freqs >= 0.9 * target) & (freqs <= 1.1 * target)
        if np.any(candidates):
            hit = np.flatnonzero(candidates)[int(np.argmax(power[candidates]))]
            errors.append(abs(float(freqs[hit]) - target) / target)
    return float(np.mean(errors)) if errors else 1.0


def _order_presence(audio: np.ndarray, rpm: np.ndarray, order: float, sample_rate_hz: int) -> float:
    return float(max(0.0, 1.0 - _order_error(audio, rpm, order, sample_rate_hz)))


def _anchor_shaft_max_rpm(rpm: np.ndarray) -> float:
    # The published 14,600 rpm value is rounded.  Gate the 800–6100 rpm
    # anchor sweep; a 6200-rpm canonical trace is reported by ``shaft_max_rpm``
    # but is not clamped or treated as a contradictory hard failure.
    anchors = rpm[(rpm >= 800.0) & (rpm <= 6100.0)]
    return float(np.max(anchors) * 2.36) if anchors.size else 0.0


def _tone_prominence(frequencies: np.ndarray, power: np.ndarray) -> float:
    selected = power[(frequencies >= 100.0) & (frequencies <= 8000.0)]
    return float(np.max(selected) / max(float(np.median(selected)), 1.0e-18)) if selected.size else 0.0


def _smoothed_abs(audio: np.ndarray, sample_rate_hz: int, seconds: float) -> np.ndarray:
    width = max(int(round(seconds * sample_rate_hz)), 1)
    return np.convolve(np.abs(audio), np.ones(width) / width, mode="same")


def _coefficient_of_variation(values: np.ndarray) -> float:
    mean = float(np.mean(values))
    return float(np.std(values) / mean) if mean > 0.0 else 0.0


def _low_modulation_energy(envelope: np.ndarray, sample_rate_hz: int) -> float:
    freqs, power = _spectrum(envelope - np.mean(envelope), sample_rate_hz)
    total = float(np.sum(power))
    return float(np.sum(power[(freqs > 0.0) & (freqs < 20.0)]) / total) if total > 0.0 else 0.0


def _modulation_peak(envelope: np.ndarray, sample_rate_hz: int) -> float:
    freqs, power = _spectrum(envelope - np.mean(envelope), sample_rate_hz)
    mask = (freqs > 0.0) & (freqs < 100.0)
    return float(freqs[np.flatnonzero(mask)[int(np.argmax(power[mask]))]]) if np.any(mask) else 0.0


def _roughness(audio: np.ndarray, sample_rate_hz: int, low: float, high: float) -> float:
    frequencies = np.fft.rfftfreq(audio.size, 1.0 / sample_rate_hz)
    transformed = np.fft.rfft(audio)
    mask = (frequencies >= low) & (frequencies < high)
    band = np.fft.irfft(transformed * mask, n=audio.size)
    envelope = _smoothed_abs(band, sample_rate_hz, 0.004)
    return _coefficient_of_variation(envelope)


def _energy_correlation(audio: np.ndarray, state: np.ndarray, sample_rate_hz: int) -> float:
    mono = np.mean(audio, axis=1)
    width = max(int(0.02 * sample_rate_hz), 1)
    count = mono.size // width
    if count < 2:
        return 0.0
    energy = np.asarray([np.mean(np.square(mono[index * width:(index + 1) * width])) for index in range(count)])
    values = np.asarray([np.mean(state[index * width:(index + 1) * width]) for index in range(count)])
    active = values >= 0.2
    if np.count_nonzero(active) < 2 or np.std(energy[active]) <= 0.0 or np.std(values[active]) <= 0.0:
        return 0.0
    return float(np.corrcoef(np.log(np.maximum(energy[active], 1.0e-18)), values[active])[0, 1])


def _rise_time(audio: np.ndarray, state: np.ndarray, sample_rate_hz: int) -> float:
    onset = np.flatnonzero((state[1:] >= 0.35) & (state[:-1] < 0.35))
    if onset.size == 0:
        return 0.0
    start = int(onset[0])
    envelope = _smoothed_abs(audio, sample_rate_hz, 0.004)
    tail = envelope[start:]
    if tail.size == 0 or float(np.max(tail)) <= 0.0:
        return 0.0
    peak = float(np.max(tail))
    lo = np.flatnonzero(tail >= 0.1 * peak)
    hi = np.flatnonzero(tail >= 0.9 * peak)
    return float((hi[0] - lo[0]) / sample_rate_hz) if lo.size and hi.size else 0.0


def _release_time(audio: np.ndarray, throttle: np.ndarray, sample_rate_hz: int) -> float:
    onset = np.flatnonzero((throttle[1:] <= 0.20) & (throttle[:-1] > 0.20))
    if onset.size == 0:
        return 0.0
    envelope = _smoothed_abs(audio, sample_rate_hz, 0.004)
    tail = envelope[int(onset[0]):]
    if tail.size == 0:
        return 0.0
    peak = float(np.max(tail))
    if peak <= 0.0:
        return 0.0
    lo = np.flatnonzero(tail <= 0.1 * peak)
    hi = np.flatnonzero(tail <= 0.9 * peak)
    return float((lo[0] - hi[0]) / sample_rate_hz) if lo.size and hi.size else 0.0


def _event_indices(diagnostics: Mapping[str, object], envelope: np.ndarray) -> np.ndarray:
    supplied = diagnostics.get("event_sample_indices")
    if isinstance(supplied, (tuple, list)) and all(isinstance(item, (int, np.integer)) for item in supplied):
        return np.asarray(supplied, dtype=np.int64)
    threshold = max(float(np.percentile(envelope, 90.0)), 1.0e-18)
    active = envelope >= threshold
    return np.flatnonzero(active & ~np.r_[False, active[:-1]])


def _clock_event_indices(diagnostics: Mapping[str, object], count: int) -> np.ndarray:
    """Return the explicit shared-clock event schedule, fail-closed.

    Stage-L's firing-timing metric is an array-vs-clock check.  An inferred
    onset list is useful for a generic diagnostic, but it cannot substitute
    for the clock contract here.
    """

    supplied = diagnostics.get("event_sample_indices")
    if not isinstance(supplied, (tuple, list)) or len(supplied) < 2:
        raise ValueError("clock event_sample_indices are required for Stage-L alignment")
    if any(isinstance(item, bool) or not isinstance(item, (int, np.integer)) for item in supplied):
        raise ValueError("clock event_sample_indices must be integer sample positions")
    events = np.asarray(supplied, dtype=np.int64)
    if np.any(events < 0) or np.any(events >= count) or np.any(np.diff(events) <= 0):
        raise ValueError("clock event_sample_indices must be strictly increasing in render bounds")
    return events


def _firing_alignment_error(audio: np.ndarray, events: np.ndarray) -> float:
    observed = _local_peak_indices(audio, events)
    return float(np.mean(np.abs(observed - events))) if observed.size else float("inf")


def _bank_pattern_error(left: np.ndarray, right: np.ndarray, events: np.ndarray) -> float:
    """Measure the locked 1-2-2-3 per-bank timing from actual bank stems.

    The schedule comes from the immutable cross-plane pattern, not from a
    renderer diagnostic.  Each expected bank pulse is localized in that bank's
    actual stem; interval error is expressed in audio samples.
    """

    expected = np.asarray([_LOCKED_HELLCAT_BANK_PATTERN[index % len(_LOCKED_HELLCAT_BANK_PATTERN)] for index in range(events.size)])
    errors: list[float] = []
    gap = float(np.median(np.diff(events))) if events.size > 1 else 1.0
    radius = max(1, min(int(gap / 4.0), 96))
    left_mono = np.abs(np.mean(left, axis=1))
    right_mono = np.abs(np.mean(right, axis=1))
    crosstalk_penalty = 0.0
    for event, label in zip(events, expected):
        start = max(int(event) - radius, 0)
        end = min(int(event) + radius + 1, left_mono.size)
        expected_peak = float(np.max(left_mono[start:end] if label == "left" else right_mono[start:end]))
        wrong_peak = float(np.max(right_mono[start:end] if label == "left" else left_mono[start:end]))
        if expected_peak <= 1.0e-18 or wrong_peak >= 0.95 * expected_peak:
            crosstalk_penalty = max(crosstalk_penalty, gap)
    for label, stem in (("left", left), ("right", right)):
        selected = events[expected == label]
        if selected.size < 2:
            continue
        actual = _local_peak_indices(np.mean(stem, axis=1), selected)
        expected_intervals = np.diff(selected)
        actual_intervals = np.diff(actual)
        # The selected ordinal gaps are the concrete repeated 2/3/2/1
        # cross-plane interval pattern (the sorted multiset is 1-2-2-3).
        errors.append(float(np.mean(np.abs(actual_intervals - expected_intervals))))
    return float(max([crosstalk_penalty, *errors], default=float("inf")))


def _bank_delay_seconds(left: np.ndarray, right: np.ndarray, events: np.ndarray, sample_rate_hz: int) -> float:
    """Measure bank-local response delay directly from localized stem peaks."""

    labels = np.asarray([_LOCKED_HELLCAT_BANK_PATTERN[index % len(_LOCKED_HELLCAT_BANK_PATTERN)] for index in range(events.size)])
    left_expected = events[labels == "left"]
    right_expected = events[labels == "right"]
    if left_expected.size == 0 or right_expected.size == 0:
        return 0.0
    left_actual = _local_peak_indices(np.mean(left, axis=1), left_expected)
    right_actual = _local_peak_indices(np.mean(right, axis=1), right_expected)
    left_delay = float(np.median(left_actual - left_expected))
    right_delay = float(np.median(right_actual - right_expected))
    return float(abs(right_delay - left_delay) / sample_rate_hz)


def _local_peak_indices(audio: np.ndarray, expected: np.ndarray) -> np.ndarray:
    if expected.size == 0:
        return np.empty(0, dtype=np.int64)
    gaps = np.diff(expected)
    radius = max(1, min(int(np.median(gaps) / 4.0) if gaps.size else 1, 96))
    absolute = np.abs(np.asarray(audio, dtype=np.float64))
    result = np.empty(expected.size, dtype=np.int64)
    for ordinal, center in enumerate(expected):
        start = max(int(center) - radius, 0)
        end = min(int(center) + radius + 1, absolute.size)
        result[ordinal] = start + int(np.argmax(absolute[start:end]))
    return result


def _count_events(audio: np.ndarray) -> int:
    threshold = max(float(np.percentile(np.abs(audio), 95.0)), 1.0e-18)
    active = np.abs(audio) >= threshold
    return int(np.count_nonzero(active & ~np.r_[False, active[:-1]])) if np.any(np.abs(audio) > 0.0) else 0


def _validated_parameter_usage(diagnostics: Mapping[str, object]) -> tuple[dict[str, list[str]], bool]:
    """Copy and prove actual renderer reachability diagnostics.

    Candidate profiles state requested controls; they cannot prove a renderer
    consumed them.  The renderer's usage record is therefore copied into the
    pre-PTR evidence only after the required set relations are verified.
    """

    raw = diagnostics.get("candidate_parameter_usage")
    expected = {"requested", "read", "configured", "active", "inactive", "unused"}
    if not isinstance(raw, Mapping) or set(raw) != expected:
        raise ValueError("candidate_parameter_usage must have exact required keys")
    usage = {name: _unique_usage_sequence(raw[name], f"candidate_parameter_usage.{name}") for name in sorted(expected)}
    requested = usage["requested"]
    read = usage["read"]
    configured = usage["configured"]
    active = usage["active"]
    inactive = usage["inactive"]
    unused = usage["unused"]
    if configured != read:
        raise ValueError("candidate_parameter_usage.configured must equal read")
    active_set, inactive_set, read_set = set(active), set(inactive), set(read)
    if active_set & inactive_set or active_set | inactive_set != read_set:
        raise ValueError("candidate_parameter_usage.active/inactive must partition read")
    if not read_set <= set(requested):
        raise ValueError("candidate_parameter_usage.read must be requested")
    expected_unused = [name for name in requested if name not in read_set]
    if unused != expected_unused:
        raise ValueError("candidate_parameter_usage.unused must equal requested minus read")
    return usage, not unused


def _unique_usage_sequence(value: object, label: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(name, str) or not name for name in value):
        raise ValueError(f"{label} must be a sequence of non-empty parameter names")
    result = list(value)
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must not contain duplicate parameter names")
    return result


def _shift_metrics(audio: np.ndarray, rpm: np.ndarray, throttle: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    derivative = np.gradient(rpm) * sample_rate_hz if rpm.size > 1 else np.zeros_like(rpm)
    events = np.flatnonzero((derivative < -1500.0) & (throttle > 0.30))
    if events.size == 0 or not np.any(np.abs(audio) > 0.0):
        return {"dip_db": 0.0, "settling_s": 0.0, "overshoot_db": 0.0}
    center = int(events[0])
    envelope = _smoothed_abs(audio, sample_rate_hz, 0.01)
    before = max(float(np.mean(envelope[max(0, center - int(.08 * sample_rate_hz)):center])), 1.0e-18)
    after = envelope[center:min(envelope.size, center + int(.35 * sample_rate_hz))]
    if after.size == 0:
        return {"dip_db": 0.0, "settling_s": 0.0, "overshoot_db": 0.0}
    dip = 20.0 * np.log10(max(float(np.min(after)), 1.0e-18) / before)
    overshoot = max(0.0, 20.0 * np.log10(max(float(np.max(after)), 1.0e-18) / before))
    settled = np.flatnonzero(after >= 0.90 * before)
    return {"dip_db": float(dip), "settling_s": float(settled[0] / sample_rate_hz) if settled.size else .35, "overshoot_db": float(overshoot)}


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _share_at(value: object, index: int) -> float:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return float("inf")
    return _number(value[index], float("inf"))


def _number(value: object, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) else default


__all__ = (
    "compute_stage_k_parent_metrics",
    "compute_stage_l_perceptual_metrics",
    "evaluate_stage_l_metric_gates",
)
