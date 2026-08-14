"""Round-2 renderer integration contracts for the Stage-L Hellcat v9 path."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import (
    load_stage_l_candidate,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import (
    build_hellcat_crank_clock,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import (
    render_stage_l_candidate,
    render_stage_l_round2_formal_final_pcm_bundle,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
V8_PROFILE = PACKAGE_ROOT / "targets/stage_l_candidates/hellcat_candidate_v8.json"
V9_PROFILE = PACKAGE_ROOT / "targets/stage_l_candidates/hellcat_candidate_v9.json"
V8_PRESSURE_SHA256 = "ea0a2be3df626dc50f5031d2a122c0aa4e9c6a6c0fe5c1b5067d0df590ade43a"
HEMI_CONTRIBUTORS = (
    "hemi_exhaust_left",
    "hemi_exhaust_right",
    "hemi_blowdown_body",
    "hemi_structure_shock",
    "hemi_mechanical_torque_ripple",
)
SC_CONTRIBUTORS = (
    "sc_intake_radiated",
    "sc_casing_radiated",
    "sc_bypass_release",
)


def _baseline_trace() -> VehicleStateTrace:
    time_s = np.linspace(0.0, 0.25, 251, dtype=np.float64)
    rpm = np.linspace(900.0, 3600.0, time_s.size)
    load = np.linspace(0.12, 0.94, time_s.size)
    throttle = np.linspace(0.08, 0.96, time_s.size)
    return VehicleStateTrace(
        time_s,
        rpm,
        load,
        throttle,
        np.gradient(rpm / 60.0, time_s),
    ).validate()


def _hot_lift_trace() -> VehicleStateTrace:
    time_s = np.linspace(0.0, 1.5, 1501, dtype=np.float64)
    hot = time_s < 1.0
    rpm = np.where(hot, 5200.0 + 200.0 * time_s, 5400.0 - 1800.0 * (time_s - 1.0))
    load = np.where(hot, 0.94, 0.07)
    throttle = np.where(hot, 0.97, 0.02)
    return VehicleStateTrace(
        time_s,
        rpm,
        load,
        throttle,
        np.gradient(rpm / 60.0, time_s),
    ).validate()


def _eight_second_frozen_trace() -> VehicleStateTrace:
    time_s = np.linspace(0.0, 8.25, 826, dtype=np.float64)
    round2_active = time_s >= 8.05
    rpm = np.where(round2_active, 5200.0, 1800.0)
    load = np.where(round2_active, 0.94, 0.18)
    throttle = np.where(round2_active, 0.97, 0.16)
    return VehicleStateTrace(
        time_s,
        rpm,
        load,
        throttle,
        np.gradient(rpm / 60.0, time_s),
    ).validate()


def _sha_array(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def test_v8_schema_v1_renderer_pressure_bytes_remain_frozen() -> None:
    candidate = load_stage_l_candidate(V8_PROFILE)

    rendered = render_stage_l_candidate(_baseline_trace(), candidate)

    assert candidate.payload["schema_version"] == "s12-stage-l-hellcat-candidate-profile-1"
    assert _sha_array(rendered.pressure) == V8_PRESSURE_SHA256
    assert "afterfire" not in rendered.diagnostics["pressure_stem_contract"]["contributors"]


def test_v9_schema_v2_dispatches_only_to_sc_v6_crossplane_v3_and_afterfire_v1(
    monkeypatch,
) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.sources import (
        hellcat_crossplane_combustion_v3,
        hellcat_supercharger_intake_v6,
    )
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import (
        hellcat_afterfire_v1,
        render_candidate as renderer,
    )

    calls: list[str] = []
    real_sc_v6 = hellcat_supercharger_intake_v6.render_hellcat_supercharger_intake_v6
    real_hemi_v3 = hellcat_crossplane_combustion_v3.render_hellcat_crossplane_combustion_v3
    real_afterfire_v1 = hellcat_afterfire_v1.render_hellcat_afterfire_v1

    def sc_v6(*args, **kwargs):
        calls.append("sc_v6")
        return real_sc_v6(*args, **kwargs)

    def hemi_v3(*args, **kwargs):
        calls.append("hemi_v3")
        return real_hemi_v3(*args, **kwargs)

    def afterfire_v1(*args, **kwargs):
        calls.append("afterfire_v1")
        return real_afterfire_v1(*args, **kwargs)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("v9 dispatched through a frozen v8 renderer")

    monkeypatch.setattr(renderer, "render_hellcat_supercharger_intake_v6", sc_v6, raising=False)
    monkeypatch.setattr(renderer, "render_hellcat_crossplane_combustion_v3", hemi_v3, raising=False)
    monkeypatch.setattr(renderer, "render_hellcat_afterfire_v1", afterfire_v1, raising=False)
    monkeypatch.setattr(renderer, "render_hellcat_supercharger_intake_v5", forbidden)
    monkeypatch.setattr(renderer, "render_hellcat_crossplane_combustion_v2", forbidden)
    monkeypatch.setattr(renderer, "apply_afterfire", forbidden)

    rendered = render_stage_l_candidate(_hot_lift_trace(), load_stage_l_candidate(V9_PROFILE))

    assert calls[:3] == ["hemi_v3", "sc_v6", "afterfire_v1"]
    assert calls.count("hemi_v3") >= 2
    assert calls.count("sc_v6") >= 2
    contributors = rendered.diagnostics["pressure_stem_contract"]["contributors"]
    assert contributors.count("afterfire") == 1
    assert rendered.diagnostics["round2_renderer_dispatch"] == {
        "schema_version": "s12-stage-l-hellcat-candidate-profile-2",
        "combustion": "hellcat_crossplane_combustion_v3",
        "supercharger": "hellcat_supercharger_intake_v6",
        "afterfire": "hellcat_afterfire_v1",
    }


def test_v9_afterfire_is_counted_once_and_pressure_equals_primitive_contributors() -> None:
    rendered = render_stage_l_candidate(_hot_lift_trace(), load_stage_l_candidate(V9_PROFILE))
    contract = rendered.diagnostics["pressure_stem_contract"]
    contributors = tuple(contract["contributors"])

    assert contributors.count("afterfire") == 1
    assert not set(contributors) & set(contract["diagnostic_aggregates"])
    rebuilt = sum(
        (np.asarray(rendered.stems[name], dtype=np.float64) for name in contributors),
        np.zeros_like(rendered.pressure),
    )
    assert np.array_equal(rendered.pressure, rebuilt)
    assert np.array_equal(
        rendered.stems["exhaust"],
        rendered.stems["hemi_exhaust_left"] + rendered.stems["hemi_exhaust_right"],
    )
    assert np.array_equal(
        rendered.stems["supercharger_intake"],
        sum(
            (rendered.stems[name] for name in SC_CONTRIBUTORS),
            np.zeros_like(rendered.pressure),
        ),
    )
    usage = rendered.diagnostics["candidate_parameter_usage"]
    assert not usage["unused"]
    assert set(usage["read"]) == set(usage["requested"])


def test_v9_supercharger_control_changes_only_sc_arrays_not_hemi_or_exhaust() -> None:
    trace = _hot_lift_trace()
    seed = load_stage_l_candidate(V9_PROFILE)
    low = seed.with_parameter(
        "supercharger_intake", "high_load_whine_post_knee_slope", 0.45,
    )
    high = seed.with_parameter(
        "supercharger_intake", "high_load_whine_post_knee_slope", 0.85,
    )

    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as renderer

    clock = build_hellcat_crank_clock(trace, 48_000)
    low_hemi = renderer.render_crossplane_combustion_l2_v3_with_clock(
        trace, clock,
        {name: float(record["value"]) for name, record in low.payload["combustion_and_blowdown"].items()},
    )
    high_hemi = renderer.render_crossplane_combustion_l2_v3_with_clock(
        trace, clock,
        {name: float(record["value"]) for name, record in high.payload["combustion_and_blowdown"].items()},
    )
    low_sc = renderer.render_supercharger_intake_l3_v6_with_clock(
        trace, clock,
        {name: float(record["value"]) for name, record in low.payload["supercharger_intake"].items()},
    )
    high_sc = renderer.render_supercharger_intake_l3_v6_with_clock(
        trace, clock,
        {name: float(record["value"]) for name, record in high.payload["supercharger_intake"].items()},
    )

    for name in HEMI_CONTRIBUTORS:
        assert np.array_equal(low_hemi.stems[name], high_hemi.stems[name]), name
    assert any(
        not np.array_equal(low_sc.stems[name], high_sc.stems[name])
        for name in SC_CONTRIBUTORS
    )
    assert not any("exhaust" in name for name in low_sc.stems)


def test_v9_first_eight_seconds_match_v8_primitive_aggregate_and_pressure_bytes() -> None:
    trace = _eight_second_frozen_trace()
    v8 = render_stage_l_candidate(trace, load_stage_l_candidate(V8_PROFILE))
    v9 = render_stage_l_candidate(trace, load_stage_l_candidate(V9_PROFILE))
    frozen = np.arange(v9.pressure.shape[0], dtype=np.float64) / 48_000.0 < 8.0

    assert np.array_equal(v9.pressure[frozen], v8.pressure[frozen])
    for name in HEMI_CONTRIBUTORS + SC_CONTRIBUTORS + (
        "exhaust",
        "hemi_exhaust",
        "hemi_combustion_and_blowdown",
        "supercharger_intake",
    ):
        assert np.array_equal(v9.stems[name][frozen], v8.stems[name][frozen]), name


def test_round2_three_track_bundle_shares_one_gain_and_derives_comfort_from_v9(
    monkeypatch,
) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as renderer

    time_s = np.arange(48_000, dtype=np.float64) / 48_000.0
    tone = np.sin(2.0 * np.pi * 220.0 * time_s)
    parent = np.column_stack((0.04 * tone, 0.04 * tone))
    v8 = np.column_stack((0.06 * tone, 0.06 * tone))
    v9 = np.column_stack((0.08 * tone, 0.08 * tone))
    calls: list[tuple[str, ...]] = []
    real_manager = renderer.manage_bundle_loudness

    def one_bundle(segments, *args, **kwargs):
        calls.append(tuple(segments))
        return real_manager(segments, *args, **kwargs)

    monkeypatch.setattr(renderer, "manage_bundle_loudness", one_bundle)
    bundle = render_stage_l_round2_formal_final_pcm_bundle(
        parent,
        v8,
        v9,
        target_lufs=-16.0,
        peak_limit_dbfs=-1.5,
        comfort_requested_gain_db=1.0,
    )

    assert calls == [("stage_k_parent", "stage_l_v8", "stage_l_v9")]
    assert bundle.pipeline_order == (
        "frozen_ptr",
        "edge_fade",
        "one_fixed_whole_cycle_gain",
        "pcm24",
    )
    assert bundle.comfort_pipeline_order == (
        *bundle.pipeline_order,
        "candidate_comfort_static_gain",
    )
    assert 0.0 <= bundle.comfort_gain_db <= 1.0
    assert np.array_equal(
        bundle.comfort_pcm,
        bundle.v9_pcm * 10.0 ** (bundle.comfort_gain_db / 20.0),
    )
    assert np.max(np.abs(bundle.comfort_pcm)) <= 10.0 ** (-1.5 / 20.0) + 1.0e-12
