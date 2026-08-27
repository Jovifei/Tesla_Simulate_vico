"""RED-to-GREEN tests for Stage-W localized afterfire contracts."""

from __future__ import annotations

import copy
import hashlib

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine


def _lift_frames(count: int = 30) -> dict[str, np.ndarray]:
    rpm = np.full(count, 6200.0)
    load = np.full(count, 0.90)
    throttle = np.full(count, 0.95)
    rpm[10:] = np.linspace(5800.0, 1100.0, count - 10)
    load[10:] = 0.55
    throttle[10:] = 0.02
    return {"rpm": rpm, "load": load, "throttle": throttle, "acceleration_mps2": np.gradient(rpm, 0.02)}


def _render(engine: PersistentEventDomainEngine, frames: dict[str, np.ndarray]) -> np.ndarray:
    pieces = []
    for index in range(frames["rpm"].size):
        state = {key: np.asarray([value[index]], dtype=np.float64) for key, value in frames.items()}
        pieces.append(engine.process(state).raw_pcm)
    return np.concatenate(pieces, axis=0)


def test_d_rpm_is_a_real_afterfire_gate() -> None:
    config = load_config("hellcat_v1")
    frames = _lift_frames()
    no_rpm_drop = {key: value.copy() for key, value in frames.items()}
    no_rpm_drop["rpm"][10:] = 6200.0
    no_rpm_drop["acceleration_mps2"][:] = 0.0
    held = PersistentEventDomainEngine(config, 48000, 960)
    falling = PersistentEventDomainEngine(config, 48000, 960)
    _render(held, no_rpm_drop)
    _render(falling, frames)
    assert held.diagnostics()["afterfire_event_count"] == 0
    assert falling.diagnostics()["afterfire_event_count"] > 0


def test_ignition_delay_changes_afterfire_arrival_sha() -> None:
    short_config = load_config("hellcat_v1")
    long_config = copy.deepcopy(short_config)
    short_config["afterfire"]["ignition_delay_s"]["value"] = 0.002
    long_config["afterfire"]["ignition_delay_s"]["value"] = 0.025
    frames = _lift_frames()
    short = _render(PersistentEventDomainEngine(short_config, 48000, 960), frames)
    long = _render(PersistentEventDomainEngine(long_config, 48000, 960), frames)
    assert hashlib.sha256(short.tobytes()).hexdigest() != hashlib.sha256(long.tobytes()).hexdigest()


def test_event_location_is_recorded_and_consumed_by_path() -> None:
    config = load_config("hellcat_v1")
    frames = _lift_frames()
    primary = PersistentEventDomainEngine(config, 48000, 960)
    collector = PersistentEventDomainEngine(config, 48000, 960)
    primary.afterfire_location_policy = "primary"
    collector.afterfire_location_policy = "collector"
    a = _render(primary, frames)
    b = _render(collector, frames)
    assert primary.diagnostics()["afterfire_event_count"] > 0
    assert primary.diagnostics()["afterfire_location_counts"]["primary"] > 0
    assert collector.diagnostics()["afterfire_location_counts"]["collector"] > 0
    assert hashlib.sha256(a.tobytes()).hexdigest() != hashlib.sha256(b.tobytes()).hexdigest()


def test_afterfire_location_contract_names_primary_bank_and_central_routes() -> None:
    config = load_config("hellcat_v1")
    assert config["afterfire"]["event_location"]["range"] == "primary|bank_collector|central_collector"


def test_afterfire_event_location_config_selects_the_runtime_route() -> None:
    base = load_config("hellcat_v1")
    frames = _lift_frames()
    for policy in ("primary", "bank_collector", "central_collector"):
        config = copy.deepcopy(base)
        config["afterfire"]["event_location"]["value"] = policy
        engine = PersistentEventDomainEngine(config, 48000, 960)
        _render(engine, frames)
        assert engine.diagnostics()["afterfire_route"]["route"] == policy
