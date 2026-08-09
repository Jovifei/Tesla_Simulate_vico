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
        "bandwidth": assess_bandwidth(audio, sample_rate_hz),
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
        result["segments"][name] = _segment_metrics(
            seg, sample_rate_hz, frame_size, hop_size
        )
    return result


# --- bandwidth acceptance thresholds (see assess_bandwidth) -----------------
# A perceptual codec at low bitrate zeroes every bin above its cutoff, which
# leaves a near-vertical wall in the spectrum. That wall is the only witness of
# bandwidth destruction that does not also respond to the *content*, so it is
# the sole gate. Measured as the steepest drop across one sixth of an octave
# above _CLIFF_SEARCH_FROM_HZ.
#
# Rejected alternatives, and why (survey: scripts/_diag_cliff_survey.py over all
# 15 research uploads, 4 s windows):
#   * -60 dB roll-off < 8 kHz -- rejects 99 windows, of which only 3 carry a
#     real cliff: a 97 % false-positive rate. The corner is measured relative to
#     the window's own peak, so any window whose low band is large reads low.
#     It threw away 25 of 53 Ferrari windows and 12 of 15 RX-7 windows while the
#     encoders had in fact kept 12.3 kHz and 13.7 kHz respectively.
#   * f99 < 500 Hz -- claimed to be a physical-impossibility bound for a loaded
#     engine. It is not: a microphone at the tailpipe measures f99 = 285-840 Hz
#     on the RX-7 because exhaust pulsation dominates the near field while
#     combustion and mechanical noise radiate from further away. That is a
#     recording-chain property, and reference_reconstruction already corrects
#     for it; discarding the clip instead loses the only RX-7 source there is.
# Both remain in the record as diagnostics, neither gates.
_CLIFF_SEARCH_FROM_HZ = 3000.0
# Band 3 spans 4-12 kHz. A cut below 8 kHz removes more than half of it, so the
# band is unmeasured rather than measured-as-zero.
_CODEC_CLIFF_FLOOR_HZ = 8000.0
# Natural spectral roll-off in this corpus stays under ~15 dB per sixth octave;
# the confirmed codec walls measure 21-23 dB.
_CODEC_CLIFF_DROP_DB = 18.0
# Retained for the diagnostic flag only -- see the note above.
_MIN_WOT_F99_HZ = 500.0
_BANDWIDTH_NFFT = 8192
# Resolution of the short-time bandwidth mask. Codec truncation changes at edit
# points in a compilation, not frame by frame, so one second is ample -- and it
# must stay above _BANDWIDTH_NFFT samples at every supported sample rate.
_BANDWIDTH_BLOCK_S = 1.0
_CLIFF_OCTAVE_RATIO = 2.0 ** (1.0 / 6.0)
_CLIFF_SMOOTH_HALFWIDTH = 3

# --- idle acceptance thresholds (see _find_physical_idle) -------------------
_IDLE_SILENCE_DBFS = -55.0      # below this a window is digital silence, not engine
_IDLE_LF_SHARE_MIN = 0.45       # 20-250 Hz must dominate a true idle window
_IDLE_LF_SHARE_RELAXED = 0.40   # last-resort relaxation
_IDLE_LOUD_MARGINS_DB = (8.0, 5.0, 3.0, 1.0)  # progressive relaxation vs loud P90
_IDLE_PROBE_WIN_S = 2.0
_IDLE_PROBE_HOP_S = 0.5


def _spectral_cliff(freqs: np.ndarray, power: np.ndarray) -> tuple[float, float]:
    """Steepest drop across one sixth of an octave above :data:`_CLIFF_SEARCH_FROM_HZ`.

    Returns ``(cliff_hz, drop_db)`` where ``cliff_hz`` is the frequency the drop
    starts from. A lossy encoder that discards everything above its cutoff
    produces a wall here; natural spectral roll-off does not, because it is
    spread over octaves rather than concentrated in one sixth of one.
    """
    if freqs.size == 0:
        return 0.0, 0.0
    db = 10.0 * np.log10(np.maximum(power, 1e-30))
    width = 2 * _CLIFF_SMOOTH_HALFWIDTH + 1
    if db.size >= width:
        db = np.convolve(db, np.ones(width) / width, mode="same")
    lo_idx = np.where(freqs >= _CLIFF_SEARCH_FROM_HZ)[0]
    if lo_idx.size == 0:
        return 0.0, 0.0
    hi_idx = np.searchsorted(freqs, freqs[lo_idx] * _CLIFF_OCTAVE_RATIO)
    keep = hi_idx < freqs.size
    lo_idx, hi_idx = lo_idx[keep], hi_idx[keep]
    if lo_idx.size == 0:
        return 0.0, 0.0
    drops = db[lo_idx] - db[hi_idx]
    best = int(np.argmax(drops))
    return float(freqs[lo_idx[best]]), float(drops[best])


def _is_codec_truncated(cliff_hz: float, drop_db: float) -> bool:
    """A wall steep enough to be an encoder, low enough to eat into band 3."""
    return bool(cliff_hz < _CODEC_CLIFF_FLOOR_HZ and drop_db >= _CODEC_CLIFF_DROP_DB)


def _unmeasurable_bandwidth(reason: str) -> dict[str, object]:
    """Verdict for a clip the measurement cannot be run on at all.

    Unusable rather than usable: a window too short or too quiet to analyse has
    not been shown to be intact, and letting it set a spectral target would be
    asserting something never measured.
    """
    return {
        "spectral_shape_usable": False,
        "codec_truncated": False,
        "low_frequency_dominated": False,
        "cliff_hz": 0.0,
        "cliff_drop_db": 0.0,
        "f99_hz": 0.0,
        "rolloff_hi_hz": 0.0,
        "cliff_floor_hz": _CODEC_CLIFF_FLOOR_HZ,
        "cliff_drop_floor_db": _CODEC_CLIFF_DROP_DB,
        "f99_diagnostic_floor_hz": _MIN_WOT_F99_HZ,
        "reason": reason,
    }


def assess_bandwidth(audio: np.ndarray, sample_rate_hz: int) -> dict[str, object]:
    """Decide whether a recording can legitimately describe a spectral shape.

    Why this gate exists
    --------------------
    The recording-chain fit only checks that a clip is *self-consistent*. A clip
    that a lossy codec truncated at 4.4 kHz is perfectly self-consistent, so it
    sails through that check and still poisons every band-share target it feeds:
    because shares are normalised, the destroyed top band reads 0.000 and the
    surviving bands are inflated by 1/(1 - missing).

    What is measured
    ----------------
    ``cliff_hz`` / ``cliff_drop_db`` -- the encoder wall, via
    :func:`_spectral_cliff`. This is the only gate. It is a property of the
    *encode*: it appears at the same frequency in every window of a file the
    codec truncated, and it does not move when the engine's own spectrum moves.

    ``f99_hz`` and ``rolloff_hi_hz`` are still reported, but as diagnostics
    only. Both respond to content: they read low on any clip whose low band is
    large, which describes a tailpipe-adjacent microphone just as well as a
    destroyed encode. Gating on them rejected 97 % of healthy material in this
    corpus -- see the note beside :data:`_CODEC_CLIFF_FLOOR_HZ`. The near-field
    tilt they detect is real and is corrected in ``reference_reconstruction``
    by the recording-chain fit, which is where it belongs.

    Args:
        audio: mono float signal.
        sample_rate_hz: sample rate in Hz.

    Returns:
        A record with the measurements, the verdict flags and a human-readable
        ``reason``. ``spectral_shape_usable`` is the field callers should gate
        on before letting the clip set a band-share or centroid target;
        temporal features (modulation rate, pulse statistics) live in the low
        band and survive truncation, so they are deliberately not gated here.
    """
    x = np.asarray(audio, dtype=np.float64)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= 0.0 or x.size < _BANDWIDTH_NFFT:
        return _unmeasurable_bandwidth("clip too short or silent to measure bandwidth")
    x = x / peak

    nfft = _BANDWIDTH_NFFT
    hop = nfft // 2
    win = np.hanning(nfft)
    acc = np.zeros(nfft // 2 + 1)
    used = 0
    for start in range(0, x.size - nfft + 1, hop):
        acc += np.square(np.abs(np.fft.rfft(x[start : start + nfft] * win)))
        used += 1
    acc /= max(used, 1)
    freqs = np.fft.rfftfreq(nfft, 1.0 / sample_rate_hz)

    band = (freqs >= 20.0) & (freqs <= min(20000.0, sample_rate_hz / 2 - 1))
    f, p = freqs[band], acc[band]
    total = float(p.sum())
    if total <= 0.0:
        return _unmeasurable_bandwidth("no energy in the 20 Hz-20 kHz analysis range")

    cumulative = np.cumsum(p) / total
    f99 = float(f[min(int(np.searchsorted(cumulative, 0.99)), f.size - 1)])
    db = 10.0 * np.log10(np.maximum(p, 1e-30) / p.max())
    above = np.where(db > -60.0)[0]
    rolloff_hi = float(f[above[-1]]) if above.size else 0.0
    cliff_hz, cliff_drop = _spectral_cliff(f, p)

    truncated = _is_codec_truncated(cliff_hz, cliff_drop)
    low_frequency_dominated = f99 < _MIN_WOT_F99_HZ
    if truncated:
        reason = (
            f"{cliff_drop:.0f} dB wall across 1/6 octave at {cliff_hz:.0f} Hz "
            f"(< {_CODEC_CLIFF_FLOOR_HZ:.0f} Hz): the encoder discarded most of "
            "the 4-12 kHz band"
        )
    elif low_frequency_dominated:
        reason = (
            f"full-bandwidth recording (cliff {cliff_hz:.0f} Hz); note 99% of "
            f"energy sits below {f99:.0f} Hz -- near-field bias for the "
            "recording-chain fit to remove, not codec damage"
        )
    else:
        reason = f"full-bandwidth recording (cliff {cliff_hz:.0f} Hz)"
    return {
        "spectral_shape_usable": not truncated,
        "codec_truncated": bool(truncated),
        "low_frequency_dominated": bool(low_frequency_dominated),
        "cliff_hz": round(cliff_hz, 1),
        "cliff_drop_db": round(cliff_drop, 1),
        "f99_hz": round(f99, 1),
        "rolloff_hi_hz": round(rolloff_hi, 1),
        "cliff_floor_hz": _CODEC_CLIFF_FLOOR_HZ,
        "cliff_drop_floor_db": _CODEC_CLIFF_DROP_DB,
        "f99_diagnostic_floor_hz": _MIN_WOT_F99_HZ,
        "reason": reason,
    }


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

    loud = rms > 1.3 * median_rms
    full_band = _full_band_frame_mask(audio, sample_rate_hz, frame_rate, rms.size)

    # A window may only set a spectral target if its spectrum was actually
    # captured. Preferring loud-AND-full-band keeps the selector out of the
    # truncated sub-sections of compilation clips; the plain loud run stays as
    # a fallback so a fully truncated recording still yields a window (its
    # segment-level bandwidth record then disqualifies it downstream).
    accel_win = _longest_run(loud & full_band, frame_rate, 3.0, 25.0)
    accel_verdict = "energy_run_full_band"
    if accel_win is None:
        accel_win = _longest_run(loud, frame_rate, 3.0, 25.0)
        accel_verdict = "energy_run_bandwidth_unverified"
    after_win = _longest_run(flux > flux_median + 1.5 * flux_std, frame_rate, 2.0, 20.0) if flux.size else None

    duration = audio.size / sample_rate_hz
    if accel_win is None:
        accel_win = (max(0.0, duration * 0.4), min(duration, duration * 0.7))
        accel_verdict = "fallback_mid_clip"
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
        "acceleration": accel_verdict,
        "acceleration_full_band_fraction": round(float(np.mean(full_band)), 4),
        "afterfire": "flux_cluster",
    }
    return {k: (float(v[0]), float(v[1])) for k, v in segments.items()}, quality


def _full_band_frame_mask(
    audio: np.ndarray, sr: int, frame_rate: float, n_frames: int
) -> np.ndarray:
    """Per-RMS-frame mask: True where the local spectrum shows no codec wall.

    Evaluated on coarse blocks (an FFT per block is plenty -- codec truncation
    changes on the scale of an edit point, not a frame) and then broadcast onto
    the RMS frame grid. A block is "full band" when :func:`_is_codec_truncated`
    is False on it.
    """
    block = int(_BANDWIDTH_BLOCK_S * sr)
    if block < _BANDWIDTH_NFFT or audio.size < block:
        return np.ones(n_frames, dtype=bool)
    n_blocks = audio.size // block
    corners = np.zeros(n_blocks)
    drops = np.zeros(n_blocks)
    for i in range(n_blocks):
        seg = audio[i * block : (i + 1) * block]
        _rms, _lf, _centroid, corners[i], drops[i] = _window_probe_ext(seg, sr)
    truncated = np.array(
        [_is_codec_truncated(c, d) for c, d in zip(corners, drops)], dtype=bool
    )
    index = np.clip(
        (np.arange(n_frames) / max(frame_rate, 1e-9) / _BANDWIDTH_BLOCK_S).astype(int),
        0,
        n_blocks - 1,
    )
    return ~truncated[index]


def _window_probe_ext(seg: np.ndarray, sr: int) -> tuple[float, float, float, float, float]:
    """Return (rms_dbfs, low_band_share, spectral_centroid_hz, cliff_hz, cliff_drop_db).

    The cliff is the encoder-wall witness (see :func:`_spectral_cliff` /
    :func:`assess_bandwidth`): the steepest drop across one sixth of an octave
    above 3 kHz. A bandwidth-destroyed sub-section of a compilation file shows a
    wall here even when the file as a whole reads healthy, so it is what the
    window selectors use to stay out of truncated cuts.
    """
    freqs, energy = _mean_stft_energy(seg, sr, 4096, 1024)
    total = float(energy.sum()) or 1e-15
    lf_share = _band_fraction(energy, freqs, *BAND_EDGES[0])
    centroid = float(np.sum(freqs * energy) / total)
    rms = float(np.sqrt(np.mean(np.square(seg))))
    cliff_hz, cliff_drop = _spectral_cliff(freqs, energy)
    return (
        20.0 * math.log10(max(rms, 1e-15)),
        lf_share,
        centroid,
        float(cliff_hz),
        float(cliff_drop),
    )


def _window_probe(seg: np.ndarray, sr: int) -> tuple[float, float, float]:
    """Return (rms_dbfs, low_band_share, spectral_centroid_hz) for one window."""
    rms_db, lf_share, centroid, _cliff_hz, _cliff_drop = _window_probe_ext(seg, sr)
    return rms_db, lf_share, centroid


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

    # (t, rms_db, lf, centroid, cliff_hz, cliff_drop_db)
    probes: list[tuple[float, float, float, float, float, float]] = []
    for start in range(0, audio.size - win + 1, hop):
        seg = audio[start : start + win]
        rms_db, lf, centroid, cliff_hz, cliff_drop = _window_probe_ext(seg, sr)
        probes.append((start / sr, rms_db, lf, centroid, cliff_hz, cliff_drop))
    if not probes:
        return None, detail

    audible = [p for p in probes if p[1] > _IDLE_SILENCE_DBFS]
    detail["probe_windows"] = len(probes)
    detail["audible_windows"] = len(audible)
    if not audible:
        return None, detail
    loud_p90 = float(np.percentile([p[1] for p in audible], 90))
    detail["loud_p90_dbfs"] = round(loud_p90, 1)

    # A truncated window is disqualified before any of the loudness relaxations
    # run: relaxing the margin must never be able to buy back a window whose
    # spectrum was destroyed. On lfa_full_accel.wav the quietest idle-looking
    # windows sit in the tail section that is cut at 5 kHz, and that is exactly
    # where the old selector landed.
    full_band_audible = [p for p in audible if not _is_codec_truncated(p[4], p[5])]
    detail["full_band_windows"] = len(full_band_audible)
    if full_band_audible:
        audible = full_band_audible
    else:
        detail["bandwidth_note"] = (
            "no audible window escapes a codec wall (see _is_codec_truncated); "
            "idle spectrum is bandwidth-limited throughout this recording"
        )

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
    hits: list[tuple[float, float, float, float, float, float]],
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


def _segment_metrics(
    seg: np.ndarray, sr: int, frame: int, hop: int
) -> dict[str, object]:
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
        # Per-segment, not per-file: the references are compilation clips whose
        # sub-sections come from different uploads. lfa_full_accel.wav measures
        # 11 kHz over the whole file yet its selected idle and acceleration
        # windows both sit in sections truncated near 5 kHz.
        "bandwidth": assess_bandwidth(seg, sr),
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
    shape_rejected = []
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
        bandwidth = feats.get("bandwidth")
        if isinstance(bandwidth, Mapping):
            entry["bandwidth"] = dict(bandwidth)
            if not bandwidth.get("spectral_shape_usable", True):
                shape_rejected.append({"id": rec["id"], "reason": bandwidth.get("reason", "")})
        sources.append(entry)

    stock = [r for r in recordings if r.get("include_in_stock_target", True)]
    stock_median = _compute_stock_median(stock) if stock else {}

    targets: dict[str, object] = {
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
    # Auditability: a missing *_band_shares key must be traceable to a stated
    # reason, never look like an extraction that silently forgot to run.
    targets["bandwidth_gate"] = {
        "f99_diagnostic_floor_hz": _MIN_WOT_F99_HZ,
        "cliff_floor_hz": _CODEC_CLIFF_FLOOR_HZ,
        "cliff_drop_floor_db": _CODEC_CLIFF_DROP_DB,
        "shape_rejected_sources": shape_rejected,
        "shape_metrics_available": sorted(
            key for key in stock_median
            if key.endswith("_band_shares") or key.endswith("_spectral_centroid_hz")
        ),
    }
    return targets


# Metrics that describe *where in frequency* the energy sits. A codec-truncated
# recording reports these as confident numbers that are in fact artefacts: the
# destroyed top bands normalise to ~0 and inflate the surviving low band by
# 1/(1-missing). They must not vote on the aggregate.
_SHAPE_METRICS = frozenset({"spectral_centroid_hz", "spectral_flux"})
# Everything else is a time-domain / envelope statistic. Low-frequency
# modulation, pulse regularity and crest factor survive a low-pass intact
# (the firing pulses that carry them live below the truncation corner), so a
# bandwidth-destroyed clip is still a valid witness for those.


def _compute_stock_median(recordings: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate the full metric set over stock-biased recordings.

    Two independent gates decide whether a recording votes on a given metric:

    * ``stock_segments`` -- a *segment* gate. A downshift clip has a real
      afterfire window but no real acceleration window.
    * ``bandwidth.spectral_shape_usable`` -- a *metric-class* gate. A
      codec-truncated clip is excluded from :data:`_SHAPE_METRICS` and from
      ``band_shares``, but still votes on the time-domain metrics.

    When no recording is left to supply a shape metric the key is **omitted**
    rather than written as zero. Zero would be read downstream as "measured and
    found empty"; absence is read by
    ``reference_reconstruction.available_reference_segments`` as "no reference
    for this segment", which is what routes the state to ``physics_derived``.
    """

    def _verdict(record: object) -> bool:
        if not isinstance(record, Mapping):
            return True  # feature dicts extracted before the gate existed
        return bool(record.get("spectral_shape_usable", True))

    def _shape_usable(r: dict[str, object], seg_field: str) -> bool:
        """Both the file-level and the segment-level verdict must pass.

        They catch different damage and neither subsumes the other. Codec
        truncation is a property of the *encode*, so a condemned file condemns
        every window inside it -- a short window can measure a healthy roll-off
        simply because its own noise floor is high enough to keep the -60 dB
        corner up. Section-level damage is the converse: a compilation can be
        healthy overall while the selected window sits in a truncated cut.
        """
        segment = r["features"]["segments"].get(seg_field)
        segment_ok = True
        if isinstance(segment, Mapping):
            segment_ok = _verdict(segment.get("bandwidth"))
        return _verdict(r["features"].get("bandwidth")) and segment_ok

    def _contributes(r: dict[str, object], seg_field: str, *, shape: bool) -> bool:
        """True when recording ``r`` may feed segment ``seg_field`` into the median."""
        allowed = r.get("stock_segments")
        if allowed and seg_field not in allowed:
            return False
        if shape and not _shape_usable(r, seg_field):
            return False
        return seg_field in r["features"]["segments"]

    def _band_median(seg_field: str) -> list[float] | None:
        collected: list[list[float]] = [[] for _ in BAND_EDGES]
        for r in recordings:
            segs = r["features"]["segments"]
            if _contributes(r, seg_field, shape=True) and "band_shares" in segs[seg_field]:
                for i, b in enumerate(segs[seg_field]["band_shares"]):
                    collected[i].append(b)
        if not any(collected):
            return None
        return [float(np.median(c)) if c else 0.0 for c in collected]

    def _scalar_median(seg_field: str, metric: str) -> float | None:
        shape = metric in _SHAPE_METRICS
        vals = [
            r["features"]["segments"][seg_field][metric]
            for r in recordings
            if _contributes(r, seg_field, shape=shape)
            and metric in r["features"]["segments"][seg_field]
        ]
        return float(np.median(vals)) if vals else None

    result: dict[str, object] = {}
    scalar_metrics = [
        "spectral_flux", "modulation_depth", "modulation_peak_hz", "modulation_energy",
        "pulse_amplitude_cv", "pulse_interval_cv", "crest_factor", "dropout_ratio",
        "spectral_centroid_hz", "rms_dbfs",
    ]
    for seg in ["idle", "acceleration", "afterfire"]:
        shares = _band_median(seg)
        if shares is not None:
            result[f"{seg}_band_shares"] = shares
        for m in scalar_metrics:
            value = _scalar_median(seg, m)
            if value is not None:
                result[f"{seg}_{m}"] = value
    return result


def write_targets_json(targets: dict[str, object], out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the repo LF-only; the Windows default (CRLF) would make
    # `git diff --check` report trailing whitespace on every line and trip the
    # Track-P assertion (see docs/S12_TrackP_Baseline_v3.md).
    out.write_text(
        json.dumps(targets, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
