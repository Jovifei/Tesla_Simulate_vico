from __future__ import annotations

import numpy as np

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.sources.flat_plane_v8_source import render_ferrari_458
from tools.sound_sim.s12.acoustic_identity_v015.sources.rotary_turbo_source import render_rx7_fd
from tools.sound_sim.s12.acoustic_identity_v015.sources.supercharged_hemi_source import render_hellcat
from tools.sound_sim.s12.acoustic_identity_v015.stage_g.candidate_profiles import SOURCE_KEYS


def _trace(rpm: float, load: float = 0.75, duration_s: float = 0.35) -> VehicleStateTrace:
    time_s = np.linspace(0.0, duration_s, int(round(duration_s * 48_000)) + 1)
    return VehicleStateTrace(time_s, np.full_like(time_s, rpm), np.full_like(time_s, load), np.full_like(time_s, load), np.zeros_like(time_s)).validate()


def _relative_change(before: np.ndarray, after: np.ndarray) -> float:
    return float(np.linalg.norm(after - before) / max(np.linalg.norm(before), 1e-12))


def test_stage_u_candidate_schema_exposes_real_source_controls() -> None:
    assert {"metallic_gain_scale", "mid_carrier_gain_scale", "metallic_texture_mix"} <= SOURCE_KEYS["ferrari_458"]
    assert {"blower_intake_balance", "intake_gain_scale", "pressure_attack_gain_scale"} <= SOURCE_KEYS["hellcat"]
    assert {"rotary_amplitude_scale", "housing_gain_scale", "housing_decay_scale", "housing_order_weight_scale"} <= SOURCE_KEYS["rx7_fd"]


def test_ferrari_metallic_and_mid_controls_change_their_target_stems() -> None:
    trace = _trace(5_200.0)
    baseline = render_ferrari_458(trace)
    metallic = render_ferrari_458(trace, overrides={"metallic_gain_scale": 1.4})
    mid = render_ferrari_458(trace, overrides={"mid_carrier_gain_scale": 1.4})
    assert _relative_change(baseline.stems["metallic"], metallic.stems["metallic"]) > 0.05
    assert _relative_change(baseline.stems["left_bank"], mid.stems["left_bank"]) > 0.05


def test_hellcat_blower_intake_and_pressure_attack_controls_are_reachable() -> None:
    trace = _trace(3_600.0, 0.85)
    baseline = render_hellcat(trace)
    balanced = render_hellcat(trace, overrides={"blower_intake_balance": 0.25})
    attacked = render_hellcat(trace, overrides={"pressure_attack_gain_scale": 1.0})
    assert _relative_change(baseline.stems["blower"], balanced.stems["blower"]) > 0.05
    assert _relative_change(baseline.stems["intake"], balanced.stems["intake"]) > 0.05
    assert "pressure_attack" in attacked.stems
    assert float(np.linalg.norm(attacked.stems["pressure_attack"])) > 0.0


def test_rx7_new_amplitude_and_housing_controls_are_reachable() -> None:
    trace = _trace(4_800.0)
    baseline = render_rx7_fd(trace)
    amplitude = render_rx7_fd(trace, overrides={"rotary_amplitude_scale": 1.35})
    housing = render_rx7_fd(trace, overrides={"housing_gain_scale": 1.5, "housing_decay_scale": 1.3, "housing_order_weight_scale": 1.4})
    assert _relative_change(baseline.stems["rotary"], amplitude.stems["rotary"]) > 0.20
    assert _relative_change(baseline.stems["rotor_housing"], housing.stems["rotor_housing"]) > 0.20
    assert amplitude.diagnostics["candidate_source_overrides"]["rotary_amplitude_scale"] == 1.35
