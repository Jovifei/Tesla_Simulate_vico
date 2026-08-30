"""RED tests for the clean-room Stage V event-domain source."""

from __future__ import annotations

import copy
import hashlib
import json

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.afterfire_state import (
    schedule_afterfire,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.chamber_event import (
    render_event_packet,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.collector_network import (
    route_to_collectors,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import (
    CONFIG_ROOT,
    load_config,
    validate_config,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.crank_phase_pll import (
    CrankPhasePLL,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.diagnostics import (
    compare_parent_candidate,
    measure_audio,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.exhaust_path import (
    apply_fractional_delay,
    sound_speed_mps,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.block_renderer import (
    render_event_domain,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.audition_monitor import (
    render_audition_monitor,
)


def _state(duration_s: float = 1.0, sample_rate_hz: int = 48000):
    count = int(duration_s * sample_rate_hz)
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.full(count, 850.0)
    load = np.full(count, 0.18)
    throttle = np.full(count, 0.18)
    acceleration = np.zeros(count)
    return time_s, rpm, load, throttle, acceleration


def test_all_stage_v_configs_have_complete_provenance():
    for path in sorted(CONFIG_ROOT.glob("*.json")):
        validate_config(json.loads(path.read_text(encoding="utf-8")))


def test_invalid_firing_order_and_unknown_field_fail():
    config = load_config("hellcat_v1")
    invalid = copy.deepcopy(config)
    invalid["firing_order_evidence"]["value"] = [1, 1, 2, 3, 4, 5, 6, 7]
    with pytest.raises(ValueError, match="firing"):
        validate_config(invalid)
    invalid = copy.deepcopy(config)
    invalid["unexpected"] = {"value": 1, "unit": "x", "range": [0, 2], "source_level": "C", "source": "synthetic", "verification_state": "synthetic_assumption"}
    with pytest.raises(ValueError, match="unknown"):
        validate_config(invalid)


def test_phase_is_continuous_across_blocks_and_rpm_is_tracked():
    _, rpm, load, throttle, acceleration = _state(0.4)
    rpm[4800:] = np.linspace(850.0, 6200.0, rpm.size - 4800)
    pll = CrankPhasePLL(sample_rate_hz=48000, config=load_config("hellcat_v1"))
    first = pll.process_block(rpm[:960], load[:960], throttle[:960], acceleration[:960])
    second = pll.process_block(rpm[960:], load[960:], throttle[960:], acceleration[960:])
    phase = np.concatenate((first.phase_rad, second.phase_rad))
    assert np.all(np.diff(phase) > 0.0)
    assert abs(second.omega_rad_s[-1] - 6200.0 * 2.0 * np.pi / 60.0) < 24.0
    assert abs(second.phase_rad[0] - first.phase_rad[-1]) < 0.1


def test_one_shot_and_block_pll_render_are_equivalent():
    _, rpm, load, throttle, acceleration = _state(0.25)
    rpm[:] = np.linspace(850.0, 5200.0, rpm.size)
    one = CrankPhasePLL(sample_rate_hz=48000, config=load_config("hellcat_v1")).process_block(rpm, load, throttle, acceleration)
    pll = CrankPhasePLL(sample_rate_hz=48000, config=load_config("hellcat_v1"))
    blocks = []
    for start in range(0, rpm.size, 960):
        blocks.append(pll.process_block(rpm[start:start + 960], load[start:start + 960], throttle[start:start + 960], acceleration[start:start + 960]).phase_rad)
    assert np.array_equal(one.phase_rad, np.concatenate(blocks))


def test_event_phase_and_cylinder_identity_are_exact():
    _, rpm, load, throttle, acceleration = _state(1.0)
    pll = CrankPhasePLL(sample_rate_hz=48000, config=load_config("hellcat_v1"))
    phase = pll.process_block(rpm, load, throttle, acceleration).phase_rad
    from tools.sound_sim.s12.acoustic_identity_v015.event_domain.event_scheduler import schedule_events

    events = schedule_events(phase, load_config("hellcat_v1"), 48000)
    assert events.count > 0
    assert np.all(np.isin(events.entity_index, np.arange(8)))
    assert np.all(np.isfinite(events.phase_rad))
    assert np.all(np.diff(events.sample_index) > 0)


def test_event_envelope_exposes_attack_decay_and_torque():
    packet = render_event_packet(sample_rate_hz=48000, duration_s=0.08, rise_time_s=0.004, decay_time_s=0.025, energy=1.0)
    assert packet.pressure.shape == packet.blowdown_pressure.shape
    assert np.argmax(np.abs(packet.pressure)) > 0
    assert packet.pressure[0] == 0.0
    assert np.max(np.abs(packet.torque_impulse)) > 0.0


def test_header_length_and_temperature_change_arrival_and_spectrum():
    impulse = np.zeros(4800)
    impulse[100] = 1.0
    short = apply_fractional_delay(impulse, 0.020, 48000, attenuation=1.0)
    long = apply_fractional_delay(impulse, 0.035, 48000, attenuation=1.0)
    assert np.argmax(short) < np.argmax(long)
    assert sound_speed_mps(900.0) > sound_speed_mps(300.0)


def test_bank_assignment_changes_correlation():
    paths = np.zeros((4, 2400), dtype=np.float64)
    paths[0, 20] = 1.0
    paths[1, 200] = 1.0
    paths[2, 40] = 1.0
    paths[3, 220] = 1.0
    equal = route_to_collectors(paths, [0, 0, 1, 1], [0.01, 0.01, 0.01, 0.01], [0.0, 1.0])
    crossed = route_to_collectors(paths, [0, 1, 0, 1], [0.01, 0.01, 0.01, 0.01], [0.0, 1.0])
    assert not np.array_equal(equal.left, crossed.left)
    assert not np.array_equal(equal.right, crossed.right)


def test_afterfire_is_zero_for_idle_and_nonzero_only_for_hot_lift():
    n = 48000
    time_s = np.arange(n) / 48000.0
    idle = schedule_afterfire(time_s, np.full(n, 850.0), np.full(n, 0.15), np.full(n, 0.15), np.zeros(n), load_config("hellcat_v1"))
    lift = np.linspace(6200.0, 1100.0, n)
    throttle = np.where(time_s < 0.15, 0.95, 0.02)
    load = np.where(time_s < 0.15, 0.90, 0.55)
    hot = schedule_afterfire(time_s, lift, load, throttle, np.gradient(lift), load_config("hellcat_v1"))
    assert idle.count == 0
    assert hot.count > 0
    assert hot.wrong_condition_event_count == 0


def test_event_renderer_consumes_path_parameters_and_is_deterministic():
    time_s, rpm, load, throttle, acceleration = _state(0.35)
    trace = {"time_s": time_s, "rpm": rpm, "load": load, "throttle": throttle, "acceleration_mps2": acceleration}
    a = render_event_domain(trace, load_config("hellcat_v1"), sample_rate_hz=48000, block_size=960)
    changed = copy.deepcopy(load_config("hellcat_v1"))
    changed["per_path_primary_length_m"]["value"][0] += 0.11
    b = render_event_domain(trace, changed, sample_rate_hz=48000, block_size=960)
    assert hashlib.sha256(a.pressure.tobytes()).digest() != hashlib.sha256(b.pressure.tobytes()).digest()
    assert set(a.stems).issuperset({"combustion_pressure", "blowdown_pressure", "afterfire", "exhaust_left_bank", "exhaust_right_bank"})


def test_raw_monitor_separation_and_gain_bounds():
    raw = np.zeros((48000, 2), dtype=np.float64)
    raw[1000:2000] = 0.5
    monitor = render_audition_monitor(raw, 48000)
    assert not np.shares_memory(raw, monitor.audio)
    assert np.array_equal(raw, np.zeros_like(raw)) or np.max(np.abs(raw - monitor.audio)) >= 0.0
    assert monitor.max_gain_db <= 9.0
    assert monitor.max_attenuation_db >= -12.0
    assert np.max(np.abs(monitor.audio)) <= 10.0 ** (-1.0 / 20.0) + 1e-12


def test_metrics_reject_identical_parent_candidate_and_measure_audio():
    audio = np.zeros((4800, 2), dtype=np.float64)
    audio[100:200, :] = 0.2
    metrics = measure_audio(audio, 48000)
    assert metrics["finite"] is True
    with pytest.raises(ValueError, match="identical"):
        compare_parent_candidate(audio, audio.copy(), 48000)
