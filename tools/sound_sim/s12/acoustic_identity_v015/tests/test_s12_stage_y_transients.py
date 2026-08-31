import copy
import hashlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.harmonic_map_fit import load_committed_fixture_timbre_map
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.state_transients import StateTransientMixer
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace, _render_architecture
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine


def _frame(rpm: float, throttle: float, load: float = 0.70) -> dict[str, np.ndarray]:
    return {
        "rpm": np.asarray([rpm], dtype=np.float64),
        "load": np.asarray([load], dtype=np.float64),
        "throttle": np.asarray([throttle], dtype=np.float64),
        "acceleration_mps2": np.asarray([0.0], dtype=np.float64),
    }


def _engine(*, fitted_timbre_map: bool = False, transient_model: str = "state_v1") -> PersistentEventDomainEngine:
    config = load_config("hellcat_v1")
    forced_induction_model = "harmonic_v1"
    if fitted_timbre_map:
        fitted, table = load_committed_fixture_timbre_map()
        config["timbre_map"] = {
            "rpm_axis": table.rpm_axis.tolist(),
            "load_axis": table.load_axis.tolist(),
            "boost_axis": table.boost_axis.tolist(),
            "order_axis": table.order_axis.tolist(),
            "values": table.values.tolist(),
        }
        config["fitted_timbre_map"] = fitted
        config["require_fitted_timbre_map"] = True
        forced_induction_model = "timbre_map_v1"
    return PersistentEventDomainEngine(
        config,
        sample_rate_hz=48000,
        block_size=960,
        path_model="waveguide_v1",
        forced_induction_model=forced_induction_model,
        transient_model=transient_model,
    )


def _active_tip_snapshot(engine: PersistentEventDomainEngine) -> dict:
    engine.process(_frame(3600.0, 0.18))
    engine.process(_frame(3600.0, 0.90))
    return engine.snapshot_state()


def _assert_snapshot_equal(left, right) -> None:
    if isinstance(left, np.ndarray):
        assert isinstance(right, np.ndarray)
        assert np.array_equal(left, right)
    elif isinstance(left, dict):
        assert isinstance(right, dict)
        assert left.keys() == right.keys()
        for key in left:
            _assert_snapshot_equal(left[key], right[key])
    elif isinstance(left, list):
        assert isinstance(right, list)
        assert len(left) == len(right)
        for left_item, right_item in zip(left, right):
            _assert_snapshot_equal(left_item, right_item)
    else:
        assert left == right


def test_equal_power_crossfade_has_endpoints_and_unit_gain_square_sum_for_orthogonal_inputs() -> None:
    mixer = StateTransientMixer(sample_rate_hz=48000)
    a = np.zeros((960, 2)); a[:, 0] = 1.0
    b = np.zeros((960, 2)); b[:, 1] = 2.0
    assert np.array_equal(mixer.equal_power_crossfade(a, b, mix=0.0), a)
    assert np.array_equal(mixer.equal_power_crossfade(a, b, mix=1.0), b)
    mix = 0.5
    out = mixer.equal_power_crossfade(a, b, mix=mix)
    gain_a = np.cos(mix * np.pi / 2.0)
    gain_b = np.sin(mix * np.pi / 2.0)
    assert gain_a * gain_a + gain_b * gain_b == pytest.approx(1.0)
    assert float(np.mean(np.square(out))) == pytest.approx(
        gain_a * gain_a * float(np.mean(np.square(a)))
        + gain_b * gain_b * float(np.mean(np.square(b)))
    )


def test_transient_events_are_one_shot_and_tip_tail_continues_across_calls() -> None:
    mixer = StateTransientMixer(sample_rate_hz=48000)
    mixer.render_block(960, throttle=0.18, rpm=4200.0, boost=0.70, dt=0.020)
    first, first_diag = mixer.render_block(960, throttle=0.90, rpm=4200.0, boost=0.70, dt=0.020)
    second, second_diag = mixer.render_block(960, throttle=0.90, rpm=4200.0, boost=0.70, dt=0.020)
    assert first_diag["transient_tip_in_count"] == 1
    assert second_diag["transient_tip_in_count"] == 1
    assert np.any(first)
    assert np.any(second)

    mixer.render_block(960, throttle=0.10, rpm=4200.0, boost=0.70, dt=0.020)
    _shift, shift_diag = mixer.render_block(960, throttle=0.75, rpm=3200.0, boost=0.70, dt=0.020)
    _steady_shift, steady_shift_diag = mixer.render_block(960, throttle=0.75, rpm=3200.0, boost=0.70, dt=0.020)
    assert shift_diag["transient_shift_count"] == 1
    assert steady_shift_diag["transient_shift_count"] == 1

    mixer.render_block(960, throttle=0.90, rpm=3200.0, boost=0.80, dt=0.020)
    _lift_bov, lift_bov_diag = mixer.render_block(960, throttle=0.05, rpm=3200.0, boost=0.20, dt=0.020)
    _steady_lift_bov, steady_lift_bov_diag = mixer.render_block(960, throttle=0.05, rpm=3200.0, boost=0.20, dt=0.020)
    assert lift_bov_diag["transient_lift_count"] >= 1
    assert lift_bov_diag["transient_bov_count"] == 1
    assert steady_lift_bov_diag["transient_lift_count"] == lift_bov_diag["transient_lift_count"]
    assert steady_lift_bov_diag["transient_bov_count"] == 1


def test_render_block_rejects_size_above_tail_capacity_atomically() -> None:
    mixer = StateTransientMixer(sample_rate_hz=48000)
    capacity = mixer._tail_length
    block, _ = mixer.render_block(capacity, throttle=0.18, rpm=4200.0, boost=0.70, dt=0.020)
    assert block.shape == (capacity, 2)
    before = copy.deepcopy(mixer.snapshot())

    with pytest.raises(ValueError, match="tail capacity"):
        mixer.render_block(capacity + 1, throttle=0.90, rpm=4200.0, boost=0.70, dt=0.020)

    _assert_snapshot_equal(mixer.snapshot(), before)


def test_each_transient_latch_releases_before_the_same_threshold_can_trigger_again() -> None:
    # Each scenario is isolated so the assertion proves the event-specific
    # latch/re-arm contract rather than relying on another event's state.
    mixer = StateTransientMixer(sample_rate_hz=48000)
    mixer.render_block(960, throttle=0.18, rpm=4200.0, boost=0.70, dt=0.020)
    for _ in range(3):
        _, diagnostics = mixer.render_block(960, throttle=0.90, rpm=4200.0, boost=0.70, dt=0.020)
    assert diagnostics["transient_tip_in_count"] == 1
    mixer.render_block(960, throttle=0.18, rpm=4200.0, boost=0.70, dt=0.020)
    _, diagnostics = mixer.render_block(960, throttle=0.90, rpm=4200.0, boost=0.70, dt=0.020)
    assert diagnostics["transient_tip_in_count"] == 2

    mixer = StateTransientMixer(sample_rate_hz=48000)
    mixer.render_block(960, throttle=0.90, rpm=4200.0, boost=0.70, dt=0.020)
    for throttle in (0.40, 0.0, 0.0):
        _, diagnostics = mixer.render_block(960, throttle=throttle, rpm=4200.0, boost=0.70, dt=0.020)
    assert diagnostics["transient_lift_count"] == 1
    mixer.render_block(960, throttle=0.20, rpm=4200.0, boost=0.70, dt=0.020)
    _, diagnostics = mixer.render_block(960, throttle=0.05, rpm=4200.0, boost=0.70, dt=0.020)
    assert diagnostics["transient_lift_count"] == 2

    mixer = StateTransientMixer(sample_rate_hz=48000)
    mixer.render_block(960, throttle=0.75, rpm=4200.0, boost=0.70, dt=0.020)
    for rpm in (3200.0, 2200.0, 1200.0):
        _, diagnostics = mixer.render_block(960, throttle=0.75, rpm=rpm, boost=0.70, dt=0.020)
    assert diagnostics["transient_shift_count"] == 1
    mixer.render_block(960, throttle=0.75, rpm=3200.0, boost=0.70, dt=0.020)
    mixer.render_block(960, throttle=0.75, rpm=4200.0, boost=0.70, dt=0.020)
    _, diagnostics = mixer.render_block(960, throttle=0.75, rpm=3200.0, boost=0.70, dt=0.020)
    assert diagnostics["transient_shift_count"] == 2

    mixer = StateTransientMixer(sample_rate_hz=48000)
    mixer.render_block(960, throttle=0.90, rpm=4200.0, boost=0.80, dt=0.020)
    for boost in (0.20, 0.05, 0.0):
        _, diagnostics = mixer.render_block(960, throttle=0.05, rpm=4200.0, boost=boost, dt=0.020)
    assert diagnostics["transient_bov_count"] == 1
    mixer.render_block(960, throttle=0.30, rpm=4200.0, boost=0.20, dt=0.020)
    mixer.render_block(960, throttle=0.90, rpm=4200.0, boost=0.80, dt=0.020)
    _, diagnostics = mixer.render_block(960, throttle=0.05, rpm=4200.0, boost=0.20, dt=0.020)
    assert diagnostics["transient_bov_count"] == 2


def test_shift_tail_uses_maximum_packet_duration_and_drains_completely() -> None:
    mixer = StateTransientMixer(sample_rate_hz=48000)
    mixer.render_block(960, throttle=0.75, rpm=4200.0, boost=0.70, dt=0.020)
    first, diagnostics = mixer.render_block(960, throttle=0.75, rpm=3200.0, boost=0.70, dt=0.020)
    assert diagnostics["transient_shift_count"] == 1
    later = []
    for _ in range(5):
        block, _ = mixer.render_block(960, throttle=0.75, rpm=3200.0, boost=0.70, dt=0.020)
        later.append(block)
    assert np.any(first)
    assert np.any(later[3])  # 80-100 ms: beyond the old 80 ms allocation.
    assert np.any(later[4])  # 100-120 ms: the configured shift tail's final block.
    drained, drained_diagnostics = mixer.render_block(960, throttle=0.75, rpm=3200.0, boost=0.70, dt=0.020)
    assert not np.any(drained)
    assert drained_diagnostics["transient_crossfade_active_samples"] == 0


def test_transient_snapshot_rejects_malformed_tail_and_latch_atomically() -> None:
    mixer = StateTransientMixer(sample_rate_hz=48000)
    mixer.render_block(960, throttle=0.18, rpm=4200.0, boost=0.70, dt=0.020)
    mixer.render_block(960, throttle=0.90, rpm=4200.0, boost=0.70, dt=0.020)
    before = copy.deepcopy(mixer.snapshot())
    for mutate in (
        lambda value: value["audio_tails"]["tip_in"].__setitem__(0, np.nan),
        lambda value: value["mix_tails"]["shift"].__setitem__(0, np.inf),
        lambda value: value.__setitem__("lift_latched", 1),
    ):
        invalid = copy.deepcopy(before)
        mutate(invalid)
        with pytest.raises(ValueError):
            mixer.restore(invalid)
        _assert_snapshot_equal(mixer.snapshot(), before)


def test_state_v1_transient_engine_streaming_matches_one_shot_and_hard_reset_repeats() -> None:
    states = {
        "rpm": np.asarray([850.0, 4200.0, 4200.0, 3200.0, 3200.0, 4200.0, 4200.0], dtype=np.float64),
        "load": np.asarray([0.18, 0.70, 0.70, 0.70, 0.70, 0.70, 0.70], dtype=np.float64),
        "throttle": np.asarray([0.18, 0.90, 0.90, 0.05, 0.05, 0.90, 0.90], dtype=np.float64),
        "acceleration_mps2": np.zeros(7, dtype=np.float64),
    }
    one = _engine()
    one_audio = one.process(states).raw_pcm
    streamed = _engine()
    streamed_audio = np.concatenate([streamed.process(_frame(float(states["rpm"][i]), float(states["throttle"][i]), float(states["load"][i]))).raw_pcm for i in range(7)], axis=0)
    assert np.array_equal(one_audio, streamed_audio)
    streamed.reset("hard")
    assert np.array_equal(streamed.process(states).raw_pcm, one_audio)


def test_real_p5_diagnostics_propagate_all_transient_stems_and_bakeoff_aggregates_them() -> None:
    trace = build_hellcat_bakeoff_trace("gear_shift", 2.0)
    _raw, _post, _monitor, diagnostics = _render_architecture("P5", trace)
    count_keys = tuple(f"transient_{name}_count" for name in ("tip_in", "lift", "shift", "bov"))
    energy_keys = tuple(f"transient_{name}_stem_energy" for name in ("tip_in", "lift", "shift", "bov"))
    assert all(key in diagnostics for key in count_keys + energy_keys)
    assert "transient_crossfade_active_samples" in diagnostics
    assert diagnostics["transient_residual_event_count"] == sum(diagnostics[key] for key in count_keys)
    assert diagnostics["transient_shift_count"] >= 1
    assert diagnostics["transient_shift_stem_energy"] > 0.0
    assert diagnostics["transient_crossfade_active_samples"] > 0


def test_real_renderer_consumes_equal_power_crossfade_and_requires_shift_event(monkeypatch) -> None:
    calls: list[np.ndarray] = []
    original = StateTransientMixer.equal_power_crossfade

    def traced(self, a, b, mix):
        calls.append(np.asarray(mix, dtype=np.float64).copy())
        return original(self, a, b, mix)

    monkeypatch.setattr(StateTransientMixer, "equal_power_crossfade", traced)
    shift = build_hellcat_bakeoff_trace("gear_shift", 2.0)
    _raw_on, post_on, _mon_on, diagnostics = _render_architecture("P5", shift)
    _raw_off, post_off, _mon_off, _ = _render_architecture("P3", shift)
    assert diagnostics["transient_shift_count"] >= 1
    assert hashlib.sha256(post_on.tobytes()).hexdigest() != hashlib.sha256(post_off.tobytes()).hexdigest()
    assert calls
    assert any(np.any((mix > 0.0) & (mix < 1.0)) for mix in calls)


@pytest.mark.parametrize("fitted_timbre_map", (False, True))
def test_snapshot_restore_replays_active_transient_tail_in_same_and_fresh_engine(fitted_timbre_map: bool) -> None:
    engine = _engine(fitted_timbre_map=fitted_timbre_map)
    snapshot = _active_tip_snapshot(engine)
    expected = engine.process(_frame(3600.0, 0.90)).raw_pcm
    engine.process(_frame(3600.0, 0.90))
    engine.restore_state(snapshot)
    assert np.array_equal(engine.process(_frame(3600.0, 0.90)).raw_pcm, expected)

    fresh = _engine(fitted_timbre_map=fitted_timbre_map)
    fresh.restore_state(snapshot)
    assert np.array_equal(fresh.process(_frame(3600.0, 0.90)).raw_pcm, expected)


def test_snapshot_restore_rejects_filter_or_model_mismatch_atomically() -> None:
    engine = _engine()
    _active_tip_snapshot(engine)
    before = copy.deepcopy(engine.snapshot_state())
    for mutate in (
        lambda value: value.__setitem__("path_filter_state", [0.0]),
        lambda value: value.__setitem__("path_filter_state", [float("nan")] * engine.entity_count),
        lambda value: value["runtime_models"].__setitem__("transient_model", "off"),
    ):
        invalid = copy.deepcopy(before)
        mutate(invalid)
        with pytest.raises(ValueError):
            engine.restore_state(invalid)
        _assert_snapshot_equal(engine.snapshot_state(), before)


def test_legacy_snapshot_is_accepted_only_at_zero_state_and_off_mode_retains_default_output() -> None:
    pristine = _engine()
    legacy_zero = pristine.snapshot_state()
    legacy_zero["schema_version"] = "s12.stage_w.persistent_engine_state.v1"
    legacy_zero.pop("path_filter_state")
    legacy_zero.pop("runtime_models")
    legacy_zero.pop("transient_state")
    restored = _engine()
    restored.restore_state(legacy_zero)
    assert restored.sample_counter == 0

    nonzero_legacy = _active_tip_snapshot(pristine)
    nonzero_legacy["schema_version"] = "s12.stage_w.persistent_engine_state.v1"
    nonzero_legacy.pop("path_filter_state")
    nonzero_legacy.pop("runtime_models")
    nonzero_legacy.pop("transient_state")
    with pytest.raises(ValueError, match="legacy snapshot"):
        restored.restore_state(nonzero_legacy)

    default = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, path_model="waveguide_v1")
    explicit_off = PersistentEventDomainEngine(load_config("hellcat_v1"), 48000, 960, path_model="waveguide_v1", transient_model="off")
    state = _frame(3300.0, 0.72)
    assert np.array_equal(default.process(state).raw_pcm, explicit_off.process(state).raw_pcm)


def test_legacy_zero_snapshot_migration_discards_dirty_target_transient_state() -> None:
    source = _engine()
    legacy_zero = source.snapshot_state()
    legacy_zero["schema_version"] = "s12.stage_w.persistent_engine_state.v1"
    legacy_zero.pop("path_filter_state")
    legacy_zero.pop("runtime_models")
    legacy_zero.pop("transient_state")

    restored = _engine()
    restored.process(_frame(3600.0, 0.18))
    restored.process(_frame(3600.0, 0.90))
    restored.restore_state(legacy_zero)

    fresh = _engine()
    state = _frame(3600.0, 0.18)
    assert np.array_equal(restored.process(state).raw_pcm, fresh.process(state).raw_pcm)
