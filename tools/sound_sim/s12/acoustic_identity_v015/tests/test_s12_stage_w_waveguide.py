"""RED tests for the stateful clean-room waveguide_v1 path."""

from __future__ import annotations

import copy
import hashlib

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.stage_w.waveguide import (
    WaveguideConfig,
    StatefulWaveguide,
    WaveguideNetwork,
)
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine


def test_waveguide_reflection_is_stateful_across_block_boundaries() -> None:
    guide = StatefulWaveguide(WaveguideConfig(length_m=0.20, area_ratio=0.55, sample_rate_hz=48000))
    first = np.zeros(16, dtype=np.float64)
    first[0] = 1.0
    output_a = guide.process(first)
    output_b = guide.process(np.zeros(16, dtype=np.float64))
    assert np.max(np.abs(output_a)) > 0.0
    assert np.max(np.abs(output_b)) > 0.0
    assert guide.snapshot()["sample_counter"] == 32


def test_waveguide_one_shot_and_block_processing_match() -> None:
    signal = np.zeros(128, dtype=np.float64)
    signal[3] = 1.0
    one = StatefulWaveguide(WaveguideConfig(length_m=0.04, area_ratio=0.70, sample_rate_hz=48000))
    expected = one.process(signal)
    many = StatefulWaveguide(WaveguideConfig(length_m=0.04, area_ratio=0.70, sample_rate_hz=48000))
    actual = np.concatenate([many.process(signal[index:index + 16]) for index in range(0, signal.size, 16)])
    assert np.array_equal(expected, actual)


def test_waveguide_network_equal_and_unequal_headers_change_arrival_and_sha() -> None:
    paths = np.zeros((2, 512), dtype=np.float64)
    paths[:, 0] = 1.0
    equal = WaveguideNetwork([0.10, 0.10], [0, 1], 48000).process(paths)
    unequal = WaveguideNetwork([0.10, 0.16], [0, 1], 48000).process(paths)
    assert not np.array_equal(equal.left, unequal.left)
    assert hashlib.sha256(equal.left.tobytes()).hexdigest() != hashlib.sha256(unequal.left.tobytes()).hexdigest()
    assert equal.arrival_samples[0] == equal.arrival_samples[1]
    assert unequal.arrival_samples[0] != unequal.arrival_samples[1]


def test_persistent_engine_can_select_waveguide_v1_without_changing_delay_baseline() -> None:
    state = {"rpm": np.array([2400.0]), "load": np.array([0.5]), "throttle": np.array([0.6]), "acceleration_mps2": np.array([2.0])}
    baseline = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, path_model="delay_lpf_v1")
    waveguide = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, path_model="waveguide_v1")
    a = baseline.process(state).raw_pcm
    b = waveguide.process(state).raw_pcm
    assert not np.array_equal(a, b)
    assert waveguide.diagnostics()["path_model"] == "waveguide_v1"


def test_persistent_engine_reduced_cfd_teacher_is_stateful_and_snapshot_safe() -> None:
    config = load_config("hellcat_v1")
    frames = {"rpm": np.array([2400.0, 4200.0]), "load": np.array([0.5, 0.8]), "throttle": np.array([0.6, 0.9]), "acceleration_mps2": np.array([2.0, 3.0])}
    delay = PersistentEventDomainEngine(config, 48000, 960, path_model="delay_lpf_v1")
    teacher = PersistentEventDomainEngine(config, 48000, 960, path_model="reduced_cfd_teacher_v1")
    teacher.process({key: value[:1] for key, value in frames.items()})
    snapshot = teacher.snapshot_state()
    expected = teacher.process({key: value[1:] for key, value in frames.items()}).raw_pcm
    teacher.restore_state(snapshot)
    replay = teacher.process({key: value[1:] for key, value in frames.items()}).raw_pcm
    assert np.array_equal(expected, replay)
    teacher_compare = PersistentEventDomainEngine(config, 48000, 960, path_model="reduced_cfd_teacher_v1")
    assert not np.array_equal(delay.process(frames).raw_pcm, teacher_compare.process(frames).raw_pcm)
    diagnostics = teacher.diagnostics()
    assert diagnostics["path_model"] == "reduced_cfd_teacher_v1"
    assert diagnostics["teacher_response"]["status"] == "TEACHER_METRIC_REDUCTION_ONLY"


def test_waveguide_consumes_collector_and_distinguishes_three_afterfire_locations() -> None:
    config = load_config("hellcat_v1")
    rpm = np.r_[np.full(10, 6200.0), np.linspace(5800.0, 1100.0, 20)]
    load = np.r_[np.full(10, 0.90), np.full(20, 0.55)]
    throttle = np.r_[np.full(10, 0.95), np.full(20, 0.02)]
    frames = {"rpm": rpm, "load": load, "throttle": throttle, "acceleration_mps2": np.gradient(rpm, 0.02)}
    outputs = {}
    arrivals = {}
    for policy in ("primary", "bank_collector", "central_collector"):
        engine = PersistentEventDomainEngine(config, 48000, 960, path_model="waveguide_v1")
        engine.afterfire_location_policy = policy
        outputs[policy] = np.concatenate([engine.process({key: value[i:i + 1] for key, value in frames.items()}).raw_pcm for i in range(30)])
        assert engine.diagnostics()["afterfire_event_count"] > 0
        assert engine.diagnostics()["afterfire_route"]["route"] == policy
        assert engine.diagnostics()["afterfire_route"]["path_id"]
        arrivals[policy] = engine.diagnostics()["afterfire_route"]["arrival_samples"]
    assert len({hashlib.sha256(value.tobytes()).hexdigest() for value in outputs.values()}) == 3
    assert len(set(arrivals.values())) == 3

    changed = copy.deepcopy(config)
    changed["collector_length_m"]["value"] += 0.20
    baseline = PersistentEventDomainEngine(config, 48000, 960, path_model="waveguide_v1")
    altered = PersistentEventDomainEngine(changed, 48000, 960, path_model="waveguide_v1")
    assert not np.array_equal(baseline.process(frames).raw_pcm, altered.process(frames).raw_pcm)


def test_afterfire_route_does_not_rewrite_pre_event_combustion() -> None:
    config = load_config("hellcat_v1")
    high = {"rpm": np.array([6200.0]), "load": np.array([0.90]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([0.0])}
    outputs = []
    for policy in ("primary", "bank_collector", "central_collector"):
        engine = PersistentEventDomainEngine(config, 48000, 960, path_model="waveguide_v1")
        engine.afterfire_location_policy = policy
        outputs.append(engine.process(high).raw_pcm)
    assert np.array_equal(outputs[0], outputs[1])
    assert np.array_equal(outputs[1], outputs[2])


def test_afterfire_route_snapshot_restores_queued_tail_exactly() -> None:
    config = load_config("hellcat_v1")
    engine = PersistentEventDomainEngine(config, 48000, 960, path_model="waveguide_v1")
    engine.afterfire_location_policy = "central_collector"
    engine.process({"rpm": np.array([6200.0]), "load": np.array([0.90]), "throttle": np.array([0.95]), "acceleration_mps2": np.array([0.0])})
    engine.process({"rpm": np.array([5800.0]), "load": np.array([0.55]), "throttle": np.array([0.02]), "acceleration_mps2": np.array([-8.0])})
    snapshot = engine.snapshot_state()
    next_state = {"rpm": np.array([5600.0]), "load": np.array([0.50]), "throttle": np.array([0.04]), "acceleration_mps2": np.array([-4.0])}
    expected = engine.process(next_state).raw_pcm
    engine.restore_state(snapshot)
    replay = engine.process(next_state).raw_pcm
    assert np.array_equal(expected, replay)
