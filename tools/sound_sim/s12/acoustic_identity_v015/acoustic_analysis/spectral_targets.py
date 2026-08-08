# tools/sound_sim/s12/acoustic_identity_v015/acoustic_analysis/spectral_targets.py
"""逐状态谱目标测量：band energy 占比、centroid、pairwise 谱距。"""
from __future__ import annotations

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace

BAND_EDGES = [(20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0)]


def band_energy_shares(signal: np.ndarray, sample_rate_hz: int = 48000) -> tuple[float, float, list[float]]:
    """返回 (spectral_centroid_hz, total_energy, [4 个 band 能量占比])。signal 为单声道。"""
    mono = np.asarray(signal, dtype=np.float64).ravel()
    windowed = mono * np.hanning(mono.size)
    spectrum = np.square(np.abs(np.fft.rfft(windowed)))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / sample_rate_hz)
    total = float(spectrum.sum()) or 1e-15
    centroid = float(np.sum(freqs * spectrum) / total)
    shares = [float(spectrum[(freqs >= lo) & (freqs <= hi)].sum() / total) for lo, hi in BAND_EDGES]
    return centroid, total, shares


def render_state_band_shares(render: SourceRender, sample_rate_hz: int = 48000) -> tuple[float, list[float]]:
    centroid, _, shares = band_energy_shares(render.pressure.mean(axis=1), sample_rate_hz)
    return centroid, shares


def spectral_distance(render_a: SourceRender, render_b: SourceRender, trace: VehicleStateTrace, sample_rate_hz: int = 48000) -> float:
    """复用 engine_identity_metrics 的 log-order cosine distance（已在 compare_identity_renders 中使用）。"""
    from .engine_identity_metrics import compute_order_map, _log_order_cosine_distance

    a = compute_order_map(render_a.pressure, trace, sample_rate_hz).order_energy
    b = compute_order_map(render_b.pressure, trace, sample_rate_hz).order_energy
    return float(_log_order_cosine_distance(a, b))
