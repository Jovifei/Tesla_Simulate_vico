"""Load/throttle driven source-level balance for Stage K.

This is a pre-PTR operating-state trim.  It is intentionally not an AGC:
the envelope is derived only from the vehicle state and is applied once to
the named continuous source stems.  Event stems remain independently timed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace


@dataclass(frozen=True)
class OperatingLevelTrim:
    low_load_gain_db: float
    high_load_gain_db: float
    blend_load: tuple[float, float]
    smoothing_s: float

    def validate(self) -> "OperatingLevelTrim":
        values = (self.low_load_gain_db, self.high_load_gain_db, self.smoothing_s, *self.blend_load)
        if not all(np.isfinite(float(value)) for value in values):
            raise ValueError("operating trim values must be finite")
        low, high = self.blend_load
        if not 0.0 <= low < high <= 1.0:
            raise ValueError("blend_load must be an increasing pair in [0, 1]")
        if self.smoothing_s < 0.0:
            raise ValueError("smoothing_s must be >= 0")
        return self


def apply_source_operating_trim(
    render: SourceRender,
    trace: VehicleStateTrace,
    *,
    stem_names: tuple[str, ...],
    trim: OperatingLevelTrim,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Apply a smooth load/throttle operating-level trim before shared layers.

    RPM is deliberately not used to derive the gain envelope.  It remains in
    the trace for source phase/frequency generation, but equal operating
    states produce the same trim envelope even when RPM differs.
    """
    render.validate()
    trace.validate()
    trim.validate()
    if not isinstance(sample_rate_hz, int) or isinstance(sample_rate_hz, bool) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    if not stem_names:
        raise ValueError("stem_names must not be empty")
    missing = set(stem_names) - set(render.stems)
    if missing:
        raise ValueError(f"operating trim stems are missing: {sorted(missing)}")

    count = render.pressure.shape[0]
    audio_time = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    load = np.interp(audio_time, trace.time_s, trace.load, left=trace.load[0], right=trace.load[-1])
    throttle = np.interp(audio_time, trace.time_s, trace.throttle, left=trace.throttle[0], right=trace.throttle[-1])
    operating_state = np.clip(0.65 * load + 0.35 * throttle, 0.0, 1.0)
    target_gain_db = _blend_gain(operating_state, trim)
    gain_db = _smooth(target_gain_db, sample_rate_hz, trim.smoothing_s)
    gain = np.power(10.0, gain_db / 20.0)

    stems = dict(render.stems)
    pressure = np.asarray(render.pressure, dtype=np.float64).copy()
    for stem_name in stem_names:
        old = np.asarray(render.stems[stem_name], dtype=np.float64)
        new = old * gain[:, None]
        stems[stem_name] = new
        pressure += new - old

    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "stage_k_source_operating_trim": {
                "low_load_gain_db": float(trim.low_load_gain_db),
                "high_load_gain_db": float(trim.high_load_gain_db),
                "blend_load": [float(trim.blend_load[0]), float(trim.blend_load[1])],
                "smoothing_s": float(trim.smoothing_s),
                "state_inputs": ("load", "throttle"),
                "forbidden_inputs": ("rpm", "speed", "pcm", "rms", "lufs", "peak"),
                "stem_names": list(stem_names),
            },
            "operating_trim_gain_db": gain_db,
            "operating_trim_state": operating_state,
        }
    )
    return replace(render, pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def _blend_gain(operating_state: np.ndarray, trim: OperatingLevelTrim) -> np.ndarray:
    low, high = trim.blend_load
    fraction = np.clip((operating_state - low) / (high - low), 0.0, 1.0)
    return trim.low_load_gain_db + fraction * (trim.high_load_gain_db - trim.low_load_gain_db)


def _smooth(values: np.ndarray, sample_rate_hz: int, smoothing_s: float) -> np.ndarray:
    if smoothing_s == 0.0 or values.size < 2:
        return values.copy()
    coefficient = 1.0 - np.exp(-1.0 / (smoothing_s * sample_rate_hz))
    result = np.empty_like(values)
    result[0] = values[0]
    for index in range(1, values.size):
        result[index] = result[index - 1] + coefficient * (values[index] - result[index - 1])
    return result


__all__ = ("OperatingLevelTrim", "apply_source_operating_trim")
