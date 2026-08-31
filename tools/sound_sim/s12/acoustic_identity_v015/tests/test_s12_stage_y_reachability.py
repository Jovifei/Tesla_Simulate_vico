from __future__ import annotations

import hashlib
import copy
from types import SimpleNamespace

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import unwrap
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_w import persistent_engine as persistent_engine_module
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import (
    FITTED_MAP_BROADBAND_COUPLING,
    FITTED_MAP_FORCED_LAYER_COUPLING,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_y.harmonic_map_fit import (
    configure_committed_fixture_timbre_map,
    load_committed_fixture_timbre_map,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_x import search_parameters as search_parameter_module
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.search_parameters import (
    METRIC_FUNCS,
    PARAMETER_NOT_REACHABLE,
    PARAMETER_REACHABLE,
    SearchParameter,
    _build_parameter_probe_trace,
    _post_ptr_narrowband_energy_share,
    _render_config_pcm,
    apply_parameters,
    hellcat_search_parameters,
    run_parameter_reachability,
)


def _sha(pcm: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(pcm, dtype=np.float64).tobytes()).hexdigest()


def _render(config, architecture: str, scene: str, duration_s: float = 2.0):
    trace = build_hellcat_bakeoff_trace(scene, duration_s)
    settings = {
        "P2H": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"},
        "P3": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"},
    }[architecture]
    engine = PersistentEventDomainEngine(copy.deepcopy(config), 48000, 960, ptr_enabled=True, **settings)
    return engine.process_with_trace(
        {"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2}
    )


def test_p3_reachability_probe_receives_committed_fitted_map(monkeypatch) -> None:
    """P3 probes must receive the same committed map contract as final runtime."""
    captured: list[tuple[dict, dict]] = []

    class CapturingEngine:
        def __init__(self, config, sample_rate_hz, block_size, *, ptr_enabled, **settings):
            del sample_rate_hz, ptr_enabled
            captured.append((config, {"block_size": block_size, **settings}))

        def process_with_trace(self, state):
            samples = len(state["rpm"]) * captured[-1][1]["block_size"]
            pcm = np.zeros((samples, 2), dtype=np.float64)
            return SimpleNamespace(raw_pcm=pcm, post_ptr_raw=pcm, monitor_pcm=pcm)

    monkeypatch.setattr(persistent_engine_module, "PersistentEventDomainEngine", CapturingEngine)
    trace = _build_parameter_probe_trace("y1_boost_attack", 1.6)
    _render_config_pcm(load_config("hellcat_v1"), "P3", [trace])

    expected_payload, expected_table = load_committed_fixture_timbre_map()
    assert len(captured) == 1
    config, settings = captured[0]
    assert settings["forced_induction_model"] == "timbre_map_v1"
    assert config["require_fitted_timbre_map"] is True
    assert config["fitted_timbre_map"] == expected_payload
    assert config["timbre_map"] == {
        "rpm_axis": expected_table.rpm_axis.tolist(),
        "load_axis": expected_table.load_axis.tolist(),
        "boost_axis": expected_table.boost_axis.tolist(),
        "order_axis": expected_table.order_axis.tolist(),
        "values": expected_table.values.tolist(),
    }


def test_fitted_map_declares_local_broadband_coupling() -> None:
    config = load_config("hellcat_v1")
    configure_committed_fixture_timbre_map(config)
    engine = PersistentEventDomainEngine(
        config, 48000, 960, ptr_enabled=True,
        path_model="waveguide_v1", forced_induction_model="timbre_map_v1",
    )
    balance = engine.diagnostics()["timbre_layer_coupling"]
    assert balance["provenance"] == "bounded_local_fitted_map_source_layer_balance"
    assert balance["fitted_map"] is True
    assert balance["broadband"] == FITTED_MAP_BROADBAND_COUPLING
    assert balance["broadband"] > balance["legacy_broadband"]
    assert balance["forced_layer"] == FITTED_MAP_FORCED_LAYER_COUPLING
    assert balance["forced_layer"] > balance["legacy_forced_layer"]


def test_post_ptr_narrowband_energy_share_is_gain_invariant_and_selective() -> None:
    sample_rate = 48000
    time_s = np.arange(sample_rate, dtype=np.float64) / sample_rate
    target = np.sin(2.0 * np.pi * 118.0 * time_s)
    non_target = np.sin(2.0 * np.pi * 1000.0 * time_s)
    target_stereo = np.column_stack((target, target))
    non_target_stereo = np.column_stack((non_target, non_target))

    target_share = _post_ptr_narrowband_energy_share(target_stereo, sample_rate, (118.0,))
    gained_share = _post_ptr_narrowband_energy_share(7.0 * target_stereo, sample_rate, (118.0,))
    non_target_share = _post_ptr_narrowband_energy_share(non_target_stereo, sample_rate, (118.0,))

    assert target_share > 0.95
    assert np.isclose(
        gained_share, target_share, rtol=1.0e-12, atol=1.0e-15
    )
    assert non_target_share < 0.01
    assert _post_ptr_narrowband_energy_share(np.zeros((sample_rate, 2)), sample_rate, (118.0,)) == 0.0


def test_y1_blower_spectrum_trace_is_fixed_condition_probe() -> None:
    trace = _build_parameter_probe_trace("y1_blower_spectrum", 2.5)
    assert trace.time_s.size == 125
    assert np.all(trace.rpm == 3000.0)
    assert np.all(trace.load == 0.8)
    assert np.all(trace.throttle == 0.8)
    assert np.all(trace.acceleration_mps2 == 0.0)


def test_y1_blower_spectrum_controls_use_committed_map_narrowband_metrics(tmp_path) -> None:
    names = ("blower_sideband_mix", "blower_broadband_mix", "blower_casing_mix")
    summary = _selected_y1_summary(tmp_path, *names)
    by_name = {row["parameter"]: row for row in summary["results"]}
    expected_metrics = {
        "blower_sideband_mix": "blower_sideband_narrowband_share",
        "blower_broadband_mix": "blower_broadband_narrowband_share",
        "blower_casing_mix": "blower_casing_narrowband_share",
    }
    assert tuple(by_name) == names
    assert summary["reachable_count"] == len(names)
    for name, metric in expected_metrics.items():
        row = by_name[name]
        assert row["probe_architecture"] == "P3"
        assert row["probe_scenes"] == ["y1_blower_spectrum"]
        assert row["target_metrics"] == [metric]
        assert row["probe_stem"] == "post_ptr"
        assert row["status"] == PARAMETER_REACHABLE, row["reason"]
        assert row["metric_movement"][metric] > 0.02
        assert row["probe_evidence"]["require_fitted_timbre_map"] is True


def test_crank_inertia_changes_post_ptr_sha_on_idle() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"crank_inertia": 0.24}, parameters)
    high = apply_parameters(base, {"crank_inertia": 0.44}, parameters)
    a = _render(low, "P2H", "hot_idle_20s", 2.0)
    b = _render(high, "P2H", "hot_idle_20s", 2.0)
    assert a.post_ptr_raw is not None and b.post_ptr_raw is not None
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_idle_governor_changes_post_ptr_sha_on_idle() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"idle_governor": 0.15}, parameters)
    high = apply_parameters(base, {"idle_governor": 0.29}, parameters)
    a = _render(low, "P2H", "hot_idle_20s", 2.0)
    b = _render(high, "P2H", "hot_idle_20s", 2.0)
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_primary_attenuation_spread_changes_post_ptr_sha() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"primary_attenuation_spread": 0.72}, parameters)
    high = apply_parameters(base, {"primary_attenuation_spread": 1.28}, parameters)
    a = _render(low, "P2H", "full_load_acceleration", 2.0)
    b = _render(high, "P2H", "full_load_acceleration", 2.0)
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_primary_attenuation_spread_reaches_early_post_ptr_path_balance(tmp_path) -> None:
    """Path attenuation must change early stereo balance without changing topology."""
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"primary_attenuation_spread": 0.75}, parameters)
    high = apply_parameters(base, {"primary_attenuation_spread": 1.25}, parameters)
    unoverridden = apply_parameters(base, {}, parameters)
    low_pcm = _render(low, "P2H", "full_load_acceleration", 1.6).post_ptr_raw
    high_pcm = _render(high, "P2H", "full_load_acceleration", 1.6).post_ptr_raw
    default_pcm = _render(base, "P2H", "full_load_acceleration", 1.6).post_ptr_raw
    unoverridden_pcm = _render(unoverridden, "P2H", "full_load_acceleration", 1.6).post_ptr_raw
    assert low_pcm is not None and high_pcm is not None
    assert default_pcm is not None and unoverridden_pcm is not None
    assert np.all(np.isfinite(low_pcm)) and np.all(np.isfinite(high_pcm))
    assert low_pcm.shape == high_pcm.shape and low_pcm.shape[1] == 2
    assert len(unwrap(low, "per_path_attenuation")) == len(unwrap(high, "per_path_attenuation"))
    assert _sha(default_pcm) == _sha(unoverridden_pcm)

    low_balance = METRIC_FUNCS["early_path_balance"](low_pcm, 48000)
    high_balance = METRIC_FUNCS["early_path_balance"](high_pcm, 48000)
    assert abs(high_balance - low_balance) / max(abs(low_balance), 1.0e-12) > 0.02

    summary = _selected_y1_summary(tmp_path, "primary_attenuation_spread")
    row = summary["results"][0]
    assert row["target_metrics"] == ["early_path_balance"]
    assert row["status"] == PARAMETER_REACHABLE, row["reason"]
    assert row["metric_movement"]["early_path_balance"] > 0.02


def test_blower_sideband_mix_changes_p3_post_ptr_sha() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"blower_sideband_mix": 0.70}, parameters)
    high = apply_parameters(base, {"blower_sideband_mix": 1.30}, parameters)
    a = _render(low, "P3", "full_load_acceleration", 2.0)
    b = _render(high, "P3", "full_load_acceleration", 2.0)
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_afterfire_energy_changes_sha_on_eligible_scene() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"afterfire_energy": 0.04}, parameters)
    high = apply_parameters(base, {"afterfire_energy": 0.08}, parameters)
    a = _render(low, "P3", "afterfire_eligible", 2.5)
    b = _render(high, "P3", "afterfire_eligible", 2.5)
    assert int(a.diagnostics["afterfire_event_count"]) >= 1
    assert int(b.diagnostics["afterfire_event_count"]) >= 1
    assert _sha(a.post_ptr_raw) != _sha(b.post_ptr_raw)


def test_afterfire_ineligible_stays_zero() -> None:
    base = load_config("hellcat_v1")
    block = _render(base, "P3", "afterfire_ineligible", 2.5)
    assert int(block.diagnostics["afterfire_event_count"]) == 0


def test_afterfire_reservoir_state_fraction_modulates_scheduled_energy() -> None:
    """Reservoir rate must affect event energy through accumulated state, not eligibility."""
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"afterfire_reservoir_rate": 0.52}, parameters)
    high = apply_parameters(base, {"afterfire_reservoir_rate": 0.92}, parameters)
    low_result = _render(low, "P3", "afterfire_eligible", 2.5)
    high_result = _render(high, "P3", "afterfire_eligible", 2.5)
    assert int(low_result.diagnostics["afterfire_event_count"]) >= 1
    assert int(low_result.diagnostics["afterfire_event_count"]) == int(high_result.diagnostics["afterfire_event_count"])
    assert low_result.diagnostics["afterfire_route"]["energy"] < high_result.diagnostics["afterfire_route"]["energy"]


def test_monitor_max_makeup_changes_monitor_sha() -> None:
    parameters = hellcat_search_parameters()
    base = load_config("hellcat_v1")
    low = apply_parameters(base, {"monitor_max_makeup": 6.0}, parameters)
    high = apply_parameters(base, {"monitor_max_makeup": 12.0}, parameters)
    a = _render(low, "P2H", "hot_idle_20s", 2.0)
    b = _render(high, "P2H", "hot_idle_20s", 2.0)
    assert _sha(a.monitor_pcm) != _sha(b.monitor_pcm)


NON_AFTERFIRE_Y1 = (
    "crank_inertia", "idle_governor", "primary_attenuation_spread",
    "blower_sideband_mix", "blower_broadband_mix", "blower_casing_mix",
    "boost_attack", "boost_release", "bypass_threshold",
    "monitor_attack", "monitor_release", "monitor_max_makeup",
)

AFTERFIRE_Y1 = (
    "afterfire_reservoir_rate", "afterfire_ignition_delay",
    "afterfire_location_mix", "afterfire_energy",
)


def _selected_y1_summary(tmp_path, *names: str):
    return run_parameter_reachability(
        tmp_path,
        traces=[],
        parameter_names=names,
        write_artifact=False,
    )


def test_y1_selected_probe_is_pure_and_keeps_legacy_artifact_default(tmp_path) -> None:
    summary = _selected_y1_summary(tmp_path, "crank_inertia")
    assert summary["parameter_count"] == 1
    assert not (tmp_path / "parameter_reachability.json").exists()


def test_y1_default_p3_render_matches_fixed_pre_task_parent_golden() -> None:
    """Default Stage-X absence must retain the exact parent runtime behavior."""
    pcm = _render(load_config("hellcat_v1"), "P3", "full_load_acceleration", 1.6).post_ptr_raw
    assert pcm is not None
    assert _sha(pcm) == "7f2906d2a6566f7d49a8b6784e9a1173cb3b2e26ea9f712b4fd01008ea42384e"


def test_y1_reachability_rejects_an_inert_perturbation_direction(monkeypatch, tmp_path) -> None:
    """A one-sided metric/SHA change is not evidence of bilateral reachability."""
    item = SearchParameter(
        "one_sided_probe",
        baseline=1.0,
        delta=0.5,
        apply=lambda config, value: config.__setitem__("one_sided_probe", value),
        target_metrics=("early_path_balance",),
        scenes=(),
    )
    baseline = np.column_stack((np.ones(61440), np.full(61440, 0.5)))
    minus = np.column_stack((np.ones(61440), np.full(61440, 0.9)))

    def fake_render(_item, config, _traces):
        pcm = minus if config.get("one_sided_probe") == 0.5 else baseline
        return [(pcm, pcm, pcm)], {}

    monkeypatch.setattr(search_parameter_module, "hellcat_search_parameters", lambda: [item])
    monkeypatch.setattr(search_parameter_module, "_render_parameter_probe", fake_render)
    row = search_parameter_module.run_parameter_reachability(
        tmp_path, traces=[], parameter_names=(item.name,), write_artifact=False
    )["results"][0]
    assert row["status"] == PARAMETER_NOT_REACHABLE
    assert row["directions"]["minus"]["sha_changed"]
    assert not row["directions"]["plus"]["sha_changed"]


def test_y1_monitor_diagnostic_api_uses_stateful_production_monitor() -> None:
    """Stage X must obtain monitor evidence without touching private state."""
    engine = PersistentEventDomainEngine(
        copy.deepcopy(load_config("hellcat_v1")), 48000, 960, ptr_enabled=True,
        path_model="waveguide_v1", forced_induction_model="harmonic_v1",
    )
    sample = np.arange(engine.block_size, dtype=np.float64) / engine.sample_rate_hz
    low = 0.02 * np.sqrt(2.0) * np.sin(2.0 * np.pi * 233.0 * sample)
    high = 0.15 * np.sqrt(2.0) * np.sin(2.0 * np.pi * 233.0 * sample)
    trace = engine.monitor_diagnostic_trace(
        [np.column_stack((low, low)) for _ in range(60)]
        + [np.column_stack((high, high)) for _ in range(40)]
    )
    assert np.all(np.isfinite(trace.monitor_pcm))
    assert trace.gain_trace_db[59] > trace.gain_trace_db[0]
    assert trace.desired_gain_trace_db[60] < trace.gain_trace_db[59]
    assert trace.gain_trace_db[-1] < trace.gain_trace_db[59]


def test_y1_high_slew_and_idle_recovery_metrics_are_reachable(tmp_path) -> None:
    summary = _selected_y1_summary(tmp_path, "crank_inertia", "idle_governor")
    by_name = {row["parameter"]: row for row in summary["results"]}
    for name in ("crank_inertia", "idle_governor"):
        row = by_name[name]
        assert row["probe_stem"] == "post_ptr"
        assert row["status"] == PARAMETER_REACHABLE, row["reason"]
        assert max(row["metric_movement"][metric] for metric in row["target_metrics"]) > 0.02


def test_y1_path_and_narrowband_metrics_are_reachable(tmp_path) -> None:
    summary = _selected_y1_summary(
        tmp_path, "primary_attenuation_spread", "blower_sideband_mix",
        "blower_broadband_mix", "blower_casing_mix",
    )
    for row in summary["results"]:
        assert row["probe_stem"] == "post_ptr"
        assert row["status"] == PARAMETER_REACHABLE, row["reason"]
        assert max(row["metric_movement"][metric] for metric in row["target_metrics"]) > 0.02


def test_y1_boost_and_bypass_dynamic_metrics_are_reachable(tmp_path) -> None:
    summary = _selected_y1_summary(tmp_path, "boost_attack", "boost_release", "bypass_threshold")
    for row in summary["results"]:
        assert row["probe_stem"] == "post_ptr"
        assert row["status"] == PARAMETER_REACHABLE, row["reason"]
        assert max(row["metric_movement"][metric] for metric in row["target_metrics"]) > 0.02


def test_y1_boost_targets_are_transition_high_band_metrics() -> None:
    assert "boost_attack_high_band_share" in METRIC_FUNCS
    assert "boost_release_high_band_share" in METRIC_FUNCS


def test_y1_boost_attack_and_release_have_positive_bilateral_post_ptr_high_band_share(tmp_path) -> None:
    """Boost taus move the local post-PTR high-band transition share."""
    summary = _selected_y1_summary(tmp_path, "boost_attack", "boost_release")
    by_name = {row["parameter"]: row for row in summary["results"]}
    parameters = {item.name: item for item in hellcat_search_parameters()}
    base = load_config("hellcat_v1")
    normal_default = _render(base, "P3", "full_load_acceleration", 1.6).post_ptr_raw
    normal_unoverridden = _render(
        apply_parameters(base, {}, parameters.values()), "P3", "full_load_acceleration", 1.6
    ).post_ptr_raw
    assert normal_default is not None and normal_unoverridden is not None
    assert np.all(np.isfinite(normal_default)) and np.all(np.isfinite(normal_unoverridden))
    assert _sha(normal_default) == _sha(normal_unoverridden)
    expected = {
        "boost_attack": (0.08, 0.07, "boost_attack_high_band_share"),
        "boost_release": (0.25, 0.24, "boost_release_high_band_share"),
    }
    assert tuple(by_name) == tuple(expected)
    for name, (baseline, delta, metric) in expected.items():
        row = by_name[name]
        assert row["baseline"] == baseline
        assert row["delta"] == delta
        assert row["baseline"] - row["delta"] > 0.0
        assert row["baseline"] + row["delta"] > row["baseline"]
        assert row["target_metrics"] == [metric]
        assert row["probe_stem"] == "post_ptr"
        assert row["status"] == PARAMETER_REACHABLE, row["reason"]
        assert row["metric_movement"][metric] > 0.02
        trace = _build_parameter_probe_trace(parameters[name].scenes[0][0], parameters[name].scenes[0][1])
        post_ptr = []
        for value in (baseline, baseline - delta, baseline + delta):
            config = apply_parameters(base, {name: value}, parameters.values())
            post_ptr.append(_render_config_pcm(config, parameters[name].architecture, [trace])[0][1])
        assert all(np.all(np.isfinite(pcm)) for pcm in post_ptr)
        assert _sha(post_ptr[0]) != _sha(post_ptr[1])
        assert _sha(post_ptr[0]) != _sha(post_ptr[2])


def test_y1_descending_monitor_gain_metrics_are_reachable(tmp_path) -> None:
    summary = _selected_y1_summary(tmp_path, "monitor_attack", "monitor_release", "monitor_max_makeup")
    for row in summary["results"]:
        assert row["probe_stem"] == "monitor"
        assert row["status"] == PARAMETER_REACHABLE, row["reason"]
        assert max(row["metric_movement"][metric] for metric in row["target_metrics"]) > 0.02


def test_y1_monitor_release_probe_raises_then_releases_with_actual_consumer(tmp_path) -> None:
    """The monitor-release probe must exercise both branches of the stateful consumer."""
    row = _selected_y1_summary(tmp_path, "monitor_release")["results"][0]
    assert row.get("probe_mode") == "monitor_step"
    evidence = row["probe_evidence"]
    assert evidence["attack_gain_end_db"] > evidence["attack_gain_start_db"]
    assert evidence["release_desired_gain_db"] < evidence["attack_gain_end_db"]
    assert evidence["release_gain_end_db"] < evidence["attack_gain_end_db"]
    assert row["status"] == PARAMETER_REACHABLE, row["reason"]
    assert row["metric_movement"]["monitor_release_envelope_rms"] > 0.02


def test_y1_selected_non_afterfire_parameters_are_reachable(tmp_path) -> None:
    summary = _selected_y1_summary(tmp_path, *NON_AFTERFIRE_Y1)
    by_name = {row["parameter"]: row for row in summary["results"]}
    assert tuple(by_name) == NON_AFTERFIRE_Y1
    assert summary["reachable_count"] == len(NON_AFTERFIRE_Y1)
    assert not summary["unreachable"]


def test_y1_afterfire_controls_are_bilateral_event_local_residual_probes(tmp_path) -> None:
    """Afterfire reachability measures event-local residuals but SHA stays post-PTR."""
    summary = _selected_y1_summary(tmp_path, *AFTERFIRE_Y1)
    by_name = {row["parameter"]: row for row in summary["results"]}
    expected_metrics = {
        "afterfire_reservoir_rate": {"afterfire_residual_energy_envelope"},
        "afterfire_ignition_delay": {"afterfire_residual_onset", "afterfire_residual_peak_offset"},
        "afterfire_location_mix": {"afterfire_residual_path_balance", "afterfire_residual_peak_offset"},
        "afterfire_energy": {"afterfire_residual_energy_envelope", "afterfire_residual_crest"},
    }
    assert tuple(by_name) == AFTERFIRE_Y1
    for name in AFTERFIRE_Y1:
        row = by_name[name]
        assert row["probe_mode"] == "afterfire_residual"
        assert row["probe_stem"] == "post_ptr"
        assert set(row["target_metrics"]) == expected_metrics[name]
        assert row["status"] == PARAMETER_REACHABLE, row["reason"]
        assert row["probe_evidence"]["afterfire_gain_zero_control"] is True
        for direction in ("minus", "plus"):
            evidence = row["directions"][direction]
            assert evidence["finite"]
            assert evidence["sha_changed"]
            assert evidence["target_movement"] > 0.02
