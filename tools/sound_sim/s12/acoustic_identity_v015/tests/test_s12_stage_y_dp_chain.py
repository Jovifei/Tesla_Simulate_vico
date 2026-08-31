import copy
import hashlib
import os
import unittest
import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.audio_chain_dp import PressureAudioChain
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace, _render_architecture
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine


def _assert_state_equal(left, right) -> None:
    if isinstance(left, np.ndarray):
        assert isinstance(right, np.ndarray)
        assert np.array_equal(left, right)
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            _assert_state_equal(left[key], right[key])
    elif isinstance(left, list):
        assert len(left) == len(right)
        for left_item, right_item in zip(left, right):
            _assert_state_equal(left_item, right_item)
    else:
        assert left == right


def test_warmup_then_stream_matches_oneshot_within_tolerance() -> None:
    chain = PressureAudioChain(sample_rate_hz=48000, delay_samples=64.0)
    noise = np.random.default_rng(0).standard_normal((48000, 2)) * 0.01
    chain.warmup(noise[: 4800])
    streamed = []
    for index in range(0, 9600, 960):
        streamed.append(chain.process(noise[index : index + 960]))
    streamed = np.concatenate(streamed, axis=0)
    oneshot = PressureAudioChain(sample_rate_hz=48000, delay_samples=64.0)
    oneshot.warmup(noise[: 4800])
    full = oneshot.process(noise[: 9600])
    assert np.max(np.abs(streamed - full)) < 1e-9
    metrics = block_boundary_click_metrics(streamed, 960)
    assert metrics.get("max_abs_jump", metrics.get("max_boundary_jump")) < 0.35


def test_dc_offset_removal_is_per_sample_and_stereo_isolated() -> None:
    chain = PressureAudioChain(sample_rate_hz=1000, delay_samples=0.0)
    output = chain.process(np.tile(np.asarray([1.25, -0.75]), (4000, 1)))
    assert np.max(np.abs(output[-500:, 0])) < 1.0e-4
    assert np.max(np.abs(output[-500:, 1])) < 1.0e-4

    isolated = PressureAudioChain(sample_rate_hz=1000, delay_samples=2.0)
    impulse = np.zeros((64, 2), dtype=np.float64)
    impulse[0, 0] = 1.0
    isolated_output = isolated.process(impulse)
    assert np.array_equal(isolated_output[:, 1], np.zeros(64, dtype=np.float64))


def test_fractional_delay_changes_interpolated_stereo_output() -> None:
    signal = np.zeros((32, 2), dtype=np.float64)
    signal[0] = [1.0, -1.0]
    integer = PressureAudioChain(sample_rate_hz=1000, delay_samples=2.0)
    fractional = PressureAudioChain(sample_rate_hz=1000, delay_samples=2.5)
    integer_output = integer.process(signal)
    fractional_output = fractional.process(signal)
    assert not np.array_equal(integer_output, fractional_output)
    assert np.array_equal(integer_output[:, 0] * -1.0, integer_output[:, 1])
    assert np.array_equal(fractional_output[:, 0] * -1.0, fractional_output[:, 1])


def test_empty_and_invalid_chain_inputs_reject_before_mutation() -> None:
    chain = PressureAudioChain(sample_rate_hz=1000, delay_samples=2.25)
    before = copy.deepcopy(chain.snapshot())
    empty = chain.process(np.empty((0, 2), dtype=np.float64))
    assert empty.shape == (0, 2)
    _assert_state_equal(chain.snapshot(), before)

    for invalid in (np.zeros(4), np.zeros((4, 1)), np.asarray([[0.0, np.nan]]), np.asarray([[0.0, np.inf]]), None):
        with pytest.raises(ValueError):
            chain.process(invalid)
        _assert_state_equal(chain.snapshot(), before)
    chain.warmup(np.zeros((2, 2), dtype=np.float64))
    warmed = copy.deepcopy(chain.snapshot())
    with pytest.raises(ValueError):
        chain.warmup(np.asarray([[np.nan, 0.0]]))
    _assert_state_equal(chain.snapshot(), warmed)


@pytest.mark.parametrize("sample_rate", (0, -1, True, 1000.5, "1000"))
def test_invalid_sample_rate_rejected(sample_rate) -> None:
    with pytest.raises(ValueError):
        PressureAudioChain(sample_rate_hz=sample_rate, delay_samples=1.0)


@pytest.mark.parametrize("delay", (-1.0, np.nan, np.inf, True, "1.0"))
def test_invalid_delay_rejected(delay) -> None:
    with pytest.raises(ValueError):
        PressureAudioChain(sample_rate_hz=1000, delay_samples=delay)


def test_auto_warmup_uses_configured_rate_once_and_discards_output() -> None:
    chain = PressureAudioChain(sample_rate_hz=1000, delay_samples=1.5)
    block = np.ones((7, 2), dtype=np.float64)
    first = chain.process(block)
    state = chain.snapshot()
    second = chain.process(block)
    assert first.shape == second.shape == block.shape
    assert state["warm"] is True
    assert state["warmup_sample_count"] == 100
    assert state["sample_counter"] == 7
    assert chain.snapshot()["sample_counter"] == 14


def test_chain_snapshot_restore_replays_all_active_state_atomically() -> None:
    chain = PressureAudioChain(sample_rate_hz=1000, delay_samples=2.25)
    signal = np.random.default_rng(4).standard_normal((64, 2))
    chain.process(signal)
    snapshot = chain.snapshot()
    expected = chain.process(signal[:11])
    chain.process(signal[11:22])
    chain.restore(snapshot)
    assert np.array_equal(chain.process(signal[:11]), expected)

    fresh = PressureAudioChain(sample_rate_hz=1000, delay_samples=2.25)
    fresh.restore(snapshot)
    assert np.array_equal(fresh.process(signal[:11]), expected)

    before = copy.deepcopy(chain.snapshot())
    for mutate in (
        lambda value: value["dc"].__setitem__(0, np.nan),
        lambda value: value["prev"].__setitem__(1, np.inf),
        lambda value: value["history"].__setitem__((0, 0), np.nan),
        lambda value: value.__setitem__("warm", 1),
        lambda value: value.__setitem__("sample_counter", -1),
        lambda value: value.__setitem__("delay_samples_exact", 2.5),
    ):
        invalid = copy.deepcopy(before)
        mutate(invalid)
        with pytest.raises(ValueError):
            chain.restore(invalid)
        _assert_state_equal(chain.snapshot(), before)


def test_enabled_engine_streaming_and_snapshot_replay_include_audio_chain_state() -> None:
    config = load_config("hellcat_v1")
    index = np.arange(8, dtype=np.float64)
    frames = {
        "rpm": 1200.0 + 200.0 * index,
        "load": 0.25 + 0.02 * index,
        "throttle": 0.30 + 0.01 * index,
        "acceleration_mps2": np.gradient(1200.0 + 200.0 * index, 0.02),
    }
    one = PersistentEventDomainEngine(config, 48000, 960, ptr_enabled=True, audio_chain="dp_v1")
    expected = one.process(frames)
    many = PersistentEventDomainEngine(config, 48000, 960, ptr_enabled=True, audio_chain="dp_v1")
    streamed = [many.process({key: value[index : index + 1] for key, value in frames.items()}) for index in range(8)]
    assert np.array_equal(expected.raw_pcm, np.concatenate([item.raw_pcm for item in streamed]))
    assert np.array_equal(expected.post_ptr_raw, np.concatenate([item.post_ptr_raw for item in streamed]))
    snapshot = many.snapshot_state()
    assert snapshot["schema_version"] == "s12.stage_w.persistent_engine_state.v3"
    assert snapshot["audio_chain_state"]["warm"] is True
    next_frame = {key: value[0:1] for key, value in frames.items()}
    expected_next = many.process(next_frame).raw_pcm
    many.process(next_frame)
    many.restore_state(snapshot)
    assert np.array_equal(many.process(next_frame).raw_pcm, expected_next)

    invalid = copy.deepcopy(snapshot)
    invalid["audio_chain_state"]["history"][0, 0] = np.nan
    before = copy.deepcopy(many.snapshot_state())
    with pytest.raises(ValueError):
        many.restore_state(invalid)
    _assert_state_equal(many.snapshot_state(), before)
    missing = copy.deepcopy(snapshot)
    missing.pop("audio_chain_state")
    with pytest.raises(ValueError):
        many.restore_state(missing)
    _assert_state_equal(many.snapshot_state(), before)
    null_state = copy.deepcopy(snapshot)
    null_state["audio_chain_state"] = None
    with pytest.raises(ValueError):
        many.restore_state(null_state)
    _assert_state_equal(many.snapshot_state(), before)


def _legacy_v1_snapshot(engine: PersistentEventDomainEngine) -> dict:
    legacy = copy.deepcopy(engine.snapshot_state())
    legacy["schema_version"] = "s12.stage_w.persistent_engine_state.v1"
    for field in ("path_filter_state", "runtime_models", "transient_state", "audio_chain_state"):
        legacy.pop(field, None)
    return legacy


def test_legacy_zero_dp_migration_ignores_dirty_target_chain_state() -> None:
    config = load_config("hellcat_v1")
    frame = {
        "rpm": np.asarray([1800.0]),
        "load": np.asarray([0.35]),
        "throttle": np.asarray([0.40]),
        "acceleration_mps2": np.asarray([0.0]),
    }
    source = PersistentEventDomainEngine(config, 48000, 960, audio_chain="dp_v1")
    legacy = _legacy_v1_snapshot(source)

    restored = PersistentEventDomainEngine(config, 48000, 960, audio_chain="dp_v1")
    restored.process(frame)
    restored.restore_state(legacy)
    fresh = PersistentEventDomainEngine(config, 48000, 960, audio_chain="dp_v1")
    assert np.array_equal(restored.process(frame).raw_pcm, fresh.process(frame).raw_pcm)


def test_pre_y5_v2_without_audio_chain_state_restores_on_off_target() -> None:
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, audio_chain="off")
    legacy = copy.deepcopy(engine.snapshot_state())
    legacy["schema_version"] = "s12.stage_w.persistent_engine_state.v2"
    legacy.pop("audio_chain_state")
    legacy["runtime_models"].pop("audio_chain")
    before = copy.deepcopy(legacy)

    engine.restore_state(legacy)
    restored = engine.snapshot_state()
    assert restored["schema_version"] == "s12.stage_w.persistent_engine_state.v3"
    assert restored["audio_chain_state"] is None
    _assert_state_equal(legacy, before)


def test_pre_y5_v2_without_audio_chain_state_rejects_active_target_atomically() -> None:
    engine = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, audio_chain="dp_v1")
    frame = {
        "rpm": np.asarray([1800.0]),
        "load": np.asarray([0.35]),
        "throttle": np.asarray([0.40]),
        "acceleration_mps2": np.asarray([0.0]),
    }
    engine.process(frame)
    before = copy.deepcopy(engine.snapshot_state())
    legacy = copy.deepcopy(before)
    legacy["schema_version"] = "s12.stage_w.persistent_engine_state.v2"
    legacy.pop("audio_chain_state")
    legacy["runtime_models"].pop("audio_chain")
    legacy_before = copy.deepcopy(legacy)

    with pytest.raises(ValueError, match="missing active audio chain state"):
        engine.restore_state(legacy)
    _assert_state_equal(engine.snapshot_state(), before)
    _assert_state_equal(legacy, legacy_before)


def test_complete_y5_v2_snapshot_migrates_to_v3_after_validation() -> None:
    config = load_config("hellcat_v1")
    frame = {
        "rpm": np.asarray([1800.0]),
        "load": np.asarray([0.35]),
        "throttle": np.asarray([0.40]),
        "acceleration_mps2": np.asarray([0.0]),
    }
    source = PersistentEventDomainEngine(config, 48000, 960, audio_chain="dp_v1")
    source.process(frame)
    legacy = copy.deepcopy(source.snapshot_state())
    legacy["schema_version"] = "s12.stage_w.persistent_engine_state.v2"

    restored = PersistentEventDomainEngine(config, 48000, 960, audio_chain="dp_v1")
    restored.restore_state(legacy)
    assert restored.snapshot_state()["schema_version"] == "s12.stage_w.persistent_engine_state.v3"


@unittest.skipUnless(os.environ.get("S12_RUN_SLOW") == "1", "set S12_RUN_SLOW=1 for the 3000-block acceptance run")
def test_3000x960_stream_matches_one_shot_for_enabled_chain() -> None:
    rng = np.random.default_rng(12)
    signal = rng.standard_normal((3000 * 960, 2)) * 0.01
    one = PressureAudioChain(sample_rate_hz=48000, delay_samples=64.0)
    expected = one.process(signal)
    many = PressureAudioChain(sample_rate_hz=48000, delay_samples=64.0)
    streamed = np.concatenate([many.process(signal[start : start + 960]) for start in range(0, signal.shape[0], 960)], axis=0)
    assert np.max(np.abs(expected - streamed)) < 1.0e-9
    metrics = block_boundary_click_metrics(streamed, 960)
    assert metrics.get("max_abs_jump", metrics.get("max_boundary_jump")) < 0.35


def test_dp_chain_ablation_changes_sha() -> None:
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 1.5)
    _off_raw, off_post, _off_mon, _off_d = _render_architecture("P3", trace)
    _on_raw, on_post, _on_mon, _on_d = _render_architecture("P3DP", trace)
    assert hashlib.sha256(on_post.tobytes()).hexdigest() != hashlib.sha256(off_post.tobytes()).hexdigest()
