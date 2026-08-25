"""RED tests for the Stage-W persistent 20 ms event-domain engine."""

from __future__ import annotations

import hashlib
import os
import unittest

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
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
