"""Analyze immutable offline captures; derived audio and listening copies are explicit.

Example:
  python -B analyze_captures.py --capture low=CAPTURE_DIR --v0 low=V0_DIR --out NEW_DIR
Use repeated --capture/--v0 for scenes. No capture, model, seed or DSP is changed.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

import numpy as np
import scipy
from scipy import optimize, signal
from scipy.io import wavfile

TARGET = (1 / .6, 1 / .5)
SLOW = (.5, 10.)
AUDIO_COLUMNS = ("rawsum_internal", "post_dsp_prelevel_internal", "leveled_preclip_int16_units",
                 "final_normalized_pcm", "leveler_gain", "clip_flag")


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    with open(path, "x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def signal_health(x):
    x = np.asarray(x, dtype=np.float64)
    finite = np.isfinite(x)
    y = x[finite]
    return {"valid": bool(finite.all() and x.size), "frames": int(x.size),
            "nonfinite_count": int(x.size - y.size),
            "mean": float(np.mean(y)) if y.size else None,
            "rms": float(np.sqrt(np.mean(y * y))) if y.size else None,
            "peak": float(np.max(np.abs(y))) if y.size else None,
            "minimum": float(np.min(y)) if y.size else None,
            "maximum": float(np.max(y)) if y.size else None,
            "finite_statistics_only_when_invalid": bool(not finite.all())}


def rms_envelope(x, fs, window_ms, hop_ms=10):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("Envelope requires finite mono data; nonfinite data is not repaired")
    width = max(1, int(math.floor(fs * window_ms / 1000 + .5)))
    hop = max(1, int(math.floor(fs * hop_ms / 1000 + .5)))
    if x.size < width:
        raise ValueError("Signal shorter than RMS window")
    starts = np.arange(0, x.size - width + 1, hop)
    summed = np.concatenate(([0.], np.cumsum(x * x, dtype=np.float64)))
    envelope = np.sqrt(np.maximum(0, (summed[starts + width] - summed[starts]) / width))
    return (starts + width / 2) / fs, envelope, fs / hop


def bandpower(f, p, low, high):
    f, p = np.asarray(f), np.asarray(p)
    low, high = max(float(f[0]), low), min(float(f[-1]), high)
    if low >= high:
        return 0.
    ix = (f > low) & (f < high)
    xx = np.concatenate(([low], f[ix], [high]))
    yy = np.concatenate(([np.interp(low, f, p)], p[ix], [np.interp(high, f, p)]))
    return float(np.trapezoid(yy, xx))


def fractional_lag_acf(x, fs, lag_s):
    x = np.asarray(x, dtype=np.float64)
    shift = float(lag_s) * fs
    n = int(np.floor(x.size - 1 - shift)) + 1
    if n < 3 or shift < 0:
        return 0.
    a = x[:n]
    b = np.interp(np.arange(n) + shift, np.arange(x.size), x)
    a = a - np.mean(a)
    b = b - np.mean(b)
    denominator = np.sqrt(np.dot(a, a) * np.dot(b, b))
    return float(np.dot(a, b) / denominator) if denominator > 0 else 0.


def acf_metrics(x, fs, lo=.5, hi=.6):
    x = np.asarray(x, dtype=np.float64)
    v = x - np.mean(x)
    n = v.size
    maxlag = min(int(math.ceil(hi * fs)) + 1, n - 2)
    if n < 3 or maxlag < 1 or np.dot(v, v) < np.finfo(float).tiny:
        return {"peak_lag_s": None, "peak_correlation": None, "status": "NO_VARIANCE"}, (np.array([]), np.array([]))
    corr = signal.correlate(v, v, mode="full", method="fft")[n - 1:n + maxlag]
    sq = np.concatenate(([0.], np.cumsum(v * v)))
    lags = np.arange(corr.size)
    den = np.sqrt(np.maximum(0, sq[n - lags] * (sq[n] - sq[lags])))
    rho = np.divide(corr, den, out=np.zeros_like(corr), where=den > 0)
    times = lags / fs
    select = np.flatnonzero((times >= lo) & (times <= hi))
    if not select.size:
        return {"peak_lag_s": None, "peak_correlation": None, "status": "TOO_SHORT"}, (times, rho)
    k = select[np.argmax(rho[select])]
    left, right = max(lo, (k - 1) / fs), min(hi, (k + 1) / fs)
    if right > left:
        refined = optimize.minimize_scalar(lambda lag: -fractional_lag_acf(x, fs, lag),
                                           bounds=(left, right), method="bounded",
                                           options={"xatol": 1e-10})
        lag = float(refined.x)
    else:
        lag = float(times[k])
    return {"peak_lag_s": lag, "peak_correlation": fractional_lag_acf(x, fs, lag),
            "search_s": [lo, hi], "status": "DESCRIPTIVE_NOT_AN_ACCEPTANCE_GATE",
            "method": "FFT overlap-energy ACF grid, continuous-lag Pearson refinement by linear interpolation"}, (times, rho)


def envelope_metrics(x, fs, window_ms):
    t, env, rate = rms_envelope(x, fs, window_ms)
    nperseg = min(env.size, max(8, int(rate * 20)))
    f, p = signal.welch(env, fs=rate, nperseg=nperseg, detrend="constant", scaling="density")
    mean = float(np.mean(env))
    slow = bandpower(f, p, *SLOW)
    target = bandpower(f, p, *TARGET)
    select = (f >= SLOW[0]) & (f <= SLOW[1])
    peak = float(f[select][np.argmax(p[select])]) if select.any() and slow > 0 else None
    acf, acf_arrays = acf_metrics(env, rate)
    result = {"window_ms": window_ms, "hop_ms": 10, "envelope_fs": rate,
              "mean_rms": mean, "std_rms": float(np.std(env)),
              "cv": float(np.std(env) / mean) if mean > 0 else 0.,
              "slow_band_hz": list(SLOW), "target_band_hz": list(TARGET),
              "slow_power": slow, "target_power": target,
              "slow_power_over_mean_squared": slow / (mean * mean) if mean > 0 else 0.,
              "target_power_over_mean_squared": target / (mean * mean) if mean > 0 else 0.,
              "target_fraction_of_slow": target / slow if slow > 0 else 0.,
              "slow_peak_hz": peak, "psd_resolution_hz": float(f[1] - f[0]),
              "acf": acf, "absolute_power_unit": "input_unit_squared",
              "normalization": "none; dimensionless ratios are reported in addition to original-unit power"}
    return result, {"time_s": t, "rms": env, "psd_hz": f, "psd": p,
                    "acf_lag_s": acf_arrays[0], "acf": acf_arrays[1]}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        names = reader.fieldnames
        rows = list(reader)
    if not rows or not names:
        raise ValueError(f"Empty CSV: {path}")
    result = {name: np.array([float(row[name]) for row in rows]) for name in names}
    if any(not np.isfinite(v).all() for v in result.values()):
        raise ValueError(f"Nonfinite control/state CSV: {path}")
    return result


def continuous_cycle_phase(state):
    t = state["t_s"]
    if np.any(np.diff(t) <= 0):
        raise ValueError("State timestamps are not increasing")
    phase = np.unwrap(state["cycle_angle_rad"], period=4 * np.pi) / (4 * np.pi)
    if np.any(np.diff(phase) <= 0) or np.max(np.diff(phase)) >= .5:
        raise ValueError("State rate cannot resolve monotonic 720-degree phase")
    return phase


def make_e2(source, fs, state, duration_s, scene):
    if scene not in ("low", "high"):
        raise ValueError("E2 is defined only for low/high steady scenes, never dynamic playback")
    phase = continuous_cycle_phase(state)
    t = state["t_s"]
    if t[-1] < 6:
        raise ValueError("E2 needs source data after its fixed five-second exclusion")
    first = float(np.ceil(np.interp(5., t, phase) + 1e-9))
    start = float(np.interp(first, phase, t))
    next_cycle = float(np.interp(first + 1, phase, t))
    cycles = max(1, int(math.floor(.55 / (next_cycle - start) + .5)))
    end = float(np.interp(first + cycles, phase, t))
    if first + cycles >= phase[-1]:
        raise ValueError("E2 complete-cycle crop is outside recorded data")
    lo, hi = int(math.floor(start * fs + .5)), int(math.floor(end * fs + .5))
    fade = max(2, int(math.floor(fs * .005 + .5)))
    left = fade // 2
    offsets = np.arange(-left, fade - left)
    if lo + offsets[0] < 0 or hi + offsets[-1] >= len(source) or hi - lo <= 2 * fade:
        raise ValueError("E2 seam context is outside recorded data")
    loop = np.array(source[lo:hi], copy=True)
    weights = .5 - .5 * np.cos(np.linspace(0, np.pi, fade))
    # Overlap real continuation after crop end with real preroll before crop start.
    # Write across the wrap; keep the complete-cycle period (do not shorten by 5 ms).
    loop[np.mod(offsets, loop.size)] = ((1 - weights) * source[hi + offsets]
                                                  + weights * source[lo + offsets])
    output = np.resize(loop, int(math.floor(duration_s * fs + .5)))
    receipt = {"scope": "FINITE_LOOP_COUNTEREXAMPLE_CONTROL_NOT_HELLCAT_OR_DYNAMIC_MODEL",
               "source": "E0 rawsum, original internal audio units", "excluded_initial_s": 5,
               "start_cycle_time_s": start, "end_cycle_time_s": end,
               "start_absolute_unwrapped_cycle": first, "complete_720_cycles": cycles,
               "nominal_target_period_s": .55, "crop_start_frame": lo, "crop_end_frame": hi,
               "rounded_boundary_errors_s": [lo / fs - start, hi / fs - end],
               "effective_period_frames": int(loop.size), "effective_period_s": loop.size / fs,
               "effective_repeat_hz": fs / loop.size, "crossfade_frames": fade,
               "crossfade_requested_ms": 5, "crossfade_actual_ms": fade / fs * 1000,
               "crossfade": "fixed raised-cosine blend of recorded continuation/preroll across wrap, period preserved",
               "seed_phase_gain_or_window_search": False}
    return output, loop, receipt


def listening_gain(segments, target_rms, peak_limit):
    n = sum(len(x) for x in segments)
    square = sum(float(np.dot(np.asarray(x, dtype=float), np.asarray(x, dtype=float))) for x in segments)
    rms = math.sqrt(square / n) if n else 0.
    peak = max((float(np.max(np.abs(x))) for x in segments if len(x)), default=0.)
    rms_gain = target_rms / rms if rms else 0.
    peak_gain = peak_limit / peak if peak else 0.
    gain = min(rms_gain, peak_gain) if rms and peak else 0.
    return {"gain": gain, "pooled_original_rms": rms, "original_peak": peak,
            "target_rms": target_rms, "peak_limit": peak_limit,
            "peak_constraint_active": bool(peak_gain < rms_gain),
            "achieved_pooled_rms": rms * gain, "achieved_peak": peak * gain,
            "policy": "one fixed scalar per route pooled over all available scenes; no limiter or per-window gains",
            "measurement_audio_modified": False}


def resample(x, fs, target):
    if fs == target:
        return np.asarray(x, dtype=np.float64)
    ratio = Fraction(int(target), int(fs))
    return signal.resample_poly(np.asarray(x, dtype=np.float64), ratio.numerator, ratio.denominator)


def top_peaks(f, p, low, high, count=10):
    peaks, _ = signal.find_peaks(p)
    peaks = [int(k) for k in peaks if low <= f[k] <= high]
    peaks.sort(key=lambda k: float(p[k]), reverse=True)
    return [{"axis": float(f[k]), "density": float(p[k])} for k in peaks[:count]]


def spectral_metrics(x, fs, state, steady):
    nperseg = min(len(x), int(fs * 4))
    f, p = signal.welch(x, fs=fs, nperseg=nperseg, detrend="constant", scaling="density")
    rpm = float(np.mean(state["rpm"]))
    result = {"frequency_resolution_hz": float(f[1] - f[0]),
              "major_frequency_peaks": top_peaks(f, p, 10, min(10000, fs / 2)),
              "mean_rpm": rpm,
              "frequency_to_mean_rpm_order_validity": "steady descriptive" if steady else "nonstationary; use angle spectrum"}
    if steady:
        sidebands = []
        for order in (.5, 1, 2, 4, 8, 12, 16):
            carrier = rpm / 60 * order
            central = bandpower(f, p, carrier - .5, carrier + .5)
            sides = (bandpower(f, p, carrier - TARGET[1], carrier - TARGET[0])
                     + bandpower(f, p, carrier + TARGET[0], carrier + TARGET[1]))
            sidebands.append({"crank_order": order, "carrier_hz": carrier,
                              "carrier_plus_minus_half_hz_power": central,
                              "sideband_power_at_target_offsets": sides,
                              "sideband_to_carrier_power": sides / central if central > 0 else None})
        result["sidebands"] = sidebands
    cycles = state["integrated_cycles"]
    times = state["t_s"]
    dc = np.diff(cycles)
    if np.any(dc <= 0):
        result["order_status"] = "INVALID_NONMONOTONIC_CYCLE_TRACE"
        return result, (f, p), None
    samples_per_cycle = 512
    min_cps = float(np.min(dc / np.diff(times)))
    cutoff = min(fs * .4, .4 * samples_per_cycle * min_cps)
    filtered = signal.sosfiltfilt(signal.butter(8, cutoff, fs=fs, output="sos"), x)
    cycle_grid = np.arange(math.ceil(cycles[0] * samples_per_cycle),
                           math.floor(cycles[-1] * samples_per_cycle)) / samples_per_cycle
    angle_times = np.interp(cycle_grid, cycles, times)
    angled = np.interp(angle_times * fs, np.arange(len(filtered)), filtered)
    of, op = signal.welch(angled, fs=samples_per_cycle,
                          nperseg=min(len(angled), samples_per_cycle * 16),
                          detrend="constant", scaling="density")
    orders = of / 2
    result["angle_spectrum"] = {"major_crank_orders": top_peaks(orders, op, .25, 64),
                                  "samples_per_720_cycle": samples_per_cycle,
                                  "time_domain_lowpass_hz_before_angle_resampling": cutoff,
                                  "method": "actual integrated_cycles; conservative anti-alias lowpass, linear time-to-angle interpolation",
                                  "no_phase_alignment_or_source_fitting": True}
    return result, (f, p), (orders, op)


def analyze_signal(x, fs, domain, state, steady):
    health = signal_health(x)
    result = {"domain": domain, "sample_rate": fs, "health": health}
    artifacts = {}
    if not health["valid"]:
        result["status"] = "INVALID_NONFINITE_OR_EMPTY_NOT_REPAIRED"
        return result, artifacts
    for width in (10, 20):
        result[f"envelope_{width}ms"], artifacts[f"envelope_{width}ms"] = envelope_metrics(x, fs, width)
    if steady and len(x) > fs * 6:
        fixed_tail = x[fs * 5:]
        result["steady_after_fixed_5s_exclusion"] = {
            "excluded_s": 5, "reason": "fixed secondary steady view; V0 has no reconstructed physical warmup trace",
            "health": signal_health(fixed_tail),
            "envelope_10ms": envelope_metrics(fixed_tail, fs, 10)[0],
            "envelope_20ms": envelope_metrics(fixed_tail, fs, 20)[0]}
    t100, e100, _ = rms_envelope(x, fs, 100, 100)
    jumps = np.diff(20 * np.log10(np.maximum(e100, np.finfo(float).tiny)))
    result["dynamic_100ms_rms"] = {"minimum": float(e100.min()), "maximum": float(e100.max()),
                                   "median": float(np.median(e100)),
                                   "max_adjacent_window_change_db": float(np.max(np.abs(jumps))) if jumps.size else 0.,
                                   "window_ms": 100, "hop_ms": 100,
                                   "meaning": "original units, same windows for each route; not calibrated loudness"}
    artifacts["rms100"] = (t100, e100)
    wave = resample(x, fs, 4000)
    result["waveform_acf_4khz_lowpassed"], artifacts["waveform_acf"] = acf_metrics(wave, 4000)
    result["waveform_acf_interpretation"] = "engine-order recurrence is expected; this peak alone is neither noise failure nor improvement"
    result["spectrum"], artifacts["spectrum"], artifacts["orders"] = spectral_metrics(x, fs, state, steady)
    result["status"] = "DESCRIPTIVE_MEASUREMENT_NO_AUTOMATIC_ACOUSTIC_PASS"
    return result, artifacts


def save_artifacts(directory, route, artifacts):
    for name, row in artifacts.items():
        if row is None:
            continue
        if name.startswith("envelope_"):
            np.savetxt(directory / f"{route}-{name}.csv", np.column_stack((row["time_s"], row["rms"])),
                       delimiter=",", header="t_s,rms_original_units", comments="")
            np.savetxt(directory / f"{route}-{name}-psd.csv", np.column_stack((row["psd_hz"], row["psd"])),
                       delimiter=",", header="frequency_hz,density_original_unit_squared_per_hz", comments="")
        else:
            np.savetxt(directory / f"{route}-{name}.csv", np.column_stack(row), delimiter=",", comments="")


def make_plot(path, scene, metrics, artifacts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 2, figsize=(13, 8))
    for route, values in artifacts.items():
        if not values:
            continue
        env = values["envelope_10ms"]
        mean = metrics[route]["envelope_10ms"]["mean_rms"]
        axs[0, 0].plot(env["time_s"], env["rms"] / max(mean, 1e-30), label=route, linewidth=.6)
        axs[0, 1].semilogy(env["psd_hz"], np.maximum(env["psd"] / max(mean * mean, 1e-60), 1e-20), label=route)
        lag, rho = values["waveform_acf"]
        axs[1, 0].plot(lag, rho, label=route)
        lag, rho = env["acf_lag_s"], env["acf"]
        axs[1, 1].plot(lag, rho, label=route)
    axs[0, 0].set(title="10 ms RMS / own mean (dimensionless display)", xlabel="physical trace time (s)")
    axs[0, 1].set(title="Envelope PSD / mean RMS squared", xlim=SLOW, xlabel="Hz")
    axs[0, 1].axvspan(*TARGET, color="grey", alpha=.2)
    axs[1, 0].set(title="Waveform ACF (4 kHz sample rate / 2 kHz Nyquist); carrier repeats expected", xlim=(.45, .65), ylim=(-1, 1), xlabel="lag (s)")
    axs[1, 1].set(title="10 ms RMS envelope ACF", xlim=(.45, .65), ylim=(-1, 1), xlabel="lag (s)")
    for ax in axs.flat:
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle(f"{scene}: original signals measured; no audio gain applied to measurements")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def named_paths(values):
    result = {}
    for value in values:
        name, sep, location = value.partition("=")
        if not sep or not re.fullmatch(r"[a-z][a-z0-9_-]*", name) or name in result:
            raise ValueError("Use each scene once as name=absolute_path")
        result[name] = Path(location).resolve()
    return result


def load_capture(path):
    meta = json.loads((path / "capture.json").read_text(encoding="utf-8"))
    fs, pfs = int(meta["audio_fs"]), int(meta["physics_fs"])
    expected_audio, expected_physics = int(meta["audio_frames"]), int(meta["physics_frames"])
    if (path / "audio-taps.f32le").stat().st_size != expected_audio * 6 * 4:
        raise ValueError("Audio tap byte count/schema mismatch")
    if (path / "pressure-input.f32le").stat().st_size != expected_physics * 18 * 4:
        raise ValueError("Pressure/source byte count/schema mismatch")
    audio = np.memmap(path / "audio-taps.f32le", dtype="<f4", mode="r", shape=(expected_audio, 6))
    pressure = np.memmap(path / "pressure-input.f32le", dtype="<f4", mode="r", shape=(expected_physics, 18))
    state = read_csv(path / "state.csv")
    for key in ("t_s", "rpm", "target_rpm", "map_pa", "integrated_cycles", "cycle_angle_rad"):
        if key not in state:
            raise ValueError(f"Missing state field {key}")
    # The CSV labels the last source-step index (n-1)/pfs, but observes after that step.
    # Correct the known clock convention, never a fitted signal/phase alignment.
    state["t_s"] = state["t_s"] + 1 / pfs
    if abs(expected_audio / fs - float(meta["duration_s"])) > 1 / fs:
        raise ValueError("Declared capture duration and audio sample count differ")
    if abs(expected_physics / pfs - float(meta["duration_s"])) > 1 / pfs:
        raise ValueError("Declared capture duration and physics sample count differ")
    return meta, audio, pressure, state


def control_summary(state, torque, ambient):
    result = {key: signal_health(value) for key, value in state.items() if key != "t_s"}
    result["map_over_ambient"] = signal_health(state["map_pa"] / ambient)
    result["map_above_ambient_fraction"] = float(np.mean(state["map_pa"] > ambient))
    result["map_above_two_atm_fraction"] = float(np.mean(state["map_pa"] > 2 * ambient))
    result["rpm_tracking_rmse"] = float(np.sqrt(np.mean((state["rpm"] - state["target_rpm"]) ** 2)))
    result["dyno_torque_nm"] = signal_health(torque["torque_nm"])
    result["dyno_negative_fraction"] = float(np.mean(torque["torque_nm"] < 0))
    result["throttle_plate_column_semantics"] = "linkage scalar 1-speed_control**2, not measured physical plate angle"
    result["load_equivalence"] = "NONE: imposed dyno RPM and MAP proxy do not establish road speed/torque/load equality"
    return result


def validate_physical_sidecar(validity):
    """Fail closed on missing evidence; this is only a coarse mechanical check."""
    errors = []
    if not isinstance(validity, dict):
        return {"status": "NOT_EVALUATED_MISSING_SIGNED_ROTATION_AND_ACTIVE_LIT_EVIDENCE",
                "errors": ["Signed rotation and active-lit coarse physical validity sidecar is absent"]}
    try:
        low = float(validity["min_omega_rad_s"])
        high = float(validity["max_omega_rad_s"])
        if (validity.get("cw_all_capture") is not True or not math.isfinite(low)
                or not math.isfinite(high) or not (low <= high < 0)):
            errors.append("Signed crankshaft rotation is not verified strictly negative throughout capture")
    except (KeyError, TypeError, ValueError):
        errors.append("Signed crankshaft angular-velocity evidence is missing or invalid")
    try:
        dwell = validity["lit_cylinder_steps"]
        if isinstance(dwell, bool) or not float(dwell).is_integer() or int(dwell) <= 0:
            errors.append("No positive active-lit cylinder-step dwell is recorded")
    except (KeyError, TypeError, ValueError, OverflowError):
        errors.append("Active-lit cylinder-step evidence is missing or invalid")
    return {"status": "INVALID_PHYSICAL_MODEL" if errors else "COARSE_DIRECTION_AND_ACTIVE_LIT_ONLY_NOT_CALIBRATED",
            "errors": errors,
            "scope": "not per-cylinder ignition-event count, burn completion, acoustic fidelity or OEM evidence"}


def source_diagnostics(pressure, pfs, ambient):
    result = {"pressure_pa": {str(i): signal_health(pressure[:, i]) for i in range(16)},
              "pressure_columns": "0..7 combustion chamber Pa; 8..15 exhaust runner Pa",
              "source_audio_columns": "16..17 staging internal audio units, not Pa",
              "mixing": {}}
    a, b = np.asarray(pressure[:, 16], dtype=float), np.asarray(pressure[:, 17], dtype=float)
    for width in (10, 20):
        ea, _ = envelope_metrics(a, pfs, width)
        eb, _ = envelope_metrics(b, pfs, width)
        es, _ = envelope_metrics(a + b, pfs, width)
        _, ra, _ = rms_envelope(a, pfs, width)
        _, rb, _ = rms_envelope(b, pfs, width)
        _, rs, _ = rms_envelope(a + b, pfs, width)
        cross = rs * rs - ra * ra - rb * rb
        mean_sum = float(np.mean(rs * rs))
        cf, cp = signal.welch(cross, fs=100, nperseg=min(len(cross), 2000), detrend="constant")
        result["mixing"][f"{width}ms"] = {
            "exhaust_0": ea, "exhaust_1": eb, "sum": es,
            "cross_energy_identity": "RMS(a+b)^2 - RMS(a)^2 - RMS(b)^2 = 2 mean_window(a*b)",
            "mean_cross_energy": float(np.mean(cross)),
            "cross_energy_fraction_of_mean_sum_energy": float(np.mean(cross)) / mean_sum if mean_sum else None,
            "cross_energy_target_psd_power_over_sum_mean_energy_squared": bandpower(cf, cp, *TARGET) / (mean_sum ** 2) if mean_sum else None}
    for label, section in (("chamber_pressure_fluctuation_sum_pa", pressure[:, :8]),
                           ("runner_pressure_fluctuation_sum_pa", pressure[:, 8:16])):
        summed = np.sum(section, axis=1, dtype=float) - 8 * ambient
        result[label] = {"explicit_pressure_reference_pa": ambient,
                         "health": signal_health(summed),
                         "envelope_10ms": envelope_metrics(summed, pfs, 10)[0],
                         "envelope_20ms": envelope_metrics(summed, pfs, 20)[0]}
    return result


def run(args, out):
    captures, v0s = named_paths(args.capture), named_paths(args.v0)
    if not captures or set(v0s) - set(captures):
        raise ValueError("At least one capture is required; V0 names must match captures")
    manifest = {"scope": "OFFLINE_SYNTHETIC_MECHANISM_ONLY_NOT_OEM_PRODUCT_OR_HUMAN_ACCEPTANCE",
                "command": [sys.executable, *sys.argv], "script_sha256": sha_file(Path(__file__)),
                "numpy": np.__version__, "scipy": scipy.__version__,
                "physical_invalid_reason": args.physical_invalid_reason,
                "capture_alignment": "same nominal recording start, exact sample-count durations; sub-physics-step synth delay not realigned or fitted",
                "state_clock": "state.csv t_s is (sourceFrames-1)/physics_fs at a post-step observation: add exactly 1/physics_fs (100us) to state endpoints for analysis, matching V0. Original CSV bytes unchanged; first endpoint hold only where no earlier state exists.",
                "throttle_plate_column": "linkage scalar 1-speed_control**2, not a measured physical throttle angle",
                "randomness": "C RNG fixed seed from capture; jitter std::default_random_engine is default-constructed and fixed; no seed search",
                "preregistration": {"path": str(Path(args.prereg).resolve()), "sha256": sha_file(args.prereg)} if args.prereg else None,
                "route_definitions": {"V0": "actual dirty-product BankRenderer NORMAL_SEAM_ENVELOPE_V1, actual RPM plus declared MAP/ambient proxy",
                                      "E0": "audio tap column 0 unchanged original resampled rawsum, internal audio units",
                                      "E1": "audio tap column 3 unchanged finalnorm PCM, full frozen DSP, intermediate taps retained",
                                      "E2": "low/high only, finite complete-cycle E0 crop ~.55 s plus fixed 5 ms seam, repeated; counterexample control"},
                "cross_domain_rule": "Absolute power only within a declared unit domain. Cross-route ratios are dimensionless descriptive metrics, not proof of equal timbre/load.",
                "scenes": {}}
    summary = []
    listening = {name: [] for name in ("V0", "E0", "E1", "E2")}
    for index, (scene, source) in enumerate(captures.items(), 1):
        print(f"[{index}/{len(captures)}] analyze {scene}", flush=True)
        meta, audio, pressure, state = load_capture(source)
        fs, pfs = int(meta["audio_fs"]), int(meta["physics_fs"])
        scene_dir = out / scene
        scene_dir.mkdir()
        inputs = {name: {"path": str(source / name), "sha256": sha_file(source / name)}
                  for name in ("capture.json", "audio-taps.f32le", "pressure-input.f32le", "state.csv", "dyno.csv")}
        validity_path = source / "physical-validity.json"
        validity = json.loads(validity_path.read_text(encoding="utf-8")) if validity_path.exists() else None
        validity_check = validate_physical_sidecar(validity)
        if validity is not None:
            inputs["physical-validity.json"] = {"path": str(validity_path), "sha256": sha_file(validity_path)}
        torque = read_csv(source / "dyno.csv")
        controls = control_summary(state, torque, args.ambient_pa)
        invalid = []
        if args.physical_invalid_reason:
            invalid.append(args.physical_invalid_reason)
        invalid.extend(validity_check["errors"])
        if controls["map_above_two_atm_fraction"] > 0:
            invalid.append("Naturally aspirated plenum exceeds 2*ambient; coarse physical sanity failure, not calibration")
        for key, values in state.items():
            if "omega" in key.lower() and np.any(values >= 0):
                invalid.append(f"Unexpected nonnegative crankshaft angular velocity in {key}")
        item = {"capture": meta, "inputs": inputs, "controls": controls,
                "physical_validity_sidecar": validity,
                "physical_validity_check": validity_check,
                "physical_validity_scope": "coarse signed rotation and active-lit dwell only, not per-cylinder ignition-event count, burn-completion rate, calibration or OEM evidence",
                "state_endpoint_correction_s": 1 / pfs,
                "physical_status": "INVALID_PHYSICAL_MODEL" if invalid else "COARSE_PHYSICS_SANITY_ONLY_NOT_CALIBRATED",
                "physical_invalid_reasons": invalid,
                "audio_intermediates": {name: signal_health(audio[:, i]) for i, name in enumerate(AUDIO_COLUMNS)},
                "clip_samples": int(np.count_nonzero(audio[:, 5])),
                "clip_fraction": float(np.mean(audio[:, 5] != 0)),
                "E1_digital_gate": "FAIL_CLIPPING" if np.any(audio[:, 5]) else "FINITE_PEAK_GATE_ONLY",
                "source_diagnostics": source_diagnostics(pressure, pfs, args.ambient_pa),
                "routes": {}}
        # Preserve traceability through the actual original DSP taps, including envelope changes.
        item["dsp_envelopes"] = {
            name: {f"{w}ms": envelope_metrics(audio[:, col], fs, w)[0] for w in (10, 20)}
            for col, name in ((1, "post_dsp_prelevel"), (2, "leveled_preclip"), (4, "leveler_gain"))}
        routes = {"E0": (np.array(audio[:, 0]), fs, "engine_internal_audio_units"),
                  "E1": (np.array(audio[:, 3]), fs, "normalized_pcm")}
        if scene in ("low", "high"):
            e2, loop, receipt = make_e2(routes["E0"][0], fs, state, float(meta["duration_s"]), scene)
            routes["E2"] = (e2, fs, "engine_internal_audio_units")
            loop.astype("<f4").tofile(scene_dir / "E2-frozen-loop.f32le")
            item["E2_receipt"] = receipt
        else:
            item["E2_status"] = "NOT_DEFINED_FOR_DYNAMIC_SCENE_NO_FAKE_RPM_PLAYBACK"
        if scene in v0s:
            vp = v0s[scene]
            vr = json.loads((vp / "receipt.json").read_text(encoding="utf-8"))
            raw_path = vp / "capture.f32le"
            if sha_file(raw_path) != vr["sha256"]:
                raise ValueError(f"V0 hash mismatch for {scene}")
            v = np.fromfile(raw_path, dtype="<f4")
            if len(v) != int(round(float(meta["duration_s"]) * 48000)):
                raise ValueError(f"V0 duration mismatch for {scene}")
            routes["V0"] = (v, 48000, "normalized_pcm")
            item["V0_receipt"] = vr
            item["inputs"]["V0_capture"] = {"path": str(raw_path), "sha256": vr["sha256"]}
            item["inputs"]["V0_receipt"] = {"path": str(vp / "receipt.json"), "sha256": sha_file(vp / "receipt.json")}
        all_artifacts = {}
        for route, (x, rate, domain) in routes.items():
            print(f"  {scene}/{route}: {len(x)} frames at {rate} Hz", flush=True)
            result, artifacts = analyze_signal(x, rate, domain, state, scene in ("low", "high"))
            result["physical_trial_status"] = item["physical_status"]
            result["route_role"] = "counterexample control" if route == "E2" else "descriptive comparison"
            raw_file = scene_dir / f"{route}.f32le"
            x.astype("<f4").tofile(raw_file)
            result["measurement_copy"] = {"file": str(raw_file.relative_to(out)), "sha256": sha_file(raw_file),
                                          "gain_applied": 1, "domain": domain}
            item["routes"][route] = result
            all_artifacts[route] = artifacts
            save_artifacts(scene_dir, route, artifacts)
            if result["health"]["valid"]:
                listening[route].append((scene, resample(x, rate, 48000)))
                env = result["envelope_10ms"]
                summary.append({"scene": scene, "route": route, "domain": domain,
                                "physical_status": item["physical_status"], "rms": result["health"]["rms"],
                                "peak": result["health"]["peak"], "nonfinite": result["health"]["nonfinite_count"],
                                "env10_cv": env["cv"], "slow_0p5_10_power_over_mean2": env["slow_power_over_mean_squared"],
                                "target_power_over_mean2": env["target_power_over_mean_squared"],
                                "target_fraction_of_slow": env["target_fraction_of_slow"],
                                "envelope_acf_lag_s": env["acf"]["peak_lag_s"],
                                "envelope_acf_rho": env["acf"]["peak_correlation"],
                                "E1_clip_samples": item["clip_samples"] if route == "E1" else ""})
        make_plot(scene_dir / "comparison.png", scene, item["routes"], all_artifacts)
        write_json(scene_dir / "metrics.json", item)
        manifest["scenes"][scene] = item
        for record in inputs.values():
            if sha_file(record["path"]) != record["sha256"]:
                raise ValueError("An immutable input changed while analysis was running")
    with open(out / "summary.csv", "x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    listen_dir = out / "listening-48khz"
    listen_dir.mkdir()
    listen_receipt = {"scope": "SAFETY_LISTENING_ONLY_NEVER_USED_FOR_METRICS", "sample_rate": 48000,
                      "target_dbfs_rms": args.listen_rms_dbfs, "routes": {}}
    for route, segments in listening.items():
        if not segments:
            continue
        match = listening_gain([x for _, x in segments], 10 ** (args.listen_rms_dbfs / 20), args.listen_peak)
        match["files"] = []
        for scene, x in segments:
            y = x * match["gain"]
            if np.max(np.abs(y)) > args.listen_peak + 1e-10:
                raise ValueError("Listening peak constraint implementation failed")
            file = listen_dir / f"{scene}-{route}-SAFETY_COPY.wav"
            wavfile.write(file, 48000, np.rint(y * 32767).astype("<i2"))
            match["files"].append({"file": file.name, "sha256": sha_file(file),
                                    "frames": len(y), "rms": signal_health(y)["rms"],
                                    "peak": signal_health(y)["peak"]})
        listen_receipt["routes"][route] = match
    write_json(listen_dir / "listening-receipt.json", listen_receipt)
    manifest["listening"] = listen_receipt
    manifest["assessment"] = {
        "automatic_acoustic_pass": False,
        "physical_invalid_scenes": [name for name, s in manifest["scenes"].items() if s["physical_invalid_reasons"]],
        "default_dsp_clipping_scenes": [name for name, s in manifest["scenes"].items() if s["clip_samples"]],
        "decision_rule": "An ACF or target-band decrease alone cannot pass. Inspect full 0.5-10 Hz AM, source/group cross terms, orders/sidebands, dynamics, clipping/leveling and physical validity. Noise masking is not causal source improvement.",
        "authenticity": "UNKNOWN: generic physical model vs Hellcat bank is not an OEM timbre test; load proxy is not physical load equality"}
    write_json(out / "all-metrics.json", manifest)
    with open(out / "README.md", "x", encoding="utf-8") as f:
        f.write("# Offline comparison evidence\n\nOriginal captures are immutable. E0 keeps internal audio units; E1/V0 are normalized PCM. Absolute powers cannot be ranked across those domains. E2 exists only for low/high steady scenes.\n\n")
        f.write("The PNG RMS/mean and PSD/mean-squared curves are dimensionless displays; measured PCM is not normalized. Listening WAVs use one pooled gain per route, with an explicit peak constraint and no limiter; they are not measurement inputs.\n\n")
        f.write("The 0.5-0.6 second waveform ACF can reflect correct engine-order recurrence. Inspect envelope AM, the complete slow band and physical/digital failures before interpreting it. No automatic acoustic, OEM, product or human acceptance is granted.\n\n")
        f.write(json.dumps(manifest["assessment"], indent=2) + "\n")
    return manifest["assessment"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", default=[], metavar="SCENE=DIR")
    parser.add_argument("--v0", action="append", default=[], metavar="SCENE=DIR")
    parser.add_argument("--out", required=True, help="New directory; existing directories are refused")
    parser.add_argument("--prereg")
    parser.add_argument("--ambient-pa", type=float, default=101325.)
    parser.add_argument("--physical-invalid-reason", default="")
    parser.add_argument("--listen-rms-dbfs", type=float, default=-23.)
    parser.add_argument("--listen-peak", type=float, default=.85)
    args = parser.parse_args()
    if not (args.ambient_pa > 0 and 0 < args.listen_peak < 1 and -60 <= args.listen_rms_dbfs <= -12):
        parser.error("Invalid ambient or listening constraint")
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    try:
        assessment = run(args, out)
        receipt = {"status": "ANALYSIS_COMPLETE_DESCRIPTIVE_ONLY", "exit_code": 0,
                   "started_utc": started, "ended_utc": datetime.now(timezone.utc).isoformat(),
                   "wall_s": time.perf_counter() - start, "command": [sys.executable, *sys.argv],
                   "script_sha256": sha_file(Path(__file__)), "assessment": assessment}
        write_json(out / "execution-receipt.json", receipt)
        print(json.dumps(receipt), flush=True)
        return 0
    except Exception as exc:
        write_json(out / "execution-failure.json", {"status": "FAILED_PARTIAL_OUTPUT_RETAINED", "exit_code": 1,
                                                    "error": str(exc), "command": [sys.executable, *sys.argv],
                                                    "wall_s": time.perf_counter() - start})
        raise


if __name__ == "__main__":
    raise SystemExit(main())
