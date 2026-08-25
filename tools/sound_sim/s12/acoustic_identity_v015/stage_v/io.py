"""Fail-closed PCM24 WAV publication and reopen receipts for Stage V."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any
import wave

import numpy as np


@dataclass(frozen=True)
class WavWriteReceipt:
    path: str
    sha256: str
    reopened_audio: np.ndarray
    metadata: dict[str, Any]


def _validate_audio(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] == 0:
        raise ValueError("Stage-V WAV audio must be nonempty stereo")
    if not np.all(np.isfinite(values)):
        raise ValueError("Stage-V WAV audio must be finite")
    if np.any(np.abs(values) >= 1.0):
        raise ValueError("Stage-V WAV audio would clip")
    return values


def _pack_pcm24(audio: np.ndarray) -> bytes:
    values = _validate_audio(audio)
    integers = np.rint(values * (1 << 23)).astype(np.int32).reshape(-1)
    packed = np.empty((integers.size, 3), dtype=np.uint8)
    packed[:, 0] = integers & 0xFF
    packed[:, 1] = (integers >> 8) & 0xFF
    packed[:, 2] = (integers >> 16) & 0xFF
    return packed.tobytes()


def _unpack_pcm24(raw: bytes, channels: int) -> np.ndarray:
    if channels != 2 or len(raw) % (channels * 3) != 0:
        raise ValueError("Stage-V WAV must contain complete stereo PCM24 frames")
    packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
    integers = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
    integers = np.where((integers & 0x800000) != 0, integers - (1 << 24), integers)
    return (integers.astype(np.float64) / (1 << 23)).reshape(-1, channels)


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_pcm24_wav(path: str | Path) -> tuple[np.ndarray, dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        sample_width = stream.getsampwidth()
        sample_rate_hz = stream.getframerate()
        frames = stream.getnframes()
        if stream.getcomptype() != "NONE":
            raise ValueError("compressed WAV is not allowed")
        raw = stream.readframes(frames)
    if sample_width != 3 or sample_rate_hz <= 0:
        raise ValueError("Stage-V WAV must be PCM24 with a positive sample rate")
    audio = _unpack_pcm24(raw, channels)
    if audio.shape[0] != frames or not np.all(np.isfinite(audio)):
        raise ValueError("Stage-V WAV frame count or finite-value check failed")
    metadata = {
        "channels": channels,
        "sample_width_bits": sample_width * 8,
        "sample_rate_hz": sample_rate_hz,
        "frames": int(frames),
        "clipping": int(np.count_nonzero(np.abs(audio) >= 1.0)),
        "sha256": sha256_file(path),
    }
    return audio, metadata


def write_pcm24_wav(path: str | Path, audio: np.ndarray, sample_rate_hz: int) -> WavWriteReceipt:
    values = _validate_audio(audio)
    if int(sample_rate_hz) <= 0:
        raise ValueError("sample_rate_hz must be positive")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _pack_pcm24(values)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(int(sample_rate_hz))
        stream.writeframes(raw)
    reopened, metadata = read_pcm24_wav(path)
    if reopened.shape != values.shape:
        raise ValueError("WAV reopen changed frame shape")
    return WavWriteReceipt(str(path), metadata["sha256"], reopened, metadata)


def write_json(path: str | Path, payload: object) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return path


__all__ = ["WavWriteReceipt", "read_pcm24_wav", "sha256_file", "write_json", "write_pcm24_wav"]
