"""Synthetic intake/casing transfer used only by the Stage-I Hellcat whine."""

from __future__ import annotations

import numpy as np


_TRANSFER_MODES_HZ = (720.0, 1320.0, 2380.0)
_TRANSFER_MODE_GAINS = (0.72, 1.28, 0.78)
_TRANSFER_PROVENANCE = "C/synthetic"


def apply_intake_casing_voicing(
    stereo: np.ndarray,
    sample_rate_hz: int,
    mix: float,
) -> tuple[np.ndarray, dict[str, object]]:
    """Return a deterministic 400--3000 Hz transfer and its diagnostics.

    The operation is a private source radiation model, not the shared public
    Pre-PTR equalizer. Frequencies outside the bounded source band retain a
    unity response.
    """
    signal = np.asarray(stereo, dtype=np.float64)
    if signal.ndim != 2 or signal.shape[1] != 2:
        raise ValueError("intake/casing voicing input must be stereo")
    if not np.isfinite(mix) or not 0.0 <= float(mix) <= 1.0:
        raise ValueError("intake_voicing_mix must be finite and in [0, 1]")
    if signal.shape[0] == 0:
        return signal.copy(), _diagnostics(mix)

    frequencies = np.fft.rfftfreq(signal.shape[0], 1.0 / sample_rate_hz)
    response = np.ones_like(frequencies)
    active = (frequencies >= 400.0) & (frequencies <= 3000.0)
    safe_hz = np.maximum(frequencies[active], 1.0)
    modal = np.zeros_like(safe_hz)
    weights = np.zeros_like(safe_hz)
    for center_hz, gain in zip(_TRANSFER_MODES_HZ, _TRANSFER_MODE_GAINS, strict=True):
        weight = np.exp(-0.5 * np.square(np.log(safe_hz / center_hz) / 0.34))
        modal += gain * weight
        weights += weight
    modal = np.where(weights > 1.0e-12, modal / weights, 1.0)
    response[active] = 1.0 + float(mix) * (modal - 1.0)
    spectrum = np.fft.rfft(signal, axis=0)
    voiced = np.fft.irfft(spectrum * response[:, np.newaxis], n=signal.shape[0], axis=0)
    return voiced, _diagnostics(mix)


def _diagnostics(mix: float) -> dict[str, object]:
    return {
        "mode_frequencies_hz": _TRANSFER_MODES_HZ,
        "mode_linear_gains": _TRANSFER_MODE_GAINS,
        "active_band_hz": (400.0, 3000.0),
        "mix": float(mix),
        "provenance": _TRANSFER_PROVENANCE,
        "scope": "synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction",
    }


__all__ = ("apply_intake_casing_voicing",)
