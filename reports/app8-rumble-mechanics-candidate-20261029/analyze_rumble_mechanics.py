"""Verify frozen Simulink evidence before measuring the approved rumble experiment.

No renderer imports, resimulation, parameter fitting, or perceptual qualification.
Native Float64LE taps are independently decoded; their MATLAB capture provenance is
SHA-bound and separately checked by the parent against the original MAT files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import wave
from pathlib import Path

import numpy as np
from scipy import signal

BANDS = {"20_80": (20, 80), "80_250": (80, 250), "250_500": (250, 500),
         "500_1000": (500, 1000), "1000_2000": (1000, 2000), "2000_5000": (2000, 5000),
         "20_250": (20, 250), "250_1000": (250, 1000)}
ORDERS = (.5, 1, 1.5, 2, 4, 5, 7, 8, 11, 22, 44)
MODES = ("B0", "S", "R", "SR", "S2", "SR2")
FULL = ("B0", "S", "R", "SR", "SR_repeat", "S2", "SR2", "SR2_repeat")
SHORT = ("B0", "S_gain", "S_timing", "S", "S2_gain", "S2_timing", "S2")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_hash(path, expected):
    if not isinstance(expected, str) or re.fullmatch("[0-9a-fA-F]{64}", expected) is None:
        raise ValueError(f"invalid SHA256: {path}")
    if sha256(path) != expected.lower():
        raise ValueError(f"SHA256 mismatch: {path}")


def audio_array(audio):
    if np.iscomplexobj(audio):
        raise ValueError("audio must be real")
    x = np.asarray(audio, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2 or not len(x) or not np.isfinite(x).all():
        raise ValueError("audio must be finite, nonempty, real stereo")
    return x


def validate_pcm(audio):
    x = audio_array(audio)
    if not np.any(x) or np.max(np.abs(x)) > 1:
        raise ValueError("PCM must be nonzero and inside [-1,1]")
    return x


def power_ratio_db(after, before):
    if not np.isfinite([after, before]).all() or min(after, before) <= 0:
        raise ValueError("power ratio requires positive finite powers")
    return float(10 * (np.log10(after) - np.log10(before)))


def _welch(audio, fs):
    x = audio_array(audio)
    n = int(fs)
    if fs != n or n < 10000 or len(x) < n:
        raise ValueError("need at least one second for fixed Welch analysis")
    f, p = signal.welch(x, fs=fs, nperseg=n, noverlap=n//2, window="hann",
                        detrend="constant", scaling="density", axis=0)
    return x, f, p


def _integrate(f, values):
    return {name: np.sum(values[(f >= lo) & (f < hi)], axis=0) * (f[1]-f[0])
            for name, (lo, hi) in BANDS.items()}


def band_powers(audio, fs):
    """Absolute Welch power per channel; stereo mean is a power mean."""
    x, f, p = _welch(audio, fs)
    powers = _integrate(f, p)
    _, csd = signal.csd(x[:, 0], x[:, 1], fs=fs, nperseg=int(fs), noverlap=int(fs)//2,
                        window="hann", detrend="constant", scaling="density")
    cross = _integrate(f, csd.real)
    if any(not np.isfinite(v).all() or np.any(v < 0) for v in powers.values()):
        raise ValueError("invalid absolute power")
    return {"channels": [{k: float(v[c]) for k, v in powers.items()} for c in range(2)],
            "power_mean": {k: float(v.mean()) for k, v in powers.items()},
            "stereo_cross_power": {k: float(v) for k, v in cross.items()},
            "stereo_note": "identical mono copies are not independent stereo evidence"}


def compare_bands(reference, candidate, fs):
    b, c = audio_array(reference), audio_array(candidate)
    if b.shape != c.shape:
        raise ValueError("comparison samples must align")
    before, after = band_powers(b, fs), band_powers(c, fs)
    def delta(x, y):
        return {k: power_ratio_db(y[k], x[k]) for k in BANDS}
    return {"reference_power": before, "candidate_power": after,
            "channels": [delta(x,y) for x,y in zip(before["channels"], after["channels"])],
            "power_mean": delta(before["power_mean"], after["power_mean"])}


def gate_comparison(comparison, mode):
    """Apply fixed absolute LF and midrange gates to each channel and power mean."""
    rows = [*comparison["channels"], comparison["power_mean"]]
    if mode == "R":
        checks = [row["20_250"] >= 3 for row in rows]
    elif mode in ("SR", "SR2"):
        checks = [row["20_250"] <= 8 and row["250_1000"] >= -1 for row in rows]
    else:
        raise ValueError("no approved gate for this mode")
    return {"pass": all(checks), "channel_and_mean_pass": checks}


def signal_difference(reference, candidate, fs):
    b, c = audio_array(reference), audio_array(candidate)
    if b.shape != c.shape:
        raise ValueError("difference requires aligned samples")
    delta = c-b
    pb, pc, pd = (band_powers(x, fs) for x in (b,c,delta))
    rows = []
    for channel in range(2):
        f, cross = signal.csd(b[:,channel], delta[:,channel], fs=fs, nperseg=int(fs),
                              noverlap=int(fs)//2, window="hann", scaling="density", detrend="constant")
        cross = _integrate(f, cross.real)
        row = {}
        for key in BANDS:
            p0,p1,pd0 = (p["channels"][channel][key] for p in (pb,pc,pd))
            term = float(2*cross[key])
            row[key] = {"difference_power": pd0, "cross_term": term,
                        "closure_error": abs(p1-p0-pd0-term)}
        rows.append(row)
    return {"maximum_absolute_delta": float(np.max(np.abs(delta))),
            "rms_delta": np.sqrt(np.mean(delta*delta,axis=0)).tolist(), "channels": rows}


def order_spectrum(audio, phase_revs, fs):
    """Eight-revolution Hann spectra, oversampled in angle then FIR-decimated."""
    x = audio_array(audio)
    rev = np.asarray(phase_revs, dtype=float).reshape(-1)
    if len(rev) != len(x) or not np.isfinite(rev).all() or np.any(np.diff(rev) <= 0):
        raise ValueError("orders need aligned strictly increasing actual phase")
    high, low, turns = 4096, 256, 8
    if np.min(np.diff(rev))*high < 1-1e-6:
        raise ValueError("angular interpolation would downsample without anti-alias filtering")
    grid = np.arange(high*turns)/high
    starts = np.arange(rev[0], rev[-1]-grid[-1], turns/2)
    if not len(starts):
        raise ValueError("no complete eight-revolution order window")
    total = np.zeros((len(ORDERS),2))
    for start in starts:
        points = start+grid
        first = max(0, np.searchsorted(rev,points[0])-1)
        last = min(len(rev),np.searchsorted(rev,points[-1],side="right")+1)
        angular = np.column_stack([np.interp(points,rev[first:last],x[first:last,c]) for c in range(2)])
        angular = signal.resample_poly(angular,1,high//low,axis=0)
        f,p = signal.periodogram(angular,fs=low,window="hann",detrend="constant",scaling="spectrum",axis=0)
        indexes = np.rint(np.asarray(ORDERS)*turns).astype(int)
        if not np.array_equal(f[indexes], np.asarray(ORDERS)):
            raise ValueError("orders not on pre-registered bins")
        total += p[indexes]
    total /= len(starts)
    return {"window_count":len(starts), "orders":[{"order":o,"channel_power":v.tolist(),
            "power_mean":float(v.mean())} for o,v in zip(ORDERS,total)]}


def read_pcm24(path, fs):
    """Decode signed little endian packed PCM24 without an audio library."""
    try:
        with wave.open(str(path), "rb") as wav:
            if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getcomptype()) != (2,3,fs,"NONE"):
                raise ValueError("PCM24 format mismatch")
            count = wav.getnframes()
            raw = wav.readframes(count)
            if len(raw) != count*6 or count == 0:
                raise ValueError("PCM24 truncated or empty")
    except (wave.Error,EOFError) as exc:
        raise ValueError("invalid PCM24 WAV") from exc
    bits = np.frombuffer(raw,np.uint8).reshape(-1,3).astype(np.int32)
    values = bits[:,0] | bits[:,1]<<8 | bits[:,2]<<16
    return ((values ^ 0x800000)-0x800000).reshape(-1,2)/2**23


def verify_pcm24(path, pcm, fs):
    decoded = read_pcm24(path,fs)
    if decoded.shape != pcm.shape:
        raise ValueError("PCM24 length differs from raw PCM")
    error = float(np.max(np.abs(decoded-pcm)))
    if error > 2**-23+np.finfo(float).eps:
        raise ValueError("PCM24 bytes differ from native PCM")
    return error


def unique_case_paths(root, records):
    root = Path(root).resolve()
    paths = []
    for item in records:
        path = Path(item["directory"])
        if not path.is_absolute() or path.resolve() == root or not path.resolve().is_relative_to(root):
            raise ValueError("case directories must be inside run root")
        paths.append(path.resolve())
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate render directory")
    return paths


def validate_controls(actual, expected, clock):
    actual,expected = np.asarray(actual),np.asarray(expected)
    clock = np.asarray(clock).reshape(-1)
    if (actual.ndim != 2 or actual.shape[1] != 9 or actual.shape != expected.shape
            or not np.isfinite(actual).all() or not np.array_equal(actual,expected)):
        raise ValueError("native actual controls must equal expected double packets exactly")
    if clock.shape != (len(actual),) or not np.array_equal(clock,actual[:,8]):
        raise ValueError("actual clock must equal control column nine exactly")
    if not np.allclose(clock,np.arange(len(actual))*.02,rtol=0,atol=1e-10):
        raise ValueError("control frame clock is missing, reordered, or duplicated")
    if np.any(actual[:,0] <= 0) or np.any((actual[:,1:3] < 0)|(actual[:,1:3] > 1)):
        raise ValueError("invalid actual engine controls")


def phase_diagnostics(cycle_phase, controls, fs, frame):
    theta = np.asarray(cycle_phase,dtype=float).reshape(-1)
    controls = np.asarray(controls)
    if len(theta) != len(controls)*frame or not np.isfinite(theta).all():
        raise ValueError("actual sample phase is missing or malformed")
    unwrapped = np.unwrap(theta)
    if abs(theta[0]) > 1e-12:
        raise ValueError("sample cycle phase did not start from the frozen zero context")
    previous = np.r_[controls[0,0],controls[:-1,0]]
    rpm = np.linspace(previous,controls[:,0],frame,axis=1).reshape(-1)
    expected = rpm[:-1]*np.pi/(60*fs)
    error = np.abs(np.diff(unwrapped)-expected)
    if np.max(error) > 1e-8:
        raise ValueError("sample cycle phase discontinuity or reset")
    return {"maximum_step_error_rad":float(error.max()),
            "completed_720deg_cycles":float((unwrapped[-1]-unwrapped[0])/(2*np.pi)),
            "crank_revolutions":unwrapped/np.pi}


def verify_pressure_color(before,after,k):
    """Independent transfer-function evaluation on actual mono pressure taps."""
    x,y = (np.asarray(v,dtype=float).reshape(-1) for v in (before,after))
    if not len(x) or x.shape != y.shape or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("pressure color taps must be finite and aligned")
    if k == 0:
        if not np.array_equal(x,y):
            raise ValueError("pressure color zero bypass is not exact")
        expected = x
    elif k == 1:
        a,b = .9973854300793629,.9716127758430366
        branch = signal.sosfilt(np.array([[(1+a)/2,-(1+a)/2,0,1,-a,0],
                                         [1-b,0,0,1,-b,0]]),x)
        expected = x+branch
    else:
        raise ValueError("pressure color coefficient is not the frozen trial")
    residual = float(np.max(np.abs(y-expected)))
    if residual > 1e-10*max(1,float(np.max(np.abs(expected)))):
        raise ValueError("actual pressure color differs from independent causal filter")
    return {"maximum_equation_residual":residual,"before_rms":float(np.sqrt(np.mean(x*x))),
            "after_rms":float(np.sqrt(np.mean(y*y))),"before_peak":float(np.abs(x).max()),
            "after_peak":float(np.abs(y).max()),"pressure_note":"finite unbounded pressure; no PCM amplitude gate"}


def mechanical_envelope(theta,phases_degrees,bank_map):
    theta = np.asarray(theta,float).reshape(-1)
    phases = np.asarray(phases_degrees,float)
    banks = np.asarray(bank_map)
    if (phases.shape != (8,) or banks.shape != (8,) or not np.array_equal(np.sort(phases),np.arange(8)*90)
            or np.count_nonzero(banks == -1) != 4 or np.count_nonzero(banks == 1) != 4):
        raise ValueError("mechanical event profile is not the approved eight-event/two-bank map")
    values = []
    degrees = theta*720/(2*np.pi)
    for bank in (-1,1):
        deltas = (degrees[:,None]-phases[banks == bank]+360)%720-360
        pulses = np.where(np.abs(deltas)<=20,.5*(1+np.cos(np.pi*deltas/20)),0)
        values.append((pulses.sum(axis=1)-1/9)/(8/9))
    return np.column_stack(values)


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


class Evidence:
    """Freeze bytes before analysis and recheck at output; reject duplicate identities."""
    def __init__(self):
        self.files = {}
        self.radiation_proofs = set()

    def bind(self, path, expected=None):
        path = Path(path).resolve()
        expected = expected if expected is not None else sha256(path)
        verify_hash(path,expected)
        if path in self.files and self.files[path] != expected:
            raise ValueError("same evidence path has conflicting SHA256 bindings")
        self.files[path] = expected
        return path

    def recheck(self):
        for path,digest in self.files.items():
            verify_hash(path,digest)

    def export(self):
        return [{"path":str(p),"sha256":v} for p,v in sorted(self.files.items())]


def _binary(entry, evidence):
    path = evidence.bind(entry["path"],entry["sha256"])
    shape = tuple(entry["shape"])
    if (entry.get("order") != "row-major" or entry.get("dtype") != "float64-le" or not shape or any(int(n) != n or n <= 0 for n in shape)
            or path.stat().st_size != int(np.prod(shape))*8):
        raise ValueError(f"invalid Float64LE shape/order/bytes: {path}")
    shape = tuple(int(n) for n in shape)
    values = np.memmap(path,dtype="<f8",mode="r",shape=shape)
    if not np.isfinite(values).all():
        raise ValueError(f"nonfinite Float64LE: {path}")
    return values


def _csv(path):
    values = np.atleast_1d(np.genfromtxt(path,delimiter=",",names=True,encoding="utf-8-sig"))
    if not values.dtype.names or not len(values):
        raise ValueError("numeric CSV missing headers or data")
    result = {k:np.asarray(values[k],float) for k in values.dtype.names}
    if any(not np.isfinite(x).all() for x in result.values()):
        raise ValueError("nonfinite CSV")
    return result


def verify_repeats(records):
    for original,repeat in (("SR","SR_repeat"),("SR2","SR2_repeat")):
        for key in ("pcm_sha256","wav_sha256"):
            if records[original]["receipt"][key] != records[repeat]["receipt"][key]:
                raise ValueError("same-session repeat does not match exactly")


def verify_radiation_evaluations(receipt,frames,evidence,contract_path):
    calls = receipt["function_calls"]
    if calls["source_frame"] != frames:
        raise ValueError("actual source call count mismatch")
    if calls["frozen_frame"] == frames and calls["radiation_wrapper"] == frames:
        return
    if calls["frozen_frame"] != frames+1 or calls["radiation_wrapper"] != frames+1:
        raise ValueError("unexpected actual Frozen/radiation call count")
    if frames <= 100 and "sequential_frozen_max_error" in receipt:
        clock = _binary(receipt["binary_exports"]["actual_clock"],evidence).reshape(-1)
        times = np.asarray(receipt["radiation_evaluation_times"],float).reshape(-1)
        residual = receipt["sequential_frozen_max_error"]
        if (len(clock) != frames or not np.array_equal(times,np.r_[0.,clock])
                or not np.isfinite(residual) or residual > 1e-14):
            raise ValueError("short actual Frozen initialization trace/sequential output mismatch")
        return
    proof_path = evidence.bind(receipt["radiation_initialization_proof"],receipt["radiation_initialization_proof_sha256"])
    if proof_path in evidence.radiation_proofs:
        return
    proof = _json(proof_path)
    if proof["contract_sha256"] != receipt["contract_sha256"] or proof["baseline_pcm_exact"] is not True:
        raise ValueError("Frozen initialization proof lacks contract or exact baseline")
    smoke_summary_path = evidence.bind(proof["run_summary"],proof["run_summary_sha256"])
    smoke = _json(smoke_summary_path)
    if (smoke["mode"] != "smoke" or smoke["status"] != "RENDERED_DIGITAL_PASS_ANALYSIS_PENDING"
            or smoke["dependency_snapshot"] != receipt["dependency_snapshot"] or set(smoke["cases"]) != set(FULL)
            or set(smoke["short_cases"]) != set(SHORT)):
        raise ValueError("Frozen initialization proof is incomplete or uses different dependencies")
    for record in [*smoke["cases"].values(),*smoke["short_cases"].values()]:
        smoke_receipt = _json(evidence.bind(record["receipt_path"],record["receipt_sha256"]))
        clock = _binary(smoke_receipt["binary_exports"]["actual_clock"],evidence).reshape(-1)
        times = np.asarray(smoke_receipt["radiation_evaluation_times"],float).reshape(-1)
        if (not np.array_equal(times,np.r_[0.,clock])
                or not np.isfinite(smoke_receipt["sequential_frozen_max_error"])
                or smoke_receipt["sequential_frozen_max_error"] > 1e-14):
            raise ValueError("actual Frozen initialization trace is not [0;clock] with exact sequential output")
    baseline = smoke["cases"]["B0"]
    path = evidence.bind(baseline["pcm_path"],baseline["pcm_sha256"])
    sample_count = path.stat().st_size//8
    old_pcm = Path(_json(contract_path)["reference"]["capture_mat"]).parent/"candidate.pcm.f64le"
    reference_sha = _json(contract_path)["reference"]["pcm_sha256"]
    evidence.bind(old_pcm,reference_sha)
    old = np.memmap(old_pcm,dtype="<f8",mode="r",shape=(sample_count,))
    new = np.memmap(path,dtype="<f8",mode="r",shape=(sample_count,))
    if not np.array_equal(old,new):
        raise ValueError("Frozen initialization smoke B0 differs from old native B prefix")
    evidence.radiation_proofs.add(proof_path)


def _record(record, root, contract_sha, dependencies, model_sha, evidence, duration, mode, contract_path):
    directory = Path(record["directory"]).resolve()
    receipt_path = evidence.bind(directory/"receipt.json",record["receipt_sha256"])
    receipt = _json(receipt_path)
    for key in ("directory","receipt_path","contract_sha256","model_sha256","dependency_snapshot"):
        if record.get(key) != receipt.get(key):
            raise ValueError(f"summary/receipt mismatch for {key}")
    if (receipt["contract_sha256"] != contract_sha or receipt["model_sha256"] != model_sha
            or receipt["dependency_snapshot"] != dependencies):
        raise ValueError("render receipt differs from frozen contract/model/dependencies")
    if Path(receipt["receipt_path"]).resolve() != receipt_path:
        raise ValueError("receipt self path mismatch")
    expression = "s12_v12_model_rumble_mechanics_step(u, '"+str(contract_path).replace("'","''")+"', '"+mode+"')"
    # MATLAB may retain Windows separators from the supplied contract path.
    def normalized_expression(value):
        return str(value).replace("\\","/")
    if (normalized_expression(receipt.get("wrapper_expression")) != normalized_expression(expression)
            or receipt.get("SimulationInput_wrapper_expression") != receipt.get("wrapper_expression")
            or receipt.get("actual_wrapper_mode") != mode):
        raise ValueError("receipt actual Simulink override expression/mode differs from frozen case")
    for field,filename in (("pcm","candidate.pcm.f64le"),("wav","candidate.wav"),
                            ("drive","drive.csv"),("actual_control","actual_control.csv"),
                            ("source_telemetry","source-telemetry.csv"),("capture_mat","capture.mat")):
        path_key = field + ("_csv" if field in ("drive","actual_control","source_telemetry") else "_path")
        if field == "capture_mat":
            path_key = "capture_mat"
        if Path(receipt[path_key]).resolve() != directory/filename:
            raise ValueError(f"evidence path escapes case: {field}")
        evidence.bind(receipt[path_key],receipt[field+"_sha256"])
        if record.get(field+"_sha256") != receipt[field+"_sha256"]:
            raise ValueError(f"summary/receipt SHA mismatch: {field}")
    n = int(round(duration*48000))
    frames = int(round(duration/.02))
    if (receipt["frame_count"] != frames or receipt["samples_per_channel"] != n
            or receipt["sample_rate_hz"] != 48000 or receipt["channels"] != 2
            or receipt["unique_source_frames"] != frames):
        raise ValueError("actual frame/sample/source/Frozen call count mismatch")
    verify_radiation_evaluations(receipt,frames,evidence,contract_path)
    if (directory/"candidate.pcm.f64le").stat().st_size != n*16:
        raise ValueError("raw PCM byte count mismatch")
    pcm = validate_pcm(np.memmap(directory/"candidate.pcm.f64le",dtype="<f8",mode="r",shape=(n,2)))
    verify_pcm24(directory/"candidate.wav",pcm,48000)
    export_paths = [Path(entry["path"]).resolve() for entry in receipt["binary_exports"].values()]
    if len(set(export_paths)) != len(export_paths) or any(p.parent != directory for p in export_paths):
        raise ValueError("native exports duplicate or escape their case directory")
    exports = {key:_binary(item,evidence) for key,item in receipt["binary_exports"].items()}
    needed = {"actual_control","actual_clock","source_pressure","source_pressure_before","radiated_pressure","cycle_phase"}
    if not needed.issubset(exports):
        raise ValueError("receipt lacks required native control/pressure/phase taps")
    controls = exports["actual_control"]
    if controls.shape != (int(round(duration/.02)),9):
        raise ValueError("actual control dimensions mismatch")
    validate_controls(controls,controls,exports["actual_clock"])
    drive = _csv(directory/"drive.csv")
    names = ("rpm","load","throttle","acceleration","shift_event","shift_progress","afterfire_code","afterfire_progress","source_time_s")
    listed = np.column_stack([drive[key] for key in names])
    csv_actual = np.loadtxt(directory/"actual_control.csv",delimiter=",",ndmin=2)
    if (listed.shape != controls.shape or csv_actual.shape != controls.shape
            or not np.allclose(listed,controls,rtol=0,atol=1e-9)
            or not np.allclose(csv_actual,controls,rtol=0,atol=1e-9)):
        raise ValueError("recorded control CSV disagrees with actual native controls")
    for name in ("source_pressure","source_pressure_before","radiated_pressure","cycle_phase"):
        if exports[name].size != n:
            raise ValueError("mono native pressure/phase dimensions mismatch")
    telemetry = _csv(directory/"source-telemetry.csv")
    if (len(telemetry["frame_index"]) != len(controls)
            or not np.array_equal(telemetry["frame_index"],np.arange(1,len(controls)+1))
            or not np.allclose(telemetry["time_s"],controls[:,8],rtol=0,atol=1e-10)):
        raise ValueError("telemetry frame sequence mismatch")
    phase = phase_diagnostics(exports["cycle_phase"],controls,48000,960)
    if not np.allclose(np.remainder(phase["crank_revolutions"][::960]*np.pi,2*np.pi),
                       np.remainder(telemetry["phase_before"],2*np.pi),rtol=0,atol=1e-8):
        # Compare wrapped phase errors to accommodate a value just below 2pi versus zero.
        wrapped_error = np.angle(np.exp(1j*(phase["crank_revolutions"][::960]*np.pi-telemetry["phase_before"])))
        if np.max(np.abs(wrapped_error)) > 1e-8:
            raise ValueError("sample phase and frame telemetry disagree")
    for before,after in zip(telemetry["phase_before"][1:],telemetry["phase_after"][:-1]):
        if abs(np.angle(np.exp(1j*(before-after)))) > 1e-9:
            raise ValueError("frame phase reset")
    return {"pcm":pcm,"controls":controls,"exports":exports,"phase":phase,
            "telemetry":telemetry,"receipt":receipt}


def _same_controls(records):
    first = records[0]["controls"]
    for item in records[1:]:
        validate_controls(item["controls"],first,item["exports"]["actual_clock"])


def _segment(x, window, fs=48000):
    first,end = [int(round(v*fs)) for v in window]
    if first < 0 or end > len(x) or end-first < fs:
        raise ValueError("fixed analysis interval is missing or too short")
    return x[first:end]


def _mech_stats(exports,profile):
    """Actual short-run layer waveforms, modulation and event lock; no listening claim."""
    required = ("mechanics_envelope","mechanics_multiplier","mechanics_source_before", "mechanics_source_after",
                "mechanics_identity_before","mechanics_identity_after")
    if any(k not in exports for k in required):
        raise ValueError("short diagnostic lacks actual mechanical layer taps")
    q,m = (np.asarray(exports[k]).reshape(-1,2) for k in required[:2])
    theta = np.asarray(exports["mechanics_cycle_phase_rad"]).reshape(-1)
    source = profile["source"]
    expected_q = mechanical_envelope(theta,source["firing_phases_deg"]["value"],source["bank_map"]["value"])
    if q.shape != expected_q.shape or np.max(np.abs(q-expected_q)) > 1e-10:
        raise ValueError("actual mechanical events do not lock to frozen profile phase")
    if np.min(q) < -.125-1e-10 or np.max(q) > 1+1e-10:
        raise ValueError("mechanical envelope outside registered bounds")
    result = {"envelope_mean":q.mean(axis=0).tolist(),"envelope_range":[q.min(axis=0).tolist(),q.max(axis=0).tolist()],
              "multiplier_range":[m.min(axis=0).tolist(),m.max(axis=0).tolist()]}
    fit = np.column_stack([np.ones(len(theta)),np.cos(8*theta),np.sin(8*theta)])
    coefficients = np.linalg.lstsq(fit,m.mean(axis=1),rcond=None)[0]
    result["equal_bank_multiplier_fourth_crank_order_relative_amplitude"] = float(np.hypot(*coefficients[1:])/coefficients[0])
    for layer in ("source","identity"):
        before,after = (np.asarray(exports[f"mechanics_{layer}_{when}"]).reshape(-1,2) for when in ("before","after"))
        if before.shape != m.shape or after.shape != m.shape or np.max(np.abs(after-before*m)) > 1e-10:
            raise ValueError("mechanics layer does not equal its actual before waveform times multiplier")
        change = after-before
        energy = np.square(change)
        result[layer] = {"before_rms":np.sqrt(np.mean(before**2,axis=0)).tolist(),
                         "after_rms":np.sqrt(np.mean(after**2,axis=0)).tolist(),
                         "delta_rms":np.sqrt(np.mean(energy,axis=0)).tolist(),
                         "delta_energy_event_covariance":np.mean((energy-energy.mean(axis=0))*(q-q.mean(axis=0)),axis=0).tolist()}
    return result


def analyze_run(run_root, contract_path, *, write=True):
    root,contract_path = Path(run_root).resolve(),Path(contract_path).resolve()
    if not root.is_dir() or (root/"INVALIDATED.json").exists():
        raise ValueError("missing or invalidated run")
    if write and (root/"analysis.json").exists():
        raise ValueError("analysis report already exists; never overwrite frozen evidence")
    evidence = Evidence()
    contract_sha = sha256(contract_path); evidence.bind(contract_path,contract_sha)
    contract = _json(contract_path)
    summary_path = evidence.bind(root/"run-summary.json")
    summary = _json(summary_path)
    if (Path(summary["run_root"]).resolve() != root or Path(summary["contract_path"]).resolve() != contract_path
            or summary["contract_sha256"] != contract_sha):
        raise ValueError("run/contract provenance mismatch")
    if tuple(contract["full_cases"]) != FULL or set(summary["cases"]) != set(FULL):
        raise ValueError("complete eight drive cases required before analysis")
    if summary.get("status") != "RENDERED_DIGITAL_PASS_ANALYSIS_PENDING" or summary.get("mode") != "full":
        raise ValueError("only a completed actual full run may enter analysis")
    if set(summary["short_cases"]) != set(SHORT):
        raise ValueError("all short mechanical causal cases required")
    anchors = {a["name"]:a for a in contract["anchors"]}
    stationary = summary["stationary"]
    if len(anchors) != 7 or len(stationary) != 7 or {a["name"] for a in stationary} != set(anchors):
        raise ValueError("exactly seven unique stationary anchors required")
    all_records = list(summary["cases"].values())+list(summary["short_cases"].values())
    for anchor in stationary:
        if set(anchor["cases"]) != set(MODES):
            raise ValueError("all six modes required for every anchor")
        all_records.extend(anchor["cases"].values())
    unique_case_paths(root,all_records)
    dependencies = summary["dependency_snapshot"]
    dep_paths = [Path(v["path"]).resolve() for v in dependencies]
    if not dependencies or len(set(dep_paths)) != len(dep_paths):
        raise ValueError("missing/duplicate dependency snapshot")
    for entry in dependencies:
        evidence.bind(entry["path"],entry["sha256"])
        if Path(entry["path"]).suffix == ".m":
            resolved = entry.get("which_all")
            if not isinstance(resolved,list) or not resolved or Path(resolved[0]).resolve() != Path(entry["path"]).resolve():
                raise ValueError("pre-render which-all does not resolve the frozen MATLAB dependency")
    build_path = evidence.bind(contract_path.parent/"build-receipt.json",summary["build_receipt_sha256"])
    build = _json(build_path)
    if (build["contract_sha256"] != contract_sha
            or build["status"] != "BUILT_COLD_RELOAD_UPDATE_COMPILE_MODEL_CHECK"
            or "status: healthy" not in build["model_check"]):
        raise ValueError("model build contract mismatch")
    for path_key,sha_key in (("source","source_sha256"),("candidate","candidate_sha256")):
        evidence.bind(build[path_key],build[sha_key])
    baseline_path = evidence.bind(contract_path.parent/"baseline.json")
    baseline = _json(baseline_path)
    source_root = Path(baseline["worktree"]).resolve()
    protected = baseline["protected"]
    original_models = {Path(key).resolve():digest for key,digest in baseline["prior_listening_files"].items()}
    if original_models.get(Path(build["source"]).resolve()) != build["source_sha256"]:
        raise ValueError("prior listening model differs from protected pre-edit baseline")
    frozen_key = "tools/sound_sim/s12/playground_v12/common/shared_model/S12_Frozen_Radiation_Adapter_v12.slx"
    evidence.bind(source_root/frozen_key,protected[frozen_key])
    model_sha = build["candidate_sha256"]
    reference = contract["reference"]
    evidence.bind(reference["capture_mat"],reference["capture_mat_sha256"])
    evidence.bind(Path(reference["capture_mat"]).parent/"candidate.pcm.f64le",reference["pcm_sha256"])
    expected = _binary(summary["reference_controls"],evidence)
    if expected.shape != (4500,9):
        raise ValueError("reference native controls must be actual 4500x9 double")
    print("[1/5] verifying all eight complete native driving receipts",flush=True)
    records = {name:_record(summary["cases"][name],root,contract_sha,dependencies,model_sha,evidence,90,
                           name.replace("_repeat",""),contract_path) for name in FULL}
    _same_controls(list(records.values()))
    validate_controls(records["B0"]["controls"],expected,records["B0"]["exports"]["actual_clock"])
    shifts = np.zeros(len(expected))
    for event in contract["events"]:
        first = int(round(event["start_s"]/.02));length = int(round(event["duration_s"]/.02))
        shifts[first:first+length] = np.sign(event["to_gear"]-event["from_gear"])
    if not np.array_equal(expected[:,4],shifts):
        raise ValueError("actual native baseline does not retain declared three upshifts/one downshift")
    if records["B0"]["receipt"]["pcm_sha256"] != reference["pcm_sha256"]:
        raise ValueError("B0 is not byte-exact with previous B native PCM")
    verify_repeats(records)
    print("[2/5] verifying mechanical diagnostic receipts and fixed driving windows",flush=True)
    short = {name:_record(summary["short_cases"][name],root,contract_sha,dependencies,model_sha,evidence,contract["short_seconds"],
                         name,contract_path) for name in SHORT}
    _same_controls(list(short.values()))
    for key,column in (("rpm",0),("load",1),("throttle",2)):
        if not np.all(short["B0"]["controls"][:,column] == contract["short_state"][key]):
            raise ValueError("actual short diagnostic control differs from frozen state")
    if not np.all(short["B0"]["controls"][:,3:8] == 0):
        raise ValueError("short diagnostic unexpectedly contains acceleration/shift/afterfire")
    profile_paths = [p for p in dep_paths if p.name == "source_profile.json"]
    if len(profile_paths) != 1:
        raise ValueError("exactly one frozen source profile dependency required")
    profile = _json(profile_paths[0])
    mechanisms = {name:_mech_stats(item["exports"],profile) for name,item in short.items() if name != "B0"}
    mechanisms["B0"] = {"note":"neutral path retains old diagnostics schema; no new mechanical treatment"}
    for name,item in short.items():
        params = contract["cases"][name]
        if name == "B0":
            continue
        q = item["exports"]["mechanics_envelope"]
        m = item["exports"]["mechanics_multiplier"]
        if not np.allclose(m,params["mechanical_gain"]*(1+params["mechanical_mod_depth"]*q),rtol=0,atol=1e-12):
            raise ValueError("actual mechanical multiplier differs from frozen causal treatment")
        for layer,old in (("source","mechanical"),("identity","identity_mechanical")):
            if not np.allclose(item["telemetry"]["mechanics_"+layer+"_before"],
                               short["B0"]["telemetry"][old+"_before"],rtol=0,atol=1e-10):
                raise ValueError("short mechanical before energy differs from neutral B0")
            if not np.array_equal(item["exports"]["mechanics_"+layer+"_before"],
                                  short["S"]["exports"]["mechanics_"+layer+"_before"]):
                raise ValueError("short mechanical treatment changed its baseline waveform")
    groups = []
    for window in contract["drive_analysis_windows_s"]:
        comparisons = {mode:compare_bands(_segment(records["B0"]["pcm"],window),_segment(records[mode]["pcm"],window),48000) for mode in MODES if mode != "B0"}
        groups.append({"kind":"drive","window_s":window,"comparisons":comparisons,
                       "gates":{mode:gate_comparison(comparisons[mode],mode) for mode in ("R","SR","SR2")},
                       "orders":{mode:order_spectrum(_segment(records[mode]["pcm"],window),
                           _segment(records[mode]["phase"]["crank_revolutions"],window),48000) for mode in MODES}})
    anchor_records = {}
    for anchor in stationary:
        print("  verifying stationary anchor "+anchor["name"],flush=True)
        definition = anchors[anchor["name"]]
        for key in ("role","rpm","load","throttle"):
            if anchor[key] != definition[key]:
                raise ValueError("stationary metadata differs from contract")
        items = {name:_record(anchor["cases"][name],root,contract_sha,dependencies,model_sha,evidence,6,name,contract_path) for name in MODES}
        _same_controls(list(items.values()))
        for key,col in (("rpm",0),("load",1),("throttle",2)):
            if not np.all(items["B0"]["controls"][:,col] == definition[key]):
                raise ValueError("actual stationary controls differ from registered anchor")
        if not np.all(items["B0"]["controls"][:,3:8] == 0):
            raise ValueError("stationary anchor unexpectedly contains acceleration/shift/afterfire")
        window = contract["stationary_analysis_s"]
        comparisons = {name:compare_bands(_segment(items["B0"]["pcm"],window),_segment(items[name]["pcm"],window),48000) for name in MODES if name != "B0"}
        groups.append({"kind":"stationary","name":anchor["name"],"window_s":window,"comparisons":comparisons,
                       "gates":{mode:gate_comparison(comparisons[mode],mode) for mode in ("R","SR","SR2")},
                       "orders":{mode:order_spectrum(_segment(items[mode]["pcm"],window),
                           _segment(items[mode]["phase"]["crank_revolutions"],window),48000) for mode in MODES}})
        anchor_records[anchor["name"]] = items
    pressure_color = {}
    print("[3/5] verifying actual pressure coloring and fixed renderer gain",flush=True)
    for label,item in [(name,item) for name,item in records.items()]+[("short/"+name,item) for name,item in short.items()]+[
            ("stationary/"+anchor+"/"+name,item) for anchor,items in anchor_records.items() for name,item in items.items()]:
        mode = item["receipt"]["actual_wrapper_mode"]
        pressure_color[label] = verify_pressure_color(item["exports"]["source_pressure_before"],
                                                       item["exports"]["source_pressure"],contract["cases"][mode]["rumble_k"])
        expected_pcm = np.repeat(np.asarray(item["exports"]["radiated_pressure"]).reshape(-1,1)*.1,2,axis=1)
        if not np.array_equal(item["pcm"],expected_pcm):
            raise ValueError("final PCM does not equal captured Frozen output times fixed 0.1 gain")
        telemetry = item["telemetry"]
        for component in ("mechanical","identity_mechanical","identity_whine"):
            if not np.array_equal(telemetry[component+"_before"],telemetry[component+"_after"]):
                raise ValueError("mechanics/whine were incorrectly affected by combustion cut")
        if not np.all(telemetry["cut_min"][item["controls"][:,4] == 0] == 1):
            raise ValueError("combustion cut persists outside shift")
    for collection in (records,short,*anchor_records.values()):
        baseline_phase = collection["B0"]["exports"]["cycle_phase"]
        for item in collection.values():
            if not np.array_equal(baseline_phase,item["exports"]["cycle_phase"]):
                raise ValueError("mechanics/rumble treatment unexpectedly changed actual source phase")
    # Every receipt and binary is bound before invoking any independent loudness meter.
    from make_audition import meter
    print("[4/5] independent EBU R128 and true-peak measurements",flush=True)
    safety = {}
    for name,item in records.items():
        pcm = item["pcm"]
        jumps = np.abs(np.diff(pcm,axis=0))
        max_sample = float(jumps.max()); max_frame = float(jumps[959::960].max())
        checks = (max_sample <= contract["screening"]["maximum_sample_jump"] and
                  max_frame <= contract["screening"]["continuity_reference_A_frame_jump"]+.02)
        metered = meter(pcm,48000,root/"analysis-meter"/name)
        safety[name] = {"sample_peak":float(np.abs(pcm).max()),"maximum_sample_jump":max_sample,
                        "maximum_frame_jump":max_frame,"continuity_pass":checks,
                        "channels_identical":bool(np.array_equal(pcm[:,0],pcm[:,1])),**metered}
    source_diagnostics = {}
    for name,item in records.items():
        telemetry = item["telemetry"]
        layers = {}
        for layer in ("source","identity"):
            before,after = [telemetry["mechanics_"+layer+"_"+when] for when in ("before","after")]
            layers[layer] = {"before_energy_mean":float(before.mean()),"after_energy_mean":float(after.mean()),
                             "energy_ratio_db":power_ratio_db(float(after.sum()),float(before.sum()))}
        source_diagnostics[name] = {"actual_mode":item["receipt"]["actual_wrapper_mode"],
            "phase_capture_basis":item["receipt"]["source_phase_origin"],"mechanical_layers":layers,
            "multiplier_range":[float(telemetry["multiplier_min"].min()),float(telemetry["multiplier_max"].max())],
            "combustion_cut_range":[float(telemetry["cut_min"].min()),float(telemetry["cut_max"].max())]}
    print("[5/5] full driving order spectra and final evidence recheck",flush=True)
    result = {"schema":"s12.rumble_mechanics.analysis.v1","run_root":str(root),"contract_path":str(contract_path),
              "contract_sha256":contract_sha,"basis":"Actual Simulink numeric evidence; no human or acoustic authenticity acceptance",
              "gate_policy":"Each channel and their power mean, all 7 anchors and 3 fixed driving windows",
              "groups":groups,"safety":safety,"mechanical_causal_diagnostics":mechanisms,
              "pressure_color":pressure_color,
              "source_diagnostics":source_diagnostics,
              "differences":{name:signal_difference(records["B0"]["pcm"],records[name]["pcm"],48000) for name in MODES if name != "B0"},
              "orders":{name:order_spectrum(records[name]["pcm"],records[name]["phase"]["crank_revolutions"],48000) for name in MODES},
              "phase":{name:{k:v for k,v in item["phase"].items() if k != "crank_revolutions"} for name,item in records.items()},
              "pass":all(g["pass"] for group in groups for g in group["gates"].values()) and all(v["continuity_pass"] for v in safety.values()),
              "human_acceptance":"PENDING_JOVI","evidence":evidence.export()}
    evidence.recheck()
    if (root/"INVALIDATED.json").exists():
        raise ValueError("run invalidated during analysis")
    if write:
        destination = root/"analysis.json"
        if destination.exists():
            raise ValueError("analysis report already exists; never overwrite frozen evidence")
        destination.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        lines = ["# Rumble/mechanics numeric experiment", "", "Numeric gate: "+("PASS" if result["pass"] else "FAIL — stop without retuning"),
                 "", "Human assessment: PENDING_JOVI. These metrics do not establish vehicle authenticity.", "",
                 "| Window / anchor | R LF min dB | SR LF max dB | SR mid min dB | SR2 LF max dB | SR2 mid min dB | Pass |",
                 "|---|---:|---:|---:|---:|---:|---|"]
        for group in groups:
            def vals(mode,key):
                c=group["comparisons"][mode];return [r[key] for r in [*c["channels"],c["power_mean"]]]
            label = group.get("name",str(group["window_s"]))
            values = [min(vals("R","20_250")),max(vals("SR","20_250")),min(vals("SR","250_1000")),
                      max(vals("SR2","20_250")),min(vals("SR2","250_1000"))]
            lines.append("| "+label+" | "+" | ".join(f"{v:.3f}" for v in values)+" | "+str(all(x["pass"] for x in group["gates"].values()))+" |")
        (root/"analysis.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root",required=True); parser.add_argument("--contract",required=True)
    args = parser.parse_args()
    result = analyze_run(args.run_root,args.contract)
    print("Numeric experiment gate:","PASS" if result["pass"] else "FAIL; stop trial without retuning")
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
