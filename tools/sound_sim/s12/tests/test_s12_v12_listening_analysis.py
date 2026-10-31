"""Behavioural tests for the isolated listening-candidate analysis."""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import wave

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "reports/app8-listening-candidate-20261029/analyze_listening_candidate.py"


@pytest.fixture(scope="module")
def analysis():
    if not SCRIPT.is_file():
        return None
    spec = importlib.util.spec_from_file_location("listening_analysis", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def screening():
    return {
        "lf_band_hz": [20, 250],
        "hf_band_hz": [1000, 10000],
        "reference_band_hz": [20, 10000],
        "welch_window_seconds": 1,
        "welch_overlap_fraction": 0.5,
        "drive_high_rpm_min": 3500,
        "drive_high_load_min": 0.55,
        "drive_shift_exclusion_s": 0.5,
        "drive_minimum_window_s": 1,
        "order_samples_per_revolution": 4096,
        "order_analysis_samples_per_revolution": 256,
        "order_window_revolutions": 8,
        "orders_to_report": [0.5, 1, 1.5, 2, 4, 8, 22, 44, 56],
        "pcm24_max_error": 2**-23,
    }


def stereo(t, high_amplitude=0.06):
    left = 0.12 * np.sin(2 * np.pi * 100 * t) + high_amplitude * np.sin(2 * np.pi * 2000 * t)
    return np.column_stack((left, -left))


def test_stereo_band_power_is_not_destroyed_by_opposite_phase(analysis, screening):
    assert analysis is not None, "listening analysis module has not been implemented"
    fs = 48000
    audio = stereo(np.arange(fs * 2) / fs)
    result = analysis.band_powers(audio, fs, screening)
    for channel in result["channels"]:
        assert channel["lf_power"] == pytest.approx(0.12**2 / 2, rel=1e-6)
        assert channel["hf_power"] == pytest.approx(0.06**2 / 2, rel=1e-6)
    assert result["combined"]["lf_power"] == pytest.approx(0.12**2 / 2, rel=1e-6)
    assert result["combined"]["hf_lf_db"] == pytest.approx(10 * np.log10(0.25), abs=1e-5)


def test_comparison_preserves_absolute_lf_power_and_ratio(analysis, screening):
    fs = 48000
    t = np.arange(fs * 2) / fs
    comparison = analysis.compare_bands(stereo(t), stereo(t, 0.03), fs, screening)
    for result in [*comparison["channels"], comparison["combined"]]:
        assert result["lf_change_db"] == pytest.approx(0, abs=1e-6)
        assert result["hf_lf_change_db"] == pytest.approx(-6.020599913, abs=1e-5)


@pytest.mark.parametrize("bad", ["empty", "one_channel", "nan", "silence"])
def test_invalid_audio_or_zero_denominator_is_rejected(analysis, screening, bad):
    fs = 48000
    x = stereo(np.arange(fs) / fs)
    if bad == "empty":
        x = np.empty((0, 2))
    elif bad == "one_channel":
        x = x[:, :1]
    elif bad == "nan":
        x[100, 0] = np.nan
    else:
        x[:] = 0
    with pytest.raises(ValueError):
        analysis.band_powers(x, fs, screening)


def test_comparison_rejects_misaligned_channels_and_length(analysis, screening):
    fs = 48000
    x = stereo(np.arange(fs * 2) / fs)
    with pytest.raises(ValueError, match="align"):
        analysis.compare_bands(x, x[:-1], fs, screening)


def test_drive_windows_preserve_all_segments_and_exclude_whole_shift(analysis, screening):
    time = np.arange(250) * 0.02
    rpm = np.full(time.shape, 4000.)
    load = np.full(time.shape, 0.7)
    shift = np.zeros(time.shape)
    shift[100:110] = 1
    windows = analysis.drive_windows(time, rpm, load, shift, screening)
    assert [(x["start_s"], x["end_s"]) for x in windows] == pytest.approx([(0., 1.5), (2.7, 5.)])


def test_drive_windows_reject_misalignment_nonfinite_and_irregular_time(analysis, screening):
    time = np.arange(150) * 0.02
    rpm = np.full(150, 4000.)
    load = np.full(150, 0.7)
    shift = np.zeros(150)
    with pytest.raises(ValueError):
        analysis.drive_windows(time, rpm[:-1], load, shift, screening)
    rpm[5] = np.nan
    with pytest.raises(ValueError):
        analysis.drive_windows(time, rpm, load, shift, screening)
    rpm[5] = 4000.
    time[9] += 0.001
    with pytest.raises(ValueError):
        analysis.drive_windows(time, rpm, load, shift, screening)


def test_phase_uses_source_sample_ramp_and_retains_frame_continuity(analysis):
    rpm = np.array([750., 1500., 3000.])
    rev = analysis.reconstruct_crank_revolutions(rpm, 960, 48000)
    assert rev.shape == (2880,)
    assert rev[0] == 0.
    assert rev[960] == pytest.approx(0.25, abs=1e-12)
    assert rev[1920] == pytest.approx(0.25 + 960 * (750 + 1500) / 2 / (60 * 48000), abs=1e-12)
    assert rev[961] - rev[960] == pytest.approx(750 / (60 * 48000), abs=1e-12)
    assert np.all(np.diff(rev) > 0)


@pytest.mark.parametrize("targets", [[], [750., float("nan")], [750., 0.]])
def test_phase_rejects_empty_nonfinite_or_nonpositive_rpm(analysis, targets):
    with pytest.raises(ValueError):
        analysis.reconstruct_crank_revolutions(np.asarray(targets), 960, 48000)


def independent_phase(targets, frame_samples, fs):
    increments = []
    previous = targets[0]
    for current in targets:
        increments.extend(np.linspace(previous, current, frame_samples) / (60 * fs))
        previous = current
    return np.r_[0., np.cumsum(np.asarray(increments)[:-1])]


def test_known_order_ramp_recovers_22_and_44_without_stereo_cancellation(analysis, screening):
    fs = 48000
    targets = np.linspace(750, 4500, 250)
    rev = independent_phase(targets, 960, fs)
    left = 0.4 * np.sin(2 * np.pi * 22 * rev) + 0.2 * np.sin(2 * np.pi * 44 * rev)
    audio = np.column_stack((left, -left))
    found = analysis.order_spectrum(audio, rev, fs, screening)
    orders = {item["order"]: item for item in found["orders"]}
    assert orders[22]["combined_power"] == pytest.approx(0.4**2 / 2, rel=0.08)
    assert orders[44]["combined_power"] == pytest.approx(0.2**2 / 2, rel=0.14)
    assert orders[22]["combined_power"] > 100 * orders[2]["combined_power"]
    assert orders[44]["channel_power"][0] == pytest.approx(orders[44]["channel_power"][1], rel=1e-10)


def test_order_resampling_filters_high_frequency_before_angle_decimation(analysis, screening):
    fs = 48000
    rev = independent_phase(np.full(150, 750.), 960, fs)
    # 968th order aliases to 56th if one directly samples only 256 points/rev.
    left = np.sin(2 * np.pi * 44 * rev) + 0.5 * np.sin(2 * np.pi * 968 * rev)
    result = analysis.order_spectrum(np.column_stack((left, -left)), rev, fs, screening)
    orders = {item["order"]: item["combined_power"] for item in result["orders"]}
    assert orders[44] > 0.45
    assert orders[56] < orders[44] * 1e-4


def test_order_analysis_rejects_misaligned_and_short_inputs(analysis, screening):
    rev = independent_phase(np.full(150, 750.), 960, 48000)
    audio = stereo(np.arange(rev.size) / 48000)
    with pytest.raises(ValueError):
        analysis.order_spectrum(audio[:-1], rev, 48000, screening)
    with pytest.raises(ValueError):
        analysis.order_spectrum(audio[:100], rev[:100], 48000, screening)
    rev[500] = np.nan
    with pytest.raises(ValueError):
        analysis.order_spectrum(audio, rev, 48000, screening)


def test_drive_events_must_align_with_contract(analysis):
    cfg = {"duration_seconds": 5, "frame_time_s": .02, "frame_samples": 960, "sample_rate_hz": 48000,
           "events": [{"start_s": 2, "duration_s": .2, "from_gear": 1, "to_gear": 2}]}
    drive = {"time_s": np.arange(250) * .02, "rpm": np.full(250, 4000.), "load": np.full(250, .7),
             "shift_event": np.r_[np.zeros(100), np.ones(10), np.zeros(140)]}
    analysis.validate_drive(drive, cfg, 250 * 960)
    drive["shift_event"] = np.roll(drive["shift_event"], 1)
    with pytest.raises(ValueError, match="shift"):
        analysis.validate_drive(drive, cfg, 250 * 960)




def write_csv(path, columns):
    names = list(columns)
    data = np.column_stack([columns[name] for name in names])
    np.savetxt(path, data, delimiter=",", header=",".join(names), comments="", fmt="%.12g")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_pcm_wav(directory, audio):
    np.asarray(audio, dtype="<f8").tofile(directory / "candidate.pcm.f64le")
    quantized = np.clip(np.rint(audio * (2**23)), -(2**23), 2**23 - 1).astype("<i4")
    packed = quantized.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].copy()
    with wave.open(str(directory / "candidate.wav"), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(3)
        out.setframerate(48000)
        out.writeframes(packed.tobytes())


def bind_receipt(directory, drive, contract_sha, snapshot, model_sha, telemetry_path=""):
    state_names = ("rpm", "load", "throttle", "acceleration", "shift_event", "shift_progress",
                   "afterfire_code", "afterfire_progress", "source_time_s")
    data = np.genfromtxt(drive, delimiter=",", names=True)
    actual = np.column_stack([data[key] for key in state_names])
    actual_path = directory / "actual_control.csv"
    np.savetxt(actual_path, actual, delimiter=",", fmt="%.12g")
    receipt_path = directory / "receipt.json"
    record = {
        "directory": str(directory), "drive_csv": str(drive), "drive_sha256": sha(drive),
        "actual_control_csv": str(actual_path), "actual_control_sha256": sha(actual_path),
        "source_telemetry_csv": str(telemetry_path),
        "source_telemetry_sha256": sha(telemetry_path) if telemetry_path else "",
        "pcm_path": str(directory / "candidate.pcm.f64le"), "wav_path": str(directory / "candidate.wav"),
        "pcm_sha256": sha(directory / "candidate.pcm.f64le"),
        "wav_sha256": sha(directory / "candidate.wav"), "contract_sha256": contract_sha,
        "model_sha256": model_sha, "dependency_snapshot": snapshot, "receipt_path": str(receipt_path),
    }
    receipt_path.write_text(json.dumps(record), encoding="utf-8")
    return {**record, "receipt_sha256": sha(receipt_path)}


def refresh_receipt(summary_path, case=None, stationary_side=None):
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if case is not None:
        directory = Path(summary["cases"][case]["directory"])
    else:
        directory = Path(summary["stationary"][0][stationary_side + "_directory"])
    receipt_path = directory / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["pcm_sha256"] = sha(directory / "candidate.pcm.f64le")
    receipt["wav_sha256"] = sha(directory / "candidate.wav")
    for field in ("drive", "actual_control", "source_telemetry"):
        path = receipt[field + "_csv"]
        receipt[field + "_sha256"] = sha(Path(path)) if path else ""
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    if case is not None:
        summary["cases"][case].update(receipt, receipt_sha256=sha(receipt_path))
    else:
        summary["stationary"][0][stationary_side + "_receipt_sha256"] = sha(receipt_path)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")


def build_complete_fixture(screening, tmp_path):
    fs, dt, frame = 48000, .02, 960
    config = {
        "schema": "test.fixture",
        "duration_seconds": 5,
        "sample_rate_hz": fs,
        "frame_time_s": dt,
        "frame_samples": frame,
        "stationary_seconds": 6,
        "stationary_analysis_s": [1, 5],
        "anchors": [{"name": "heldout", "role": "heldout_virtual_state", "rpm": 4000,
                     "load": .8, "throttle": .7}],
        "events": [{"start_s": 2, "duration_s": .2, "from_gear": 1, "to_gear": 2}],
        "screening": {**screening, "stationary_hf_lf_reduction_min_db": 3,
                      "stationary_lf_absolute_change_max_db": 1,
                      "drive_hf_lf_reduction_min_db": 3},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(config), encoding="utf-8")
    ft = np.arange(250) * dt
    sh = np.r_[np.zeros(100), np.ones(10), np.zeros(140)]
    drive = {"time_s": ft, "rpm": np.full(250, 4000.), "load": np.full(250, .8),
             "throttle": np.full(250, .7), "acceleration": np.zeros(250), "shift_event": sh,
             "shift_progress": np.zeros(250), "afterfire_code": np.zeros(250),
             "afterfire_progress": np.zeros(250), "source_time_s": ft}
    write_csv(tmp_path / "drive.csv", drive)
    t = np.arange(fs * 5) / fs
    b = stereo(t)
    c = np.column_stack((.12 * np.sin(2 * np.pi * 100 * t) +
                         np.where(t < 2.5, .03, .054) * np.sin(2 * np.pi * 2000 * t),
                         -.12 * np.sin(2 * np.pi * 100 * t) -
                         np.where(t < 2.5, .03, .054) * np.sin(2 * np.pi * 2000 * t)))
    rev = independent_phase(drive["rpm"], frame, fs)
    cycle = np.remainder(np.pi * np.r_[rev[::frame], rev[-1] + drive["rpm"][-1] / (60 * fs)], 2 * np.pi)
    telemetry = {"time_s": ft, "frame_index": np.arange(1, 251),
                 "phase_before": cycle[:-1], "phase_after": cycle[1:],
                 "cut_min": np.where(sh, .35, 1), "cut_max": np.ones(250),
                 "cut_mean": np.where(sh, .6, 1),
                 "whine_scale": np.full(250, .5), "induction_scale": np.full(250, .7),
                 "voicing_activation": np.full(250, .8)}
    for component in ("combustion", "orders", "identity_exhaust", "identity_whine", "identity_mechanical", "mechanical"):
        telemetry[component + "_before"] = np.ones(250)
        telemetry[component + "_after"] = np.full(250, .4)
    cases = {}
    for name, audio in (("A", b), ("B", b), ("C", c), ("C_repeat", c)):
        directory = tmp_path / name
        directory.mkdir()
        write_pcm_wav(directory, audio)
        case_drive = directory / "drive.csv"
        telemetry_path = directory / "source-telemetry.csv"
        if name == "A":
            write_csv(case_drive, {**drive, "rpm": np.full(250, 3000.), "shift_event": np.zeros(250)})
            telemetry_path = ""
        else:
            case_drive.write_bytes((tmp_path / "drive.csv").read_bytes())
            write_csv(telemetry_path, telemetry)
        cases[name] = {"directory": str(directory), "drive_csv": str(case_drive),
                       "source_telemetry_csv": str(telemetry_path)}
    st = np.arange(fs * 6) / fs
    stationary = {"name": "heldout", "role": "heldout_virtual_state", "rpm": 4000,
                  "load": .8, "throttle": .7}
    for name, amplitude in (("B", .06), ("C", .03)):
        directory = tmp_path / ("stationary_" + name)
        directory.mkdir()
        write_pcm_wav(directory, stereo(st, amplitude))
        tm = np.arange(300) * dt
        write_csv(directory / "drive.csv", {"time_s": tm, "rpm": np.full(300, 4000.),
                    "load": np.full(300, .8), "throttle": np.full(300, .7),
                    "acceleration": np.zeros(300), "shift_event": np.zeros(300),
                    "shift_progress": np.zeros(300), "afterfire_code": np.zeros(300),
                    "afterfire_progress": np.zeros(300), "source_time_s": tm})
        st_rev = independent_phase(np.full(300, 4000.), frame, fs)
        st_cycle = np.remainder(np.pi * np.r_[st_rev[::frame], st_rev[-1] + 4000 / (60 * fs)], 2 * np.pi)
        st_telemetry = {key: np.resize(value, 300) for key, value in telemetry.items()}
        st_telemetry.update(time_s=tm, frame_index=np.arange(1, 301),
                            phase_before=st_cycle[:-1], phase_after=st_cycle[1:])
        write_csv(directory / "source-telemetry.csv", st_telemetry)
        stationary[name + "_directory"] = str(directory)
    shared_stationary = tmp_path / "stationary_drive.csv"
    shared_stationary.write_bytes((tmp_path / "stationary_B" / "drive.csv").read_bytes())
    stationary.update(drive_csv=str(shared_stationary), drive_sha256=sha(shared_stationary))
    contract_sha = sha(contract_path)
    source = tmp_path / "source_dependency.m"
    profile = tmp_path / "profile_dependency.json"
    source.write_text("fixture source", encoding="utf-8")
    profile.write_text('{"fixture":true}', encoding="utf-8")
    snapshot = [{"path": str(path), "sha256": sha(path)} for path in (source, profile)]
    models = tmp_path / "models"
    models.mkdir()
    original_model, candidate_model = models / "original.slx", models / "candidate.slx"
    original_model.write_bytes(b"fixture stock model")
    candidate_model.write_bytes(b"fixture candidate model")
    adapter_rel = Path("tools/sound_sim/s12/playground_v12/common/shared_model/S12_Frozen_Radiation_Adapter_v12.slx")
    adapter = tmp_path / adapter_rel
    adapter.parent.mkdir(parents=True)
    adapter.write_bytes(b"fixture frozen radiation adapter")
    (tmp_path / "baseline.json").write_text(json.dumps({"source_root": str(tmp_path), "protected": {
        original_model.relative_to(tmp_path).as_posix(): sha(original_model), adapter_rel.as_posix(): sha(adapter)}}), encoding="utf-8")
    (tmp_path / "build-receipt.json").write_text(json.dumps({"source": str(original_model),
        "candidate": str(candidate_model), "source_sha256": sha(original_model),
        "candidate_sha256": sha(candidate_model), "contract_sha256": contract_sha}), encoding="utf-8")
    for name, case in cases.items():
        cases[name] = bind_receipt(Path(case["directory"]), Path(case["drive_csv"]),
                                   contract_sha, snapshot, sha(original_model if name == "A" else candidate_model),
                                   case["source_telemetry_csv"])
    for name in ("B", "C"):
        directory = Path(stationary[name + "_directory"])
        record = bind_receipt(directory, directory / "drive.csv", contract_sha, snapshot, sha(candidate_model),
                              directory / "source-telemetry.csv")
        stationary[name + "_receipt_sha256"] = record["receipt_sha256"]
    summary = {"run_root": str(tmp_path), "contract_path": str(contract_path),
               "contract_sha256": contract_sha, "dependency_snapshot": snapshot,
               "drive_csv": str(tmp_path / "drive.csv"), "drive_sha256": sha(tmp_path / "drive.csv"),
               "cases": cases, "stationary": [stationary]}
    (tmp_path / "run-summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return contract_path


def test_complete_fixture_reports_every_drive_window_and_independent_a_cycle(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    result = analysis.analyze_run(tmp_path, contract_path)
    import hashlib
    assert result["contract_sha256"] == hashlib.sha256(contract_path.read_bytes()).hexdigest()
    assert result["stationary_screening"]["pass"] is True
    assert result["stationary"][0]["hf_lf_applicable"] is True
    assert len(result["drive"]["windows"]) == 2
    assert result["drive"]["windows"][0]["pass"] is True
    assert result["drive"]["windows"][1]["pass"] is False
    assert result["drive"]["worst_window"]["comparison"]["combined"]["hf_lf_change_db"] > -3
    assert result["drive"]["pass"] is False
    assert result["phase"]["B"]["max_abs_error_rad"] < 1e-7
    assert result["phase"]["A"]["status"] == "source_telemetry_unavailable"
    assert result["source_diagnostics"]["C"]["component_energy"]["identity_whine"]["before_mean"] == pytest.approx(1)
    assert result["source_diagnostics"]["C"]["component_energy"]["identity_whine"]["after_mean"] == pytest.approx(.4)
    assert result["source_diagnostics"]["C"]["shifts"][0]["cut_min"] == pytest.approx(.35)
    assert len(result["orders"]["A"]["orders"]) == len(screening["orders_to_report"])
    for filename in ("analysis.json", "comparable_windows.csv", "phase.png", "order.png", "shift-envelope.png"):
        assert (tmp_path / filename).is_file()
    saved = json.loads((tmp_path / "analysis.json").read_text(encoding="utf-8"))
    assert saved["drive"]["pass"] is False
    assert len((tmp_path / "comparable_windows.csv").read_text(encoding="utf-8").splitlines()) == 3
    import csv
    with (tmp_path / "comparable_windows.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert float(rows[0]["B_left_lf_power"]) == pytest.approx(.12**2 / 2, rel=1e-5)
    assert float(rows[0]["C_right_lf_power"]) == pytest.approx(.12**2 / 2, rel=1e-5)
    assert float(rows[1]["right_hf_lf_change_db"]) > -3



def test_stationary_lf_gate_rejects_large_absolute_increase(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    t = np.arange(48000 * 6) / 48000
    high_lf = .30 * np.sin(2 * np.pi * 100 * t) + .03 * np.sin(2 * np.pi * 2000 * t)
    write_pcm_wav(tmp_path / "stationary_C", np.column_stack((high_lf, -high_lf)))
    refresh_receipt(tmp_path / "run-summary.json", stationary_side="C")
    result = analysis.analyze_run(tmp_path, contract_path)
    assert result["stationary"][0]["lf_pass"] is False
    assert result["stationary"][0]["comparison"]["combined"]["lf_change_db"] > 1
    assert result["stationary_screening"]["pass"] is False


def test_b_and_c_with_different_control_data_are_rejected(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    data = np.genfromtxt(tmp_path / "drive.csv", delimiter=",", names=True)
    columns = {key: data[key] for key in data.dtype.names}
    columns["rpm"][4] += 1
    changed_drive = tmp_path / "C" / "drive.csv"
    write_csv(changed_drive, columns)
    summary_path = tmp_path / "run-summary.json"
    refresh_receipt(summary_path, case="C")
    with pytest.raises(ValueError, match="control frames"):
        analysis.analyze_run(tmp_path, contract_path)


def test_no_qualifying_drive_windows_is_a_failed_screen(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    data = np.genfromtxt(tmp_path / "drive.csv", delimiter=",", names=True)
    columns = {key: data[key] for key in data.dtype.names}
    columns["load"][:] = .5
    write_csv(tmp_path / "drive.csv", columns)
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["drive_sha256"] = sha(tmp_path / "drive.csv")
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    for name in ("B", "C", "C_repeat"):
        directory = tmp_path / name
        (directory / "drive.csv").write_bytes((tmp_path / "drive.csv").read_bytes())
        actual = np.loadtxt(directory / "actual_control.csv", delimiter=",")
        actual[:, 1] = .5
        np.savetxt(directory / "actual_control.csv", actual, delimiter=",", fmt="%.12g")
        refresh_receipt(summary_path, case=name)
    result = analysis.analyze_run(tmp_path, contract_path)
    assert result["drive"]["windows"] == []
    assert result["drive"]["aggregate"] is None
    assert result["drive"]["worst_window"] is None
    assert result["drive"]["pass"] is False


def test_stationary_uses_explicit_shared_drive_csv(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    shared = tmp_path / "stationary_drive.csv"
    assert shared.read_bytes() == (tmp_path / "stationary_B" / "drive.csv").read_bytes()
    assert shared.read_bytes() == (tmp_path / "stationary_C" / "drive.csv").read_bytes()
    result = analysis.analyze_run(tmp_path, contract_path)
    import hashlib
    assert result["contract_sha256"] == hashlib.sha256(contract_path.read_bytes()).hexdigest()
    assert result["stationary_screening"]["pass"] is True




def test_command_line_writes_reports_and_exposes_failed_gate(analysis, screening, tmp_path):
    import os
    import subprocess
    import sys
    contract_path = build_complete_fixture(screening, tmp_path)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run([sys.executable, str(SCRIPT), "--run-root", str(tmp_path),
                                "--contract", str(contract_path)], capture_output=True, text=True, env=env)
    assert completed.returncode == 0, completed.stderr
    assert "stationary_screening: PASS" in completed.stdout
    assert "drive_screening: FAIL" in completed.stdout
    assert (tmp_path / "analysis.json").is_file()


def test_db_ratio_handles_extreme_nonzero_powers_without_overflow(analysis):
    assert analysis.power_ratio_db(1e300, 1e-300) == pytest.approx(6000.)
    assert analysis.power_ratio_db(1e-300, 1e300) == pytest.approx(-6000.)


@pytest.mark.parametrize("numerator, denominator", [(1., 0.), (0., 1.), (1., float("nan")), (float("inf"), 1.)])
def test_db_ratio_rejects_zero_or_nonfinite_boundary(analysis, numerator, denominator):
    with pytest.raises(ValueError):
        analysis.power_ratio_db(numerator, denominator)


def test_source_phase_misalignment_is_rejected(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    path = tmp_path / "B" / "source-telemetry.csv"
    data = np.genfromtxt(path, delimiter=",", names=True)
    columns = {key: data[key] for key in data.dtype.names}
    columns["phase_before"][20] += .25
    write_csv(path, columns)
    refresh_receipt(tmp_path / "run-summary.json", case="B")
    with pytest.raises(ValueError, match="phase"):
        analysis.analyze_run(tmp_path, contract_path)




def test_invalidated_run_is_rejected_before_analysis(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    (tmp_path / "INVALIDATED.json").write_text('{"reason":"test"}', encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)invalidat"):
        analysis.analyze_run(tmp_path, contract_path)
    assert not (tmp_path / "analysis.json").exists()


@pytest.mark.parametrize("which", ["case", "stationary"])
def test_all_render_directories_must_be_unique(analysis, screening, tmp_path, which):
    contract_path = build_complete_fixture(screening, tmp_path)
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if which == "case":
        summary["cases"]["C"]["directory"] = summary["cases"]["B"]["directory"]
    else:
        summary["stationary"][0]["C_directory"] = summary["stationary"][0]["B_directory"]
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)(unique|duplicat|reus)"):
        analysis.analyze_run(tmp_path, contract_path)


def test_contract_hash_must_match_run_summary(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["contract_sha256"] = "0" * 64
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)contract.*(hash|sha)"):
        analysis.analyze_run(tmp_path, contract_path)


@pytest.mark.parametrize("relative", [
    "B/candidate.pcm.f64le", "B/candidate.wav", "B/receipt.json",
    "B/actual_control.csv", "B/drive.csv", "B/source-telemetry.csv",
    "stationary_C/candidate.pcm.f64le", "stationary_C/candidate.wav",
    "stationary_C/receipt.json", "stationary_C/drive.csv", "stationary_C/source-telemetry.csv",
    "drive.csv", "stationary_drive.csv",
])
def test_tampered_case_and_anchor_evidence_is_rejected(analysis, screening, tmp_path, relative):
    contract_path = build_complete_fixture(screening, tmp_path)
    path = tmp_path / relative
    if path.suffix in (".f64le", ".wav"):
        with path.open("r+b") as stream:
            stream.seek(-1, 2)
            byte = stream.read(1)
            stream.seek(-1, 2)
            stream.write(bytes([byte[0] ^ 1]))
    else:
        with path.open("ab") as stream:
            stream.write(b" ")
    with pytest.raises(ValueError, match="(?i)(sha|hash|byte|size)"):
        analysis.analyze_run(tmp_path, contract_path)
    assert not (tmp_path / "analysis.json").exists()


def test_changed_source_dependency_is_rejected(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    (tmp_path / "source_dependency.m").write_text("changed after render", encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)dependenc"):
        analysis.analyze_run(tmp_path, contract_path)


def test_receipt_snapshot_must_match_pre_render_snapshot(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    receipt_path = tmp_path / "C" / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["dependency_snapshot"][0]["sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    summary["cases"]["C"].update(receipt, receipt_sha256=sha(receipt_path))
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)dependency snapshot"):
        analysis.analyze_run(tmp_path, contract_path)


def test_wav_must_match_pcm_even_when_all_hashes_are_rebound(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    path = tmp_path / "C" / "candidate.wav"
    with path.open("r+b") as stream:
        stream.seek(-1, 2)
        byte = stream.read(1)
        stream.seek(-1, 2)
        stream.write(bytes([byte[0] ^ 0x40]))
    refresh_receipt(tmp_path / "run-summary.json", case="C")
    with pytest.raises(ValueError, match="WAV does not match"):
        analysis.analyze_run(tmp_path, contract_path)


def test_actual_control_must_match_drive_even_when_hashes_are_rebound(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    path = tmp_path / "B" / "actual_control.csv"
    data = np.loadtxt(path, delimiter=",")
    data[7, 0] += 1
    np.savetxt(path, data, delimiter=",", fmt="%.12g")
    refresh_receipt(tmp_path / "run-summary.json", case="B")
    with pytest.raises(ValueError, match="actual control frames"):
        analysis.analyze_run(tmp_path, contract_path)


def test_render_directory_outside_run_is_rejected(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["cases"]["B"]["directory"] = str(tmp_path.parent / "outside")
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="inside the run root"):
        analysis.analyze_run(tmp_path, contract_path)


def test_stationary_state_must_match_declared_anchor_even_with_consistent_hashes(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    shared = tmp_path / "stationary_drive.csv"
    data = np.genfromtxt(shared, delimiter=",", names=True)
    columns = {key: data[key] for key in data.dtype.names}
    columns["load"][:] = .4
    write_csv(shared, columns)
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["stationary"][0]["drive_sha256"] = sha(shared)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    for side in ("B", "C"):
        directory = tmp_path / ("stationary_" + side)
        (directory / "drive.csv").write_bytes(shared.read_bytes())
        actual = np.loadtxt(directory / "actual_control.csv", delimiter=",")
        actual[:, 1] = .4
        np.savetxt(directory / "actual_control.csv", actual, delimiter=",", fmt="%.12g")
        refresh_receipt(summary_path, stationary_side=side)
    with pytest.raises(ValueError, match="stationary control state differs"):
        analysis.analyze_run(tmp_path, contract_path)


def test_replaced_contract_and_summary_still_conflict_with_case_receipt(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["screening"]["drive_hf_lf_reduction_min_db"] = 1
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["contract_sha256"] = sha(contract_path)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt contract SHA256"):
        analysis.analyze_run(tmp_path, contract_path)


def test_evidence_change_during_analysis_is_rejected(analysis, screening, tmp_path, monkeypatch):
    contract_path = build_complete_fixture(screening, tmp_path)
    original = analysis.order_spectrum
    did_change = False

    def during_analysis(*args, **kwargs):
        nonlocal did_change
        result = original(*args, **kwargs)
        if not did_change:
            with (tmp_path / "B" / "candidate.wav").open("ab") as stream:
                stream.write(b" ")
            did_change = True
        return result

    monkeypatch.setattr(analysis, "order_spectrum", during_analysis)
    with pytest.raises(ValueError, match="(?i)(wav|sha|hash)"):
        analysis.analyze_run(tmp_path, contract_path)
    assert not (tmp_path / "analysis.json").exists()


@pytest.mark.parametrize("relative", ["models/original.slx", "models/candidate.slx",
    "tools/sound_sim/s12/playground_v12/common/shared_model/S12_Frozen_Radiation_Adapter_v12.slx"])
def test_model_must_match_preexisting_build_and_baseline_evidence(analysis, screening, tmp_path, relative):
    contract_path = build_complete_fixture(screening, tmp_path)
    with (tmp_path / relative).open("ab") as stream:
        stream.write(b"drift")
    with pytest.raises(ValueError, match="(?i)(model|radiation|sha)"):
        analysis.analyze_run(tmp_path, contract_path)


def test_case_receipt_model_must_match_corresponding_built_model(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    receipt_path = tmp_path / "B" / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["model_sha256"] = sha(tmp_path / "models" / "original.slx")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    summary["cases"]["B"].update(receipt, receipt_sha256=sha(receipt_path))
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)model"):
        analysis.analyze_run(tmp_path, contract_path)


def test_receipt_audio_path_must_belong_to_its_own_render_directory(analysis, screening, tmp_path):
    contract_path = build_complete_fixture(screening, tmp_path)
    summary_path = tmp_path / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    receipt_path = tmp_path / "C" / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["pcm_path"] = str(tmp_path / "B" / "candidate.pcm.f64le")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    summary["cases"]["C"].update(receipt, receipt_sha256=sha(receipt_path))
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)(audio|pcm).*path"):
        analysis.analyze_run(tmp_path, contract_path)

