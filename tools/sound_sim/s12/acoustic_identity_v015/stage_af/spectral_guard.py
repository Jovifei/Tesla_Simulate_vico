"""Multi-resolution spectral counterexample guard, not a realism certificate.

Clean implementation of an audio-domain comparison, not a port of DDSP code.
Time-pooled spectra avoid assuming exact sample alignment of public references;
this also means RPM trajectories and temporal order require separate validation.
No absolute sound-pressure or perceptual-accuracy claim is made.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import stft


def _normalized_mono(audio: np.ndarray) -> np.ndarray:
    x = np.asarray(audio)
    if np.iscomplexobj(x):
        raise ValueError("real PCM expected")
    # Center unsigned 8-bit PCM. Signed PCM and float share scale invariance.
    if x.dtype == np.uint8:
        x = x.astype(np.float64) - 128.0
    else:
        x = x.astype(np.float64)
    if x.ndim == 2 and x.shape[1] in (1, 2):
        x = np.mean(x, axis=1)
    if x.ndim != 1 or x.size < 32 or not np.all(np.isfinite(x)):
        raise ValueError("at least 32 finite mono/stereo PCM samples required")
    x = x - np.mean(x)
    peak = float(np.max(np.abs(x)))
    if peak <= 1e-15:
        raise ValueError("silent/DC-only or cancelling stereo is not a usable reference")
    return x / peak


def multires_spectral_distance(
    candidate: np.ndarray, reference: np.ndarray, sr: int = 48000
) -> float:
    """Mean total-variation distance of normalized spectra, nominally [0, 1].

    Same frequency bins at three window sizes distinguish same-band pitch
    changes which a median of broad-band statistics can completely ignore.
    Caller must ensure the same sample rate and comparable RPM/load scenes.
    This does not infer RPM, correct microphone response, or align transients.
    """
    if not isinstance(sr, (int, np.integer)) or sr <= 0:
        raise ValueError("sample rate must be a positive integer")
    x = _normalized_mono(candidate)
    y = _normalized_mono(reference)
    sizes = sorted({min(n, x.size, y.size) for n in (1024, 4096, 8192)})
    distances = []
    for size in sizes:
        spectra = []
        for audio in (x, y):
            _, _, z = stft(audio, fs=sr, nperseg=size, noverlap=3*size//4,
                           boundary=None, padded=False)
            energy = np.mean(np.abs(z)**2, axis=1)
            total = float(np.sum(energy))
            if not np.isfinite(total) or total <= 0.0:
                raise ValueError("no usable spectral energy")
            spectra.append(energy / total)
        distances.append(0.5 * float(np.sum(np.abs(spectra[0] - spectra[1]))))
    return float(np.mean(distances))
