"""Final-PCM reference-distance helpers for Stage F."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

BANDS = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))


def band_distance(actual: Sequence[float], target: Sequence[float]) -> float:
    actual_array = np.asarray(actual, dtype=np.float64); target_array = np.asarray(target, dtype=np.float64)
    if actual_array.shape != (4,) or target_array.shape != (4,) or not np.all(np.isfinite(actual_array)) or not np.all(np.isfinite(target_array)):
        raise ValueError("band distance requires four finite band shares")
    return float(math.sqrt(0.25 * np.sum(np.square(actual_array - target_array))))


def final_pcm_band_shares(audio: np.ndarray, sample_rate_hz: int = 48000) -> tuple[float, float, float, float]:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.ndim == 2:
        samples = np.mean(samples, axis=1)
    if samples.ndim != 1 or samples.size == 0 or not np.all(np.isfinite(samples)):
        raise ValueError("final PCM must be finite mono or stereo audio")
    spectrum = np.square(np.abs(np.fft.rfft(samples * np.hanning(samples.size))))
    frequencies = np.fft.rfftfreq(samples.size, 1.0 / sample_rate_hz)
    energy = np.asarray([float(np.sum(spectrum[(frequencies >= lo) & (frequencies < hi)])) for lo, hi in BANDS])
    total = float(np.sum(energy))
    return tuple((energy / total).tolist()) if total > 0.0 else (0.0, 0.0, 0.0, 0.0)


def compare_final_pcm(target: Mapping[str, object], actual_stage_c: Sequence[float], actual_stage_f: Sequence[float]) -> dict[str, object]:
    target_shares = target.get("band_shares") if isinstance(target, Mapping) else None
    if not isinstance(target_shares, Sequence) or len(target_shares) != 4:
        return {"availability": "not_available", "target": None, "actual_stage_c": list(actual_stage_c), "actual_stage_f": list(actual_stage_f)}
    stage_c_distance = band_distance(actual_stage_c, target_shares); stage_f_distance = band_distance(actual_stage_f, target_shares)
    return {"availability": "eligible", "target": list(target_shares), "actual_stage_c": list(actual_stage_c), "actual_stage_f": list(actual_stage_f), "signed_error": [float(a - b) for a, b in zip(actual_stage_f, target_shares)], "absolute_error": [float(abs(a - b)) for a, b in zip(actual_stage_f, target_shares)], "stage_c_distance": stage_c_distance, "stage_f_distance": stage_f_distance, "improvement_ratio": (stage_c_distance - stage_f_distance) / max(stage_c_distance, 1e-12)}


def load_target(path: str | Path) -> Mapping[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload.get("features"), Mapping):
        segments = payload["features"].get("segments", {})
        for state in ("idle", "acceleration", "afterfire"):
            if isinstance(segments, Mapping) and isinstance(segments.get(state), Mapping) and "band_shares" in segments[state]:
                return segments[state]
    if "band_shares" in payload:
        return payload
    return {}
