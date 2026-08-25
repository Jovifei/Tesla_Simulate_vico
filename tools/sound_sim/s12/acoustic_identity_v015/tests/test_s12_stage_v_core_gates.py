"""TDD gates for parameters that must remain causally reachable."""

from __future__ import annotations

import copy

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.collector_network import (
    route_to_collectors,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import (
    load_config,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.crank_phase_pll import (
    CrankPhasePLL,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.afterfire_state import (
    schedule_afterfire,
)


def test_per_path_attenuation_is_reachable_in_collector_output() -> None:
    paths = np.zeros((2, 2400), dtype=np.float64)
    paths[:, 100] = 1.0
    baseline = route_to_collectors(paths, [0, 1], [0.1, 0.1], [0.0, 1.0], per_path_attenuation=[1.0, 1.0])
    changed = route_to_collectors(paths, [0, 1], [0.1, 0.1], [0.0, 1.0], per_path_attenuation=[1.0, 0.2])
    assert not (np.array_equal(baseline.left, changed.left) and np.array_equal(baseline.right, changed.right))


def test_pll_exposes_continuous_torque_state() -> None:
    config = load_config("hellcat_v1")
    n = 960
    values = np.full(n, 850.0)
    block = CrankPhasePLL(48000, config).process_block(values, np.full(n, 0.2), np.full(n, 0.2), np.zeros(n))
    assert block.load_torque is not None
    assert block.friction_torque is not None
    assert block.idle_governor_torque is not None
    assert np.all(np.isfinite(block.load_torque))


def test_afterfire_exposes_eligibility_state_and_location() -> None:
    config = load_config("hellcat_v1")
    n = 4800
    time_s = np.arange(n, dtype=np.float64) / 48000.0
    rpm = np.where(time_s < 0.05, 6200.0, np.linspace(6200.0, 1100.0, n))
    throttle = np.where(time_s < 0.05, 0.95, 0.02)
    load = np.where(time_s < 0.05, 0.90, 0.55)
    events = schedule_afterfire(time_s, rpm, load, throttle, np.gradient(rpm), config)
    assert events.unburned_fuel_reservoir is not None
    assert events.exhaust_oxygen_proxy is not None
    assert events.exhaust_temperature is not None
    assert events.event_location is not None
    assert events.count >= 0
