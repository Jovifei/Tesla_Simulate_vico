"""Verify V2's three fixed-gain replayable outputs against raw Simulink PCM."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import soundfile as sf


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main(root, prior_path):
    root = Path(root)
    receipt_path = root / "receipt.json"
    current = json.loads(receipt_path.read_text(encoding="utf-8"))
    prior = json.loads(Path(prior_path).read_text(encoding="utf-8"))
    conditions = []
    for item, previous in zip(current["conditions"], prior["conditions"], strict=True):
        if (item["rpm"], item["load"]) != (previous["rpm"], previous["load"]):
            raise ValueError("Condition mismatch")
        for key in ("input_sha256", "source_sha256", "frozen_sha256", "combined_sha256", "wav_sha256"):
            if item[key] != previous[key]:
                raise ValueError(f"V2 relocation changed {key} at {item['rpm']} RPM")
        results = {"rpm": item["rpm"], "load": item["load"], "stems": {}}
        for source, name, factor in (("source", "source", 0.1),
                                     ("frozen", "frozen_cabin", 0.1),
                                     ("combined", "combined", 1.0)):
            raw = Path(item[f"{source}_path"])
            f32 = Path(item[f"{name}_rendered_f32_path"])
            wav = Path(item["wav_path"] if name == "combined" else item[f"{name}_wav_path"])
            expected_wav = item["wav_sha256"] if name == "combined" else item[f"{name}_wav_sha256"]
            if digest(raw) != item[f"{source}_sha256"] or digest(f32) != item[f"{name}_rendered_f32_sha256"] or digest(wav) != expected_wav:
                raise ValueError(f"Hash mismatch in {name}")
            expected = np.fromfile(raw, dtype="<f8") * factor
            rendered = np.fromfile(f32, dtype="<f4")
            info = sf.info(wav)
            pcm, sample_rate = sf.read(wav, dtype="float64")
            if (len(expected) != 144000 or sample_rate != 48000 or info.channels != 1
                    or info.subtype != "PCM_24" or not np.array_equal(rendered, expected.astype("<f4"))
                    or np.max(np.abs(pcm - expected)) > 2**-23 + np.finfo(float).eps
                    or np.any(np.abs(expected) >= 1)):
                raise ValueError(f"Rendered stem differs or clips: {wav}")
            results["stems"][name] = {
                "wav_sha256": expected_wav,
                "rendered_f32_sha256": item[f"{name}_rendered_f32_sha256"],
                "renderer_scalar": 0.1,
                "sample_peak": float(np.max(np.abs(expected))),
                "clip_count": int(np.count_nonzero(np.abs(expected) >= 1)),
            }
        conditions.append(results)
    result = {
        "status": "PASS_RENDERED_STEMS_AND_RELOCATION",
        "qualification": "SYNTHETIC_DIAGNOSTIC_NO_ACOUSTIC_ACCEPTANCE",
        "current_receipt_sha256": digest(receipt_path),
        "prior_receipt_sha256": digest(Path(prior_path)),
        "sample_rate_hz": 48000,
        "channels": 1,
        "wav_subtype": "PCM_24",
        "combined_semantics": "0.5 * (source renderer output + Frozen renderer output)",
        "conditions": conditions,
    }
    destination = root / "rendered-stems-verification.json"
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"RENDERED_STEMS_PASS {destination}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_rendered_stems.py ABSOLUTE_V2_ROOT ABSOLUTE_PRIOR_RECEIPT")
    main(sys.argv[1], sys.argv[2])
