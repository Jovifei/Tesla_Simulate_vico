"""RED tests for the stateful clean-room waveguide_v1 path."""

from __future__ import annotations

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
