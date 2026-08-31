import hashlib
import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.click_contract import block_boundary_click_metrics
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.fixture_cycles import synthesize_hellcat_cycle_bank
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.cycle_sync_resynth import CycleSyncResampler
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.harmonic_map_fit import load_committed_fixture_timbre_map
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import PLACEHOLDER_RECORDS, RENDERABLE_ARCHITECTURES, _render_architecture
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace


def test_p4_is_not_a_placeholder() -> None:
    assert "P4" not in PLACEHOLDER_RECORDS
    assert "P4" in RENDERABLE_ARCHITECTURES


def test_cycle_sync_shares_phase_and_has_no_block_click() -> None:
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    resampler = CycleSyncResampler(bank, sample_rate_hz=48000)
    phase = np.linspace(0.0, 40.0 * np.pi, 9600)
    rpm = np.full(9600, 2000.0)
    audio = resampler.render(phase, rpm)
    assert audio.shape == (9600, 2)
    assert np.all(np.isfinite(audio))
    metrics = block_boundary_click_metrics(audio, 960)
    assert metrics.get("max_abs_jump", metrics.get("max_boundary_jump")) < 0.35
    resampler2 = CycleSyncResampler(bank, sample_rate_hz=48000)
    assert hashlib.sha256(resampler2.render(phase, rpm).tobytes()).hexdigest() == hashlib.sha256(audio.tobytes()).hexdigest()


def test_cycle_sync_uses_full_four_stroke_720_degree_fixture_cycle() -> None:
    """A 360-degree crank turn must not reset a non-symmetric fixture cycle."""
    bank = synthesize_hellcat_cycle_bank(sample_rate_hz=48000)
    resampler = CycleSyncResampler(bank, sample_rate_hz=48000)
    phase = np.array([0.0, 2.0 * np.pi, 4.0 * np.pi])
    rpm = np.full(phase.size, 2000.0)

    audio = resampler.render(phase, rpm)

    assert not np.array_equal(audio[0], audio[1])
    np.testing.assert_array_equal(audio[0], audio[2])


def test_p4_bakeoff_render_differs_from_p2h() -> None:
    trace = build_hellcat_bakeoff_trace("steady_2000rpm", 1.5)
    _p2h_raw, p2h_post, _p2h_mon, _p2h_diag = _render_architecture("P2H", trace)
    p4_raw, p4_post, _p4_mon, _p4_diag = _render_architecture("P4", trace)
    assert np.max(np.abs(p4_raw)) < 1.0
    assert hashlib.sha256(p4_post.tobytes()).hexdigest() != hashlib.sha256(p2h_post.tobytes()).hexdigest()


def _committed_fitted_hellcat_config() -> dict:
    config = load_config("hellcat_v1")
    fitted_map, fitted_table = load_committed_fixture_timbre_map()
    config["timbre_map"] = {
        "rpm_axis": fitted_table.rpm_axis.tolist(),
        "load_axis": fitted_table.load_axis.tolist(),
        "boost_axis": fitted_table.boost_axis.tolist(),
        "order_axis": fitted_table.order_axis.tolist(),
        "values": fitted_table.values.tolist(),
    }
    config["fitted_timbre_map"] = fitted_map
    config["require_fitted_timbre_map"] = True
    return config


def _fresh_p4_engine() -> PersistentEventDomainEngine:
    return PersistentEventDomainEngine(
        _committed_fitted_hellcat_config(),
        sample_rate_hz=48000,
        block_size=960,
        ptr_enabled=True,
        path_model="waveguide_v1",
        forced_induction_model="timbre_map_v1",
        cycle_sync_model="fixture_v1",
    )


def test_p4_one_shot_and_persistent_20ms_partitions_are_exactly_equivalent() -> None:
    """P4 must preserve its absolute cycle-sync phase and all persistent state per 20 ms call."""
    trace = build_hellcat_bakeoff_trace("full_load_acceleration", 0.40)
    state = {
        "rpm": trace.rpm,
        "load": trace.load,
        "throttle": trace.throttle,
        "acceleration_mps2": trace.acceleration_mps2,
    }

    one_shot = _fresh_p4_engine().process_with_trace(state)

    partitioned_engine = _fresh_p4_engine()
    cycle_sync_identity = id(partitioned_engine._cycle_sync)
    pll_identity = id(partitioned_engine.pll)
    raw_blocks = []
    post_ptr_blocks = []
    monitor_blocks = []
    sample_counters = []
    for index in range(trace.rpm.size):
        frame = {name: values[index : index + 1] for name, values in state.items()}
        rendered = partitioned_engine.process_with_trace(frame)
        assert id(partitioned_engine._cycle_sync) == cycle_sync_identity
        assert id(partitioned_engine.pll) == pll_identity
        sample_counters.append(rendered.diagnostics["sample_counter"])
        raw_blocks.append(rendered.raw_pcm)
        post_ptr_blocks.append(rendered.post_ptr_raw)
        monitor_blocks.append(rendered.monitor_pcm)

    assert sample_counters == [960 * (index + 1) for index in range(trace.rpm.size)]
    assert one_shot.diagnostics["sample_counter"] == partitioned_engine.sample_counter
    np.testing.assert_array_equal(np.concatenate(raw_blocks), one_shot.raw_pcm)
    np.testing.assert_array_equal(np.concatenate(post_ptr_blocks), one_shot.post_ptr_raw)
    np.testing.assert_array_equal(np.concatenate(monitor_blocks), one_shot.monitor_pcm)
