"""Analyse frozen, isolated listening candidates; never modify audio or model inputs."""
from __future__ import annotations

import numpy as np
from scipy import signal


def power_ratio_db(numerator, denominator):
    """A finite positive power ratio without division overflow or an invented floor."""
    if not np.isfinite(numerator) or not np.isfinite(denominator) or numerator <= 0 or denominator <= 0:
        raise ValueError("power ratio requires finite, positive operands")
    return float(10 * (np.log10(numerator) - np.log10(denominator)))


def _audio_array(audio):
    x = np.asarray(audio, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2 or not x.shape[0] or not np.isfinite(x).all():
        raise ValueError("audio must be a nonempty, finite, two-channel array")
    return x


def band_powers(audio, fs, screening):
    """Welch power per channel and power-averaged stereo; no waveform mixing."""
    x = _audio_array(audio)
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError("invalid sample rate")
    nperseg = int(round(float(screening["welch_window_seconds"]) * fs))
    overlap = float(screening["welch_overlap_fraction"])
    if nperseg < 2 or x.shape[0] < nperseg or not 0 <= overlap < 1:
        raise ValueError("audio shorter than Welch window or invalid overlap")
    frequencies, spectrum = signal.welch(
        x, fs=fs, window="hann", nperseg=nperseg,
        noverlap=int(round(nperseg * overlap)), axis=0, detrend="constant",
        scaling="density",
    )
    df = frequencies[1] - frequencies[0]
    values = {}
    for name, key in (("lf_power", "lf_band_hz"), ("hf_power", "hf_band_hz"),
                      ("reference_power", "reference_band_hz")):
        low, high = map(float, screening[key])
        if not 0 <= low < high <= fs / 2:
            raise ValueError("invalid frequency band")
        selected = (frequencies >= low) & (frequencies <= high)
        if not selected.any():
            raise ValueError("empty frequency band")
        values[name] = np.sum(spectrum[selected], axis=0) * df
    matrix = np.column_stack([values[key] for key in ("lf_power", "hf_power", "reference_power")])
    if not np.isfinite(matrix).all() or np.any(matrix <= 0):
        raise ValueError("band powers must be finite and positive for ratio calculations")

    def make_result(row):
        lf, hf, ref = map(float, row)
        return {"lf_power": lf, "hf_power": hf, "reference_power": ref,
                "hf_lf_db": power_ratio_db(hf, lf)}

    return {"channels": [make_result(row) for row in matrix],
            "combined": make_result(matrix.mean(axis=0))}


def compare_bands(reference, candidate, fs, screening):
    """Return B and C powers and their level differences, retaining both channels."""
    b = _audio_array(reference)
    c = _audio_array(candidate)
    if b.shape != c.shape:
        raise ValueError("reference and candidate audio must align")
    before, after = band_powers(b, fs, screening), band_powers(c, fs, screening)

    def delta(a, z):
        return {"lf_change_db": power_ratio_db(z["lf_power"], a["lf_power"]),
                "hf_lf_change_db": float(z["hf_lf_db"] - a["hf_lf_db"])}

    return {"B": before, "C": after,
            "channels": [delta(a, z) for a, z in zip(before["channels"], after["channels"])],
            "combined": delta(before["combined"], after["combined"])}


def _aligned_vectors(*vectors):
    arrays = [np.asarray(value, dtype=float) for value in vectors]
    if not arrays or any(a.ndim != 1 or not len(a) or not np.isfinite(a).all() for a in arrays):
        raise ValueError("vectors must be finite, nonempty, and one-dimensional")
    if any(len(a) != len(arrays[0]) for a in arrays):
        raise ValueError("vectors must align")
    return arrays


def drive_windows(time, rpm, load, shift, screening):
    """All qualifying half-open frame intervals, after excluding entire shifts."""
    time, rpm, load, shift = _aligned_vectors(time, rpm, load, shift)
    if len(time) < 2:
        raise ValueError("drive requires multiple frames")
    dt = time[1] - time[0]
    if dt <= 0 or not np.allclose(np.diff(time), dt, rtol=0, atol=1e-9):
        raise ValueError("drive time must be on a regular frame grid")
    exclusion = float(screening["drive_shift_exclusion_s"])
    minimum = float(screening["drive_minimum_window_s"])
    if exclusion < 0 or minimum <= 0:
        raise ValueError("invalid drive window policy")
    margin_frames = int(np.ceil(exclusion / dt - 1e-9))
    active = shift != 0
    edges = np.diff(np.r_[False, active, False].astype(int))
    excluded = np.zeros(len(time), dtype=bool)
    for first, end in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        excluded[max(0, first - margin_frames):min(len(time), end + margin_frames)] = True
    selected = (rpm >= screening["drive_high_rpm_min"]) & (load >= screening["drive_high_load_min"]) & ~excluded
    edges = np.diff(np.r_[False, selected, False].astype(int))
    result = []
    for first, end in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if (end - first) * dt + 1e-10 >= minimum:
            result.append({"start_s": float(time[first]), "end_s": float(time[0] + end * dt),
                           "first_frame": int(first), "end_frame_exclusive": int(end)})
    return result


def validate_drive(drive, contract, sample_count, *, check_events=True):
    """Fail closed on frame count, timestamps, and declared shift intervals."""
    required = ("time_s", "rpm", "load", "shift_event")
    if not all(key in drive for key in required):
        raise ValueError("drive lacks required columns")
    columns = _aligned_vectors(*(drive[key] for key in drive))
    count = len(columns[0])
    dt = float(contract["frame_time_s"])
    nframe = int(contract["frame_samples"])
    fs = float(contract["sample_rate_hz"])
    if nframe <= 0 or fs <= 0 or abs(nframe / fs - dt) > 1e-12:
        raise ValueError("invalid frame timing in contract")
    n_expected = int(round(float(contract["duration_seconds"]) / dt))
    time = np.asarray(drive["time_s"], dtype=float)
    if count != n_expected or sample_count != count * nframe or not np.allclose(time, np.arange(count) * dt, rtol=0, atol=1e-9):
        raise ValueError("drive time and audio samples must align to contract")
    if "source_time_s" in drive and not np.allclose(drive["source_time_s"], time, rtol=0, atol=1e-9):
        raise ValueError("source time must align with drive time")
    if np.any(np.asarray(drive["rpm"]) <= 0) or np.any((np.asarray(drive["load"]) < 0) | (np.asarray(drive["load"]) > 1)):
        raise ValueError("invalid drive state")
    if not check_events:
        return
    expected = np.zeros(count)
    for event in contract["events"]:
        start = float(event["start_s"]) / dt
        duration = float(event["duration_s"]) / dt
        first, length = int(round(start)), int(round(duration))
        direction = np.sign(float(event["to_gear"]) - float(event["from_gear"]))
        if abs(start - first) > 1e-8 or abs(duration - length) > 1e-8 or length <= 0 or first < 0 or first + length > count or not direction or np.any(expected[first:first + length]):
            raise ValueError("invalid or overlapping contract shift")
        expected[first:first + length] = direction
    if not np.array_equal(np.asarray(drive["shift_event"]), expected):
        raise ValueError("drive shift frames do not align with contract events")


def reconstruct_crank_revolutions(rpm_targets, frame_samples, fs):
    """Replicate source smoothing and cumulative sample-start crank phase."""
    (rpm,) = _aligned_vectors(rpm_targets)
    if np.any(rpm <= 0) or int(frame_samples) != frame_samples or frame_samples < 2 or not np.isfinite(fs) or fs <= 0:
        raise ValueError("invalid RPM, frame size, or sample rate")
    previous = np.r_[rpm[0], rpm[:-1]]
    smoothed = np.linspace(previous, rpm, int(frame_samples), axis=1).reshape(-1)
    rev = np.empty_like(smoothed)
    rev[0] = 0
    rev[1:] = np.cumsum(smoothed[:-1] / (60.0 * fs))
    return rev


def order_spectrum(audio, phase_revs, fs, screening):
    """Eight-revolution spectra, with high-resolution angle interpolation and FIR decimation."""
    x = _audio_array(audio)
    (rev,) = _aligned_vectors(phase_revs)
    if len(rev) != len(x) or np.any(np.diff(rev) <= 0) or not np.isfinite(fs) or fs <= 0:
        raise ValueError("audio and increasing crank phase must align")
    high = int(screening["order_samples_per_revolution"])
    low = int(screening["order_analysis_samples_per_revolution"])
    revolutions = int(screening["order_window_revolutions"])
    if high <= 0 or low <= 0 or high % low or revolutions <= 0:
        raise ValueError("invalid angular sampling policy")
    if np.min(np.diff(rev)) * fs * high + 1e-7 < fs:
        raise ValueError("high-resolution angular grid would downsample time data")
    orders = np.asarray(screening["orders_to_report"], dtype=float)
    if orders.ndim != 1 or not len(orders) or not np.isfinite(orders).all() or np.any(orders <= 0) or np.any(orders >= low / 2):
        raise ValueError("invalid requested orders")
    grid = np.arange(high * revolutions, dtype=float) / high
    step = revolutions / 2
    end = rev[-1] - grid[-1]
    if end < rev[0]:
        raise ValueError("audio does not contain an eight-revolution window")
    starts = rev[0] + np.arange(int(np.floor((end - rev[0]) / step)) + 1) * step
    rows, centres = [], []
    for start in starts:
        points = start + grid
        first = max(0, np.searchsorted(rev, points[0]) - 1)
        last = min(len(rev), np.searchsorted(rev, points[-1], side="right") + 1)
        angular = np.column_stack([np.interp(points, rev[first:last], x[first:last, channel]) for channel in range(2)])
        decimated = signal.resample_poly(angular, up=1, down=high // low, axis=0)
        bins, power = signal.periodogram(decimated, fs=low, window="hann", detrend="constant",
                                         scaling="spectrum", axis=0)
        indexes = np.rint(orders * revolutions).astype(int)
        if not np.allclose(bins[indexes], orders, rtol=0, atol=1e-9):
            raise ValueError("requested order is not on an eight-revolution spectrum bin")
        rows.append(power[indexes])
        middle = np.searchsorted(rev, start + revolutions / 2)
        fraction = (start + revolutions / 2 - rev[middle - 1]) / (rev[middle] - rev[middle - 1])
        centres.append(float((middle - 1 + fraction) / fs))
    powers = np.mean(np.asarray(rows), axis=0)
    return {"window_count": len(rows), "window_center_s": centres,
            "orders": [{"order": float(order), "channel_power": [float(v) for v in power],
                        "combined_power": float(np.mean(power))} for order, power in zip(orders, powers)]}



def _csv_columns(path):
    from pathlib import Path
    path = Path(path)
    try:
        values = np.genfromtxt(path, delimiter=",", names=True, dtype=float,
                               encoding="utf-8-sig", autostrip=True)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read numeric CSV: {path}") from exc
    if values.dtype.names is None:
        raise ValueError(f"CSV lacks a header: {path}")
    values = np.atleast_1d(values)
    columns = {key: np.asarray(values[key], dtype=float) for key in values.dtype.names}
    _aligned_vectors(*columns.values())
    return columns


def _run_path(root, value):
    from pathlib import Path
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("run paths must be absolute")
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError("case paths must remain inside the run root")
    return path


def _read_pcm(directory, expected_samples):
    path = directory / "candidate.pcm.f64le"
    if not path.is_file() or path.stat().st_size != expected_samples * 2 * 8:
        raise ValueError(f"PCM byte count does not align: {path}")
    audio = np.memmap(path, dtype="<f8", mode="r", shape=(expected_samples, 2))
    return _audio_array(audio)


def _sha256_file(path):
    import hashlib
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ValueError(f"cannot hash evidence file: {path}") from exc
    return digest.hexdigest()


def _verified_hash(path, expected, label):
    import re
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-fA-F]{64}", expected) is None:
        raise ValueError(f"invalid SHA256 for {label}")
    if _sha256_file(path) != expected.lower():
        raise ValueError(f"SHA256 mismatch for {label}: {path}")


def _snapshot_map(snapshot):
    from pathlib import Path
    if not isinstance(snapshot, list) or not snapshot:
        raise ValueError("dependency snapshot is missing or empty")
    result = {}
    for entry in snapshot:
        path = Path(entry["path"])
        if not path.is_absolute():
            raise ValueError("dependency path must be absolute")
        path = path.resolve()
        if path in result:
            raise ValueError("dependency snapshot has a duplicate path")
        result[path] = entry["sha256"]
    return result


def _verify_dependencies(snapshot):
    result = _snapshot_map(snapshot)
    for path, expected in result.items():
        _verified_hash(path, expected, "dependency")
    return result


def _verify_model_evidence(contract_file, contract_sha):
    """Check models against the existing build receipt and protected baseline."""
    import json
    from pathlib import Path
    lab = contract_file.parent
    build_path, baseline_path = lab / "build-receipt.json", lab / "baseline.json"
    try:
        build_bytes, baseline_bytes = build_path.read_bytes(), baseline_path.read_bytes()
        build = json.loads(build_bytes.decode("utf-8-sig"))
        baseline = json.loads(baseline_bytes.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read pre-existing model build or baseline evidence") from exc
    source_root = Path(baseline["source_root"])
    source, candidate = Path(build["source"]), Path(build["candidate"])
    if not all(path.is_absolute() for path in (source_root, source, candidate)):
        raise ValueError("model evidence paths must be absolute")
    source_root, source, candidate = source_root.resolve(), source.resolve(), candidate.resolve()
    if source == candidate or not source.is_relative_to(source_root) or not candidate.is_relative_to(source_root):
        raise ValueError("model paths do not match the protected source root")
    if build["contract_sha256"] != contract_sha:
        raise ValueError("model build receipt contract SHA256 differs")
    stock_key = source.relative_to(source_root).as_posix()
    adapter_key = "tools/sound_sim/s12/playground_v12/common/shared_model/S12_Frozen_Radiation_Adapter_v12.slx"
    protected = baseline["protected"]
    if stock_key not in protected or adapter_key not in protected or protected[stock_key] != build["source_sha256"]:
        raise ValueError("model build receipt does not match protected baseline")
    adapter = source_root / adapter_key
    references = [(source, build["source_sha256"], "stock model"),
                  (candidate, build["candidate_sha256"], "candidate model"),
                  (adapter, protected[adapter_key], "frozen radiation model")]
    for path, expected, label in references:
        _verified_hash(path, expected, label)
    import hashlib
    references.extend([(build_path, hashlib.sha256(build_bytes).hexdigest(), "model build receipt"),
                       (baseline_path, hashlib.sha256(baseline_bytes).hexdigest(), "model baseline")])
    provenance = {"basis": "existing pre-render build receipt and protected baseline; current files checked",
                  "build_receipt": str(build_path), "baseline": str(baseline_path),
                  "stock_model": {"path": str(source), "sha256": build["source_sha256"]},
                  "candidate_model": {"path": str(candidate), "sha256": build["candidate_sha256"]},
                  "frozen_radiation": {"path": str(adapter), "sha256": protected[adapter_key]}}
    return build["source_sha256"], build["candidate_sha256"], references, provenance


def _verify_wav(directory, pcm, fs, maximum_error):
    import wave
    path = directory / "candidate.wav"
    try:
        with wave.open(str(path), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes(), wav.getcomptype()) != (2, 3, fs, len(pcm), "NONE"):
                raise ValueError(f"WAV format or length does not match PCM: {path}")
            for first in range(0, len(pcm), 65536):
                count = min(65536, len(pcm) - first)
                data = wav.readframes(count)
                if len(data) != count * 2 * 3:
                    raise ValueError(f"WAV data is truncated: {path}")
                bits = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
                integer = bits[:, 0] | (bits[:, 1] << 8) | (bits[:, 2] << 16)
                decoded = ((integer ^ 0x800000) - 0x800000).reshape(-1, 2) / (2**23)
                if np.max(np.abs(decoded - pcm[first:first + count])) > maximum_error + np.finfo(float).eps:
                    raise ValueError(f"WAV does not match native PCM: {path}")
    except (OSError, wave.Error, EOFError) as exc:
        raise ValueError(f"cannot read PCM24 WAV: {path}") from exc


def _verify_receipt(root, directory, receipt_sha, summary_record, contract_sha,
                    snapshot_map, expected_model_sha, samples, fs, maximum_error, telemetry_required):
    import json
    receipt_path = directory / "receipt.json"
    _verified_hash(receipt_path, receipt_sha, "receipt")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid receipt: {receipt_path}") from exc
    fields = ("directory", "drive_csv", "drive_sha256", "actual_control_csv", "actual_control_sha256",
              "source_telemetry_csv", "source_telemetry_sha256", "contract_sha256", "pcm_sha256",
              "wav_sha256", "model_sha256", "dependency_snapshot", "receipt_path")
    if not all(key in receipt for key in fields):
        raise ValueError(f"receipt is missing required evidence fields: {receipt_path}")
    if summary_record is not None and any(summary_record.get(key) != receipt[key] for key in fields):
        raise ValueError(f"run-summary and receipt differ: {receipt_path}")
    if _run_path(root, receipt["directory"]) != directory or _run_path(root, receipt["receipt_path"]) != receipt_path:
        raise ValueError(f"receipt directory or path does not match render directory: {receipt_path}")
    if receipt["contract_sha256"] != contract_sha:
        raise ValueError(f"receipt contract SHA256 differs: {receipt_path}")
    if receipt["model_sha256"] != expected_model_sha:
        raise ValueError(f"receipt model SHA256 differs from pre-render model evidence: {receipt_path}")
    if _snapshot_map(receipt["dependency_snapshot"]) != snapshot_map:
        raise ValueError(f"pre-render dependency snapshot differs: {receipt_path}")
    for field, filename in (("drive", "drive.csv"), ("actual_control", "actual_control.csv")):
        path = _run_path(root, receipt[field + "_csv"])
        if path != directory / filename:
            raise ValueError(f"{field} path does not belong to render directory")
        _verified_hash(path, receipt[field + "_sha256"], field)
    telemetry_path = receipt["source_telemetry_csv"]
    if telemetry_required:
        if not telemetry_path or _run_path(root, telemetry_path) != directory / "source-telemetry.csv":
            raise ValueError("source telemetry path is missing or misaligned")
        _verified_hash(directory / "source-telemetry.csv", receipt["source_telemetry_sha256"], "source telemetry")
    elif telemetry_path or receipt["source_telemetry_sha256"]:
        raise ValueError("original cycle unexpectedly claims source telemetry")
    for field, filename in (("pcm", "candidate.pcm.f64le"), ("wav", "candidate.wav")):
        path_key = field + "_path"
        if path_key in receipt:
            if _run_path(root, receipt[path_key]) != directory / filename:
                raise ValueError(f"{field} audio path does not belong to render directory")
            if summary_record is not None and summary_record.get(path_key) != receipt[path_key]:
                raise ValueError(f"{field} audio path differs between summary and receipt")
        _verified_hash(directory / filename, receipt[field + "_sha256"], field)
    pcm = _read_pcm(directory, samples)
    _verify_wav(directory, pcm, fs, maximum_error)
    return receipt, pcm


def _verify_actual_control(receipt, drive):
    from pathlib import Path
    names = ("rpm", "load", "throttle", "acceleration", "shift_event", "shift_progress",
             "afterfire_code", "afterfire_progress", "source_time_s")
    if not all(key in drive for key in names):
        raise ValueError("drive lacks the nine recorded control columns")
    try:
        actual = np.loadtxt(Path(receipt["actual_control_csv"]), delimiter=",", ndmin=2)
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read actual control evidence") from exc
    expected = np.column_stack([drive[key] for key in names])
    if actual.shape != expected.shape or not np.isfinite(actual).all() or not np.allclose(actual, expected, rtol=0, atol=1e-9):
        raise ValueError("actual control frames do not match recorded drive")


def _receipt_evidence(receipt, receipt_sha):
    from pathlib import Path
    directory = Path(receipt["directory"])
    result = [(Path(receipt["receipt_path"]), receipt_sha, "receipt"),
              (directory / "candidate.pcm.f64le", receipt["pcm_sha256"], "pcm"),
              (directory / "candidate.wav", receipt["wav_sha256"], "wav")]
    for field in ("drive", "actual_control", "source_telemetry"):
        if receipt[field + "_csv"]:
            result.append((Path(receipt[field + "_csv"]), receipt[field + "_sha256"], field))
    return result


def _same_drive(left, right):
    if set(left) != set(right) or any(not np.array_equal(left[key], right[key]) for key in left):
        raise ValueError("B, C and repeat control frames must match exactly")


def _gate_comparison(comparison, *, max_lf_change=None, min_reduction=None):
    values = [*comparison["channels"], comparison["combined"]]
    lf_pass = None if max_lf_change is None else all(abs(x["lf_change_db"]) <= max_lf_change for x in values)
    hf_pass = None if min_reduction is None else all(x["hf_lf_change_db"] <= -min_reduction for x in values)
    return lf_pass, hf_pass


def _weighted_comparison(windows):
    weights = np.array([w["end_s"] - w["start_s"] for w in windows])
    result = {}
    for item in ("combined", "channel_0", "channel_1"):
        def values(side):
            rows = [w["comparison"][side]["combined"] if item == "combined"
                    else w["comparison"][side]["channels"][int(item[-1])] for w in windows]
            lf = float(np.average([r["lf_power"] for r in rows], weights=weights))
            hf = float(np.average([r["hf_power"] for r in rows], weights=weights))
            return {"lf_power": lf, "hf_power": hf, "hf_lf_db": power_ratio_db(hf, lf)}
        b, c = values("B"), values("C")
        result[item] = {"B": b, "C": c, "lf_change_db": power_ratio_db(c["lf_power"], b["lf_power"]),
                        "hf_lf_change_db": float(c["hf_lf_db"] - b["hf_lf_db"])}
    return {"method": "duration_weighted_mean_of_window_powers", **result}


def _phase_diagnostics(telemetry, drive, phase, contract):
    required = ("time_s", "frame_index", "phase_before", "phase_after", "cut_min", "cut_max", "cut_mean")
    if not all(key in telemetry for key in required):
        raise ValueError("source telemetry lacks phase or cut fields")
    if len(telemetry["time_s"]) != len(drive["time_s"]) or not np.allclose(telemetry["time_s"], drive["time_s"], rtol=0, atol=1e-9):
        raise ValueError("source telemetry time must align with drive")
    if not np.all(np.diff(telemetry["frame_index"]) == 1):
        raise ValueError("source telemetry frame index must be sequential")
    frame = int(contract["frame_samples"])
    fs = float(contract["sample_rate_hz"])
    end_rev = phase[-1] + drive["rpm"][-1] / (60 * fs)
    cycle_phase = np.remainder(np.pi * np.r_[phase[::frame], end_rev], 2 * np.pi)
    before_error = np.angle(np.exp(1j * (telemetry["phase_before"] - cycle_phase[:-1])))
    after_error = np.angle(np.exp(1j * (telemetry["phase_after"] - cycle_phase[1:])))
    max_error = float(max(np.max(np.abs(before_error)), np.max(np.abs(after_error))))
    # Numerical/data-alignment tolerance, not an acoustic qualification threshold.
    tolerance = 1e-5
    if max_error > tolerance:
        raise ValueError(f"recorded source phase does not align with reconstructed drive phase: {max_error} rad")
    return {"status": "recorded", "reference": "source cycle phase; pi radians per reconstructed crank revolution",
            "max_abs_error_rad": max_error, "alignment_tolerance_rad": tolerance}


def _write_reports(root, result, drive, telemetry, phase_tracks, contract):
    import csv
    import json
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fieldnames = ["start_s", "end_s", "duration_s", "pass", "B_lf_power", "C_lf_power", "B_hf_power", "C_hf_power",
                  "B_hf_lf_db", "C_hf_lf_db", "lf_change_db", "hf_lf_change_db", "left_hf_lf_change_db", "right_hf_lf_change_db"]
    fieldnames += [f"{side}_{channel}_{measure}" for side in ("B", "C") for channel in ("left", "right")
                   for measure in ("lf_power", "hf_power", "reference_power", "hf_lf_db")]
    fieldnames += ["left_lf_change_db", "right_lf_change_db"]
    with (root / "comparable_windows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for window in result["drive"]["windows"]:
            comp = window["comparison"]
            b, c = comp["B"]["combined"], comp["C"]["combined"]
            writer.writerow({"start_s": window["start_s"], "end_s": window["end_s"],
                             "duration_s": window["end_s"] - window["start_s"], "pass": window["pass"],
                             "B_lf_power": b["lf_power"], "C_lf_power": c["lf_power"],
                             "B_hf_power": b["hf_power"], "C_hf_power": c["hf_power"],
                             "B_hf_lf_db": b["hf_lf_db"], "C_hf_lf_db": c["hf_lf_db"],
                             **comp["combined"], "left_hf_lf_change_db": comp["channels"][0]["hf_lf_change_db"],
                             "right_hf_lf_change_db": comp["channels"][1]["hf_lf_change_db"],
                             **{f"{side}_{channel}_{measure}": comp[side]["channels"][index][measure]
                                for side in ("B", "C") for index, channel in enumerate(("left", "right"))
                                for measure in ("lf_power", "hf_power", "reference_power", "hf_lf_db")},
                             **{f"{channel}_lf_change_db": comp["channels"][index]["lf_change_db"]
                                for index, channel in enumerate(("left", "right"))}})

    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True, constrained_layout=True)
    axes[0].plot(drive["time_s"], drive["rpm"], label="B/C target RPM", linewidth=.8)
    axes[0].set_ylabel("RPM")
    for name in ("B", "C"):
        item = telemetry[name]
        residual = np.angle(np.exp(1j * (item["phase_before"] - phase_tracks[name])))
        axes[1].plot(item["time_s"], residual, label=name, linewidth=.6, alpha=.8)
    axes[1].axhline(0, color="black", linewidth=.6)
    axes[1].set_ylabel("Recorded − reconstructed phase (rad)")
    axes[1].set_xlabel("Time (s)")
    axes[0].legend()
    axes[1].legend()
    fig.suptitle("Source phase and virtual RPM")
    fig.savefig(root / "phase.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5), constrained_layout=True)
    for name in ("A", "B", "C", "C_repeat"):
        item = result["orders"][name]["orders"]
        ax.plot([v["order"] for v in item], [10 * np.log10(max(v["combined_power"], np.finfo(float).tiny)) for v in item], marker="o", label=name)
    ax.set_xlabel("Crank order")
    ax.set_ylabel("Mean stereo power (dB)")
    ax.set_title("8-revolution order spectra; A uses its own virtual cycle")
    ax.grid(alpha=.2)
    ax.legend()
    fig.savefig(root / "order.png", dpi=130)
    plt.close(fig)

    events = contract["events"]
    fig, axes = plt.subplots(max(1, len(events)), 1, figsize=(11, 2.5 * max(1, len(events))), squeeze=False, constrained_layout=True)
    for ax, event in zip(axes[:, 0], events):
        start, end = event["start_s"], event["start_s"] + event["duration_s"]
        for name in ("B", "C"):
            item = telemetry[name]
            select = (item["time_s"] >= start - .5) & (item["time_s"] <= end + .5)
            ax.plot(item["time_s"][select] - start, item["cut_mean"][select], label=name)
        ax.axvspan(0, end - start, color="gray", alpha=.2)
        ax.set_ylabel("Source cut")
        ax.set_title(f"Shift at {start:g} s")
        ax.grid(alpha=.2)
        ax.legend()
    axes[-1, 0].set_xlabel("Time from shift start (s)")
    fig.savefig(root / "shift-envelope.png", dpi=130)
    plt.close(fig)
    (root / "analysis.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _source_diagnostics(telemetry, contract):
    components = ("combustion", "orders", "identity_exhaust", "identity_whine", "identity_mechanical", "mechanical")
    controls = ("cut_min", "cut_max", "cut_mean", "whine_scale", "induction_scale", "voicing_activation")
    required = list(controls) + [component + suffix for component in components for suffix in ("_before", "_after")]
    if not all(key in telemetry for key in required):
        raise ValueError("source telemetry lacks energy or voicing diagnostics")
    energies = {component: {"before_mean": float(np.mean(telemetry[component + "_before"])),
                            "after_mean": float(np.mean(telemetry[component + "_after"])),
                            "before_max": float(np.max(telemetry[component + "_before"])),
                            "after_max": float(np.max(telemetry[component + "_after"]))}
                for component in components}
    summaries = {key: {"min": float(np.min(telemetry[key])), "mean": float(np.mean(telemetry[key])),
                       "max": float(np.max(telemetry[key]))} for key in controls}
    shifts = []
    time = telemetry["time_s"]
    for event in contract["events"]:
        start, end = float(event["start_s"]), float(event["start_s"] + event["duration_s"])
        selected = (time >= start - 1e-9) & (time < end - 1e-9)
        before = (time >= start - .5 - 1e-9) & (time < start - 1e-9)
        after = (time >= end - 1e-9) & (time < end + .5 - 1e-9)
        if not selected.any():
            raise ValueError("source telemetry has no frames for a shift")
        shifts.append({"start_s": start, "end_s": end,
                       "cut_min": float(np.min(telemetry["cut_min"][selected])),
                       "cut_mean": float(np.mean(telemetry["cut_mean"][selected])),
                       "cut_before_mean": float(np.mean(telemetry["cut_mean"][before])) if before.any() else None,
                       "cut_after_mean": float(np.mean(telemetry["cut_mean"][after])) if after.any() else None})
    return {"status": "recorded", "controls": summaries, "component_energy": energies, "shifts": shifts}


def analyze_run(run_root, contract_path):
    """Analyse the existing run and write auditable reports under its root."""
    import hashlib
    import json
    from pathlib import Path

    root, contract_file = Path(run_root), Path(contract_path)
    if not root.is_absolute() or not contract_file.is_absolute():
        raise ValueError("run root and contract path must be absolute")
    root, contract_file = root.resolve(), contract_file.resolve()
    if (root / "INVALIDATED.json").exists():
        raise ValueError("run is invalidated")
    summary_path = root / "run-summary.json"
    summary_bytes = summary_path.read_bytes()
    summary = json.loads(summary_bytes.decode("utf-8-sig"))
    contract_bytes = contract_file.read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8-sig"))
    if Path(summary["run_root"]).resolve() != root or Path(summary["contract_path"]).resolve() != contract_file:
        raise ValueError("run summary provenance does not match supplied paths")
    if summary.get("contract_sha256") != hashlib.sha256(contract_bytes).hexdigest():
        raise ValueError("contract SHA256 does not match run summary")
    directories = [_run_path(root, summary["cases"][name]["directory"])
                   for name in ("A", "B", "C", "C_repeat")]
    directories.extend(_run_path(root, item[side + "_directory"])
                       for item in summary["stationary"] for side in ("B", "C"))
    if root in directories or len(set(directories)) != len(directories):
        raise ValueError("render directories must be unique and distinct from the run root")
    fs, frame = int(contract["sample_rate_hz"]), int(contract["frame_samples"])
    samples = int(round(float(contract["duration_seconds"]) * fs))
    screening = contract["screening"]
    contract_sha = hashlib.sha256(contract_bytes).hexdigest()
    stock_sha, candidate_sha, model_evidence, model_provenance = _verify_model_evidence(contract_file, contract_sha)
    snapshot_map = _verify_dependencies(summary["dependency_snapshot"])
    shared_drive_path = _run_path(root, summary["drive_csv"])
    _verified_hash(shared_drive_path, summary["drive_sha256"], "shared drive")
    shared_drive = _csv_columns(shared_drive_path)
    evidence = [(summary_path, hashlib.sha256(summary_bytes).hexdigest(), "run-summary"),
                (shared_drive_path, summary["drive_sha256"], "shared drive")]
    evidence.extend(model_evidence)
    drive_data, audio_data, telemetry, orders, phase_result, source_result, phase_tracks = {}, {}, {}, {}, {}, {}, {}
    for name in ("A", "B", "C", "C_repeat"):
        record = summary["cases"][name]
        directory = _run_path(root, record["directory"])
        receipt, audio_data[name] = _verify_receipt(
            root, directory, record["receipt_sha256"], record, contract_sha, snapshot_map,
            stock_sha if name == "A" else candidate_sha, samples, fs,
            screening["pcm24_max_error"], telemetry_required=(name != "A"))
        evidence.extend(_receipt_evidence(receipt, record["receipt_sha256"]))
        drive_data[name] = _csv_columns(_run_path(root, receipt["drive_csv"]))
        validate_drive(drive_data[name], contract, samples, check_events=(name != "A"))
        if name != "A":
            if receipt["drive_sha256"] != summary["drive_sha256"]:
                raise ValueError("B, C and repeat control frames differ from shared drive SHA256")
            _same_drive(shared_drive, drive_data[name])
        _verify_actual_control(receipt, drive_data[name])
    _same_drive(drive_data["B"], drive_data["C"])
    _same_drive(drive_data["B"], drive_data["C_repeat"])
    for name in ("A", "B", "C", "C_repeat"):
        record = summary["cases"][name]
        phase = reconstruct_crank_revolutions(drive_data[name]["rpm"], frame, fs)
        orders[name] = order_spectrum(audio_data[name], phase, fs, screening)
        if name == "A":
            phase_result[name] = {"status": "source_telemetry_unavailable"}
            source_result[name] = {"status": "source_telemetry_unavailable"}
        else:
            telemetry[name] = _csv_columns(_run_path(root, record["source_telemetry_csv"]))
            phase_tracks[name] = np.remainder(np.pi * phase[::frame], 2 * np.pi)
            phase_result[name] = _phase_diagnostics(telemetry[name], drive_data[name], phase, contract)
            source_result[name] = _source_diagnostics(telemetry[name], contract)
    anchors = {anchor["name"]: anchor for anchor in contract["anchors"]}
    items = summary["stationary"]
    names = [item["name"] for item in items]
    if len(names) != len(set(names)) or set(names) != set(anchors):
        raise ValueError("stationary cases must match every contract anchor and held-out state")
    stationary = []
    count = int(round(float(contract["stationary_seconds"]) * fs))
    start, end = (int(round(float(x) * fs)) for x in contract["stationary_analysis_s"])
    if not 0 <= start < end <= count:
        raise ValueError("invalid stationary analysis interval")
    for item in items:
        anchor = anchors[item["name"]]
        for key in ("role", "rpm", "load", "throttle"):
            if item[key] != anchor[key]:
                raise ValueError("stationary metadata differs from frozen contract")
        directory_b = _run_path(root, item["B_directory"])
        directory_c = _run_path(root, item["C_directory"])
        shared = _run_path(root, item["drive_csv"])
        _verified_hash(shared, item["drive_sha256"], "stationary shared drive")
        evidence.append((shared, item["drive_sha256"], "stationary shared drive"))
        state_b = _csv_columns(shared)
        outputs = []
        for side, directory in (("B", directory_b), ("C", directory_c)):
            receipt, output = _verify_receipt(
                root, directory, item[side + "_receipt_sha256"], None, contract_sha,
                snapshot_map, candidate_sha, count, fs, screening["pcm24_max_error"], telemetry_required=True)
            evidence.extend(_receipt_evidence(receipt, item[side + "_receipt_sha256"]))
            if receipt["drive_sha256"] != item["drive_sha256"]:
                raise ValueError("stationary control frames differ from shared drive SHA256")
            state = _csv_columns(_run_path(root, receipt["drive_csv"]))
            _same_drive(state_b, state)
            _verify_actual_control(receipt, state)
            outputs.append(output)
        b, c = outputs
        stationary_contract = {**contract, "duration_seconds": contract["stationary_seconds"], "events": []}
        validate_drive(state_b, stationary_contract, count)
        for key in ("rpm", "load", "throttle"):
            if key not in state_b or not np.allclose(state_b[key], anchor[key], rtol=0, atol=1e-9):
                raise ValueError("stationary control state differs from its anchor")
        comparison = compare_bands(b[start:end], c[start:end], fs, screening)
        applicable = anchor["rpm"] >= 3500 and anchor["load"] >= .65
        lf_pass, hf_pass = _gate_comparison(comparison, max_lf_change=screening["stationary_lf_absolute_change_max_db"],
                                            min_reduction=screening["stationary_hf_lf_reduction_min_db"] if applicable else None)
        stationary.append({**{key: item[key] for key in ("name", "role", "rpm", "load", "throttle")},
                           "comparison": comparison, "lf_pass": lf_pass,
                           "hf_lf_applicable": applicable, "hf_lf_pass": hf_pass})
    applicable = [x for x in stationary if x["hf_lf_applicable"]]
    stationary_pass = bool(applicable) and all(x["lf_pass"] and x["hf_lf_pass"] is not False for x in stationary)

    drive = drive_data["B"]
    windows = drive_windows(drive["time_s"], drive["rpm"], drive["load"], drive["shift_event"], screening)
    for window in windows:
        first, end = window["first_frame"] * frame, window["end_frame_exclusive"] * frame
        comparison = compare_bands(audio_data["B"][first:end], audio_data["C"][first:end], fs, screening)
        _, hf_pass = _gate_comparison(comparison, min_reduction=screening["drive_hf_lf_reduction_min_db"])
        window.update(comparison=comparison, **{"pass": hf_pass})
    worst = max(windows, key=lambda w: max(d["hf_lf_change_db"] for d in
                [*w["comparison"]["channels"], w["comparison"]["combined"]])) if windows else None
    result = {"schema": "s12.listening.analysis.v1", "run_root": str(root), "contract_path": str(contract_file), "contract_sha256": hashlib.sha256(contract_bytes).hexdigest(), "screening_contract": screening,
              "basis": "research-assumption virtual control state; acoustic metrics do not imply human acceptance",
              "gate_channel_policy": "both channels and their power-averaged stereo must satisfy each applicable threshold",
              "stationary": stationary,
              "stationary_screening": {"pass": stationary_pass, "eligible_hf_lf_count": len(applicable)},
              "drive": {"control_basis": "drive.csv frame targets", "windows": windows,
                        "aggregate": _weighted_comparison(windows) if windows else None,
                        "worst_window": worst, "pass": bool(windows) and all(w["pass"] for w in windows)},
              "phase": phase_result, "source_diagnostics": source_result, "orders": orders,
              "evidence": {"run_summary_sha256": hashlib.sha256(summary_bytes).hexdigest(),
                           "dependency_snapshot": summary["dependency_snapshot"], "model_provenance": model_provenance,
                           "render_receipt_sha256": {name: summary["cases"][name]["receipt_sha256"]
                                                     for name in ("A", "B", "C", "C_repeat")},
                           "stationary_receipt_sha256": {item["name"]: {side: item[side + "_receipt_sha256"]
                                                                        for side in ("B", "C")}
                                                         for item in items}}}
    _verify_dependencies(summary["dependency_snapshot"])
    for path, expected, label in evidence:
        _verified_hash(path, expected, label)
    if (root / "INVALIDATED.json").exists():
        raise ValueError("run became invalidated during analysis")
    _write_reports(root, result, drive, telemetry, phase_tracks, contract)
    return result


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--contract", required=True)
    args = parser.parse_args()
    result = analyze_run(args.run_root, args.contract)
    print("stationary_screening:", "PASS" if result["stationary_screening"]["pass"] else "FAIL")
    print("drive_screening:", "PASS" if result["drive"]["pass"] else "FAIL")
    print("analysis:", str(Path(args.run_root) / "analysis.json"))


if __name__ == "__main__":
    main()
