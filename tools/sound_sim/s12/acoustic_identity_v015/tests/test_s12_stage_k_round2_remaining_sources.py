"""TDD contracts for the Supra JZA80 and Aventador LP700 Round-2 layer."""

from __future__ import annotations

import gc
import hashlib

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.round2_remaining_sources import (
    PARAMETER_GRIDS,
    VEHICLES,
    apply_round2_overlay,
    measure_round2_metrics,
    render_round2_baseline,
    render_round2_candidate,
    resolve_event_windows,
)


SAMPLE_RATE_HZ = 48_000


@pytest.fixture(autouse=True)
def _release_render_arrays() -> None:
    """Keep repeated 48 kHz source renders bounded on the shared runner."""
    yield
    gc.collect()


def _small_trace_and_render(vehicle_id: str) -> tuple[VehicleStateTrace, SourceRender]:
    """Use a compact 10.5 s trace for the per-knob reachability loop."""
    local_rate = 1_000
    time_s = np.arange(0.0, 10.5, 1.0 / local_rate, dtype=np.float64)
    rpm = np.where(time_s < 8.0, 1100.0, 1100.0 + 850.0 * (time_s - 8.0))
    distance = np.abs(time_s - 9.0)
    rpm -= np.where(distance < 0.06, 500.0 * (1.0 - distance / 0.06), 0.0)
    throttle = np.where(time_s < 9.5, 0.90, 0.05)
    load = np.where(time_s < 9.5, 0.85, 0.10)
    trace = VehicleStateTrace(time_s, rpm, load, throttle, np.gradient(rpm / 60.0, time_s)).validate()
    phase = np.cumsum(rpm) / (60.0 * local_rate)
    base = 0.02 * np.column_stack((np.sin(2.0 * np.pi * phase), np.sin(2.0 * np.pi * phase)))
    if vehicle_id == "supra_jza80":
        stems = {"exhaust": base.copy(), "whistle": 0.5 * base.copy()}
    else:
        stems = {
            "exhaust": base.copy(),
            "wail": 0.8 * base.copy(),
            "scream": 0.2 * base.copy(),
            "shift_recovery_boom": 0.1 * base.copy(),
            "afterfire": 0.15 * base.copy(),
        }
    pressure = sum(stems.values(), np.zeros_like(base))
    return trace, SourceRender(pressure=pressure, stems=stems, diagnostics={}).validate()


def _sha_arrays(render: SourceRender) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(render.pressure, dtype=np.float64).tobytes())
    for name in sorted(render.stems):
        digest.update(name.encode("utf-8"))
        digest.update(np.asarray(render.stems[name], dtype=np.float64).tobytes())
    return digest.hexdigest()


@pytest.mark.parametrize("vehicle_id", VEHICLES)
def test_remaining_baseline_delegates_to_current_eight_vehicle_none_path(vehicle_id: str) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_candidate import render_stage_k_candidate

    trace = build_drive_cycle_trace(vehicle_id, duration_s=8.5)
    expected = render_stage_k_candidate(vehicle_id, trace, None)
    actual = render_round2_baseline(vehicle_id, trace)
    assert _sha_arrays(actual) == _sha_arrays(expected)


@pytest.mark.parametrize("vehicle_id", VEHICLES)
def test_remaining_candidate_is_byte_identical_through_first_eight_seconds(vehicle_id: str) -> None:
    trace = build_drive_cycle_trace(vehicle_id, duration_s=10.0)
    baseline = render_round2_baseline(vehicle_id, trace)
    seed = {name: bounds[1] for name, bounds in PARAMETER_GRIDS[vehicle_id].items()}
    prefix = trace.time_s <= 8.0
    baseline_pressure_prefix = baseline.pressure[prefix].copy()
    baseline_stem_prefix = {name: stem[prefix].copy() for name, stem in baseline.stems.items()}
    baseline_stem_suffix = {name: stem[~prefix].copy() for name, stem in baseline.stems.items()}
    del baseline
    gc.collect()
    candidate = render_round2_candidate(vehicle_id, trace, seed)
    assert np.array_equal(candidate.pressure[prefix], baseline_pressure_prefix)
    assert set(candidate.stems) >= set(baseline_stem_prefix)
    for name in baseline_stem_prefix:
        assert np.array_equal(candidate.stems[name][prefix], baseline_stem_prefix[name]), name
    assert any(
        name not in baseline_stem_suffix or not np.array_equal(candidate.stems[name][~prefix], baseline_stem_suffix[name])
        for name in candidate.stems
    )


@pytest.mark.parametrize("vehicle_id", VEHICLES)
def test_each_vehicle_grid_is_independent_and_reaches_actual_arrays(vehicle_id: str) -> None:
    trace, baseline = _small_trace_and_render(vehicle_id)
    seed = {name: bounds[1] for name, bounds in PARAMETER_GRIDS[vehicle_id].items()}
    assert set(PARAMETER_GRIDS[vehicle_id])
    for name, bounds in PARAMETER_GRIDS[vehicle_id].items():
        low = dict(seed)
        high = dict(seed)
        low[name] = bounds[0]
        high[name] = bounds[2]
        low_render = apply_round2_overlay(vehicle_id, baseline, trace, low)
        high_render = apply_round2_overlay(vehicle_id, baseline, trace, high)
        assert any(
            not np.array_equal(low_render.stems[stem][trace.time_s > 8.0], high_render.stems[stem][trace.time_s > 8.0])
            for stem in low_render.stems
        ), f"{vehicle_id}.{name} did not reach an actual source array"


def test_remaining_vehicle_identities_do_not_cross_use_hellcat_or_c63_source_layers() -> None:
    assert set(VEHICLES) == {"supra_jza80", "aventador_lp700"}
    assert set(PARAMETER_GRIDS["supra_jza80"]) != set(PARAMETER_GRIDS["aventador_lp700"])
    assert all("hellcat" not in name.lower() and "c63" not in name.lower() for name in PARAMETER_GRIDS["supra_jza80"])
    assert all("hellcat" not in name.lower() and "c63" not in name.lower() for name in PARAMETER_GRIDS["aventador_lp700"])


@pytest.mark.parametrize("vehicle_id", VEHICLES)
def test_remaining_metrics_use_actual_arrays_trace_windows_and_vehicle_event_semantics(vehicle_id: str) -> None:
    trace = build_drive_cycle_trace(vehicle_id, duration_s=10.0)
    baseline = render_round2_baseline(vehicle_id, trace)
    seed = {name: bounds[1] for name, bounds in PARAMETER_GRIDS[vehicle_id].items()}
    candidate = render_round2_candidate(vehicle_id, trace, seed)
    windows = resolve_event_windows(vehicle_id, trace)
    metrics = measure_round2_metrics(vehicle_id, candidate, trace, parent_render=baseline)
    assert {"acceleration", "lift", "shift"}.issubset(windows)
    assert metrics["measurement_provenance"] == "actual_arrays_and_trace"
    assert metrics["diagnostics_claims_used"] is False
    assert metrics["event_windows"]["lift"]["anchor_s"] == pytest.approx(windows["lift"].anchor_s)
    assert metrics["event"]["qualification"]["eligible"] is True
    if vehicle_id == "supra_jza80":
        assert metrics["event_kind"] == "twin_turbo_spool_release"
        assert metrics["identity"]["engine_layout"] == "inline-six"
        assert metrics["identity"]["forced_induction"] == "twin-turbo"
    else:
        assert metrics["event_kind"] == "even_fire_v12_shift_reengagement"
        assert metrics["identity"]["engine_layout"] == "even-fire-v12"
        assert metrics["identity"]["forced_induction"] == "naturally-aspirated"


def test_remaining_pressure_accounting_is_fail_closed_and_excludes_only_explicit_aliases() -> None:
    trace = build_drive_cycle_trace("supra_jza80", duration_s=10.0)
    seed = {name: bounds[1] for name, bounds in PARAMETER_GRIDS["supra_jza80"].items()}
    render = render_round2_candidate("supra_jza80", trace, seed)
    metrics = measure_round2_metrics("supra_jza80", render, trace)
    assert metrics["pressure_accounting"]["passes"] is True
    assert "supra_twin_turbo_spool_release" in metrics["pressure_accounting"]["aliases_excluded"]

    tampered = SourceRender(
        pressure=render.pressure + render.stems["whistle"],
        stems=render.stems,
        diagnostics={"pressure_accounting": "trusted"},
    ).validate()
    failed = measure_round2_metrics("supra_jza80", tampered, trace)
    assert failed["pressure_accounting"]["passes"] is False
    assert failed["pressure_accounting"]["unexpected_energy"] > 0.0


def test_remaining_metrics_fail_closed_without_trace_lift_or_shift() -> None:
    sample_count = int(8.5 * SAMPLE_RATE_HZ) + 1
    time_s = np.arange(sample_count, dtype=np.float64) / SAMPLE_RATE_HZ
    rpm = np.full(sample_count, 2500.0, dtype=np.float64)
    load = np.full(sample_count, 0.75, dtype=np.float64)
    throttle = np.full(sample_count, 0.75, dtype=np.float64)
    trace = VehicleStateTrace(time_s, rpm, load, throttle, np.zeros_like(time_s)).validate()
    with pytest.raises(ValueError, match="acceleration|lift|shift"):
        resolve_event_windows("aventador_lp700", trace)
