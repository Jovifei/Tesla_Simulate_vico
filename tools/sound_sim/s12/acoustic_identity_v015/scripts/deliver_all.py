"""S12 Acoustic Realism - unified re-render of all 8 vehicles.

Regenerates, for every vehicle, the audition artifacts under docs/:
  - <vid>_spectrogram.png  (idle + acceleration, 0-8 kHz, full acoustic chain)
  - <vid>_ab.wav           (idle 3s + 0.25s gap + acceleration 3s, 24-bit)

This is the Stage A "unified re-render" so every artifact reflects the final
source state after the coarse-pass tuning campaign. Per-vehicle band/centroid
metrics are produced by verify_remaining_vehicles.py (the canonical gate).

Boundary: synthetic; uncalibrated; not OEM reproduction.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import wave
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_S12 = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_S12))

from acoustic_identity_v015.scripts.verify_remaining_vehicles import (
    NEW_VEHICLES, _scenario_trace, _render_stateful, _SAMPLE_RATE_HZ,
)

DOC_DIR = Path(__file__).resolve().parent.parent / "docs"
CLIP_SECONDS = 3.0
SR = _SAMPLE_RATE_HZ


def render_clip(vid, clip):
    trace = _scenario_trace(vid, clip, CLIP_SECONDS)
    return _render_stateful(NEW_VEHICLES[vid], vid, trace).pressure


def stft_mag(sig_mono, sr, nfft=2048, hop=512):
    win = np.hanning(nfft)
    frames = []
    for s in range(0, len(sig_mono) - nfft, hop):
        seg = sig_mono[s:s + nfft] * win
        frames.append(np.abs(np.fft.rfft(seg)) ** 2)
    S = np.array(frames).T
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
    return S, freqs


def plot_clip(ax, audio, title):
    mono = audio.mean(axis=1)
    S, freqs = stft_mag(mono, SR)
    fmask = freqs <= 8000.0
    S = S[fmask]; freqs = freqs[fmask]
    Sdb = 10.0 * np.log10(S + 1e-12)
    vmin, vmax = Sdb.max() - 70.0, Sdb.max()
    t = np.arange(S.shape[1]) * 512 / SR
    ax.pcolormesh(t, freqs, Sdb, shading="auto", cmap="magma", vmin=vmin, vmax=vmax)
    ax.set_ylim(20, 8000)
    ax.set_yscale("symlog", linthresh=100)
    ax.set_yticks([100, 250, 500, 1000, 2000, 4000, 8000])
    ax.set_yticklabels(["100", "250", "500", "1k", "2k", "4k", "8k"])
    ax.set_ylabel("Hz")
    ax.set_title(title)


def write_wav_24(path, signal_stereo, sr):
    sig = np.asarray(signal_stereo, dtype=np.float64)
    peak = float(np.max(np.abs(sig))) or 1.0
    sig = sig / peak * 0.9
    pcm = np.clip(sig * (1 << 23), -(1 << 23), (1 << 23) - 1).astype("<i4")
    raw = np.empty((pcm.size, 3), dtype=np.uint8)
    rv = pcm.view(np.uint8).reshape(pcm.size, 4)
    raw[:, 0] = rv[:, 0]; raw[:, 1] = rv[:, 1]; raw[:, 2] = rv[:, 2]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(3); w.setframerate(sr)
        w.writeframes(raw.tobytes())


def main() -> None:
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    for vid, _renderer in NEW_VEHICLES.items():
        print(f"\n=== {vid} ===")
        idle = render_clip(vid, "idle")
        accel = render_clip(vid, "acceleration")
        peak = max(float(np.max(np.abs(idle))), float(np.max(np.abs(accel))))
        print(f"  peak |sample| = {peak:.4f}  (clip gate: must stay <= 0.89125)")

        fig, axs = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
        plot_clip(axs[0], idle, f"{vid} - idle (3s, full acoustic chain)")
        plot_clip(axs[1], accel, f"{vid} - acceleration (3s, full acoustic chain)")
        axs[1].set_xlabel("time (s)")
        fig.colorbar(axs[1].collections[0], ax=axs, label="dB (power)")
        fig.suptitle(f"{vid} - synthetic acoustic spectrogram (0-8 kHz)", fontsize=11)
        fig.tight_layout()
        fig.savefig(DOC_DIR / f"{vid}_spectrogram.png", dpi=140)
        plt.close(fig)
        print(f"  spectrogram -> docs/{vid}_spectrogram.png")

        gap = np.zeros((int(0.25 * SR), 2), dtype=np.float64)
        ab = np.concatenate([idle, gap, accel], axis=0)
        write_wav_24(DOC_DIR / f"{vid}_ab.wav", ab, SR)
        print(f"  AB wav -> docs/{vid}_ab.wav  ({ab.shape[0]/SR:.1f}s)")


if __name__ == "__main__":
    main()
