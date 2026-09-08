from __future__ import annotations

import json

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.render_identity_probe_r1 import (
    render_probe_r1,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.vehicle_identity import (
    VEHICLE_IDENTITY_PROFILES,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.vehicle_identity_r1 import (
    IDENTITY_MODE_LEGACY,
    IDENTITY_MODE_V1R1,
    R1_CONTROLS,
    VehicleIdentityR1Engine,
    _state_envelope,
    synthesize_vehicle_identity_layer_r1,
    vehicle_identity_r1_signature,
)


def _identity_ir(*args, **kwargs):
    return np.asarray([1.0], dtype=np.float64)


def _trace(rpm: float, throttle: float, duration: float = 0.18, sr: int = 48_000):
    n = int(duration * sr)
    return (
        np.full(n, rpm, dtype=np.float64),
        np.full(n, throttle, dtype=np.float64),
        duration,
    )


def test_r1_signature_records_absolute_state_policy():
    signature = vehicle_identity_r1_signature("ferrari_458")
    assert signature["identity_mode"] == IDENTITY_MODE_V1R1
    assert signature["state_control"]["redline_rpm"] == 9000.0
    assert "NO_PER_TRACK_IDENTITY_PEAK_NORMALIZATION" in signature["amplitude_policy"]


def test_r1_idle_layer_is_not_peak_recovered():
    for vehicle, idle in (("ferrari_458", 1050.0), ("lfa", 850.0)):
        rpm_idle, thr_idle, _ = _trace(idle, 0.0)
        rpm_pull, thr_pull, _ = _trace(R1_CONTROLS[vehicle].redline_rpm * 0.75, 1.0)
        idle_layer = synthesize_vehicle_identity_layer_r1(vehicle, rpm_idle, thr_idle, seed=7)
        pull_layer = synthesize_vehicle_identity_layer_r1(vehicle, rpm_pull, thr_pull, seed=7)
        idle_peak = float(np.max(np.abs(idle_layer)))
        pull_peak = float(np.max(np.abs(pull_layer)))
        assert idle_peak < 0.20
        assert pull_peak > idle_peak * 3.0
        assert pull_peak <= 0.94 + 1e-12


def test_gtr_r1_full_load_mix_is_selectively_attenuated():
    rpm, throttle, _ = _trace(6900.0, 1.0)
    _, scale = _state_envelope("gtr_r35", rpm, throttle)
    assert float(np.min(scale)) == pytest.approx(0.68)
    effective_mix = VEHICLE_IDENTITY_PROFILES["gtr_r35"].identity_mix * scale
    assert float(np.max(effective_mix)) == pytest.approx(0.1088)

    rpm_mid, throttle_mid, _ = _trace(3600.0, 0.45)
    _, mid_scale = _state_envelope("gtr_r35", rpm_mid, throttle_mid)
    assert np.allclose(mid_scale, 1.0)


def test_r1_hellcat_is_byte_preserving(monkeypatch):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    rpm, throttle, duration = _trace(3200.0, 0.55)
    legacy = VehicleIdentityR1Engine(
        "hellcat", identity_mode=IDENTITY_MODE_LEGACY, seed=11
    ).render_track(rpm, throttle, duration)
    r1 = VehicleIdentityR1Engine(
        "hellcat", identity_mode=IDENTITY_MODE_V1R1, seed=11
    ).render_track(rpm, throttle, duration)
    assert np.array_equal(legacy, r1)


@pytest.mark.parametrize("vehicle", ["ferrari_458", "lfa", "gtr_r35"])
def test_r1_changes_non_hellcat_pcm_without_clipping(monkeypatch, vehicle):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    rpm, throttle, duration = _trace(R1_CONTROLS[vehicle].redline_rpm * 0.55, 0.55)
    legacy = VehicleIdentityR1Engine(
        vehicle, identity_mode=IDENTITY_MODE_LEGACY, seed=13
    ).render_track(rpm, throttle, duration)
    r1 = VehicleIdentityR1Engine(
        vehicle, identity_mode=IDENTITY_MODE_V1R1, seed=13
    ).render_track(rpm, throttle, duration)
    assert legacy.shape == r1.shape
    assert not np.array_equal(legacy, r1)
    assert np.max(np.abs(r1.astype(np.int32))) <= int(0.94 * 32767) + 1


def test_r1_probe_binds_new_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    manifest = render_probe_r1(
        tmp_path / "probe",
        vehicles=("hellcat",),
        scenes=("hot_idle",),
        seed=17,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["candidate_identity_mode"] == IDENTITY_MODE_V1R1
    modes = {row["identity_mode"] for row in payload["artifacts"]}
    assert modes == {IDENTITY_MODE_LEGACY, IDENTITY_MODE_V1R1}
    rows = {row["identity_mode"]: row for row in payload["artifacts"]}
    assert rows[IDENTITY_MODE_LEGACY]["sha256"] == rows[IDENTITY_MODE_V1R1]["sha256"]
