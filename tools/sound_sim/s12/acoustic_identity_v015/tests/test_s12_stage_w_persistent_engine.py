"""RED tests for the Stage-W persistent 20 ms event-domain engine."""

from __future__ import annotations

import hashlib
import os
import unittest

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.crank_phase_pll import CrankPhasePLL
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.event_scheduler import derive_event_phase_deg
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import (
    PersistentEventDomainEngine,
)


def _frames(count: int = 120) -> dict[str, np.ndarray]:
    index = np.arange(count, dtype=np.float64)
    rpm = np.linspace(850.0, 5200.0, count)
    throttle = np.clip(0.18 + 0.72 * index / max(count - 1, 1), 0.0, 1.0)
    load = np.clip(0.15 + 0.75 * index / max(count - 1, 1), 0.0, 1.0)
    return {
        "rpm": rpm,
        "load": load,
        "throttle": throttle,
        "acceleration_mps2": np.gradient(rpm, 0.02),
    }


def _frame(blocks: dict[str, np.ndarray], index: int) -> dict[str, np.ndarray]:
    return {key: np.asarray([value[index]], dtype=np.float64) for key, value in blocks.items()}


def test_repeated_20ms_calls_match_one_shot_and_preserve_object_identity() -> None:
    config = load_config("hellcat_v1")
    blocks = _frames()
    one = PersistentEventDomainEngine(config, sample_rate_hz=48000, block_size=960)
    one_audio = one.process(blocks).raw_pcm
    many = PersistentEventDomainEngine(config, sample_rate_hz=48000, block_size=960)
    pll_id = id(many.pll)
    many_audio = np.concatenate([many.process(_frame(blocks, index)).raw_pcm for index in range(blocks["rpm"].size)], axis=0)
    assert np.array_equal(one_audio, many_audio)
    assert id(many.pll) == pll_id
    assert many.sample_counter == blocks["rpm"].size * 960


def test_snapshot_restore_replays_exact_audio_and_reset_starts_new_state() -> None:
    config = load_config("hellcat_v1")
    blocks = _frames(8)
    engine = PersistentEventDomainEngine(config, sample_rate_hz=48000, block_size=960)
    for index in range(4):
        engine.process(_frame(blocks, index))
    snapshot = engine.snapshot_state()
    expected = engine.process(_frame(blocks, 4)).raw_pcm
    engine.process(_frame(blocks, 5))
    engine.restore_state(snapshot)
    replay = engine.process(_frame(blocks, 4)).raw_pcm
    assert np.array_equal(expected, replay)
    engine.reset("hard")
    assert engine.sample_counter == 0
    assert engine.diagnostics()["afterfire_cooldown_remaining"] == 0


def test_restore_legacy_scalar_torque_snapshot_is_limited_to_one_block() -> None:
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960)
    snapshot = engine.snapshot_state()
    snapshot["pending_combustion_torque"] = 0.25
    engine.restore_state(snapshot)
    assert np.array_equal(engine._pending_combustion_torque[: engine.block_size], np.full(engine.block_size, 0.25))
    assert np.array_equal(engine._pending_combustion_torque[engine.block_size :], np.zeros(engine._pending_combustion_torque.size - engine.block_size))


def test_combustion_event_torque_and_acceleration_change_dynamics() -> None:
    config = load_config("hellcat_v1")
    base = _frames(4)
    high_accel = {key: value.copy() for key, value in base.items()}
    high_accel["acceleration_mps2"] *= 4.0
    normal = PersistentEventDomainEngine(config, 48000, 960, mode="free_dynamics")
    altered = PersistentEventDomainEngine(config, 48000, 960, mode="free_dynamics")
    normal_result = normal.process(base)
    altered_result = altered.process(high_accel)
    assert not np.array_equal(normal_result.raw_pcm, altered_result.raw_pcm)
    assert altered.diagnostics()["combustion_torque_event_count"] > 0
    assert altered.diagnostics()["omega_ripple_rms"] > 0.0


def test_firing_order_derives_phase_without_duplicate_authority() -> None:
    config = load_config("hellcat_v1")
    derived = derive_event_phase_deg(config)
    assert sorted(derived) == sorted(config["event_phase_deg"]["value"])
    assert derived != config["event_phase_deg"]["value"]
    assert config["firing_order_evidence"]["value"]


def test_afterfire_location_and_delay_change_path_output_and_sha() -> None:
    config = load_config("hellcat_v1")
    frames = _frames(30)
    frames["rpm"][:10] = 6200.0
    frames["load"][:10] = 0.90
    frames["throttle"][:10] = 0.95
    frames["rpm"][10:] = np.linspace(5800.0, 1100.0, 20)
    frames["load"][10:] = 0.55
    frames["throttle"][10:] = 0.02
    primary = PersistentEventDomainEngine(config, 48000, 960)
    collector = PersistentEventDomainEngine(config, 48000, 960)
    primary.afterfire_location_policy = "primary"
    collector.afterfire_location_policy = "collector"
    a = np.concatenate([primary.process(_frame(frames, i)).raw_pcm for i in range(frames["rpm"].size)], axis=0)
    b = np.concatenate([collector.process(_frame(frames, i)).raw_pcm for i in range(frames["rpm"].size)], axis=0)
    assert primary.diagnostics()["afterfire_event_count"] > 0
    assert not np.array_equal(a, b)
    assert hashlib.sha256(a.tobytes()).hexdigest() != hashlib.sha256(b.tobytes()).hexdigest()


def test_process_with_trace_records_phase_event_path_and_gain_per_frame() -> None:
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, ptr_enabled=True, path_model="waveguide_v1")
    result = engine.process_with_trace(_frames(6))
    trace = result.diagnostics["frame_trace"]
    assert result.post_ptr_raw is not None
    assert set(trace) == {"phase_rad", "omega_rad_s", "event_count", "afterfire_event_count", "combustion_torque_event_count", "path_state_energy", "monitor_gain_db", "sample_counter"}
    assert all(len(values) == 6 for values in trace.values())
    assert trace["sample_counter"][-1] == 6 * 960
    assert trace["event_count"] == sorted(trace["event_count"])
    assert trace["combustion_torque_event_count"] == sorted(trace["combustion_torque_event_count"])


def test_public_initialize_and_block_api_keep_ripple_diagnostics_bounded() -> None:
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960)
    pll_id = id(engine.pll)
    path_id = id(engine._path_lines[0])
    assert engine.initialize() is engine
    assert id(engine.pll) == pll_id
    assert id(engine._path_lines[0]) == path_id
    blocks = _frames(100)
    for index in range(100):
        engine.process_block(_frame(blocks, index))
    diagnostics = engine.diagnostics()
    assert not hasattr(engine, "_omega_ripple_values")
    assert diagnostics["omega_ripple_sample_count"] == 100 * 960
    assert diagnostics["state_memory_bytes"] < 4_000_000
    snapshot = engine.snapshot_state()
    assert snapshot["omega_ripple_sample_count"] == 100 * 960
    before = engine.diagnostics()
    engine.process_block(_frame(blocks, 0))
    engine.restore_state(snapshot)
    assert engine.diagnostics()["omega_ripple_sample_count"] == before["omega_ripple_sample_count"]
    assert engine.diagnostics()["omega_ripple_rms"] == before["omega_ripple_rms"]


def test_pll_torque_ripple_is_event_derived_not_a_free_running_sine() -> None:
    config = load_config("hellcat_v1")
    count = 32
    rpm = np.full(count, 850.0)
    load = np.full(count, 0.18)
    throttle = np.full(count, 0.18)
    acceleration = np.zeros(count)
    zero = CrankPhasePLL(48000, config).process_block(rpm, load, throttle, acceleration, np.zeros(count))
    event_input = np.zeros(count)
    event_input[8] = 0.4
    event = CrankPhasePLL(48000, config).process_block(rpm, load, throttle, acceleration, event_input)
    assert np.array_equal(zero.torque_ripple, np.zeros(count))
    assert event.torque_ripple[8] == 0.4
    assert not np.array_equal(zero.omega_rad_s, event.omega_rad_s)


def test_scheduled_event_energy_changes_free_dynamics_after_feedback_block() -> None:
    normal_config = load_config("hellcat_v1")
    silent_config = load_config("hellcat_v1")
    silent_config["combustion_event"]["event_energy"]["value"] = 0.0
    frames = {"rpm": np.full(8, 4200.0), "load": np.full(8, 0.85), "throttle": np.full(8, 0.90), "acceleration_mps2": np.zeros(8)}
    normal = PersistentEventDomainEngine(normal_config, 48000, 960, mode="free_dynamics")
    silent = PersistentEventDomainEngine(silent_config, 48000, 960, mode="free_dynamics")
    normal_result = normal.process(frames)
    silent_result = silent.process(frames)
    assert normal.diagnostics()["combustion_torque_event_count"] > 0
    assert abs(normal.diagnostics()["omega_ripple_rms"] - silent.diagnostics()["omega_ripple_rms"]) > 1.0e-6
    assert not np.array_equal(normal_result.raw_pcm, silent_result.raw_pcm)


@unittest.skipUnless(os.environ.get("S12_RUN_SLOW") == "1", "set S12_RUN_SLOW=1 for the 3000-block acceptance run")
def test_3000_twenty_ms_calls_match_one_shot_sixty_seconds() -> None:
    config = load_config("hellcat_v1")
    blocks = _frames(3000)
    one = PersistentEventDomainEngine(config, 48000, 960)
    expected = hashlib.sha256(one.process(blocks).raw_pcm.tobytes()).hexdigest()
    many = PersistentEventDomainEngine(config, 48000, 960)
    digest = hashlib.sha256()
    for index in range(3000):
        digest.update(many.process(_frame(blocks, index)).raw_pcm.tobytes())
    assert digest.hexdigest() == expected
    assert many.sample_counter == 3000 * 960
    assert many.diagnostics()["state_memory_bytes"] < 4_000_000
