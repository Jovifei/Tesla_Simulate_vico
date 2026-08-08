"""Regression guard for physically-valid idle segmentation.

Background
----------
The original ``auto_annotate_segments`` labelled the lowest-energy stable run as
"idle" and fell back to the first 8 s of the clip when that failed. On
``*_accel.wav`` compilation recordings the quietest region is digital silence at
the file head or wind / gap noise between pulls, so five of eight vehicles ended
up with an idle target whose spectral centroid sat *above* the wide-open-throttle
centroid -- impossible for a reciprocating engine.

The damage was measurable: the Ferrari 458 idle target was 980 Hz with 0.9 % of
its energy below 250 Hz, and the LFA synthesiser was tuned to an idle centroid of
1366 Hz, matching the poisoned reference value of 1365.65 Hz almost exactly.

These tests pin the corrected behaviour so the failure mode cannot return.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "acoustic_analysis"
if str(_ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_DIR))

from reference_feature_extractor import (  # noqa: E402
    BAND_EDGES,
    _compute_stock_median,
    _find_physical_idle,
    auto_annotate_segments,
    auto_annotate_segments_with_quality,
)

SR = 22050
RNG = np.random.default_rng(20260808)


def _tone_stack(duration_s: float, fundamental_hz: float, n_harmonics: int, amp: float) -> np.ndarray:
    """Low-frequency dominated harmonic stack, i.e. what an idling engine looks like."""
    t = np.arange(int(duration_s * SR)) / SR
    sig = np.zeros_like(t)
    for k in range(1, n_harmonics + 1):
        sig += (amp / k**1.6) * np.sin(2 * np.pi * fundamental_hz * k * t + RNG.uniform(0, 6.28))
    return sig


def _broadband(duration_s: float, amp: float) -> np.ndarray:
    """Wind / gap noise: broadband, so its centroid is high despite low energy."""
    return amp * RNG.standard_normal(int(duration_s * SR))


def _synthetic_clip() -> np.ndarray:
    """Digital silence -> quiet wind noise -> true idle -> wide-open throttle."""
    silence = np.zeros(int(3.0 * SR))
    wind = _broadband(5.0, 0.010)                       # quietest audible part, high centroid
    idle = _tone_stack(6.0, 48.0, 6, 0.055)             # low-frequency dominated
    wot = _tone_stack(8.0, 190.0, 9, 0.30) + _broadband(8.0, 0.02)
    return np.concatenate([silence, wind, idle, wot]).astype(np.float64)


IDLE_START_S = 8.0
IDLE_END_S = 14.0


class TestPhysicalIdleSelection:
    def test_idle_lands_on_the_engine_not_the_silence_or_wind(self) -> None:
        audio = _synthetic_clip()
        segments, quality = auto_annotate_segments_with_quality(audio, SR)

        assert "idle" in segments, "a valid idle window exists in this clip"
        start, end = segments["idle"]
        midpoint = 0.5 * (start + end)
        assert IDLE_START_S <= midpoint <= IDLE_END_S, (
            f"idle midpoint {midpoint:.2f}s fell outside the true idle region "
            f"[{IDLE_START_S}, {IDLE_END_S}] -- it likely latched onto silence or wind noise"
        )
        assert quality["idle"] in {"physical", "relaxed"}

    def test_idle_never_falls_back_to_the_clip_head(self) -> None:
        """The old code used (0.0, min(8.0, duration*0.25)) as a fallback."""
        audio = _synthetic_clip()
        segments = auto_annotate_segments(audio, SR)
        start, _end = segments["idle"]
        assert start > 3.0, "idle must not start inside the leading digital silence"

    def test_idle_centroid_stays_below_acceleration_centroid(self) -> None:
        """Spectral monotonicity with load -- the physical invariant that was violated."""
        from reference_feature_extractor import _window_probe

        audio = _synthetic_clip()
        segments = auto_annotate_segments(audio, SR)
        centroids = {}
        for name in ("idle", "acceleration"):
            s, e = segments[name]
            seg = audio[int(s * SR) : int(e * SR)]
            _rms, _lf, centroids[name] = _window_probe(seg, SR)
        assert centroids["idle"] < centroids["acceleration"], (
            f"idle centroid {centroids['idle']:.0f} Hz must stay below acceleration "
            f"centroid {centroids['acceleration']:.0f} Hz"
        )

    def test_idle_window_is_low_frequency_dominated(self) -> None:
        from reference_feature_extractor import _window_probe

        audio = _synthetic_clip()
        segments = auto_annotate_segments(audio, SR)
        s, e = segments["idle"]
        _rms, lf_share, _centroid = _window_probe(audio[int(s * SR) : int(e * SR)], SR)
        assert lf_share >= 0.40, f"idle low-band share {lf_share:.3f} is too small for an idling engine"


class TestIdleUnavailable:
    def test_pure_broadband_clip_reports_unavailable_instead_of_faking_idle(self) -> None:
        """A clip with no idle in it must omit the segment, not invent one."""
        loud = _broadband(6.0, 0.30)
        louder = _broadband(6.0, 0.45)
        audio = np.concatenate([loud, louder])
        segments, quality = auto_annotate_segments_with_quality(audio, SR)
        assert quality["idle"] == "unavailable"
        assert "idle" not in segments, "no idle metrics may be emitted for a clip without idle"
        assert "reason" in quality["idle_detail"]

    def test_digital_silence_is_never_selected(self) -> None:
        silence = np.zeros(int(6.0 * SR))
        engine = _tone_stack(8.0, 190.0, 9, 0.30)
        audio = np.concatenate([silence, engine])
        window, detail = _find_physical_idle(audio, SR, (6.0, 14.0))
        if window is not None:
            assert window[0] >= 6.0 - 1e-6, "selected window overlaps digital silence"
        assert detail["audible_windows"] < detail["probe_windows"]


class TestStockMedianSegmentScoping:
    @staticmethod
    def _rec(rid: str, accel_centroid: float, stock_segments: list[str] | None = None) -> dict:
        rec: dict = {
            "id": rid,
            "include_in_stock_target": True,
            "features": {
                "segments": {
                    "acceleration": {
                        "band_shares": [0.3, 0.5, 0.15, 0.05],
                        "spectral_centroid_hz": accel_centroid,
                    },
                    "afterfire": {
                        "band_shares": [0.4, 0.4, 0.15, 0.05],
                        "spectral_centroid_hz": 800.0,
                    },
                }
            },
        }
        if stock_segments is not None:
            rec["stock_segments"] = stock_segments
        return rec

    def test_downshift_clip_can_be_excluded_from_the_accel_median(self) -> None:
        """A downshift clip has no real acceleration window and must not vote."""
        recs = [
            self._rec("real_accel", 600.0),
            self._rec("downshift", 90.0, stock_segments=["idle", "afterfire"]),
        ]
        median = _compute_stock_median(recs)
        assert median["acceleration_spectral_centroid_hz"] == pytest.approx(600.0), (
            "the excluded downshift clip still dragged the acceleration centroid down"
        )
        # it must still contribute to afterfire
        assert median["afterfire_spectral_centroid_hz"] == pytest.approx(800.0)

    def test_without_scoping_the_downshift_clip_does_pollute(self) -> None:
        """Guards the guard: proves the scoping is what fixes it."""
        recs = [self._rec("real_accel", 600.0), self._rec("downshift", 90.0)]
        median = _compute_stock_median(recs)
        assert median["acceleration_spectral_centroid_hz"] == pytest.approx(345.0)


class TestBandEdgesContract:
    def test_band_edges_unchanged(self) -> None:
        assert BAND_EDGES == [(20.0, 250.0), (250.0, 1000.0), (1000.0, 4000.0), (4000.0, 12000.0)]
