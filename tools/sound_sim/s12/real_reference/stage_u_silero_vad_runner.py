"""Pinned-environment Silero VAD runner used by Stage U reference gates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read PCM WAV without torchaudio's optional TorchCodec backend."""

    sample_rate_hz, raw = wavfile.read(str(path))
    values = np.asarray(raw)
    if np.issubdtype(values.dtype, np.integer):
        info = np.iinfo(values.dtype)
        values = values.astype(np.float32) / float(max(abs(info.min), info.max))
    else:
        values = values.astype(np.float32)
    mono = values.mean(axis=1) if values.ndim > 1 else values
    if mono.size == 0 or sample_rate_hz <= 0 or not np.isfinite(mono).all():
        raise ValueError("audio must be finite, non-empty WAV")
    return np.asarray(mono, dtype=np.float32), int(sample_rate_hz)


def run(audio_path: Path) -> list[dict[str, float]]:
    try:
        import torch
        import torchaudio
        from silero_vad import get_speech_timestamps, load_silero_vad
    except ImportError as exc:
        raise RuntimeError(f"Silero VAD dependencies are unavailable: {exc}") from exc
    samples, sample_rate_hz = _load_wav(audio_path)
    mono = torch.from_numpy(samples)
    if int(sample_rate_hz) != 16_000:
        mono = torchaudio.functional.resample(mono, int(sample_rate_hz), 16_000)
        sample_rate_hz = 16_000
    model = load_silero_vad(onnx=True)
    intervals = get_speech_timestamps(mono.to(torch.float32), model, sampling_rate=int(sample_rate_hz), return_seconds=True)
    return [{"start_s": float(row["start"]), "end_s": float(row["end"])} for row in intervals]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Silero VAD and return seconds JSON")
    parser.add_argument("--audio", type=Path, required=True)
    arguments = parser.parse_args(argv)
    print(json.dumps(run(arguments.audio), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
