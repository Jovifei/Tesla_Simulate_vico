"""Regression guard for the codec-bandwidth gate on reference targets.

Background
----------
The recording-chain fit only checks that a clip is *self-consistent*. A clip a
lossy codec truncated at 5 kHz is perfectly self-consistent, so it passed that
check and still poisoned every band-share target it fed: because shares are
normalised, the destroyed top band reads 0.000 and the surviving bands are
inflated by ``1 / (1 - missing)``. The RX-7 acceleration target reached 93.6 %
below 250 Hz this way, which no rotary running to 8000 rpm can produce.

Three defects were fixed together and each one needs its own lock:

``A`` the gate was computed but never consulted by ``_compute_stock_median``;
``B`` the acceleration window was picked on loudness alone, so on a compilation
      clip it landed inside a truncated cut;
``C`` the idle window search relaxed its loudness margin *before* excluding
      truncated windows, so a destroyed section could buy itself back in.

Why a cliff, not a roll-off
---------------------------
The master witness is the encoder *wall*: the steepest drop across one sixth of
an octave above 3 kHz (``_spectral_cliff`` / ``assess_bandwidth``). It is the
only measurement that does not also respond to the *content*. A near-field
tailpipe microphone makes ``f99`` read 285-840 Hz and the -60 dB roll-off read
low even on a perfectly full-bandwidth recording -- gating on either rejected
97 % of healthy material in this corpus (see scripts/_diag_cliff_survey.py over
all 15 research uploads). The wall appears at the same frequency in every window
of a file the codec truncated and does not move when the engine's own spectrum
moves, so it is the property that actually separates "destroyed" from "just
low-frequency".

The decisive evidence was ``lfa_full_accel.wav``: measured over the whole file
it reaches 11 kHz and passes, yet the automatically selected acceleration
(24-28 s) and idle (80-84 s) windows both sit in sections cut near 5 kHz. That
is why the verdict has to be taken per segment *and* per file, as an AND.
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
    _CODEC_CLIFF_DROP_DB,
    _CODEC_CLIFF_FLOOR_HZ,
    _MIN_WOT_F99_HZ,
    _compute_stock_median,
    _find_physical_idle,
    _is_codec_truncated,
    _window_probe_ext,
    assess_bandwidth,
    auto_annotate_segments_with_quality,
    build_vehicle_targets,
)

SR = 22050
RNG = np.random.default_rng(20260808)

TRUNCATION_HZ = 5000.0  # what the real damaged uploads measure


# --------------------------------------------------------------------------
# signal builders
# --------------------------------------------------------------------------
def _tone_stack(duration_s: float, fundamental_hz: float, n_harmonics: int, amp: float) -> np.ndarray:
    t = np.arange(int(duration_s * SR)) / SR
    sig = np.zeros_like(t)
    for k in range(1, n_harmonics + 1):
        sig += (amp / k**1.6) * np.sin(2 * np.pi * fundamental_hz * k * t + RNG.uniform(0, 6.28))
    return sig


def _broadband(duration_s: float, amp: float) -> np.ndarray:
    return amp * RNG.standard_normal(int(duration_s * SR))


def _lowpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    """Brick-wall low-pass -- the spectral signature a truncating codec leaves."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1.0 / SR)
    spec[freqs > cutoff_hz] = 0.0
    return np.fft.irfft(spec, n=x.size)


def _wot(duration_s: float, amp: float = 0.25) -> np.ndarray:
    """Loaded engine: firing harmonics riding on broadband combustion noise."""
    return _tone_stack(duration_s, 190.0, 9, amp) + _broadband(duration_s, 0.03)


def _idle(duration_s: float, amp: float = 0.056) -> np.ndarray:
    """Idling engine: energy collapsed below 300 Hz, plus a faint broadband HF.

    The broadband component lifts the high band so the spectrum has no codec
    wall -- that is what separates "genuinely low-frequency content" from
    "content the codec destroyed". Both look identical in band shares; only the
    wall tells them apart, and the wall needs a dead band above it to exist.
    It stays at 0.004 RMS so the HF is well under 1 % of the energy: a real
    near-field tailpipe idle measures f99 at 285-840 Hz, not a flat spectrum.
    """
    return _tone_stack(duration_s, 48.0, 6, amp) + _broadband(duration_s, 0.004)


# --------------------------------------------------------------------------
# Fix A, part 1 -- the measurement itself
# --------------------------------------------------------------------------
class TestAssessBandwidth:
    def test_full_bandwidth_wot_is_accepted(self) -> None:
        verdict = assess_bandwidth(_wot(4.0), SR)
        assert verdict["spectral_shape_usable"] is True
        assert verdict["codec_truncated"] is False
        assert verdict["cliff_drop_db"] < _CODEC_CLIFF_DROP_DB
        assert verdict["f99_hz"] >= _MIN_WOT_F99_HZ

    def test_codec_truncated_wot_is_rejected(self) -> None:
        verdict = assess_bandwidth(_lowpass(_wot(4.0), TRUNCATION_HZ), SR)
        assert verdict["spectral_shape_usable"] is False
        assert verdict["codec_truncated"] is True
        assert verdict["cliff_hz"] < _CODEC_CLIFF_FLOOR_HZ
        assert verdict["cliff_drop_db"] >= _CODEC_CLIFF_DROP_DB
        assert "4-12 kHz" in verdict["reason"]

    def test_idle_is_not_condemned_for_being_low_frequency(self) -> None:
        """A near-field idle is legitimately LF-dominated; that is a recording
        property the chain-fit corrects, not codec damage to reject on."""
        idle = _idle(4.0)
        verdict = assess_bandwidth(idle, SR)
        assert verdict["spectral_shape_usable"] is True
        assert verdict["codec_truncated"] is False
        assert verdict["low_frequency_dominated"] is True
        assert verdict["f99_hz"] < _MIN_WOT_F99_HZ, "the test signal must be LF-dominated"

    def test_lowpass_idle_is_rejected_as_truncated(self) -> None:
        """The cliff is a property of the encode, so it catches a destroyed idle
        just as readily as a destroyed WOT."""
        verdict = assess_bandwidth(_lowpass(_idle(4.0), TRUNCATION_HZ), SR)
        assert verdict["spectral_shape_usable"] is False
        assert verdict["codec_truncated"] is True


# --------------------------------------------------------------------------
# Fix A, part 2 -- the gate has to reach the aggregate
# --------------------------------------------------------------------------
def _bw(ok: bool) -> dict[str, object]:
    return {
        "spectral_shape_usable": ok,
        "codec_truncated": not ok,
        "cliff_hz": 0.0 if not ok else 12000.0,
        "cliff_drop_db": 40.0 if not ok else 4.0,
        "reason": "full-bandwidth recording" if ok else "codec wall below 8 kHz",
    }


def _rec(
    rid: str,
    *,
    file_ok: bool = True,
    seg_ok: dict[str, bool] | None = None,
    accel_centroid: float = 600.0,
    accel_shares: list[float] | None = None,
    modulation: float = 0.5,
    omit_bandwidth: bool = False,
) -> dict[str, object]:
    segments: dict[str, object] = {
        "acceleration": {
            "band_shares": accel_shares or [0.30, 0.45, 0.20, 0.05],
            "spectral_centroid_hz": accel_centroid,
            "modulation_depth": modulation,
        },
        "afterfire": {
            "band_shares": [0.40, 0.40, 0.15, 0.05],
            "spectral_centroid_hz": 800.0,
            "modulation_depth": modulation,
        },
    }
    if not omit_bandwidth:
        for name, seg in segments.items():
            assert isinstance(seg, dict)
            seg["bandwidth"] = _bw((seg_ok or {}).get(name, True))
    features: dict[str, object] = {"segments": segments}
    if not omit_bandwidth:
        features["bandwidth"] = _bw(file_ok)
    return {"id": rid, "include_in_stock_target": True, "features": features}


class TestStockMedianBandwidthGate:
    def test_truncated_file_does_not_vote_on_shape(self) -> None:
        median = _compute_stock_median(
            [
                _rec("clean", accel_centroid=600.0, accel_shares=[0.30, 0.45, 0.20, 0.05]),
                _rec("truncated", file_ok=False, accel_centroid=120.0, accel_shares=[0.94, 0.05, 0.01, 0.0]),
            ]
        )
        assert median["acceleration_spectral_centroid_hz"] == pytest.approx(600.0)
        assert median["acceleration_band_shares"] == pytest.approx([0.30, 0.45, 0.20, 0.05])

    def test_without_the_gate_the_truncated_file_halves_the_centroid(self) -> None:
        """Guards the guard: proves the gate is what fixes it."""
        median = _compute_stock_median(
            [
                _rec("clean", accel_centroid=600.0),
                _rec("truncated", accel_centroid=120.0, accel_shares=[0.94, 0.05, 0.01, 0.0]),
            ]
        )
        assert median["acceleration_spectral_centroid_hz"] == pytest.approx(360.0)

    def test_section_damage_is_caught_even_when_the_file_reads_healthy(self) -> None:
        """The lfa_full_accel.wav case: 11 kHz over the file, 5 kHz in the window."""
        median = _compute_stock_median(
            [
                _rec("clean", accel_centroid=600.0),
                _rec(
                    "compilation",
                    file_ok=True,
                    seg_ok={"acceleration": False},
                    accel_centroid=120.0,
                    accel_shares=[0.94, 0.05, 0.01, 0.0],
                ),
            ]
        )
        assert median["acceleration_spectral_centroid_hz"] == pytest.approx(600.0)
        # the same recording's undamaged afterfire window must still vote
        assert median["afterfire_spectral_centroid_hz"] == pytest.approx(800.0)

    def test_a_condemned_file_condemns_its_healthy_looking_windows(self) -> None:
        """The RX-7 afterfire leak: a short window can measure a healthy roll-off
        purely because its own noise floor is high. Truncation is a property of
        the encode, so the file-level verdict is not overridable."""
        median = _compute_stock_median(
            [
                _rec(
                    "rx7_only_source",
                    file_ok=False,
                    seg_ok={"acceleration": True, "afterfire": True},
                    accel_shares=[0.95, 0.04, 0.01, 0.0],
                )
            ]
        )
        assert "afterfire_band_shares" not in median
        assert "acceleration_band_shares" not in median

    def test_absent_key_rather_than_zero_when_no_source_survives(self) -> None:
        """Zero reads downstream as "measured and found empty"; absence routes
        the state to ``physics_derived``, which is the honest answer."""
        median = _compute_stock_median([_rec("only_bad", file_ok=False)])
        assert "acceleration_band_shares" not in median
        assert "acceleration_spectral_centroid_hz" not in median
        assert median.get("acceleration_band_shares", "absent") != [0.0, 0.0, 0.0, 0.0]

    def test_time_domain_metrics_survive_truncation(self) -> None:
        """Firing pulses live below the truncation corner, so envelope statistics
        are still valid witnesses from a bandwidth-destroyed clip."""
        median = _compute_stock_median([_rec("only_bad", file_ok=False, modulation=0.42)])
        assert median["acceleration_modulation_depth"] == pytest.approx(0.42)
        assert "acceleration_spectral_flux" not in median

    def test_records_without_a_bandwidth_key_stay_usable(self) -> None:
        """Backwards compatibility with features extracted before the gate."""
        median = _compute_stock_median([_rec("legacy", omit_bandwidth=True, accel_centroid=555.0)])
        assert median["acceleration_spectral_centroid_hz"] == pytest.approx(555.0)


class TestBandwidthGateAudit:
    def test_rejections_are_reported_in_the_target_document(self) -> None:
        targets = build_vehicle_targets(
            "unit_test_car",
            "Unit Test Car",
            [_rec("clean"), _rec("truncated", file_ok=False)],
        )
        gate = targets["bandwidth_gate"]
        assert gate["cliff_floor_hz"] == _CODEC_CLIFF_FLOOR_HZ
        assert gate["cliff_drop_floor_db"] == _CODEC_CLIFF_DROP_DB
        assert [s["id"] for s in gate["shape_rejected_sources"]] == ["truncated"]
        assert "acceleration_band_shares" in gate["shape_metrics_available"]
        # the rejected source stays in the document so the decision is auditable
        rejected = next(s for s in targets["sources"] if s["id"] == "truncated")
        assert rejected["bandwidth"]["spectral_shape_usable"] is False


# --------------------------------------------------------------------------
# Fix B -- the acceleration window must be spectrally representative
# --------------------------------------------------------------------------
class TestAccelerationWindowBandwidth:
    def test_a_full_band_pull_is_preferred_over_a_truncated_one(self) -> None:
        quiet = _broadband(14.0, 0.005)
        truncated_pull = _lowpass(_wot(6.0), TRUNCATION_HZ)
        clean_pull = _wot(6.0)
        audio = np.concatenate([quiet, truncated_pull, clean_pull])

        segments, quality = auto_annotate_segments_with_quality(audio, SR)
        assert quality["acceleration"] == "energy_run_full_band"
        start, end = segments["acceleration"]
        assert start >= 19.0, (
            f"acceleration window [{start:.1f}, {end:.1f}]s reaches back into the "
            "truncated pull at 14-20 s"
        )
        _rms, _lf, _centroid, cliff_hz, cliff_drop = _window_probe_ext(
            audio[int(start * SR) : int(end * SR)], SR
        )
        assert not _is_codec_truncated(cliff_hz, cliff_drop)

    def test_a_fully_truncated_recording_still_yields_a_flagged_window(self) -> None:
        """Never drop the window silently -- label it and let the segment-level
        bandwidth record disqualify it downstream."""
        audio = np.concatenate([_broadband(14.0, 0.005), _lowpass(_wot(10.0), TRUNCATION_HZ)])
        segments, quality = auto_annotate_segments_with_quality(audio, SR)
        assert quality["acceleration"] == "energy_run_bandwidth_unverified"
        assert segments["acceleration"][1] > segments["acceleration"][0]

    def test_full_band_fraction_is_reported(self) -> None:
        audio = np.concatenate([_wot(6.0), _lowpass(_wot(6.0), TRUNCATION_HZ)])
        _segments, quality = auto_annotate_segments_with_quality(audio, SR)
        fraction = quality["acceleration_full_band_fraction"]
        assert 0.2 < fraction < 0.8, f"expected a roughly half-truncated clip, got {fraction}"


# --------------------------------------------------------------------------
# Fix C -- loudness relaxation must not buy back a destroyed window
# --------------------------------------------------------------------------
class TestIdleWindowBandwidth:
    @staticmethod
    def _clip() -> np.ndarray:
        """WOT, then a *quieter* truncated idle, then a full-band idle.

        The truncated section is deliberately the quietest part of the clip, so
        a selector that ranks on loudness alone is guaranteed to land on it --
        which is exactly what happened on lfa_full_accel.wav.
        """
        return np.concatenate([_wot(8.0), _lowpass(_idle(7.0, amp=0.035), TRUNCATION_HZ), _idle(9.0)])

    def test_truncated_idle_section_is_excluded_before_any_relaxation(self) -> None:
        audio = self._clip()
        window, detail = _find_physical_idle(audio, SR, (0.0, 8.0))

        assert window is not None, "the clip contains a valid full-band idle"
        assert detail["full_band_windows"] > 0
        assert window[0] >= 13.0, (
            f"idle window starts at {window[0]:.1f}s, inside the truncated 8-15 s section"
        )
        _rms, _lf, _centroid, cliff_hz, cliff_drop = _window_probe_ext(
            audio[int(window[0] * SR) : int(window[1] * SR)], SR
        )
        assert not _is_codec_truncated(cliff_hz, cliff_drop)

    def test_the_truncated_section_really_is_the_quieter_candidate(self) -> None:
        """Guards the guard: without the bandwidth filter, loudness ranking picks
        the damaged window."""
        audio = self._clip()
        truncated_rms, _lf, _c, truncated_cliff, truncated_drop = _window_probe_ext(
            audio[int(10.0 * SR) : int(12.0 * SR)], SR
        )
        clean_rms, _lf2, _c2, clean_cliff, clean_drop = _window_probe_ext(
            audio[int(18.0 * SR) : int(20.0 * SR)], SR
        )
        assert truncated_rms < clean_rms
        assert _is_codec_truncated(truncated_cliff, truncated_drop)
        assert not _is_codec_truncated(clean_cliff, clean_drop)

    def test_a_wholly_truncated_recording_is_annotated_not_silently_trusted(self) -> None:
        audio = np.concatenate([_lowpass(_wot(8.0), TRUNCATION_HZ), _lowpass(_idle(9.0), TRUNCATION_HZ)])
        _window, detail = _find_physical_idle(audio, SR, (0.0, 8.0))
        assert detail["full_band_windows"] == 0
        assert "bandwidth_note" in detail
