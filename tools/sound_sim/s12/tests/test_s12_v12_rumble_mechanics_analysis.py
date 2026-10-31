"""Independent numeric and evidence-boundary regressions for the rumble experiment."""
import importlib.util
import json
import shutil
import sys
import wave
from pathlib import Path

import numpy as np
import pytest


LAB = Path(__file__).resolve().parents[4] / "reports/app8-rumble-mechanics-candidate-20261029"


def load(name):
    path = LAB / f"{name}.py"
    assert path.is_file(), f"Required independent analysis tool is absent: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if str(LAB) not in sys.path:
        sys.path.insert(0, str(LAB))
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def analysis():
    class LazyModule:
        def __getattr__(self, name):
            return getattr(load("analyze_rumble_mechanics"),name)
    return LazyModule()


def tone(seconds=4, fs=48000):
    t = np.arange(int(seconds * fs)) / fs
    return np.column_stack([.03 * np.sin(2 * np.pi * 50 * t) + .01 * np.sin(2 * np.pi * 700 * t),
                            .06 * np.sin(2 * np.pi * 100 * t) + .02 * np.sin(2 * np.pi * 700 * t)])


def test_welch_recovers_absolute_power_and_does_not_mix_antiphase_channels(analysis):
    x = tone()
    x[:, 1] = -x[:, 0]
    result = analysis.band_powers(x, 48000)
    assert result["channels"][0]["20_250"] == pytest.approx(.03 ** 2 / 2, rel=.001)
    assert result["power_mean"]["20_250"] == pytest.approx(.03 ** 2 / 2, rel=.001)
    assert result["stereo_cross_power"]["20_250"] == pytest.approx(-.03 ** 2 / 2, rel=.001)


def test_absolute_gates_reject_one_bad_channel_even_when_average_passes(analysis):
    x = tone()
    candidate = x * np.array([1.3, 2.5])
    result = analysis.compare_bands(x, candidate, 48000)
    assert result["power_mean"]["20_250"] > 3
    assert not analysis.gate_comparison(result, "R")["pass"]
    assert analysis.gate_comparison(analysis.compare_bands(x, x * 1.5, 48000), "R")["pass"]


def test_sr_gate_limits_low_frequency_gain_and_midband_loss(analysis):
    x = tone()
    assert not analysis.gate_comparison(analysis.compare_bands(x, x * 3, 48000), "SR")["pass"]
    t = np.arange(len(x)) / 48000
    y = x - .008 * np.sin(2 * np.pi * 700 * t)[:, None] * np.array([1, 2])
    assert not analysis.gate_comparison(analysis.compare_bands(x, y, 48000), "SR2")["pass"]


def test_difference_power_retains_coherent_cross_term(analysis):
    x = tone()
    result = analysis.signal_difference(x, x * 2, 48000)
    assert result["channels"][0]["20_250"]["cross_term"] == pytest.approx(.03 ** 2, rel=.001)
    assert result["channels"][0]["20_250"]["closure_error"] < 1e-12


def test_order_analysis_resolves_5_7_11_and_preserves_channels(analysis):
    fs = 48000
    rev = np.arange(4 * fs) / fs * 25
    x = np.column_stack([.1 * np.sin(2*np.pi*5*rev) + .03*np.sin(2*np.pi*11*rev),
                         .2 * np.sin(2*np.pi*7*rev)])
    rows = {r["order"]: r for r in analysis.order_spectrum(x, rev, fs)["orders"]}
    assert rows[5]["channel_power"][0] == pytest.approx(.005, rel=.01)
    assert rows[7]["channel_power"][1] == pytest.approx(.02, rel=.01)
    assert rows[11]["channel_power"][0] == pytest.approx(.00045, rel=.02)
    assert rows[5]["channel_power"][1] < 1e-8


@pytest.mark.parametrize("bad", [np.zeros((100,2)), np.ones((100,2))*np.nan,
                                     np.ones((100,2))*1.01, np.ones((100,1))])
def test_pcm_boundary_rejects_zero_nonfinite_overrange_or_wrong_channels(analysis, bad):
    with pytest.raises(ValueError):
        analysis.validate_pcm(bad)


def test_pcm24_decode_is_independent_and_detects_changed_bytes(analysis, tmp_path):
    x = np.array([[-1, 0], [1 - 2**-23, -.5], [2**-23, -.00001]])
    path = tmp_path / "candidate.wav"
    ints = np.rint(x * 2**23).astype(np.int32).reshape(-1)
    packed = ((ints[:, None] >> np.array([0,8,16])) & 255).astype(np.uint8).tobytes()
    with wave.open(str(path), "wb") as out:
        out.setparams((2,3,48000,0,"NONE","not compressed"))
        out.writeframes(packed)
    assert analysis.verify_pcm24(path, x, 48000) <= 2**-24
    damaged = bytearray(path.read_bytes()); damaged[-3] ^= 64; path.write_bytes(damaged)
    with pytest.raises(ValueError, match="PCM24"):
        analysis.verify_pcm24(path, x, 48000)


def test_hash_binding_rejects_mutation_and_duplicate_or_external_paths(analysis, tmp_path):
    f = tmp_path / "evidence.bin"; f.write_bytes(b"frozen")
    expected = analysis.sha256(f)
    analysis.verify_hash(f, expected)
    f.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA256"):
        analysis.verify_hash(f, expected)
    with pytest.raises(ValueError, match="duplicate"):
        analysis.unique_case_paths(tmp_path, [{"directory": str(tmp_path/"case")}] * 2)
    with pytest.raises(ValueError, match="inside"):
        analysis.unique_case_paths(tmp_path, [{"directory": str(tmp_path.parent/"escape")}])


def test_native_controls_need_bit_exact_equality_not_csv_tolerance(analysis):
    expected = np.zeros((4500,9)); expected[:,0] = 1000
    expected[:,8] = np.arange(4500) * .02
    actual = expected.copy(); actual[200,0] = np.nextafter(1000., np.inf)
    with pytest.raises(ValueError, match="exact"):
        analysis.validate_controls(actual, expected, expected[:,8])
    analysis.validate_controls(expected, expected, expected[:,8])


def test_phase_reset_inside_shift_is_rejected(analysis):
    samples = 960 * 100
    theta = np.remainder(np.arange(samples) / 48000 * 25 * np.pi, 2*np.pi)
    controls = np.zeros((100,9)); controls[:,0] = 1500
    controls[:,8] = np.arange(100) * .02
    analysis.phase_diagnostics(theta, controls, 48000, 960)
    theta[960*30:] = np.remainder(theta[960*30:] + .5, 2*np.pi)
    with pytest.raises(ValueError, match="phase"):
        analysis.phase_diagnostics(theta, controls, 48000, 960)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requires independent FFmpeg meter")
def test_audition_uses_one_scalar_from_raw_and_common_peak_safe_target(tmp_path):
    audition = load("make_audition")
    fs = 48000; rng = np.random.default_rng(82)
    raw = tone(seconds=5) + rng.normal(0,.002,(5*fs,2))
    crest = raw.copy(); crest[fs, :] = .95
    root = tmp_path / "group"
    manifest = audition.make_group({"B0": raw, "SR": crest}, fs, root, target_lufs=-23)
    assert manifest["target_lufs"] < -23  # Peak requires a group-wide lower target.
    assert len(manifest["items"]) == 2
    for label, item in manifest["items"].items():
        assert item["true_peak_dbtp"] <= -1.5 + .01
        assert abs(item["integrated_lufs"] - manifest["target_lufs"]) <= .2
        decoded = audition.read_pcm24(Path(item["path"]), fs)
        original = {"B0": raw, "SR": crest}[label]
        assert np.max(np.abs(decoded - original * item["scalar"])) <= 2**-23
        assert item["source_pcm_sha256"] == audition.array_sha(original)


def test_audition_rejects_silence_nonfinite_and_too_short(tmp_path):
    audition = load("make_audition")
    for x in (np.zeros((48000*4,2)), np.ones((100,2)), np.ones((48000*4,2))*np.nan):
        with pytest.raises(ValueError):
            audition.make_group({"bad":x},48000,tmp_path/str(len(x)))


def test_pressure_tap_is_unbounded_but_coloring_must_be_causal(analysis):
    rng = np.random.default_rng(12)
    x = rng.normal(0, 12, 10000)  # Pressure is not final PCM and may exceed +/-1.
    a,b = .9973854300793629,.9716127758430366
    # Direct sample recurrence is the oracle; analyzer uses an independent SOS path.
    h=z=previous=0.; y=[]
    for sample in x:
        h=(1+a)/2*(sample-previous)+a*h
        z=(1-b)*h+b*z
        y.append(sample+z); previous=sample
    result = analysis.verify_pressure_color(x,np.asarray(y),1)
    assert result["maximum_equation_residual"] < 1e-10
    with pytest.raises(ValueError,match="color"):
        analysis.verify_pressure_color(x,np.roll(y,1),1)
    with pytest.raises(ValueError,match="bypass"):
        analysis.verify_pressure_color(x,np.nextafter(x,np.inf),0)


def test_mechanics_event_lock_requires_recorded_profile_bank_phases(analysis):
    # The profile has two banks of alternating, uniformly spaced firing events.
    theta = np.array([0,10,20,40,90,180])*2*np.pi/720
    q = analysis.mechanical_envelope(theta,[0,90,180,270,360,450,540,630],[-1,1,-1,1,-1,1,-1,1])
    assert q[0].tolist() == pytest.approx([1,-.125])
    assert q[1,0] == pytest.approx(.4375)
    assert q[2].tolist() == pytest.approx([-.125,-.125])
    assert q[4].tolist() == pytest.approx([-.125,1])


def test_analysis_refuses_incomplete_drive_set_before_any_screening(analysis,tmp_path):
    contract = LAB/"EXPERIMENT_CONTRACT.json"
    root = tmp_path/"incomplete";root.mkdir()
    (root/"run-summary.json").write_text(json.dumps({"run_root":str(root.resolve()),
        "contract_path":str(contract.resolve()),"contract_sha256":analysis.sha256(contract),"cases":{}}))
    with pytest.raises(ValueError,match="eight"):
        analysis.analyze_run(root,contract)


def test_repeat_identity_requires_both_raw_pcm_and_wav(analysis):
    records = {name:{"receipt":{"pcm_sha256":"a","wav_sha256":"b"}}
               for name in ("SR","SR_repeat","SR2","SR2_repeat")}
    analysis.verify_repeats(records)
    records["SR2_repeat"]["receipt"]["wav_sha256"] = "changed"
    with pytest.raises(ValueError,match="repeat"):
        analysis.verify_repeats(records)


def test_matlab_json_integral_float_dimensions_decode_without_relaxing_byte_count(analysis,tmp_path):
    path = tmp_path/"matlab.f64le";path.write_bytes(np.ones((100,9),dtype="<f8").tobytes())
    metadata = {"path":str(path),"sha256":analysis.sha256(path),"shape":[100.,9.],"dtype":"float64-le","order":"row-major"}
    assert analysis._binary(metadata,analysis.Evidence()).shape == (100,9)
    metadata["shape"] = [100.,9.1]
    with pytest.raises(ValueError,match="shape"):
        analysis._binary(metadata,analysis.Evidence())


def make_record(analysis,tmp_path):
    directory = tmp_path/"case";directory.mkdir()
    fs,n = 48000,100
    control = np.zeros((n,9));control[:,0]=1500;control[:,8]=np.arange(n)*.02
    phase = np.remainder(np.arange(n*960)*25*np.pi/fs,2*np.pi)
    pcm = np.repeat(tone(seconds=2)[:,:1],2,axis=1)
    audition = load("make_audition")
    audition.write_pcm24(directory/"candidate.wav",pcm,fs)
    receipt = {"directory":str(directory),"receipt_path":str(directory/"receipt.json"),
               "contract_sha256":"a"*64,"model_sha256":"b"*64,"dependency_snapshot":[],
               "wrapper_expression":f"s12_v12_model_rumble_mechanics_step(u, '{tmp_path / 'contract.json'}', 'B0')",
               "actual_wrapper_mode":"B0","frame_count":n,"samples_per_channel":len(pcm),
               "sample_rate_hz":fs,"channels":2,"unique_source_frames":n,
               "function_calls":{"source_frame":n,"frozen_frame":n,"radiation_wrapper":n},"binary_exports":{}}
    receipt["SimulationInput_wrapper_expression"]=receipt["wrapper_expression"]
    arrays = {"pcm":pcm,"actual_control":control,"actual_clock":control[:,8:9],
              "source_pressure":pcm[:,:1]*10,"source_pressure_before":pcm[:,:1]*10,
              "radiated_pressure":pcm[:,:1]*10,"cycle_phase":phase[:,None]}
    for key,array in arrays.items():
        path = directory/("candidate.pcm.f64le" if key=="pcm" else key+".f64le")
        path.write_bytes(np.asarray(array,dtype="<f8",order="C").tobytes())
        receipt["binary_exports"][key] = {"path":str(path),"sha256":analysis.sha256(path),
            "shape":list(array.shape),"order":"row-major","dtype":"float64-le"}
    names = "time_s,rpm,load,throttle,acceleration,shift_event,shift_progress,afterfire_code,afterfire_progress,source_time_s"
    np.savetxt(directory/"drive.csv",np.column_stack([control[:,8],control]),delimiter=",",header=names,comments="")
    np.savetxt(directory/"actual_control.csv",control,delimiter=",")
    after = np.remainder((np.arange(1,n+1)*960)*25*np.pi/fs,2*np.pi)
    telemetry = np.column_stack([control[:,8],np.arange(1,n+1),phase[::960],after])
    np.savetxt(directory/"source-telemetry.csv",telemetry,delimiter=",",header="time_s,frame_index,phase_before,phase_after",comments="")
    (directory/"capture.mat").write_bytes(b"fixture-MAT-provenance-only-not-runtime-evidence")
    for field,filename in (("pcm","candidate.pcm.f64le"),("wav","candidate.wav"),("drive","drive.csv"),
                           ("actual_control","actual_control.csv"),("source_telemetry","source-telemetry.csv"),("capture_mat","capture.mat")):
        key = field+"_csv" if field in ("drive","actual_control","source_telemetry") else field+"_path"
        if field == "capture_mat":key=field
        receipt[key] = str(directory/filename);receipt[field+"_sha256"] = analysis.sha256(directory/filename)
    return receipt


def freeze_record(analysis,receipt):
    path = Path(receipt["receipt_path"])
    path.write_text(json.dumps(receipt))
    return {**receipt,"receipt_sha256":analysis.sha256(path)}


def test_real_receipt_chain_accepts_complete_bytes_and_rejects_forged_native_shape(analysis,tmp_path):
    receipt = make_record(analysis,tmp_path)
    record = freeze_record(analysis,receipt)
    result = analysis._record(record,tmp_path,"a"*64,[],"b"*64,analysis.Evidence(),2,"B0",tmp_path/"contract.json")
    assert result["controls"].shape == (100,9)
    receipt["binary_exports"]["actual_control"]["shape"] = [100,10]
    record = freeze_record(analysis,receipt)
    with pytest.raises(ValueError,match="shape"):
        analysis._record(record,tmp_path,"a"*64,[],"b"*64,analysis.Evidence(),2,"B0",tmp_path/"contract.json")


def test_short_receipt_can_supply_its_own_actual_initialization_trace(analysis,tmp_path):
    receipt = make_record(analysis,tmp_path)
    receipt["function_calls"]["frozen_frame"] = 101
    receipt["function_calls"]["radiation_wrapper"] = 101
    receipt["radiation_evaluation_times"] = np.r_[0,np.arange(100)*.02].tolist()
    receipt["sequential_frozen_max_error"] = 0
    record = freeze_record(analysis,receipt)
    analysis._record(record,tmp_path,"a"*64,[],"b"*64,analysis.Evidence(),2,"B0",tmp_path/"contract.json")
    receipt["radiation_evaluation_times"][10] = 0
    record = freeze_record(analysis,receipt)
    with pytest.raises(ValueError,match="trace"):
        analysis._record(record,tmp_path,"a"*64,[],"b"*64,analysis.Evidence(),2,"B0",tmp_path/"contract.json")


def test_real_receipt_rejects_rehashed_directory_escape_and_duplicate_frames(analysis,tmp_path):
    receipt = make_record(analysis,tmp_path)
    path = tmp_path/"escaped.f64le";path.write_bytes(np.zeros((100,1),dtype="<f8").tobytes())
    original = receipt["binary_exports"]["actual_clock"].copy()
    receipt["binary_exports"]["actual_clock"] = {**original,"path":str(path),"sha256":analysis.sha256(path)}
    record = freeze_record(analysis,receipt)
    with pytest.raises(ValueError,match="escape"):
        analysis._record(record,tmp_path,"a"*64,[],"b"*64,analysis.Evidence(),2,"B0",tmp_path/"contract.json")
    receipt["binary_exports"]["actual_clock"] = original
    telemetry = Path(receipt["source_telemetry_csv"])
    lines = telemetry.read_text().splitlines();lines[10] = lines[9];telemetry.write_text("\n".join(lines)+"\n")
    receipt["source_telemetry_sha256"] = analysis.sha256(telemetry)
    record = freeze_record(analysis,receipt)
    with pytest.raises(ValueError,match="sequence"):
        analysis._record(record,tmp_path,"a"*64,[],"b"*64,analysis.Evidence(),2,"B0",tmp_path/"contract.json")


def test_extra_frozen_initialization_needs_real_clock_trace_and_old_pcm_prefix(analysis,tmp_path):
    old = tmp_path/"old"/"B";old.mkdir(parents=True)
    prior = old/"candidate.pcm.f64le";prior.write_bytes(np.arange(400,dtype="<f8").tobytes())
    contract = tmp_path/"contract.json"
    contract.write_text(json.dumps({"reference":{"capture_mat":str(old/"capture.mat"),"pcm_sha256":analysis.sha256(prior)}}))
    smoke = tmp_path/"smoke";smoke.mkdir()
    clock = np.arange(100,dtype=float)*.02
    clock_path = smoke/"actual_clock.f64le";clock_path.write_bytes(clock.astype("<f8").tobytes())
    pcm = smoke/"pcm.f64le";pcm.write_bytes(prior.read_bytes()[:800])
    metadata = {"path":str(clock_path),"sha256":analysis.sha256(clock_path),"shape":[100,1],"dtype":"float64-le","order":"row-major"}
    smoke_receipt = {"binary_exports":{"actual_clock":metadata},"radiation_evaluation_times":np.r_[0,clock].tolist(),"sequential_frozen_max_error":0}
    receipt_path = smoke/"receipt.json";receipt_path.write_text(json.dumps(smoke_receipt))
    record = {"receipt_path":str(receipt_path),"receipt_sha256":analysis.sha256(receipt_path),"pcm_path":str(pcm),"pcm_sha256":analysis.sha256(pcm)}
    summary = {"mode":"smoke","status":"RENDERED_DIGITAL_PASS_ANALYSIS_PENDING","dependency_snapshot":[],
               "cases":{name:record.copy() for name in ("B0","S","R","SR","SR_repeat","S2","SR2","SR2_repeat")},
               "short_cases":{name:record.copy() for name in ("B0","S_gain","S_timing","S","S2_gain","S2_timing","S2")}}
    summary_path = smoke/"run-summary.json"
    proof_path = tmp_path/"proof.json"
    def freeze():
        receipt_path.write_text(json.dumps(smoke_receipt));digest = analysis.sha256(receipt_path)
        for item in [*summary["cases"].values(),*summary["short_cases"].values()]:item["receipt_sha256"]=digest
        summary_path.write_text(json.dumps(summary))
        proof_path.write_text(json.dumps({"contract_sha256":"a"*64,"baseline_pcm_exact":True,
            "run_summary":str(summary_path),"run_summary_sha256":analysis.sha256(summary_path)}))
        return {"function_calls":{"source_frame":4500,"frozen_frame":4501,"radiation_wrapper":4501},
                "contract_sha256":"a"*64,"dependency_snapshot":[],"radiation_initialization_proof":str(proof_path),
                "radiation_initialization_proof_sha256":analysis.sha256(proof_path)}
    analysis.verify_radiation_evaluations(freeze(),4500,analysis.Evidence(),contract)
    smoke_receipt["radiation_evaluation_times"][40] = .1
    with pytest.raises(ValueError,match="trace"):
        analysis.verify_radiation_evaluations(freeze(),4500,analysis.Evidence(),contract)
