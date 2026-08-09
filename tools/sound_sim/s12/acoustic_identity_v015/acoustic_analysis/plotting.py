"""Deterministic, headless Matplotlib writers for acoustic analysis review."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .engine_identity_metrics import OrderMap, _audio, _frame_spectrum, _frame_starts


def write_spectrogram(path: str | Path, audio: np.ndarray, sample_rate_hz: int = 48000) -> Path:
    """Write a fixed-scale 0--8 kHz spectrogram PNG to the requested path."""
    signal = _audio(audio)
    pyplot = _pyplot()
    output = _prepare_output(path)
    figure, axis = pyplot.subplots(figsize=(8, 4), dpi=120)
    frame_size = min(2048, signal.shape[0])
    starts = _frame_starts(signal.shape[0], frame_size, max(frame_size // 4, 1))
    window = np.hanning(frame_size)
    power = np.column_stack([_frame_spectrum(signal[start : start + frame_size], window) for start in starts])
    relative_db = _relative_db(power)
    frequencies = np.fft.rfftfreq(frame_size, 1.0 / sample_rate_hz)
    extent = (0.0, (signal.shape[0] - 1) / sample_rate_hz, 0.0, 8000.0)
    axis.imshow(relative_db[frequencies <= 8000.0], origin="lower", aspect="auto", extent=extent, vmin=-120, vmax=0, cmap="magma")
    axis.set(title="Synthetic acoustic-identity spectrogram", xlabel="Time (s)", ylabel="Frequency (Hz)", ylim=(0, 8000))
    figure.tight_layout()
    figure.savefig(output, format="png", metadata={"Software": "S12 acoustic identity v0.15"})
    pyplot.close(figure)
    _ensure_nonempty(output)
    return output


def write_order_map(path: str | Path, order_map: OrderMap) -> Path:
    """Write a fixed-scale real dynamic-order-map PNG to the requested path."""
    pyplot = _pyplot()
    output = _prepare_output(path)
    figure, axis = pyplot.subplots(figsize=(8, 4), dpi=120)
    data = _relative_db(order_map.power.T)
    extent = (float(order_map.time_s[0]), float(order_map.time_s[-1]), float(order_map.orders[0]), float(order_map.orders[-1]))
    axis.imshow(data, origin="lower", aspect="auto", extent=extent, vmin=-120, vmax=0, cmap="viridis")
    axis.set(title="Synthetic acoustic-identity dynamic order map", xlabel="Time (s)", ylabel="Engine order", ylim=(0, 24))
    figure.tight_layout()
    figure.savefig(output, format="png", metadata={"Software": "S12 acoustic identity v0.15"})
    pyplot.close(figure)
    _ensure_nonempty(output)
    return output


def _pyplot():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as pyplot

    return pyplot


def _prepare_output(path: str | Path) -> Path:
    output = Path(path)
    if output.suffix.lower() != ".png":
        raise ValueError("plot output path must end in .png")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def _ensure_nonempty(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"failed to write nonempty PNG: {path}")


def _relative_db(power: np.ndarray) -> np.ndarray:
    peak = float(np.max(power)) if power.size else 0.0
    if peak <= 0.0:
        return np.full_like(power, -120.0, dtype=np.float64)
    return np.clip(10.0 * np.log10(np.maximum(power / peak, 1e-12)), -120.0, 0.0)
