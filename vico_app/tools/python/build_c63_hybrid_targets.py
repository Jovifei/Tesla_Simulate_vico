"""Offline C63 targets and a causal kernel from minimum-phase spectral design."""
from pathlib import Path
import argparse
import hashlib
import json
import math

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import welch

from build_c63_audible_targets import read_clip, validate_windows
from extract_c63_ar2_events import extract as extract_afterfire_reference


RATE = 48000
FRAME_SAMPLES = 240
ENVELOPE_RATE = RATE // FRAME_SAMPLES
KERNEL_LENGTH = 2048
KERNEL_FFT_LENGTH = 65536
CONTROL_HZ = np.geomspace(200.0, 6300.0, 8)
SPECTRAL_EDGES_HZ = np.geomspace(200.0, 6300.0, 9)
SPECTRAL_KEYS = tuple(f"spec{i}" for i in range(8))
MODULATION_BANDS_HZ = ((1.0, 5.0), (5.0, 15.0), (15.0, 40.0), (40.0, 80.0))
MODULATION_KEYS = tuple(f"mod{i}" for i in range(4))
FEATURE_KEYS = SPECTRAL_KEYS + MODULATION_KEYS + ("env_cv",)
WEIGHTS = {
    **{key: 0.50 / len(SPECTRAL_KEYS) for key in SPECTRAL_KEYS},
    **{key: 0.35 / len(MODULATION_KEYS) for key in MODULATION_KEYS},
    "env_cv": 0.15,
}
CLIP_SPECS = {
    "ref_steady_low.wav": ((0.0, 3.0, "calibration"), (3.0, 6.0, "holdout")),
    "ref_steady_mid.wav": ((0.0, 3.0, "calibration"), (3.0, 6.0, "holdout")),
    "ref_full_pull.wav": ((0.0, 3.0, "calibration"), (3.0, 5.0, "holdout")),
    "ref_steady_high.wav": ((1.0, 3.5, "calibration"), (3.5, 6.0, "holdout")),
    "ref_hot_idle.wav": ((0.0, 6.0, "context"),),
    "ref_afterfire.wav": ((0.0, 3.0, "calibration"), (3.0, 6.0, "holdout")),
    "ref_shift.wav": ((0.0, 6.0, "context"),),
}
SUSTAINED_EXCLUSIONS = frozenset(("ref_afterfire.wav", "ref_shift.wav"))


def minimum_phase_kernel(levels_db):
    """Create a 2048-tap causal kernel using a minimum-phase design step.

    Eight dB controls lie at geometric centers from 200 to 6300 Hz. Their
    log-frequency envelope is smoothed over 0.9 control spacings before a
    real-cepstrum minimum-phase transform. Fixed fourth-order 200 Hz high-pass
    and 6300 Hz low-pass factors bound the design representation. A cosine
    tail taper and smooth low-frequency-localized DC correction follow
    truncation. The delivered coefficients are causal, finite, zero-DC, and
    unit-energy; they are not claimed to be strictly minimum-phase or stably
    invertible. No inverse filtering is used.
    """
    try:
        controls = np.asarray(levels_db, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("levels_db must contain exactly eight finite values") from exc
    if controls.shape != (8,) or not np.isfinite(controls).all():
        raise ValueError("levels_db must contain exactly eight finite values")

    smooth_controls = gaussian_filter1d(controls, sigma=0.9, mode="nearest")
    freqs = np.fft.rfftfreq(KERNEL_FFT_LENGTH, d=1.0 / RATE)
    safe_freqs = np.maximum(freqs, CONTROL_HZ[0])
    envelope_db = np.interp(
        np.log(safe_freqs), np.log(CONTROL_HZ), smooth_controls,
        left=float(smooth_controls[0]), right=float(smooth_controls[-1]),
    )
    # A common offset has no effect after unit-energy normalization. Clipping
    # only the relative range avoids floating overflow for extreme finite input.
    relative_db = np.clip(envelope_db - float(np.max(envelope_db)), -120.0, 0.0)
    ratio_low = freqs / 200.0
    ratio_high = freqs / 6300.0
    highpass = ratio_low ** 4 / np.sqrt(1.0 + ratio_low ** 8)
    lowpass = 1.0 / np.sqrt(1.0 + ratio_high ** 8)
    boundary_magnitude = np.maximum(highpass * lowpass, 1e-12)
    log_magnitude = (
        relative_db * (math.log(10.0) / 20.0) + np.log(boundary_magnitude)
    )

    cepstrum = np.fft.irfft(log_magnitude, n=KERNEL_FFT_LENGTH)
    minimum_phase_cepstrum = np.zeros_like(cepstrum)
    minimum_phase_cepstrum[0] = cepstrum[0]
    minimum_phase_cepstrum[1:KERNEL_FFT_LENGTH // 2] = (
        2.0 * cepstrum[1:KERNEL_FFT_LENGTH // 2]
    )
    minimum_phase_cepstrum[KERNEL_FFT_LENGTH // 2] = cepstrum[KERNEL_FFT_LENGTH // 2]
    minimum_phase_spectrum = np.exp(
        np.fft.rfft(minimum_phase_cepstrum, n=KERNEL_FFT_LENGTH)
    )
    kernel = np.fft.irfft(minimum_phase_spectrum, n=KERNEL_FFT_LENGTH)[:KERNEL_LENGTH].copy()

    taper_start = KERNEL_LENGTH * 3 // 4
    taper_phase = np.linspace(0.0, 1.0, KERNEL_LENGTH - taper_start)
    taper = np.ones(KERNEL_LENGTH, dtype=np.float64)
    taper[taper_start:] = 0.5 * (1.0 + np.cos(np.pi * taper_phase))
    kernel *= taper

    correction_start = KERNEL_LENGTH // 2
    correction_phase = np.linspace(0.0, 1.0, KERNEL_LENGTH - correction_start)
    correction = np.zeros(KERNEL_LENGTH, dtype=np.float64)
    correction[correction_start:] = np.sin(np.pi * correction_phase) ** 2
    correction_sum = float(correction.sum())
    if correction_sum <= 0.0:
        raise ValueError("Unable to construct a zero-DC kernel")
    correction /= correction_sum
    # The smooth late-tail correction concentrates its spectral effect at low frequencies.
    kernel -= float(kernel.sum()) * correction
    kernel[-1] = 0.0

    energy = float(np.linalg.norm(kernel))
    if not math.isfinite(energy) or energy <= 1e-15:
        raise ValueError("Kernel controls produced a degenerate response")
    kernel /= energy
    kernel -= float(kernel.sum()) * correction
    kernel[-1] = 0.0
    energy = float(np.linalg.norm(kernel))
    if not math.isfinite(energy) or energy <= 1e-15:
        raise ValueError("Kernel controls produced a degenerate response")
    kernel /= energy
    kernel[-1] = 0.0
    if not np.isfinite(kernel).all():
        raise ValueError("Kernel construction produced nonfinite samples")
    return kernel


def features(pcm):
    """Return gain-invariant spectral/modulation shape and separate level data.

    PCM is interpreted as mono float or integer sample values at 48 kHz. At
    least 24000 samples are required. Spectral bands use Welch PSD, an 8192
    sample Hann window, 6144 sample overlap, and half-open geometric bands
    spanning 200-6300 Hz. Values are dB shares of the total power in that span,
    floored at -160 dB.

    The envelope is nonoverlapping 5 ms block RMS, divided by its own mean.
    Modulation uses a Welch PSD at 200 Hz with half-window overlap and bands
    [1,5), [5,15), [15,40), and [40,80) Hz; values are dB shares of 1-80 Hz
    envelope power, also floored at -160 dB. ``rms`` and ``absolute_band_power``
    are measured from the unnormalized input; no PCM samples are modified.
    Absolute band powers are mean-square power integrated from Welch PSD using
    half-open bands [20,200), [200,4000), and [4000,12000) Hz.
    """
    x = np.asarray(pcm, dtype=np.float64)
    if x.ndim != 1 or len(x) < RATE // 2 or not np.isfinite(x).all():
        raise ValueError("Expected finite mono 48 kHz PCM with at least 24000 samples")
    rms = float(np.sqrt(np.mean(x * x)))
    if not math.isfinite(rms) or rms <= 1e-10:
        raise ValueError("Silent input has no acoustic features")

    normalized = x / rms
    nperseg = 8192
    overlap = 6144
    freqs, normalized_psd = welch(
        normalized, fs=RATE, window="hann", nperseg=nperseg,
        noverlap=overlap, detrend=False, scaling="density",
    )
    _, absolute_psd = welch(
        x, fs=RATE, window="hann", nperseg=nperseg,
        noverlap=overlap, detrend=False, scaling="density",
    )
    df = RATE / nperseg

    spectral_powers = []
    for index, (lo, hi) in enumerate(zip(SPECTRAL_EDGES_HZ[:-1], SPECTRAL_EDGES_HZ[1:])):
        upper = freqs <= hi if index == len(SPECTRAL_KEYS) - 1 else freqs < hi
        selected = (freqs >= lo) & upper
        spectral_powers.append(float(np.sum(normalized_psd[selected]) * df))
    spectral_total = float(sum(spectral_powers))
    if not math.isfinite(spectral_total):
        raise ValueError("Nonfinite spectral feature power")
    result = {
        key: float(10.0 * np.log10(max(power / max(spectral_total, 1e-30), 1e-16)))
        for key, power in zip(SPECTRAL_KEYS, spectral_powers)
    }

    frame_count = len(x) // FRAME_SAMPLES
    frames = x[:frame_count * FRAME_SAMPLES].reshape(frame_count, FRAME_SAMPLES)
    envelope = np.sqrt(np.mean(frames * frames, axis=1))
    envelope_mean = float(envelope.mean())
    if not math.isfinite(envelope_mean) or envelope_mean <= 1e-12:
        raise ValueError("Envelope has no usable mean level")
    normalized_envelope = envelope / envelope_mean
    result["env_cv"] = float(normalized_envelope.std())

    mod_nperseg = min(len(normalized_envelope), 512)
    mod_freqs, mod_psd = welch(
        normalized_envelope - 1.0, fs=ENVELOPE_RATE, window="hann",
        nperseg=mod_nperseg, noverlap=mod_nperseg // 2,
        detrend=False, scaling="density",
    )
    mod_df = ENVELOPE_RATE / mod_nperseg
    band_powers = [
        float(np.sum(mod_psd[(mod_freqs >= lo) & (mod_freqs < hi)]) * mod_df)
        for lo, hi in MODULATION_BANDS_HZ
    ]
    mod_total = float(sum(band_powers))
    for key, power in zip(MODULATION_KEYS, band_powers):
        result[key] = float(10.0 * np.log10(max(power / max(mod_total, 1e-30), 1e-16)))

    absolute_band_power = []
    for lo, hi in ((20.0, 200.0), (200.0, 4000.0), (4000.0, 12000.0)):
        selected = (freqs >= lo) & (freqs < hi)
        absolute_band_power.append(float(np.sum(absolute_psd[selected]) * df))
    result["rms"] = rms
    result["absolute_band_power"] = absolute_band_power
    if not all(math.isfinite(result[key]) for key in FEATURE_KEYS):
        raise ValueError("Feature calculation produced nonfinite values")
    return result


def _provenance_group(meta):
    values = (
        meta.get("source_id", "UNSPECIFIED_SOURCE"),
        meta.get("evidence_level", "UNSPECIFIED_EVIDENCE"),
        meta.get("rights_status", "UNSPECIFIED_RIGHTS"),
    )
    return "|".join(str(value) for value in values)


def _feature_distributions(rows):
    collected = {}
    for row in rows:
        split_group = collected.setdefault(row["split"], {}).setdefault(
            row["provenance_group"], {key: [] for key in FEATURE_KEYS}
        )
        for key in FEATURE_KEYS:
            split_group[key].append(float(row["features"][key]))

    distributions = {}
    for split, groups in collected.items():
        distributions[split] = {}
        for provenance_group, values_by_key in groups.items():
            distributions[split][provenance_group] = {
                "count": len(next(iter(values_by_key.values()))),
                "features": {
                    key: {
                        "mean": float(np.mean(values)),
                        "std": float(np.std(values)),
                        "min": float(np.min(values)),
                        "max": float(np.max(values)),
                    }
                    for key, values in values_by_key.items()
                },
            }
    return distributions


def build(bundle):
    bundle = Path(bundle)
    receipt_path = bundle / "reference_clip_receipt.json"
    receipt_bytes = receipt_path.read_bytes()
    try:
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid UTF-8 reference clip receipt") from exc
    clips = receipt["clips"]
    rows = []
    identity_clips = {}

    for filename, ranges in CLIP_SPECS.items():
        meta = clips[filename]
        pcm = read_clip(bundle / filename, meta["sha256"])
        source_start = meta["start_sample"]
        identity_clips[filename] = {
            "clip_sha256": meta["sha256"],
            "source_sha256": meta["source_sha256"],
            "source_id": meta["source_id"],
            "evidence_level": meta.get("evidence_level", "UNSPECIFIED"),
            "rights_status": meta.get("rights_status", "UNSPECIFIED"),
            "source_start_sample": source_start,
            "source_end_sample": source_start + 6 * RATE,
        }
        provenance_group = _provenance_group(meta)
        for lo, hi, split in ranges:
            start = round(lo * RATE)
            end = round(hi * RATE)
            rows.append({
                "id": f"{filename}:{lo:g}-{hi:g}",
                "filename": filename,
                "clip_sha256": meta["sha256"],
                "source_sha256": meta["source_sha256"],
                "source_id": meta["source_id"],
                "evidence_level": meta.get("evidence_level", "UNSPECIFIED"),
                "rights_status": meta.get("rights_status", "UNSPECIFIED"),
                "provenance_group": provenance_group,
                "split": split,
                "start_sample": source_start + start,
                "end_sample": source_start + end,
                "clip_offset_start": start,
                "clip_offset_end": end,
                "features": features(pcm[start:end]),
                "quality_note": (
                    "EXCLUDED_IDLE_LABEL_SILENT_TAIL_CONTEXT"
                    if filename == "ref_hot_idle.wav"
                    else "RELATIVE_UNSYNCHRONIZED_R2_RIGHTS_UNVERIFIED_REFERENCE"
                ),
            })

    validate_windows(rows)
    sustained = [
        row for row in rows
        if row["split"] == "calibration" and row["filename"] not in SUSTAINED_EXCLUSIONS
    ]
    if not sustained:
        raise ValueError("No sustained calibration references remain")
    calibration_scales = {
        key: max(
            float(np.std([row["features"][key] for row in sustained])),
            0.05 if key == "env_cv" else 1.0,
        )
        for key in FEATURE_KEYS
    }

    return {
        "schema": "c63.hy1.hybrid_targets.v1",
        "scope": "R2_RIGHTS_UNVERIFIED_RESEARCH_ONLY",
        "rpm_load_assignment": "NONE_UNLABELED_REFERENCE_FEATURES_ONLY",
        "reference_identity": {
            "manifest_schema": "c63.hy1.reference_identity.v1",
            "receipt_filename": receipt_path.name,
            "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
            "clips": identity_clips,
        },
        "windows": rows,
        "feature_keys": list(FEATURE_KEYS),
        "distribution_feature_keys": list(FEATURE_KEYS),
        "feature_distributions": _feature_distributions(rows),
        "sustained_window_ids": [row["id"] for row in sustained],
        "calibration_scales": calibration_scales,
        "weights": WEIGHTS,
        "sustained_excluded_files": sorted(SUSTAINED_EXCLUSIONS),
        "afterfire_reference": extract_afterfire_reference(bundle),
        "afterfire_support": "UNLABELED_CENSORED_LOCAL_TRANSIENTS",
        "idle_reference_support": "CONTEXT_ONLY_SILENT_TAIL_NOT_CALIBRATION",
        "source_split_boundary": "SAME_SOURCE_TIME_HOLDOUT_NOT_CROSS_VEHICLE_VALIDATION",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise FileExistsError(args.out)
    result = build(args.bundle)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(
        "Built", len(result["windows"]), "non-overlapping windows; outputSHA",
        hashlib.sha256(args.out.read_bytes()).hexdigest(),
    )
    return result


if __name__ == "__main__":
    main()
