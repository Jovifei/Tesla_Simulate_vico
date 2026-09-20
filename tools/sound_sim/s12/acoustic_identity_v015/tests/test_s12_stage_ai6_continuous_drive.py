"""Stage AI-6 governed continuous-drive contracts.

These orchestration fixtures use a deterministic fake engine; real 30-second
renders are exercised separately with the current RemainingVehicleEngine.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import continuous_drive as cycle


def _safe_peak_receipt():
    return {
        "schema": "s12.stage_ai.reconstruction_peak_receipt.v1",
        "sample_rate_hz": 48_000,
        "frame_count": 64,
        "channels": 2,
        "sample_peak": 0.2,
        "threshold": 1.0,
        "factors": {
            str(factor): {"factor": factor, "peak": 0.2,
                          "channel": 0, "upsampled_index": 0,
                          "time_s": 0.0, "exceedance_count": 0}
            for factor in (4, 8, 16)
        },
        "factor_order": [4, 8, 16], "worst_factor": 4, "worst_peak": 0.2,
        "status": "PASS",
        "method": "scipy.signal.resample_poly; kaiser beta 5; line boundary",
        "domain": "FINAL_DECODED_PCM_FLOAT",
        "standard": "ENGINEERING_DIAGNOSTIC_NOT_ITU_EBU_CERTIFIED",
        "audio_modified": False,
    }


class _FakeEngine:
    calls = []

    def __init__(self, vehicle_type, sr, *, output_policy, parent_peaks=None,
                 ir=None, seed=0, scene_ids=(), boundary_policy=None):
        self.vehicle_type = vehicle_type
        self.sr = sr
        self.output_policy = output_policy
        self.parent_peaks = dict(parent_peaks or {})
        self.ir = np.asarray(ir if ir is not None else [0.9, 0.02], dtype=np.float64)
        self.seed = seed
        self.scene_ids = tuple(scene_ids)
        self.boundary_policy = boundary_policy
        self.feedback = {"parameters": {
            "rotary_pulse_width_scale": 1.0,
            "primary_spool_tau_s": 0.16,
            "blow_off_gain_scale": 1.1,
        }}
        self.reports = []
        self.calls.append(self)

    def render_track(self, rpm, throttle, duration, shift_events=None,
                     afterfire_events=None, bov_events=None):
        count = int(round(self.sr * duration))
        pcm = np.full((count, 2), 6000, dtype=np.int16)
        trace = hashlib.sha256(np.asarray(rpm, dtype=np.float64).tobytes()).hexdigest()
        key = f"{self.scene_ids[0]}|{trace}"
        self.parent_peaks.setdefault(key, 0.4)
        report = {
            "vehicle": self.vehicle_type, "scene_id": self.scene_ids[0],
            "trace_sha256": trace, "seed": self.seed, "flags": [],
            "parent_peak_key": key, "parent_peak": self.parent_peaks[key],
            "candidate_raw_peak": 0.2,
            "normalization_denominator": self.parent_peaks[key],
            "output_policy": self.output_policy, "sample_rate_hz": self.sr,
            "sample_count": count, "final_peak": 6000 / 32767,
            "final_rms": 6000 / 32767, "final_pcm_sha256": hashlib.sha256(
                np.ascontiguousarray(pcm, dtype="<i2").tobytes()).hexdigest(),
            "normalization": {
                "output_policy": self.output_policy,
                "normalization_denominator": self.parent_peaks[key],
                "legacy_ceiling_input_exceedance_samples": 0,
                "pre_guard_exceedance_longest_run": 0,
                "legacy_transfer_pre_guard_peak": 0.2,
                "pre_guard_peak": 0.2, "soft_guard_delta_peak": 0.0,
                "soft_guard_delta_rms": 0.0, "post_guard_peak": 6000 / 32767,
                "post_guard_ceiling_exceedance_samples": 0,
                "emergency_clip_count": 0, "emergency_clip_error": 0.0,
                "emergency_clip_error_rms": 0.0,
                "frame_count": count, "soft_guard_active_frames": 0,
            },
            "identity_layer_clip_count": 0, "identity_layer_clip_error": 0.0,
            "post_identity_clip_count": 0, "post_identity_clip_error": 0.0,
            "peak_estimate_4x": {"peak": 0.2},
            "reconstruction_peak": _safe_peak_receipt(),
            "boundary_repair": {"policy_id": self.boundary_policy,
                                "fade_frames": 24 if self.boundary_policy else 0,
                                "modified_frames": 24 if self.boundary_policy else 0},
            "candidate_source_diagnostics": {
                "shift_event_count": len(shift_events or []),
                "afterfire_event_count": len(afterfire_events or []),
                "afterfire_stem_energy_after_lift": 1.0,
                "afterfire_event_times_s": [18.0] if afterfire_events else [],
            },
        }
        self.reports.append(report)
        return pcm


def test_fixed_trace_has_three_shifts_and_one_lift_event():
    trace = cycle.build_continuous_trace("rx7_fd")
    assert len(trace.time_s) == 1_440_001
    events = cycle.continuous_events()
    assert len(events["shift_events"]) == 3
    assert events["afterfire_events"] == [{"time_s": 18.0, "kind": "closed_throttle_lift"}]


def test_pair_uses_one_full_render_per_role_and_shared_context(monkeypatch):
    _FakeEngine.calls = []
    monkeypatch.setattr(cycle, "RemainingVehicleEngine", _FakeEngine)
    monkeypatch.setattr(cycle, "reconstructed_peak_receipt", lambda audio, **_: _safe_peak_receipt())
    selected = {"rotary_pulse_width_scale": 1.15,
                "primary_spool_tau_s": 0.16,
                "blow_off_gain_scale": 1.1}
    pair = cycle.render_continuous_pair("rx7_fd", selected,
                                        boundary_policy="rx7_start_boundary_fade_v1")
    assert len(_FakeEngine.calls) == 3  # A, B, and the explicit feedback-off rerender
    assert all(len(engine.reports) == 1 for engine in _FakeEngine.calls)
    assert pair["pcm_a"].shape == pair["pcm_b"].shape == (1_440_000, 2)
    assert pair["receipt"]["events"]["shift_count"] == 3
    assert pair["receipt"]["events"]["afterfire_event_count"] == 1
    assert pair["receipt"]["shared"]["seed"] == 20260908
    assert pair["receipt"]["shared"]["parent_peak_key"] == pair["report_a"]["parent_peak_key"]
    assert _FakeEngine.calls[1].parent_peaks == _FakeEngine.calls[0].parent_peaks
    assert np.array_equal(pair["pcm_a"], pair["pcm_off_switch"])
    assert pair["receipt"]["boundary"]["policy_id"] == "rx7_start_boundary_fade_v1"


def test_aventador_does_not_accept_rx7_boundary_policy():
    with pytest.raises(ValueError, match="boundary"):
        cycle.render_continuous_pair("aventador_lp700", {}, boundary_policy="rx7_start_boundary_fade_v1")


def test_continuous_pair_rejects_wrong_duration(monkeypatch):
    monkeypatch.setattr(cycle, "RemainingVehicleEngine", _FakeEngine)
    with pytest.raises(ValueError, match="30 seconds"):
        cycle.render_continuous_pair("rx7_fd", {}, duration_s=29.0)


def test_renderer_diagnostics_are_required_for_shift_and_afterfire(monkeypatch):
    class _BrokenEngine(_FakeEngine):
        def render_track(self, *args, **kwargs):
            pcm = super().render_track(*args, **kwargs)
            self.reports[-1]["candidate_source_diagnostics"]["afterfire_event_count"] = 0
            return pcm

    monkeypatch.setattr(cycle, "RemainingVehicleEngine", _BrokenEngine)
    monkeypatch.setattr(cycle, "reconstructed_peak_receipt", lambda audio, **_: _safe_peak_receipt())
    with pytest.raises(ValueError, match="afterfire diagnostics"):
        cycle.render_continuous_pair(
            "rx7_fd", {"rotary_pulse_width_scale": 1.15},
            boundary_policy="rx7_start_boundary_fade_v1",
        )


def test_writer_rejects_missing_full_report_evidence(tmp_path):
    pcm = np.zeros((8, 2), dtype=np.int16)
    with pytest.raises(ValueError, match="30-second stereo|report evidence"):
        cycle.write_continuous_pair(tmp_path, {
            "pcm_a": pcm, "pcm_b": pcm,
            "receipt": {"schema": cycle.CONTINUOUS_SCHEMA, "vehicle": "rx7_fd"},
        })
