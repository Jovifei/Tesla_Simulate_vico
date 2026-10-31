"""Make fixed-scalar, named and blinded research copies directly from raw PCM."""
import argparse
import json
import math
import secrets
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

import analyze_cabin_candidate as analysis

LAB = Path(__file__).resolve().parent
FS = 48000


def scalar(lufs, target):
    return 10 ** ((target - lufs) / 20)


def safe_target(items):
    target = -23.0
    for item in items:
        if not all(math.isfinite(item[key]) for key in ("lufs", "true_peak_dbtp", "peak")) or item["peak"] <= 0:
            raise ValueError("nonfinite or silent source cannot be loudness matched")
        target = min(target, item["lufs"] - 1.5 - item["true_peak_dbtp"])
        target = min(target, item["lufs"] + 20 * math.log10(1 / item["peak"]))
    return target


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def build_group(root, output, name, windows):
    group = output / name
    (group / "raw-measurements").mkdir(parents=True, exist_ok=False)
    (group / "named").mkdir()
    (group / "blind").mkdir()
    raw, metadata = {}, {}
    for label, (case, start, end) in windows.items():
        path = root / case / "candidate.pcm.f64le"
        receipt = json.loads((root / case / "receipt.json").read_text(encoding="utf-8"))
        if analysis.digest(path) != receipt["pcm_sha256"]:
            raise ValueError(f"{case}: raw PCM hash differs")
        samples = analysis.read_pcm(path)
        last = len(samples) if end is None else round(end * FS)
        first = round(start * FS)
        if first < 0 or last > len(samples) or last <= first:
            raise ValueError(f"{name}/{label}: invalid excerpt")
        raw[label] = samples[first:last].copy()
        probe = group / "raw-measurements" / f"{label}.wav"
        sf.write(probe, raw[label], FS, subtype="PCM_24")
        item = analysis.measure_loudness(probe, group / "raw-measurements" / f"{label}.log")
        item.update({"peak": float(np.max(np.abs(raw[label]))), "source_pcm_sha256": receipt["pcm_sha256"],
                     "source_case": case, "start_s": start, "end_s": end})
        metadata[label] = item
    target = safe_target(metadata.values())
    # Leave room for FFmpeg's 0.1 dB true-peak reporting precision.
    if any(item["true_peak_dbtp"] + target - item["lufs"] > -1.7 for item in metadata.values()):
        target -= 0.2
    for label, item in metadata.items():
        factor = scalar(item["lufs"], target)
        scaled = raw[label] * factor
        if not np.isfinite(scaled).all() or np.max(np.abs(scaled)) > 1:
            raise ValueError(f"{name}/{label}: scalar would clip")
        destination = group / "named" / f"{label}.wav"
        sf.write(destination, scaled, FS, subtype="PCM_24")
        measured = analysis.measure_loudness(destination, group / "named" / f"{label}.log")
        if abs(measured["lufs"] - target) > 0.2 or measured["true_peak_dbtp"] > -1.5:
            raise ValueError(f"{name}/{label}: matched copy failed loudness or true-peak gate")
        item.update({"scalar": factor, "target_lufs": target, "measured": measured,
                     "wav_sha256": analysis.digest(destination), "matched_bands": analysis.band_powers(scaled)})
    blind = list(metadata)
    blind.append("MD" if "MD" in metadata else blind[0])  # An undisclosed repeated item.
    secrets.SystemRandom().shuffle(blind)
    key = {}
    for index, label in enumerate(blind, 1):
        code = f"{index:02d}"
        shutil.copyfile(group / "named" / f"{label}.wav", group / "blind" / f"{code}.wav")
        key[code] = label
    write_json(group / "named" / "manifest.json", {"target_lufs": target, "items": metadata})
    write_json(group / "blind" / "manifest.json", {"target_lufs": target, "items": list(key)})
    write_json(group / "blind-key.json", key)
    return {"target_lufs": target, "items": len(metadata), "blind_items": len(key)}


def build(run_root):
    root = Path(run_root).resolve()
    if not root.is_relative_to(LAB.resolve()) or not (root / "full.json").is_file() or not (root / "cold.json").is_file():
        raise ValueError("completed full and new-process cold receipts are required")
    cold = json.loads((root / "cold.json").read_text(encoding="utf-8"))
    if cold.get("md_cold") != "PASS_NEW_PROCESS":
        raise ValueError("the MD cold repeat has not passed in a new process")
    if not (root / "independent-analysis" / "analysis.json").is_file():
        raise ValueError("independent raw PCM/WAV analysis is required")
    contract = json.loads((LAB.parent / "app8-rumble-mechanics-candidate-20261029" /
                           "EXPERIMENT_CONTRACT.json").read_text(encoding="utf-8"))
    output = root / "audition-approved"
    output.mkdir(exist_ok=False)
    labels = ("B0", "N", "M", "D", "MD", "MD-repeat", "MD-cold")
    groups = {"whole_tracks": {label: (label, 0, None) for label in labels}}
    for excerpt in contract["audition"]["excerpts"]:
        name = excerpt["name"]
        if name == "idle":
            groups[name] = {label: (f"anchor-idle-{label}", excerpt["start_s"], excerpt["end_s"])
                            for label in labels[:5]}
        else:
            groups[name] = {label: (label, excerpt["start_s"], excerpt["end_s"]) for label in labels}
    result = {"qualification": "PREVIEW_ONLY_HUMAN_DEVICE_AND_VEHICLE_PENDING", "groups": {}}
    for index, (name, windows) in enumerate(groups.items(), 1):
        print(f"AUDITION [{index}/{len(groups)}] {name}", flush=True)
        result["groups"][name] = build_group(root, output, name, windows)
    write_json(output / "audition.json", result)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    print(build(parser.parse_args().run_root))
