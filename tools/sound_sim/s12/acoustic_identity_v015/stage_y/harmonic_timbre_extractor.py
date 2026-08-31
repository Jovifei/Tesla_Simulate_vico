"""Synchronized RPM/load/boost/order timbre-map extraction.

The extractor is intentionally independent from any particular vehicle or
recording provider.  It consumes an authorized audio array plus synchronized
state traces and emits only derived numerical features.  Raw third-party audio
is never stored in the resulting map.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

MAP_SCHEMA = "s12.stage_y.harmonic_timbre_map.v1"


def _mono(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float64)
    if values.ndim == 2:
        if values.shape[1] < 1:
            raise ValueError("audio must contain at least one channel")
        values = np.mean(values, axis=1)
    if values.ndim != 1 or values.size < 32 or not np.all(np.isfinite(values)):
        raise ValueError("audio must be a finite non-empty mono/stereo array")
    return values


def _strict_axis(values: Iterable[float], name: str) -> np.ndarray:
    axis = np.asarray(tuple(values), dtype=np.float64)
    if axis.ndim != 1 or axis.size < 1 or not np.all(np.isfinite(axis)):
        raise ValueError(f"{name} must be a finite one-dimensional axis")
    if axis.size > 1 and np.any(np.diff(axis) <= 0.0):
        raise ValueError(f"{name} must be strictly increasing")
    return axis


def _state_trace(times: np.ndarray, values: np.ndarray, label: str) -> tuple[np.ndarray, np.ndarray]:
    times = np.asarray(times, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if times.ndim != 1 or values.ndim != 1 or times.size != values.size or times.size < 2:
        raise ValueError(f"{label} trace must have matching one-dimensional times and values")
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(values)) or np.any(np.diff(times) <= 0.0):
        raise ValueError(f"{label} trace must be finite with strictly increasing times")
    return times, values


def _nearest_index(axis: np.ndarray, value: float) -> int:
    return int(np.argmin(np.abs(axis - float(value))))


@dataclass(frozen=True)
class HarmonicTimbreMap:
    """Derived RPM × load × boost × order amplitude table."""

    rpm_axis: np.ndarray
    load_axis: np.ndarray
    boost_axis: np.ndarray
    order_axis: np.ndarray
    amplitude_db: np.ndarray
    observation_count: np.ndarray
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        expected = (
            self.rpm_axis.size,
            self.load_axis.size,
            self.boost_axis.size,
            self.order_axis.size,
        )
        if self.amplitude_db.shape != expected or self.observation_count.shape != expected:
            raise ValueError("timbre-map arrays do not match their axes")
        if np.any(self.observation_count < 0):
            raise ValueError("observation counts must be non-negative")
        observed = self.observation_count > 0
        if np.any(observed & ~np.isfinite(self.amplitude_db)):
            raise ValueError("observed timbre-map cells must be finite")

    def to_dict(self) -> dict[str, Any]:
        amplitude: list[Any] = self.amplitude_db.astype(object).tolist()

        def replace_nonfinite(value: Any) -> Any:
            if isinstance(value, list):
                return [replace_nonfinite(item) for item in value]
            return float(value) if np.isfinite(float(value)) else None

        return {
            "schema": MAP_SCHEMA,
            "rpm_axis": self.rpm_axis.tolist(),
            "load_axis": self.load_axis.tolist(),
            "boost_axis": self.boost_axis.tolist(),
            "order_axis": self.order_axis.tolist(),
            "amplitude_db": replace_nonfinite(amplitude),
            "observation_count": self.observation_count.astype(int).tolist(),
            "metadata": dict(self.metadata),
            "raw_audio_embedded": False,
            "scope": "derived features from authorized synchronized audio; not an OEM reproduction claim",
        }

    def dominant_order(self) -> float:
        """Return the order with the strongest median observed amplitude."""
        values: list[float] = []
        for index in range(self.order_axis.size):
            observed = self.observation_count[..., index] > 0
            values.append(float(np.median(self.amplitude_db[..., index][observed])) if np.any(observed) else float("-inf"))
        if not any(np.isfinite(values)):
            raise ValueError("timbre map has no observed cells")
        return float(self.order_axis[int(np.argmax(values))])


def extract_harmonic_timbre_map(
    audio: np.ndarray,
    sample_rate_hz: int,
    *,
    state_times_s: np.ndarray,
    rpm_trace: np.ndarray,
    load_trace: np.ndarray,
    boost_trace: np.ndarray | None = None,
    rpm_axis: Iterable[float] = (800.0, 1600.0, 2400.0, 3600.0, 5200.0, 7000.0),
    load_axis: Iterable[float] = (0.15, 0.45, 0.75, 1.0),
    boost_axis: Iterable[float] = (0.0, 0.5, 1.0),
    order_axis: Iterable[float] = (0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 12.0, 16.0),
    frame_size: int = 4096,
    hop_size: int = 1024,
    search_half_width_bins: int = 1,
    provenance: dict[str, Any] | None = None,
) -> HarmonicTimbreMap:
    """Extract a scenario-independent harmonic amplitude map.

    State traces may run at any rate.  They are linearly interpolated to each
    FFT-frame centre.  Harmonic power is integrated around the predicted order
    frequency, preventing a free spectral peak from being mislabeled as an
    engine order.  Formal use still requires a rights-cleared synchronized
    recording receipt.
    """

    signal = _mono(audio)
    if not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be a positive integer")
    if frame_size < 256 or hop_size <= 0 or hop_size > frame_size or signal.size < frame_size:
        raise ValueError("invalid frame/hop size for the supplied audio")
    if search_half_width_bins < 0 or search_half_width_bins > 8:
        raise ValueError("search_half_width_bins must be in [0, 8]")

    state_times, rpm_values = _state_trace(state_times_s, rpm_trace, "rpm")
    _, load_values = _state_trace(state_times_s, load_trace, "load")
    if boost_trace is None:
        boost_values = np.zeros_like(rpm_values)
    else:
        _, boost_values = _state_trace(state_times_s, boost_trace, "boost")
    if np.any(rpm_values <= 0.0):
        raise ValueError("RPM trace must be positive")

    rpm_bins = _strict_axis(rpm_axis, "rpm_axis")
    load_bins = _strict_axis(load_axis, "load_axis")
    boost_bins = _strict_axis(boost_axis, "boost_axis")
    orders = _strict_axis(order_axis, "order_axis")
    shape = (rpm_bins.size, load_bins.size, boost_bins.size, orders.size)
    observations: np.ndarray = np.empty(shape, dtype=object)
    for index in np.ndindex(shape):
        observations[index] = []

    window = np.hanning(frame_size)
    coherent_gain = max(float(np.sum(window)) / 2.0, 1e-12)
    frequencies = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate_hz)
    frame_count = 1 + (signal.size - frame_size) // hop_size
    used_frames = 0
    rejected_nyquist = 0
    for frame_index in range(frame_count):
        start = frame_index * hop_size
        centre_s = (start + 0.5 * frame_size) / sample_rate_hz
        if centre_s < state_times[0] or centre_s > state_times[-1]:
            continue
        rpm = float(np.interp(centre_s, state_times, rpm_values))
        load = float(np.clip(np.interp(centre_s, state_times, load_values), 0.0, 1.0))
        boost = float(np.clip(np.interp(centre_s, state_times, boost_values), 0.0, 1.0))
        spectrum = np.abs(np.fft.rfft(signal[start : start + frame_size] * window)) / coherent_gain
        irpm = _nearest_index(rpm_bins, rpm)
        iload = _nearest_index(load_bins, load)
        iboost = _nearest_index(boost_bins, boost)
        frame_used = False
        for iorder, order in enumerate(orders):
            frequency = float(order * rpm / 60.0)
            if frequency <= 0.0 or frequency >= 0.98 * sample_rate_hz / 2.0:
                rejected_nyquist += 1
                continue
            centre = int(np.argmin(np.abs(frequencies - frequency)))
            lo = max(0, centre - search_half_width_bins)
            hi = min(spectrum.size, centre + search_half_width_bins + 1)
            amplitude = float(np.sqrt(np.sum(np.square(spectrum[lo:hi]))))
            observations[irpm, iload, iboost, iorder].append(20.0 * np.log10(max(amplitude, 1e-12)))
            frame_used = True
        used_frames += int(frame_used)

    amplitude_db = np.full(shape, np.nan, dtype=np.float64)
    counts = np.zeros(shape, dtype=np.int64)
    for index in np.ndindex(shape):
        values = observations[index]
        if values:
            amplitude_db[index] = float(np.median(np.asarray(values, dtype=np.float64)))
            counts[index] = len(values)

    metadata = {
        "sample_rate_hz": sample_rate_hz,
        "frame_size": frame_size,
        "hop_size": hop_size,
        "frame_count": frame_count,
        "used_frame_count": used_frames,
        "rejected_nyquist_order_observations": rejected_nyquist,
        "state_trace_points": int(state_times.size),
        "synchronized_state_required": True,
        "aggregation": "median_db_per_nearest_rpm_load_boost_cell",
        "provenance": dict(provenance or {}),
    }
    return HarmonicTimbreMap(rpm_bins, load_bins, boost_bins, orders, amplitude_db, counts, metadata)


__all__ = ["HarmonicTimbreMap", "MAP_SCHEMA", "extract_harmonic_timbre_map"]
