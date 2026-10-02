"""Synthetic, unit-energy response bases for hybrid event rendering."""

from numbers import Integral, Real

import numpy as np
from scipy.signal import butter, fftconvolve, sosfreqz


SAMPLE_RATE = 48_000
SAMPLE_COUNT = 12_288
KERNEL_TAPS = 1_024
FFT_SIZE = 16_384
TAIL_TAPER_SAMPLES = 256


def _timing_value(value, name, minimum, maximum):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number in [{minimum}, {maximum}]")
    value = float(value)
    if not np.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be a finite number in [{minimum}, {maximum}]")
    return value


def _validated_levels(levels_db):
    try:
        levels = np.asarray(levels_db)
    except (TypeError, ValueError) as exc:
        raise ValueError("levels_db must contain eight finite real values") from exc
    if levels.shape != (8,) or levels.dtype.kind not in "iuf":
        raise ValueError("levels_db must contain eight finite real values")
    levels = levels.astype(np.float64, copy=True)
    if not np.all(np.isfinite(levels)):
        raise ValueError("levels_db must contain eight finite real values")
    return levels


def _minimum_phase_kernel(levels_db):
    control_hz = np.geomspace(40.0, 4_000.0, num=8)
    smooth_db = np.convolve(
        np.pad(levels_db, (1, 1), mode="edge"),
        np.array([0.25, 0.5, 0.25], dtype=np.float64),
        mode="valid",
    )
    control_log_magnitude = smooth_db * (np.log(10.0) / 20.0)

    frequencies = np.fft.rfftfreq(FFT_SIZE, d=1.0 / SAMPLE_RATE)
    control_magnitude = np.interp(
        np.log(np.maximum(frequencies, control_hz[0])),
        np.log(control_hz),
        control_log_magnitude,
    )
    highpass = butter(4, 40.0, btype="highpass", fs=SAMPLE_RATE, output="sos")
    lowpass = butter(4, 4_000.0, btype="lowpass", fs=SAMPLE_RATE, output="sos")
    _, hp_response = sosfreqz(highpass, worN=frequencies, fs=SAMPLE_RATE)
    _, lp_response = sosfreqz(lowpass, worN=frequencies, fs=SAMPLE_RATE)
    boundary_magnitude = np.maximum(np.abs(hp_response * lp_response), 1e-12)
    log_magnitude = control_magnitude + np.log(boundary_magnitude)
    log_magnitude -= np.max(log_magnitude)

    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        real_cepstrum = np.fft.irfft(log_magnitude, n=FFT_SIZE)
        minimum_phase_cepstrum = np.zeros(FFT_SIZE, dtype=np.float64)
        minimum_phase_cepstrum[0] = real_cepstrum[0]
        minimum_phase_cepstrum[1 : FFT_SIZE // 2] = 2.0 * real_cepstrum[1 : FFT_SIZE // 2]
        minimum_phase_cepstrum[FFT_SIZE // 2] = real_cepstrum[FFT_SIZE // 2]
        designed_spectrum = np.exp(np.fft.rfft(minimum_phase_cepstrum))
        designed_impulse = np.fft.irfft(designed_spectrum, n=FFT_SIZE)

    # Fixed tap truncation does not guarantee strict minimum phase afterward.
    kernel = designed_impulse[:KERNEL_TAPS].copy()
    norm = float(np.linalg.norm(kernel))
    if not np.all(np.isfinite(kernel)) or not np.isfinite(norm) or norm <= np.finfo(np.float64).eps:
        raise ValueError("levels_db produce a degenerate response kernel")
    return kernel / norm


def _causal_color(signal, kernel):
    return fftconvolve(signal, kernel, mode="full")[:SAMPLE_COUNT]


def _taper_tail(signal):
    tapered = signal.copy()
    fade = np.linspace(0.0, np.pi, TAIL_TAPER_SAMPLES, dtype=np.float64)
    tapered[-TAIL_TAPER_SAMPLES:] *= 0.5 * (1.0 + np.cos(fade))
    tapered[-1] = 0.0
    return tapered


def _remove_dc_smooth(signal):
    phase = np.linspace(0.0, np.pi, SAMPLE_COUNT, dtype=np.float64)
    correction = np.sin(phase) ** 2
    correction /= np.sum(correction)
    return signal - np.sum(signal) * correction


def _normalize(signal):
    signal = signal.copy()
    signal[0] = 0.0
    signal[-1] = 0.0
    norm = float(np.linalg.norm(signal))
    if not np.all(np.isfinite(signal)) or not np.isfinite(norm) or norm <= np.finfo(np.float64).eps:
        raise ValueError("event response basis is degenerate")
    return signal / norm


def event_bases(attack_ms, tail_ms, levels_db, seed=5_900_023):
    """Return synthetic pressure/noise bases with fixed 256 ms, 48 kHz support.

    The timing parameters describe the design envelope; they are not measured
    attack or decay values of the eventual rendered response.
    """
    attack_ms = _timing_value(attack_ms, "attack_ms", 1.0, 100.0)
    tail_ms = _timing_value(tail_ms, "tail_ms", 5.0, 120.0)
    levels_db = _validated_levels(levels_db)
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (Integral, np.integer)):
        raise ValueError("seed must be a positive integer")
    seed = int(seed)
    if seed <= 0:
        raise ValueError("seed must be a positive integer")

    kernel = _minimum_phase_kernel(levels_db)
    time = np.arange(SAMPLE_COUNT, dtype=np.float64) / SAMPLE_RATE
    rise = attack_ms / 1_000.0
    decay = tail_ms / 1_000.0
    attack = -np.expm1(-time / rise)
    envelope = attack * attack * np.exp(-time / decay)

    pressure = np.diff(envelope, prepend=0.0)
    pressure = _taper_tail(_causal_color(pressure, kernel))
    pressure = _normalize(_remove_dc_smooth(pressure))

    rng = np.random.default_rng(seed)
    noise_a = _taper_tail(_causal_color(rng.standard_normal(SAMPLE_COUNT), kernel) * envelope)
    noise_b = _taper_tail(_causal_color(rng.standard_normal(SAMPLE_COUNT), kernel) * envelope)
    noise_a = _remove_dc_smooth(noise_a)
    noise_b = _remove_dc_smooth(noise_b)

    noise_a = _normalize(noise_a - np.dot(noise_a, pressure) * pressure)
    noise_b -= np.dot(noise_b, pressure) * pressure
    noise_b -= np.dot(noise_b, noise_a) * noise_a
    noise_b = _normalize(noise_b)

    return pressure, noise_a, noise_b
