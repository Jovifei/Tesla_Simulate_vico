"""Deterministic linear equalization before the frozen PTR adapter."""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt

from ..contracts import SourceRender, VehicleStateTrace


_SCOPE = "synthetic; uncalibrated; not OEM reproduction"
_LOW_SHELF_HZ = 220.0
_LOW_SHELF_DB = 18.0
_HIGH_SHELF_HZ = 3200.0
_HIGH_SHELF_DB = -17.0
_DC_CUTOFF_HZ = 20.0


def apply_pre_ptr_equalization(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Apply the same causal filter chain to pressure and every named stem."""
    render.validate()
    trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 8000:
        raise ValueError("sample_rate_hz must be an integer >= 8000")
    if not vehicle_id:
        raise ValueError("vehicle_id must be non-empty")
    if _HIGH_SHELF_HZ >= sample_rate_hz / 2.0:
        raise ValueError("high-shelf frequency must be below Nyquist")

    def transform(value: np.ndarray) -> np.ndarray:
        output = np.asarray(value, dtype=np.float64)
        low = sosfilt(butter(1, _LOW_SHELF_HZ / (sample_rate_hz / 2.0), btype="low", output="sos"), output, axis=0)
        output = output + (10.0 ** (_LOW_SHELF_DB / 20.0) - 1.0) * low
        high = sosfilt(butter(1, _HIGH_SHELF_HZ / (sample_rate_hz / 2.0), btype="high", output="sos"), output, axis=0)
        output = output + (10.0 ** (_HIGH_SHELF_DB / 20.0) - 1.0) * high
        return sosfilt(butter(1, _DC_CUTOFF_HZ / (sample_rate_hz / 2.0), btype="high", output="sos"), output, axis=0)

    before_shares = _band_shares(render.pressure, sample_rate_hz)
    pressure = transform(render.pressure)
    after_shares = _band_shares(pressure, sample_rate_hz)
    stems = {name: transform(stem) for name, stem in render.stems.items()}
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "pre_equalization_model": "causal_low_shelf_high_shelf_dc_removal",
            "pre_equalization_vehicle_id": vehicle_id,
            "pre_equalization_low_shelf_hz": _LOW_SHELF_HZ,
            "pre_equalization_low_shelf_db": _LOW_SHELF_DB,
            "pre_equalization_high_shelf_hz": _HIGH_SHELF_HZ,
            "pre_equalization_high_shelf_db": _HIGH_SHELF_DB,
            "pre_equalization_dc_cutoff_hz": _DC_CUTOFF_HZ,
            "pre_equalization_scope": _SCOPE,
            "pre_equalization_band_shares_before": before_shares,
            "pre_equalization_band_shares_after": after_shares,
        }
    )
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


__all__ = ("apply_pre_ptr_equalization",)


def _band_shares(stereo: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    signal = np.asarray(stereo, dtype=np.float64).mean(axis=1)
    energy = np.square(np.abs(np.fft.rfft(signal * np.hanning(signal.size))))
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / sample_rate_hz)
    total = float(energy.sum())
    bands = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0))
    return {
        f"{int(low)}_{int(high)}hz": float(energy[(frequencies >= low) & (frequencies < high)].sum() / total) if total else 0.0
        for low, high in bands
    }
