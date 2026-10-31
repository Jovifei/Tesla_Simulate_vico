"""Make named and blinded fixed-scalar auditions directly from verified RAW PCM.

Each group starts at -23 LUFS and lowers its common target when necessary.
There is no limiter, AGC, dynamic gain, stacked gain, or audio regeneration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from analyze_rumble_mechanics import (MODES, Evidence, audio_array, read_pcm24, sha256,
                                     validate_pcm, verify_hash, verify_pcm24)

HISTORICAL_C_WAV_SHA = "f3d3ae39cf511b4413958ad70a4a6ae557ada80dfe7c1129219c87035cb5d279"
HISTORICAL_C_CONTROL_SHA = "03fe20c544da402cf8310846b1d6fe8cc82c93fd8c7f890132cc5a4316e3accb"


def array_sha(audio):
    return hashlib.sha256(np.asarray(audio,dtype="<f8",order="C").tobytes()).hexdigest()


def meter(audio, fs, log_prefix):
    """Independent FFmpeg EBU R128 integrated loudness and oversampled true peak."""
    x = audio_array(audio)
    if len(x) < 2.5*fs or not np.any(x):
        raise ValueError("loudness is indeterminate: silent or shorter than 2.5 seconds")
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("independent FFmpeg meter is unavailable")
    command = [executable,"-hide_banner","-nostats","-f","f64le","-ar",str(fs),"-ac","2",
               "-i","pipe:0","-af","ebur128=peak=true","-f","null","-"]
    result = subprocess.run(command,input=np.asarray(x,dtype="<f8",order="C").tobytes(),
                            capture_output=True,check=False)
    output = result.stderr.decode("utf-8",errors="replace")
    log_prefix = Path(log_prefix); log_prefix.parent.mkdir(parents=True,exist_ok=True)
    log_prefix.with_suffix(".log").write_text(output,encoding="utf-8")
    log_prefix.with_suffix(".command.json").write_text(json.dumps(command,indent=2)+"\n",encoding="utf-8")
    summary = output.rsplit("Summary:",1)[-1]
    loudness = re.search(r"\bI:\s*([-+\w.]+)\s+LUFS",summary)
    peak = re.search(r"\bPeak:\s*([-+\w.]+)\s+dBFS",summary)
    if result.returncode or not loudness or not peak:
        raise ValueError(f"independent FFmpeg meter failed: {log_prefix}")
    integrated,true_peak = float(loudness[1]),float(peak[1])
    if not np.isfinite([integrated,true_peak]).all() or integrated <= -69.9:
        raise ValueError("loudness/true peak is nonfinite or below the meter gating floor")
    return {"integrated_lufs":integrated,"true_peak_dbtp":true_peak,
            "meter_log":str(log_prefix.with_suffix(".log")),"meter_log_sha256":sha256(log_prefix.with_suffix(".log")),
            "meter":"FFmpeg ebur128=peak=true; integrated EBU R128 and oversampled true peak"}


def write_pcm24(path, audio, fs):
    x = validate_pcm(audio)
    integers = np.rint(x*2**23).astype(np.int64)
    if np.min(integers) < -2**23 or np.max(integers) > 2**23-1:
        raise ValueError("PCM24 quantization would overflow; no clipping allowed")
    values = integers.reshape(-1)
    packed = ((values[:,None] >> np.array([0,8,16])) & 255).astype(np.uint8).tobytes()
    with wave.open(str(path),"wb") as wav:
        wav.setparams((2,3,fs,0,"NONE","not compressed")); wav.writeframes(packed)


def make_group(raw_items, fs, output_dir, target_lufs=-23, max_true_peak=-1.5):
    """Exactly one fixed scalar per original item, with a common peak-safe target."""
    if not raw_items or not np.isfinite([target_lufs,max_true_peak]).all():
        raise ValueError("invalid audition group")
    arrays = {name:validate_pcm(x) for name,x in raw_items.items()}
    if len({x.shape for x in arrays.values()}) != 1 or any(len(x)<2.5*fs for x in arrays.values()):
        raise ValueError("group inputs must align and be long enough for loudness")
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("audition group already exists; refuse overwrite")
    output_dir.mkdir(parents=True)
    raw_levels = {name:meter(x,fs,output_dir/"meter"/(name+"-raw")) for name,x in arrays.items()}
    # 0.15 dB margin accounts for the independent meter's 0.1 dB reporting resolution.
    target = min(float(target_lufs),*(max_true_peak-.15-row["true_peak_dbtp"]+row["integrated_lufs"]
                                      for row in raw_levels.values()))
    if not math.isfinite(target):
        raise ValueError("indeterminate common group target")
    result = {"target_lufs":target,"initial_target_lufs":target_lufs,"max_true_peak_dbtp":max_true_peak,
              "method":"one fixed scalar applied once to each RAW item; no limiter or AGC","items":{}}
    for name,x in arrays.items():
        if re.fullmatch(r"[A-Za-z0-9_-]+",name) is None:
            raise ValueError("invalid audition label")
        scalar = 10**((target-raw_levels[name]["integrated_lufs"])/20)
        path = output_dir/(name+".wav")
        write_pcm24(path,x*scalar,fs)
        decoded = read_pcm24(path,fs)
        if decoded.shape != x.shape or np.max(np.abs(decoded-x*scalar)) > 2**-23:
            raise ValueError("audition PCM24 differs from the declared one-scalar RAW transform")
        measured = meter(decoded,fs,output_dir/"meter"/(name+"-output"))
        if abs(measured["integrated_lufs"]-target) > .2 or measured["true_peak_dbtp"] > max_true_peak:
            raise ValueError("audition misses common loudness or true-peak gate; do not publish")
        result["items"][name] = {"path":str(path.resolve()),"sha256":sha256(path),"scalar":scalar,
                                 "gain_db":20*math.log10(scalar),"source_pcm_sha256":array_sha(x),
                                 "source_samples_per_channel":len(x),"raw_measurement":raw_levels[name],**measured}
    (output_dir/"group.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return result


def make_audition(run_root, contract_path, output_root):
    root,contract_path,output_root = (Path(x).resolve() for x in (run_root,contract_path,output_root))
    if not output_root.is_relative_to(contract_path.parent) or output_root.exists():
        raise ValueError("audition needs a new directory inside the approved new lab")
    if (root/"INVALIDATED.json").exists():
        raise ValueError("invalidated run")
    analysis_path = root/"analysis.json"
    analysis_sha = sha256(analysis_path)
    analysis = json.loads(analysis_path.read_text(encoding="utf-8-sig"))
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    if not analysis["pass"] or analysis["contract_sha256"] != sha256(contract_path):
        raise ValueError("numeric analysis must pass the frozen contract before audition")
    for entry in analysis["evidence"]:
        verify_hash(entry["path"],entry["sha256"])
    summary = json.loads((root/"run-summary.json").read_text(encoding="utf-8-sig"))
    def raw(record):
        path = Path(record["pcm_path"])
        verify_hash(path,record["pcm_sha256"])
        samples = path.stat().st_size//16
        if path.stat().st_size != samples*16:
            raise ValueError("unaligned RAW PCM bytes")
        return validate_pcm(np.memmap(path,dtype="<f8",mode="r",shape=(samples,2)))
    full = {name:raw(summary["cases"][name]) for name in MODES}
    historical = Evidence()
    old_root = Path(contract["reference"]["capture_mat"]).parent.parent
    old_summary_path = historical.bind(old_root/"run-summary.json")
    old_summary = json.loads(old_summary_path.read_text(encoding="utf-8-sig"))
    historical_record = old_summary["cases"]["C"]
    historical.bind(old_root/"C"/"candidate.wav",HISTORICAL_C_WAV_SHA)
    historical.bind(old_root/"C"/"receipt.json",historical_record["receipt_sha256"])
    historical.bind(historical_record["pcm_path"],historical_record["pcm_sha256"])
    prior_c = raw(historical_record)
    verify_pcm24(old_root/"C"/"candidate.wav",prior_c,48000)
    proof_path = historical.bind(contract_path.parent/"prior-C-native-proof.json")
    native_proof = json.loads(proof_path.read_text(encoding="utf-8-sig"))
    if (native_proof["status"] != "PASS_NATIVE_EXACT_B_C" or native_proof["shape"] != [4500,9]
            or native_proof["dtype"] != "float64-le" or native_proof["order"] != "row-major"
            or native_proof["native_C_controls_sha256"] != HISTORICAL_C_CONTROL_SHA):
        raise ValueError("historical C native control export proof is invalid")
    if (Path(native_proof["B_capture_mat"]).resolve() != Path(contract["reference"]["capture_mat"]).resolve()
            or Path(native_proof["C_capture_mat"]).resolve() != (old_root/"C"/"capture.mat").resolve()
            or native_proof["B_capture_sha256"] != contract["reference"]["capture_mat_sha256"]):
        raise ValueError("historical C native proof points to different original captures")
    for which in ("B","C"):
        historical.bind(native_proof[which+"_capture_mat"],native_proof[which+"_capture_sha256"])
    old_native = historical.bind(native_proof["native_C_controls"],HISTORICAL_C_CONTROL_SHA)
    expected = historical.bind(summary["reference_controls"]["path"],summary["reference_controls"]["sha256"])
    if old_native.stat().st_size != 4500*9*8 or expected.stat().st_size != 4500*9*8:
        raise ValueError("historical C native control byte count mismatch")
    old_controls = np.memmap(old_native,dtype="<f8",mode="r",shape=(4500,9))
    current_controls = np.memmap(expected,dtype="<f8",mode="r",shape=(4500,9))
    if not np.array_equal(old_controls,current_controls):
        raise ValueError("historical C native controls differ from the current exact B packets")
    full["C_rejected"] = prior_c
    groups = [("whole_tracks",full,{"start_s":0,"end_s":90})]
    for excerpt in contract["audition"]["excerpts"]:
        source = full
        if "anchor" in excerpt:
            entries = [x for x in summary["stationary"] if x["name"] == excerpt["anchor"]]
            if len(entries) != 1:
                raise ValueError("audition anchor absent or duplicated")
            source = {name:raw(entries[0]["cases"][name]) for name in MODES}
        first,end = (int(round(excerpt[k]*48000)) for k in ("start_s","end_s"))
        if first<0 or any(end>len(x) for x in source.values()):
            raise ValueError("audition excerpt outside original raw output")
        groups.append((excerpt["name"],{name:x[first:end] for name,x in source.items()},excerpt))
    output_root.mkdir(parents=True)
    rng = random.Random(20261029)
    manifest = {"schema":"s12.rumble_mechanics.audition.v1","analysis_path":str(analysis_path),
                "analysis_sha256":analysis_sha,"contract_sha256":sha256(contract_path),
                "qualification":"NUMERIC_RESEARCH_ONLY; Jovi human assessment pending","groups":{},
                "historical_reference":{"label":"C_rejected","status":"Previously rejected by Jovi; listening reference only",
                   "scope":"whole tracks and exact same-native-control driving excerpts; no matching historical idle anchor",
                   "native_proof_basis":"Parent MATLAB exact old B/C actualState comparison; independently checked exported Float64LE equality here",
                   "source_pcm_path":str(Path(historical_record["pcm_path"]).resolve()),
                   "source_wav_sha256":HISTORICAL_C_WAV_SHA,"evidence":historical.export()}}
    label_key = {}
    for index,(name,items,excerpt) in enumerate(groups,1):
        print(f"[{index}/{len(groups)}] matching audition group {name}",flush=True)
        group = make_group(items,48000,output_root/"named"/name,
                           contract["audition"]["initial_target_lufs"],contract["audition"]["max_true_peak_dbtp"])
        group["excerpt"] = excerpt
        blind_dir = output_root/"blinded"/name; blind_dir.mkdir(parents=True)
        labels = [*items,"B0","SR2"]; rng.shuffle(labels)
        mapping = []
        for slot,label in enumerate(labels,1):
            destination = blind_dir/f"clip_{slot:02d}.wav"
            shutil.copyfile(group["items"][label]["path"],destination)
            if sha256(destination) != group["items"][label]["sha256"]:
                raise ValueError("blinded audio differs from matched named original")
            mapping.append({"clip":destination.name,"mode":label,"sha256":sha256(destination),
                            "duplicate":labels[:slot-1].count(label)>0})
        label_key[name] = mapping
        group["blinded_paths"] = [str(p.resolve()) for p in sorted(blind_dir.glob("*.wav"))]
        manifest["groups"][name] = group
    verify_hash(analysis_path,analysis_sha)
    historical.recheck()
    for entry in analysis["evidence"]:
        verify_hash(entry["path"],entry["sha256"])
    key_path = output_root/"label-key.json"
    key_path.write_text(json.dumps(label_key,indent=2)+"\n",encoding="utf-8")
    manifest["label_key"] = {"path":str(key_path),"sha256":sha256(key_path)}
    (output_root/"audition.json").write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (output_root/"LISTENING.md").write_text(
        "# Jovi listening assessment\n\nPlay clips within the same group at unchanged playback volume. "
        "Whole tracks and every fixed excerpt each have their own common loudness target. "
        "Two hidden duplicates per group check repeatability. Keep label-key.json hidden until rating.\n\n"
        "Rate each clip separately: low-frequency rumble; mechanical texture; whine; shift clarity; overall preference. "
        "Report preferred clip labels and any fatigue, clicks, or roughness. Numeric gates do not establish vehicle authenticity or human acceptance.\n",
        encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root",required=True); parser.add_argument("--contract",required=True)
    parser.add_argument("--output-root",required=True)
    args = parser.parse_args()
    make_audition(args.run_root,args.contract,args.output_root)


if __name__ == "__main__":
    main()
