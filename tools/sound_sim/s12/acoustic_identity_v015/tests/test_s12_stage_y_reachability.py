from __future__ import annotations

import hashlib
import copy

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import load_config
from tools.sound_sim.s12.acoustic_identity_v015.event_domain.config_schema import unwrap
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import build_hellcat_bakeoff_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_w.persistent_engine import PersistentEventDomainEngine
from tools.sound_sim.s12.acoustic_identity_v015.stage_x.search_parameters import (
    PARAMETER_REACHABLE,
    _build_parameter_probe_trace,
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
    low = apply_parameters(base, {"primary_attenuation_spread": 0.75}, parameters)
    high = apply_parameters(base, {"primary_attenuation_spread": 1.25}, parameters)
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

    def early_path_balance(pcm: np.ndarray) -> float:
        early = pcm[: int(round(0.20 * pcm.shape[0]))]
        energy = np.mean(np.square(early), axis=0)
        return float((energy[0] - energy[1]) / max(float(np.sum(energy)), 1.0e-12))

    low_balance = early_path_balance(low_pcm)
    high_balance = early_path_balance(high_pcm)
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


def test_y1_boost_attack_and_release_have_positive_bilateral_post_ptr_envelopes(tmp_path) -> None:
    """Boost taus use the engine defaults and move their local post-PTR envelopes."""
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
        "boost_attack": (0.08, 0.07, "boost_attack_envelope_rms"),
        "boost_release": (0.25, 0.24, "boost_release_envelope_rms"),
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
