"""Stage-L parent isolation, contributor accounting and determinism locks."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_identity_v02 import _apply_frozen_ptr, _edge_fade, _pcm24_roundtrip
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.candidate_profiles import load_stage_k_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_candidate import render_stage_k_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import load_stage_l_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import render_stage_l_candidate, render_stage_l_parent


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = ROOT / "targets" / "stage_l_candidates" / "hellcat_candidate_v8.json"
PARENT_PATH = ROOT / "targets" / "stage_k_candidates" / "hellcat_candidate_v7.json"


def _trace() -> VehicleStateTrace:
    sample_rate_hz = 8000
    count = 241
    time_s = np.arange(count, dtype=np.float64) / sample_rate_hz
    phase = np.linspace(0.0, 1.0, count)
    rpm = 1000.0 + 3000.0 * phase
    return VehicleStateTrace(
        time_s, rpm, 0.20 + 0.65 * phase, 0.20 + 0.75 * phase, np.gradient(rpm / 60.0, time_s)
    ).validate()


def _array_sha(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def _normalize(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, np.ndarray):
        return {"dtype": str(value.dtype), "shape": list(value.shape), "sha256": _array_sha(value)}
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _object_sha(value: object) -> str:
    payload = json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_stage_l_parent_is_the_frozen_hash_bound_stage_k_v7_render() -> None:
    trace = _trace()
    actual = render_stage_l_parent(trace)
    expected = render_stage_k_candidate("hellcat", trace, load_stage_k_candidate(PARENT_PATH))
    assert np.array_equal(actual.pressure, expected.pressure)
    assert set(actual.stems) == set(expected.stems)
    assert all(np.array_equal(actual.stems[name], expected.stems[name]) for name in expected.stems)
    assert _array_sha(actual.pressure) == "bce3a0667f073808995e45f5f17833ce35cd4976bbbfac96ceeb3ebb1fa2e7d4"
    assert _object_sha(actual.stems) == "ac5bb82935167c6d22d5702ff98f3d4e862baaf69f73426e062bd6611896313f"
    assert _object_sha(actual.diagnostics) == "f3b7e4c24e7d90e742dbaea8185d8b1a2b456322456a08d97b22a5c0947183a3"


def test_stage_l_shapes_only_pressure_contributors_once_and_rebuilds_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as module

    calls: list[tuple[str, ...]] = []
    original = module._inject_state_spectral_targets

    def observing_shaper(render, vehicle_id, trace, sample_rate_hz=48000, manifest=None):
        contract = render.diagnostics["pressure_stem_contract"]
        contributors = tuple(contract["contributors"])
        aggregates = tuple(contract["diagnostic_aggregates"])
        assert set(render.stems) == set(contributors)
        assert set(contributors).isdisjoint(aggregates)
        assert np.max(np.abs(render.pressure - sum((render.stems[name] for name in contributors), np.zeros_like(render.pressure)))) <= 1e-12
        calls.append(contributors)
        return original(render, vehicle_id, trace, sample_rate_hz=sample_rate_hz, manifest=manifest)

    monkeypatch.setattr(module, "_inject_state_spectral_targets", observing_shaper)
    rendered = render_stage_l_candidate(_trace(), load_stage_l_candidate(CANDIDATE_PATH))
    assert len(calls) == 1
    contract = rendered.diagnostics["pressure_stem_contract"]
    assert set(contract) == {"contributors", "diagnostic_aggregates"}
    contributors = tuple(contract["contributors"])
    aggregates = tuple(contract["diagnostic_aggregates"])
    assert set(contributors).isdisjoint(aggregates)
    total = sum((rendered.stems[name] for name in contributors), np.zeros_like(rendered.pressure))
    assert np.max(np.abs(rendered.pressure - total)) <= 1e-12
    assert np.max(np.abs(rendered.stems["exhaust"] - rendered.stems["hemi_exhaust_left"] - rendered.stems["hemi_exhaust_right"])) <= 1e-12
    assert np.max(np.abs(rendered.stems["hemi_exhaust"] - rendered.stems["exhaust"])) <= 1e-12
    blower_names = tuple(name for name in contributors if name.startswith("blower_"))
    assert np.max(np.abs(rendered.stems["blower"] - sum((rendered.stems[name] for name in blower_names), np.zeros_like(rendered.pressure)))) <= 1e-12


def test_stage_l_candidate_parameter_usage_is_measured_not_inferred_from_json_presence() -> None:
    candidate = load_stage_l_candidate(CANDIDATE_PATH)
    rendered = render_stage_l_candidate(_trace(), candidate)
    usage = rendered.diagnostics["candidate_parameter_usage"]
    assert set(usage) == {"requested", "read", "configured", "active", "inactive", "unused"}
    requested = set(candidate.requested_parameters())
    assert set(usage["requested"]) == requested
    assert set(usage["read"]) | set(usage["unused"]) == requested
    assert set(usage["read"]).isdisjoint(usage["unused"])
    assert set(usage["active"]).isdisjoint(usage["inactive"])
    assert set(usage["active"]) | set(usage["inactive"]) == set(usage["read"])
    assert set(usage["configured"]) == set(usage["read"])
    combustion = {name for name in requested if name.startswith("combustion_and_blowdown.")}
    assert combustion <= set(usage["active"])
    assert combustion.isdisjoint(usage["unused"])
    assert any(name.startswith("supercharger_intake.") for name in usage["unused"])
    assert any(name.startswith("shift_and_load_transient.") for name in usage["unused"])


@pytest.mark.parametrize(
    "vehicle_id,candidate_name,expected_sha",
    [
        ("ferrari_458", None, "2eb4ad60f381446b2c5fb72a45f51f79d3fce32d8c611d41a9e49b5474adfd77"),
        ("rx7_fd", None, "1203e5267025ef8d2052e62fdab0c968ae763fcf0d5e70b69640d143030839b5"),
        ("aventador_lp700", None, "dfe338483da0fdd401825b8224a2be4daa4b9b67181f14964199c02786e24532"),
        ("supra_jza80", None, "1bf1062d4ba3d4f7c0f83206e8da32b7e86dcb043b8f8e3d517d12575dc9ac02"),
        ("c63_w204", "c63_w204_candidate_v2.json", "6d8f7586a64659768e4ed2fd0c075b23560b9cd5060a766f14c83f54bca89ae9"),
        ("gtr_r35", "gtr_r35_candidate_v2.json", "7c1f0fdaa7de1871566803c1e732aba39221c91c81c0a81c7e7ef4dc374a2126"),
        ("lfa", "lfa_candidate_v2.json", "18b2890558336cc497310d43e864d81b11031750e123de07b0993cb099f775c8"),
    ],
)
def test_seven_non_hellcat_formal_pcm_paths_remain_frozen(
    vehicle_id: str, candidate_name: str | None, expected_sha: str,
) -> None:
    candidate = None if candidate_name is None else load_stage_k_candidate(ROOT / "targets" / "stage_k_candidates" / candidate_name)
    rendered = render_stage_k_candidate(vehicle_id, _trace(), candidate)
    pcm = _pcm24_roundtrip(_edge_fade(_apply_frozen_ptr(rendered.pressure)))
    assert _array_sha(pcm) == expected_sha


def test_stage_l_render_is_independent_of_python_hash_seed() -> None:
    script = """
import hashlib
from pathlib import Path
import numpy as np
from tools.sound_sim.s12.acoustic_identity_v015.contracts import VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.candidate_profiles import load_stage_l_candidate
from tools.sound_sim.s12.acoustic_identity_v015.stage_l.render_candidate import render_stage_l_candidate
root=Path('tools/sound_sim/s12/acoustic_identity_v015')
sr=8000;n=241;t=np.arange(n,dtype=np.float64)/sr;p=np.linspace(0.0,1.0,n);rpm=1000.0+3000.0*p
trace=VehicleStateTrace(t,rpm,0.20+0.65*p,0.20+0.75*p,np.gradient(rpm/60.0,t)).validate()
r=render_stage_l_candidate(trace,load_stage_l_candidate(root/'targets/stage_l_candidates/hellcat_candidate_v8.json'))
d=hashlib.sha256(np.ascontiguousarray(r.pressure).tobytes())
for name in sorted(r.stems):d.update(name.encode());d.update(np.ascontiguousarray(r.stems[name]).tobytes())
print(d.hexdigest())
"""
    values = []
    for seed in ("1", "987654"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        values.append(subprocess.check_output([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[5], env=env, text=True).strip())
    assert values[0] == values[1]


def test_stage_l_does_not_accept_an_ambiguous_none_candidate() -> None:
    with pytest.raises((TypeError, ValueError), match="candidate"):
        render_stage_l_candidate(_trace(), None)  # type: ignore[arg-type]


def test_l2_combustion_and_v4_blower_adapters_receive_the_identical_clock_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as module

    combustion_adapter = getattr(module, "render_crossplane_combustion_l2_with_clock", None)
    blower_adapter = getattr(module, "render_stage_k_v4_blower_with_clock", None)
    assert callable(combustion_adapter)
    assert callable(blower_adapter)
    observed: list[object] = []

    def observe_combustion(trace, clock, overrides, sample_rate_hz=48000):
        observed.append(clock)
        return combustion_adapter(trace, clock, overrides, sample_rate_hz)

    def observe_blower(trace, clock, sample_rate_hz=48000):
        observed.append(clock)
        return blower_adapter(trace, clock, sample_rate_hz)

    monkeypatch.setattr(module, "render_crossplane_combustion_l2_with_clock", observe_combustion)
    monkeypatch.setattr(module, "render_stage_k_v4_blower_with_clock", observe_blower)
    rendered = module.render_stage_l_candidate(_trace(), load_stage_l_candidate(CANDIDATE_PATH))
    assert len(observed) == 2
    assert observed[0] is observed[1]
    evidence = rendered.diagnostics["shared_clock_consumers"]
    assert evidence["cross_plane_combustion_l2"]["clock_object_shared"] is True
    assert evidence["stage_k_v4_blower"]["clock_object_shared"] is True
    assert evidence["cross_plane_combustion_l2"]["internal_event_scheduling"] == "ACTIVE_L2_SHARED_CLOCK"
    assert evidence["cross_plane_combustion_l2"]["event_gates_consumed"] is True
    assert evidence["cross_plane_combustion_l2"]["event_sample_indices_consumed"] is True
    assert evidence["cross_plane_combustion_l2"]["bank_labels_consumed"] is True


def test_legacy_raw_adapter_validates_phase_contract_without_claiming_event_consumption() -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as module
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import build_hellcat_crank_clock

    adapter = getattr(module, "render_legacy_hellcat_raw_with_clock", None)
    assert callable(adapter)
    trace = _trace()
    clock = build_hellcat_crank_clock(trace, 48000)
    rendered = adapter(trace, clock, 48000)
    contract = rendered.diagnostics["shared_crank_clock_contract"]
    assert contract["phase_and_sample_contract_validated"] is True
    assert contract["legacy_internal_event_schedule_from_shared_clock"] is False
    assert contract["l2_event_consumption_status"] == "PENDING"


def test_v4_blower_adapter_passes_the_clock_phase_array_by_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l import render_candidate as module
    from tools.sound_sim.s12.acoustic_identity_v015.stage_l.crank_clock import build_hellcat_crank_clock

    adapter = getattr(module, "render_stage_k_v4_blower_with_clock", None)
    assert callable(adapter)
    trace = _trace()
    clock = build_hellcat_crank_clock(trace, 48000)
    original = module.render_supercharger_whine_v4
    observed: list[np.ndarray] = []

    def observe(rpm, load, throttle, phase, sample_rate_hz, overrides=None):
        observed.append(phase)
        return original(rpm, load, throttle, phase, sample_rate_hz, overrides=overrides)

    monkeypatch.setattr(module, "render_supercharger_whine_v4", observe)
    adapter(trace, clock, 48000)
    assert observed == [clock.engine_phase_cycles]
