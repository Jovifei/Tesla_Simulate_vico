"""S12 Acoustic Realism Phase 1 - upgraded real-recording reference feature extractor.

Extracts recording-dependent relative features from externally held R2 recordings
to build the per-vehicle real acoustic reference database required by the
S12 Acoustic Realism Master Plan v1, Phase 1.

Boundary:
    relative recording features only; synthetic; uncalibrated; not OEM calibration.
    Every metric is microphone / AGC / distance / modification dependent and is
    used as a relative directional target, never as an absolute acoustic target.

Metrics (aligned with the Hellcat v6 reference_targets schema):
    band_shares          4-band energy fractions [20-250, 250-1000, 1k-4k, 4k-12k] Hz
    spectral_flux        mean positive spectral difference between adjacent STFT frames
    modulation_depth     envelope AC/DC ratio (combustion pulse periodicity strength)
    modulation_peak_hz   dominant envelope modulation frequency
    modulation_energy    fraction of envelope spectral energy at the dominant peak
    pulse_amplitude_cv   coefficient of variation of detected pulse amplitudes
    pulse_interval_cv    coefficient of variation of detected pulse intervals
    crest_factor         peak / rms of the segment
    dropout_ratio        fraction of frames below the silence threshold
    spectral_centroid_hz first moment of the mean spectrum
    rms_dbfs             segment RMS in dBFS
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import json
import math
import wave

import numpy as np

try:
    from scipy.signal import find_peaks, hilbert
    _HAS_SCIPY = True
except Exception:
    _HAS_SCIPY = False

BAND_EDGES = [(20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0)]
BAND_NAMES = ["20_250hz", "250_1000hz", "1k_4khz", "4k_12khz"]

_PROVENANCE = "B/R2 extracted from external recording; microphone/AGC/configuration dependent; not OEM calibration"


def extract_reference_features(
    audio_path: str | Path,
    segments: Mapping[str, tuple[float, float]] | None = None,
    frame_size: int = 4096,
    hop_size: int = 1024,
) -> dict[str, object]:
    """Return recording-dependent features for every requested segment.

    If ``segments`` is None the idle / acceleration / afterfire windows are
    auto-annotated from the RMS envelope and spectral flux.
    """
    path = Path(audio_path)
    sample_rate_hz, audio = _read_pcm_wav(path)
    segment_quality: dict[str, object] | None = None
    if segments is None:
        segments, segment_quality = auto_annotate_segments_with_quality(audio, sample_rate_hz)

    result: dict[str, object] = {
        "analysis_domain": "relative_recording_features_only",
        "provenance": _PROVENANCE,
        "source_path": str(path.name),
        "sample_rate_hz": sample_rate_hz,
        "stft": {"window": "hann", "frame_size": frame_size, "hop_size": hop_size},
        "segments": {},
    }
    if segment_quality is not None:
        result["segment_quality"] = segment_quality
    for name, (start_s, end_s) in segments.items():
        if not 0.0 <= start_s < end_s <= audio.size / sample_rate_hz:
            raise ValueError(f"invalid segment {name!r}: ({start_s}, {end_s}) for {audio.size / sample_rate_hz:.2f}s clip")
        start = int(round(start_s * sample_rate_hz))
        end = int(round(end_s * sample_rate_hz))
        seg = audio[start:end]
        if seg.size < frame_size:
            raise ValueError(f"segment {name!r} too short for analysis")
        result["segments"][name] = _segment_metrics(seg, sample_rate_hz, frame_size, hop_size)
    return result


# --- idle acceptance thresholds (see _find_physical_idle) -------------------
_IDLE_SILENCE_DBFS = -55.0      # below this a window is digital silence, not engine
_IDLE_LF_SHARE_MIN = 0.45       # 20-250 Hz must dominate a true idle window
_IDLE_LF_SHARE_RELAXED = 0.40   # last-resort relaxation
_IDLE_LOUD_MARGINS_DB = (8.0, 5.0, 3.0, 1.0)  # progressive relaxation vs loud P90
_IDLE_PROBE_WIN_S = 2.0
_IDLE_PROBE_HOP_S = 0.5


def auto_annotate_segments(audio: np.ndarray, sample_rate_hz: int) -> dict[str, tuple[float, float]]:
    """Auto-label idle / acceleration / afterfire windows from the signal.

    Thin wrapper over :func:`auto_annotate_segments_with_quality` kept for API
    compatibility; returns the windows only.
    """
    segments, _quality = auto_annotate_segments_with_quality(audio, sample_rate_hz)
    return segments


def auto_annotate_segments_with_quality(
    audio: np.ndarray, sample_rate_hz: int
) -> tuple[dict[str, tuple[float, float]], dict[str, object]]:
    """Auto-label idle / acceleration / afterfire windows plus a quality record.

    Strategy:
      acceleration - highest-energy sustained region (longest run above 1.3 x median RMS)
      idle         - *physically validated* low-load window, see ``_find_physical_idle``
      afterfire    - densest spectral-flux transient cluster

    Why idle is not simply "the quietest region"
    --------------------------------------------
    The previous implementation labelled the lowest-energy stable run as idle and,
    when that failed, fell back to the first 8 s of the clip. On ``*_accel.wav``
    compilation recordings the quietest region is **not** engine idle -- it is
    digital silence at the file head/tail, or wind / gap noise between pulls.
    Those windows are broadband, so their spectral centroid lands *above* the
    wide-open-throttle centroid, which is impossible for a reciprocating engine
    and produces a poisoned tuning target (Ferrari 458 idle centroid came out at
    980 Hz with only 0.9 % of its energy below 250 Hz).

    Returns:
        (segments, quality) where ``quality["idle"]`` is one of ``"physical"``
        (met the strict criteria), ``"relaxed"`` (met them only after widening
        the loudness margin) or ``"unavailable"`` (no window in the recording
        looks like idle at all -- the segment is then omitted entirely rather
        than silently faked).
    """
    rms = _envelope_rms(audio, max(sample_rate_hz // 100, 1))
    frame_rate = sample_rate_hz / max(sample_rate_hz // 100, 1)
    median_rms = float(np.median(rms)) or 1e-9

    flux = _spectral_flux_series(audio, sample_rate_hz, 4096, 1024)
    flux_median = float(np.median(flux)) if flux.size else 0.0
    flux_std = float(np.std(flux)) if flux.size else 0.0

    accel_win = _longest_run(rms > 1.3 * median_rms, frame_rate, 3.0, 25.0)
    after_win = _longest_run(flux > flux_median + 1.5 * flux_std, frame_rate, 2.0, 20.0) if flux.size else None

    duration = audio.size / sample_rate_hz
    if accel_win is None:
        accel_win = (max(0.0, duration * 0.4), min(duration, duration * 0.7))
    if after_win is None:
        after_start = min(accel_win[1] + 1.0, duration - 4.0)
        after_win = (max(0.0, after_start), min(duration, after_start + 8.0))

    idle_win, idle_quality = _find_physical_idle(audio, sample_rate_hz, accel_win)

    segments: dict[str, tuple[float, float]] = {}
    if idle_win is not None:
        segments["idle"] = idle_win
    segments["acceleration"] = accel_win
    segments["afterfire"] = after_win

    quality: dict[str, object] = {
        "idle": idle_quality["verdict"],
        "idle_detail": idle_quality,
        "acceleration": "energy_run",
        "afterfire": "flux_cluster",
    }
    return {k: (float(v[0]), float(v[1])) for k, v in segments.items()}, quality


def _window_probe(seg: np.ndarray, sr: int) -> tuple[float, float, float]:
    """Return (rms_dbfs, low_band_share, spectral_centroid_hz) for one window."""
    freqs, energy = _mean_stft_energy(seg, sr, 4096, 1024)
    total = float(energy.sum()) or 1e-15
    lf_share = _band_fraction(energy, freqs, *BAND_EDGES[0])
    centroid = float(np.sum(freqs * energy) / total)
    rms = float(np.sqrt(np.mean(np.square(seg))))
    return 20.0 * math.log10(max(rms, 1e-15)), lf_share, centroid


def _find_physical_idle(
    audio: np.ndarray,
    sr: int,
    accel_win: tuple[float, float],
) -> tuple[tuple[float, float] | None, dict[str, object]]:
    """Locate a window that is physically consistent with engine idle.

    A candidate window must satisfy, in order:
      1. ``rms_dbfs > _IDLE_SILENCE_DBFS``     - not digital silence
      2. ``rms_dbfs < loud_p90 - margin``      - engine is off-throttle
      3. ``low_band_share >= lf_min``          - 20-250 Hz dominates, as the idle
         firing fundamental of any four-stroke sits at 25-80 Hz
      4. ``centroid < wot_centroid``           - spectral monotonicity with load

    The loudness margin is relaxed progressively so that heavily compressed
    recordings (small dynamic range) still yield a candidate; the relaxation
    level is reported so the caller can mark the provenance.

    Args:
        audio: mono float signal.
        sr: sample rate in Hz.
        accel_win: the acceleration window, used to derive the WOT centroid.

    Returns:
        ``(window, detail)``; ``window`` is None when nothing qualifies.
    """
    duration = audio.size / sr
    win = int(_IDLE_PROBE_WIN_S * sr)
    hop = int(_IDLE_PROBE_HOP_S * sr)
    detail: dict[str, object] = {"verdict": "unavailable"}
    if win <= 0 or audio.size < win:
        return None, detail

    a0 = int(max(0.0, accel_win[0]) * sr)
    a1 = int(min(duration, accel_win[1]) * sr)
    wot_seg = audio[a0:a1]
    if wot_seg.size < 4096:
        wot_seg = audio
    _, _, wot_centroid = _window_probe(wot_seg, sr)
    detail["wot_centroid_hz"] = round(wot_centroid, 1)

    probes: list[tuple[float, float, float, float]] = []  # (t, rms_db, lf, centroid)
    for start in range(0, audio.size - win + 1, hop):
        seg = audio[start : start + win]
        rms_db, lf, centroid = _window_probe(seg, sr)
        probes.append((start / sr, rms_db, lf, centroid))
    if not probes:
        return None, detail

    audible = [p for p in probes if p[1] > _IDLE_SILENCE_DBFS]
    detail["probe_windows"] = len(probes)
    detail["audible_windows"] = len(audible)
    if not audible:
        return None, detail
    loud_p90 = float(np.percentile([p[1] for p in audible], 90))
    detail["loud_p90_dbfs"] = round(loud_p90, 1)

    for lf_min in (_IDLE_LF_SHARE_MIN, _IDLE_LF_SHARE_RELAXED):
        for margin in _IDLE_LOUD_MARGINS_DB:
            hits = [
                p
                for p in audible
                if p[1] < loud_p90 - margin and p[2] >= lf_min and p[3] < wot_centroid
            ]
            if not hits:
                continue
            strict = lf_min == _IDLE_LF_SHARE_MIN and margin == _IDLE_LOUD_MARGINS_DB[0]
            # quietest hit wins; ties broken by strongest low-frequency dominance
            hits.sort(key=lambda p: (p[1], -p[2]))
            anchor_t = hits[0][0]
            window = _grow_idle_window(hits, anchor_t, duration)
            detail.update(
                {
                    "verdict": "physical" if strict else "relaxed",
                    "lf_share_min": lf_min,
                    "loud_margin_db": margin,
                    "anchor_t_s": round(anchor_t, 2),
                    "anchor_rms_dbfs": round(hits[0][1], 1),
                    "anchor_low_band_share": round(hits[0][2], 4),
                    "anchor_centroid_hz": round(hits[0][3], 1),
                    "candidate_windows": len(hits),
                }
            )
            return window, detail

    # Nothing in this recording behaves like idle. Report it instead of
    # falling back to the first 8 s, which is what poisoned the old database.
    nonsilent_lf_max = max((p[2] for p in audible), default=0.0)
    detail["max_low_band_share"] = round(nonsilent_lf_max, 4)
    detail["reason"] = "no window is low-frequency dominated and quieter than WOT"
    return None, detail


def _grow_idle_window(
    hits: list[tuple[float, float, float, float]],
    anchor_t: float,
    duration: float,
    max_len_s: float = 10.0,
) -> tuple[float, float]:
    """Extend the anchor over neighbouring qualifying probes (contiguous run)."""
    times = sorted(p[0] for p in hits)
    step = _IDLE_PROBE_HOP_S
    start = end = anchor_t
    tset = set(round(t, 3) for t in times)
    while round(start - step, 3) in tset and (end - (start - step)) < max_len_s:
        start = round(start - step, 3)
    while round(end + step, 3) in tset and ((end + step) - start) < max_len_s:
        end = round(end + step, 3)
    end_s = min(duration, end + _IDLE_PROBE_WIN_S)
    start_s = max(0.0, start)
    # keep at least one full probe window
    if end_s - start_s < _IDLE_PROBE_WIN_S:
        end_s = min(duration, start_s + _IDLE_PROBE_WIN_S)
    return (start_s, end_s)


def _segment_metrics(seg: np.ndarray, sr: int, frame: int, hop: int) -> dict[str, float]:
    freqs, energy = _mean_stft_energy(seg, sr, frame, hop)
    total = float(energy.sum()) or 1e-15
    band_shares = [_band_fraction(energy, freqs, lo, hi) for lo, hi in BAND_EDGES]
    flux = float(_spectral_flux(seg, sr, frame, hop))
    mod_depth, mod_peak, mod_energy = _modulation(seg, sr)
    pulse_amp_cv, pulse_int_cv = _pulse_stats(seg, sr)
    crest = float(np.max(np.abs(seg)) / (np.sqrt(np.mean(np.square(seg))) or 1e-15))
    dropout = float(_dropout_ratio(seg, sr))
    centroid = float(np.sum(freqs * energy) / total) if total > 0 else 0.0
    rms_db = float(20.0 * math.log10(max(np.sqrt(np.mean(np.square(seg))), 1e-15)))
    return {
        "duration_s": float(seg.size / sr),
        "rms_dbfs": rms_db,
        "spectral_centroid_hz": centroid,
        "band_shares": band_shares,
        "spectral_flux": flux,
        "modulation_depth": mod_depth,
        "modulation_peak_hz": mod_peak,
        "modulation_energy": mod_energy,
        "pulse_amplitude_cv": pulse_amp_cv,
        "pulse_interval_cv": pulse_int_cv,
        "crest_factor": crest,
        "dropout_ratio": dropout,
    }


def _read_pcm_wav(path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        sample_rate_hz = stream.getframerate()
        raw = stream.readframes(stream.getnframes())
    if channels < 1 or width not in {1, 2, 3, 4}:
        raise ValueError("only 8/16/24/32-bit PCM WAV is supported")
    if width == 1:
        values = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif width == 2:
        values = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        vals = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
        values = np.where(vals & (1 << 23), vals - (1 << 24), vals).astype(np.float64) / (1 << 23)
    else:
        values = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (1 << 31)
    return sample_rate_hz, values.reshape(-1, channels).mean(axis=1)


def _mean_stft_energy(audio: np.ndarray, sr: int, frame: int, hop: int) -> tuple[np.ndarray, np.ndarray]:
    size = min(frame, audio.size)
    starts = np.arange(0, audio.size - size + 1, max(hop, 1), dtype=int)
    if starts.size == 0:
        starts = np.array([0])
    window = np.hanning(size)
    energy = np.mean([np.square(np.abs(np.fft.rfft(audio[s:s + size] * window))) for s in starts], axis=0)
    return np.fft.rfftfreq(size, 1.0 / sr), energy


def _band_fraction(energy: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> float:
    mask = (freqs >= lo) & (freqs <= hi)
    total = float(energy.sum())
    return float(energy[mask].sum() / total) if total else 0.0


def _spectral_flux(audio: np.ndarray, sr: int, frame: int, hop: int) -> float:
    series = _spectral_flux_series(audio, sr, frame, hop)
    return float(np.mean(series)) if series.size else 0.0


def _spectral_flux_series(audio: np.ndarray, sr: int, frame: int, hop: int) -> np.ndarray:
    size = min(frame, audio.size)
    starts = np.arange(0, audio.size - size + 1, max(hop, 1), dtype=int)
    if starts.size < 2:
        return np.array([])
    window = np.hanning(size)
    mags = np.array([np.abs(np.fft.rfft(audio[s:s + size] * window)) for s in starts])
    diff = np.diff(mags, axis=0)
    pos = np.maximum(diff, 0.0)
    norm = mags[1:].sum(axis=1)
    norm[norm == 0] = 1e-15
    return pos.sum(axis=1) / norm


def _envelope_rms(audio: np.ndarray, frame: int) -> np.ndarray:
    if frame < 1:
        frame = 1
    n = audio.size // frame
    if n < 1:
        return np.array([float(np.sqrt(np.mean(np.square(audio))))])
    trimmed = audio[: n * frame].reshape(n, frame)
    return np.sqrt(np.mean(np.square(trimmed), axis=1))


def _modulation(audio: np.ndarray, sr: int) -> tuple[float, float, float]:
    """Envelope modulation depth, dominant pulse frequency and peak energy.

    modulation_depth   = AC_rms / DC of the amplitude envelope (0..1)
    modulation_peak_hz = dominant envelope frequency in the 5-500 Hz band
                         (covers combustion pulse fundamentals, not bulk loudness)
    modulation_energy  = fraction of 5-500 Hz envelope energy at the peak bin
    """
    if _HAS_SCIPY:
        env = np.abs(hilbert(audio))
    else:
        env = np.abs(audio)
        env = _lowpass(env, int(sr * 0.05) or 1)
    dc = float(np.mean(env))
    if dc < 1e-15:
        return 0.0, 0.0, 0.0
    ac = env - dc
    ac_rms = float(np.sqrt(np.mean(np.square(ac))))
    depth = min(ac_rms / dc, 1.0)
    if ac.size < 8:
        return depth, 0.0, 0.0
    spectrum = np.abs(np.fft.rfft(ac))
    freqs = np.fft.rfftfreq(ac.size, 1.0 / sr)
    band_mask = (freqs >= 5.0) & (freqs <= 500.0)
    if not np.any(band_mask):
        return depth, 0.0, 0.0
    band_spec = spectrum[band_mask]
    band_freqs = freqs[band_mask]
    band_total = float(band_spec.sum()) or 1e-15
    peak_idx = int(np.argmax(band_spec))
    peak_hz = float(band_freqs[peak_idx])
    peak_energy = float(band_spec[peak_idx] / band_total)
    return depth, peak_hz, peak_energy


def _lowpass(x: np.ndarray, taps: int) -> np.ndarray:
    if taps < 1:
        return x
    kernel = np.ones(taps) / taps
    return np.convolve(x, kernel, mode="same")


def _pulse_stats(audio: np.ndarray, sr: int) -> tuple[float, float]:
    env = np.abs(audio)
    env = _lowpass(env, max(int(sr * 0.01), 1))
    env = env - np.mean(env)
    if env.size < sr or np.all(env <= 0):
        return 0.0, 0.0
    threshold = float(np.max(env) * 0.35)
    if _HAS_SCIPY:
        idx, _ = find_peaks(env, height=threshold, distance=max(int(sr * 0.01), 1))
    else:
        idx = _simple_peaks(env, threshold, max(int(sr * 0.01), 1))
    if idx.size < 3:
        return 0.0, 0.0
    amps = env[idx]
    intervals = np.diff(idx) / float(sr)
    amp_cv = float(np.std(amps) / (np.mean(amps) or 1e-15))
    int_cv = float(np.std(intervals) / (np.mean(intervals) or 1e-15))
    return amp_cv, int_cv


def _simple_peaks(env: np.ndarray, threshold: float, min_dist: int) -> np.ndarray:
    above = np.where(env > threshold)[0]
    if above.size == 0:
        return np.array([], dtype=int)
    selected = [int(above[0])]
    for i in above[1:]:
        if i - selected[-1] >= min_dist:
            selected.append(int(i))
    return np.array(selected, dtype=int)


def _dropout_ratio(audio: np.ndarray, sr: int) -> float:
    frame = max(sr // 100, 1)
    rms = _envelope_rms(audio, frame)
    if rms.size == 0:
        return 0.0
    threshold = float(np.median(rms) * 0.25)
    return float(np.count_nonzero(rms < threshold) / rms.size)


def _longest_run(mask: np.ndarray, frame_rate: float, min_s: float, max_s: float) -> tuple[float, float] | None:
    if mask.size == 0:
        return None
    min_frames = int(min_s * frame_rate)
    max_frames = int(max_s * frame_rate)
    best_len = 0
    best_start = -1
    cur_start = -1
    cur_len = 0
    for i, val in enumerate(mask):
        if val:
            if cur_start < 0:
                cur_start = i
                cur_len = 1
            else:
                cur_len += 1
        else:
            if cur_len > best_len and cur_len >= min_frames:
                best_len = cur_len
                best_start = cur_start
            cur_start = -1
            cur_len = 0
    if cur_len > best_len and cur_len >= min_frames:
        best_len = cur_len
        best_start = cur_start
    if best_start < 0:
        return None
    best_len = min(best_len, max_frames)
    start_s = best_start / frame_rate
    end_s = (best_start + best_len) / frame_rate
    return (start_s, end_s)


def build_vehicle_targets(
    vehicle_id: str,
    display_name: str,
    recordings: list[dict[str, object]],
    schema: str = "s12.reference_targets.v1",
) -> dict[str, object]:
    """Aggregate per-recording features into a vehicle reference target document.

    Each recording entry: {"id", "url", "setup", "include_in_stock_target",
    "features": <extract_reference_features output>}.

    Computes ``stock_median`` over recordings where ``include_in_stock_target`` is True.
    A recording may additionally declare ``"stock_segments": [...]`` to restrict
    which of its windows feed the aggregate -- a downshift or backfire clip has a
    meaningful ``afterfire`` window but its ``acceleration`` window is not real
    acceleration and would drag the aggregate centroid below the idle centroid.
    """
    sources = []
    for rec in recordings:
        feats = rec["features"]
        segs = feats["segments"]
        entry = {
            "id": rec["id"],
            "url": rec.get("url", ""),
            "setup": rec.get("setup", ""),
            "include_in_stock_target": rec.get("include_in_stock_target", True),
            "segments": segs,
        }
        if rec.get("stock_segments"):
            entry["stock_segments"] = list(rec["stock_segments"])
        if feats.get("segment_quality") is not None:
            entry["segment_quality"] = feats["segment_quality"]
        sources.append(entry)

    stock = [r for r in recordings if r.get("include_in_stock_target", True)]
    stock_median = _compute_stock_median(stock) if stock else {}

    return {
        "schema": schema,
        "vehicle": vehicle_id,
        "display_name": display_name,
        "note": "Derived relative metrics only; public audio remains outside the repository.",
        "provenance": _PROVENANCE,
        "boundary": "synthetic; uncalibrated; not OEM reproduction",
        "band_edges_hz": [list(e) for e in BAND_EDGES],
        "sources": sources,
        "stock_median": stock_median,
    }


def _compute_stock_median(recordings: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate the full metric set over stock-biased recordings."""

    def _contributes(r: dict[str, object], seg_field: str) -> bool:
        """True when recording ``r`` may feed segment ``seg_field`` into the median."""
        allowed = r.get("stock_segments")
        if allowed and seg_field not in allowed:
            return False
        return field_in(r["features"]["segments"], seg_field)

    def _band_median(seg_field: str) -> list[float]:
        collected = [[] for _ in BAND_EDGES]
        for r in recordings:
            segs = r["features"]["segments"]
            if _contributes(r, seg_field) and "band_shares" in segs[seg_field]:
                for i, b in enumerate(segs[seg_field]["band_shares"]):
                    collected[i].append(b)
        return [float(np.median(c)) if c else 0.0 for c in collected]

    def _scalar_median(seg_field: str, metric: str) -> float:
        vals = [r["features"]["segments"][seg_field][metric] for r in recordings
                if _contributes(r, seg_field) and metric in r["features"]["segments"][seg_field]]
        return float(np.median(vals)) if vals else 0.0

    def field_in(segs: dict, seg_field: str) -> bool:
        return seg_field in segs

    result: dict[str, object] = {}
    scalar_metrics = [
        "spectral_flux", "modulation_depth", "modulation_peak_hz", "modulation_energy",
        "pulse_amplitude_cv", "pulse_interval_cv", "crest_factor", "dropout_ratio",
        "spectral_centroid_hz", "rms_dbfs",
    ]
    for seg in ["idle", "acceleration", "afterfire"]:
        result[f"{seg}_band_shares"] = _band_median(seg)
        for m in scalar_metrics:
            result[f"{seg}_{m}"] = _scalar_median(seg, m)
    return result


def write_targets_json(targets: dict[str, object], out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the repo LF-only; the Windows default (CRLF) would make
    # `git diff --check` report trailing whitespace on every line and trip the
    # Track-P assertion (see docs/S12_TrackP_Baseline_v2.md, section 7).
    out.write_text(
        json.dumps(targets, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
