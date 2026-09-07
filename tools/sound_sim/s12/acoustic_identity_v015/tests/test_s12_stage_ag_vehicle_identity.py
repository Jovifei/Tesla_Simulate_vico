from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.stage_ag.vehicle_identity import (
    IDENTITY_MODE_LEGACY,
    IDENTITY_MODE_V1,
    VEHICLE_IDENTITY_PROFILES,
    VehicleIdentityEngine,
    synthesize_vehicle_identity_layer,
    vehicle_identity_signature,
)


def _identity_ir(*args, **kwargs):
    return np.asarray([1.0], dtype=np.float64)


def _trace(sr: int = 48_000, duration: float = 0.16):
    n = int(sr * duration)
    rpm = np.linspace(1800.0, 4200.0, n, endpoint=False)
    throttle = np.linspace(0.25, 0.85, n, endpoint=False)
    return rpm, throttle, duration


def test_hellcat_vehicle_identity_v1_is_byte_preserving(monkeypatch):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    rpm, throttle, duration = _trace()
    legacy = VehicleIdentityEngine(
        "hellcat", identity_mode=IDENTITY_MODE_LEGACY, seed=41
    ).render_track(rpm, throttle, duration)
    identity = VehicleIdentityEngine(
        "hellcat", identity_mode=IDENTITY_MODE_V1, seed=41
    ).render_track(rpm, throttle, duration)
    assert np.array_equal(legacy, identity)


@pytest.mark.parametrize("vehicle", ["ferrari_458", "lfa", "gtr_r35"])
def test_vehicle_identity_v1_changes_non_hellcat_pcm(monkeypatch, vehicle):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    rpm, throttle, duration = _trace()
    legacy = VehicleIdentityEngine(
        vehicle, identity_mode=IDENTITY_MODE_LEGACY, seed=43
    ).render_track(rpm, throttle, duration)
    identity = VehicleIdentityEngine(
        vehicle, identity_mode=IDENTITY_MODE_V1, seed=43
    ).render_track(rpm, throttle, duration)
    assert legacy.shape == identity.shape
    assert not np.array_equal(legacy, identity)
    assert np.max(np.abs(identity.astype(np.int32))) <= int(0.94 * 32767) + 1


def test_identity_profiles_are_topology_distinct_and_bounded():
    assert VEHICLE_IDENTITY_PROFILES["hellcat"].primary_engine_order == 4.0
    assert VEHICLE_IDENTITY_PROFILES["ferrari_458"].primary_engine_order == 4.0
    assert VEHICLE_IDENTITY_PROFILES["lfa"].primary_engine_order == 5.0
    assert VEHICLE_IDENTITY_PROFILES["gtr_r35"].primary_engine_order == 3.0

    ferrari_orders = tuple(row[0] for row in VEHICLE_IDENTITY_PROFILES["ferrari_458"].orders)
    lfa_orders = tuple(row[0] for row in VEHICLE_IDENTITY_PROFILES["lfa"].orders)
    gtr_orders = tuple(row[0] for row in VEHICLE_IDENTITY_PROFILES["gtr_r35"].orders)
    assert ferrari_orders != lfa_orders != gtr_orders

    assert VEHICLE_IDENTITY_PROFILES["hellcat"].identity_mix == 0.0
    for vehicle in ("ferrari_458", "lfa", "gtr_r35"):
        profile = VEHICLE_IDENTITY_PROFILES[vehicle]
        assert 0.0 < profile.identity_mix <= 0.25
        assert 0.0 <= profile.broadband_mix <= 0.10


def test_identity_layers_are_not_a_single_shared_template():
    sr = 48_000
    n = int(sr * 0.20)
    rpm = np.full(n, 3000.0)
    throttle = np.full(n, 0.55)
    layers = {
        vehicle: synthesize_vehicle_identity_layer(
            vehicle, rpm, throttle, sr=sr, seed=47
        )[:, 0]
        for vehicle in ("ferrari_458", "lfa", "gtr_r35")
    }
    assert not np.array_equal(layers["ferrari_458"], layers["lfa"])
    assert not np.array_equal(layers["ferrari_458"], layers["gtr_r35"])
    assert not np.array_equal(layers["lfa"], layers["gtr_r35"])


def test_vehicle_identity_signature_is_auditable():
    signature = vehicle_identity_signature("lfa")
    assert signature["vehicle"] == "lfa"
    assert signature["primary_engine_order"] == 5.0
    assert "V10" in signature["rationale"]


def test_invalid_identity_vehicle_and_mode_fail_closed(monkeypatch):
    monkeypatch.setattr(
        "tools.sound_sim.s12.acoustic_identity_v015.stage_ad.engine_sim_acoustics.load_impulse_response",
        _identity_ir,
    )
    with pytest.raises(ValueError):
        vehicle_identity_signature("not-a-car")
    with pytest.raises(ValueError):
        VehicleIdentityEngine("hellcat", identity_mode="magic")
