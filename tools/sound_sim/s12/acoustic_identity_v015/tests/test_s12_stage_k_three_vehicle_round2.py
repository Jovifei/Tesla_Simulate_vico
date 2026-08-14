"""TDD contracts for propagating Hellcat Round-2 evidence to Stage-K cars."""

from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.round2_propagation import (
    ROUND2_PARAMETER_GRIDS,
    ROUND2_VEHICLES,
    apply_round2_tuning,
    measure_round2_metrics,
    reconcile_round2_pressure,
    render_round2_candidate,
    resolve_round2_event_windows,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.round2_search import (
    REQUIRED_FULL_GATES,
    ROUND2_PROBES,
    rank_round2_snapshots,
    run_round2_coordinate_search,
)
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.round2_package import (
    PACKAGE_ID as ROUND2_PACKAGE_ID,
    build_stage_k_three_vehicle_round2_review,
)


SAMPLE_RATE_HZ = 1000


def _trace(duration_s: float = 20.0) -> VehicleStateTrace:
    time_s = np.arange(0.0, duration_s, 1.0 / SAMPLE_RATE_HZ, dtype=np.float64)
    rpm = np.where(time_s < 8.0, 1200.0 + 320.0 * time_s, 4700.0)
    rpm = np.where((time_s >= 8.0) & (time_s < 8.35), 2900.0, rpm)
    throttle = np.where(time_s < 12.0, 0.92, 0.05)
    throttle = np.where(time_s < 8.0, 0.35 + 0.07 * time_s, throttle)
    load = np.where(time_s < 12.0, 0.88, 0.08)
    acceleration = np.gradient(rpm, time_s) / 60.0
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


def _stems(vehicle_id: str, count: int) -> dict[str, np.ndarray]:
    time_s = np.arange(count, dtype=np.float64) / SAMPLE_RATE_HZ
    base = np.column_stack((0.08 * np.sin(2.0 * np.pi * 42.0 * time_s), 0.07 * np.sin(2.0 * np.pi * 42.0 * time_s)))
    pulse = np.zeros((count, 2), dtype=np.float64)
    pulse[[12_000, 12_250, 12_700], :] = 0.25
    if vehicle_id == "c63_w204":
        return {
            "exhaust": base,
            "exhaust_left_bank": 0.4 * base,
            "exhaust_right_bank": 0.3 * base,
            "bark": 0.5 * base,
            "bark_primary": 0.2 * base,
            "mechanical": 0.2 * base,
            "closed_throttle_tail": pulse,
        }
    if vehicle_id == "gtr_r35":
        return {
            "exhaust": base,
            "order_family": 0.4 * base,
            "turbo_primary": 0.2 * base,
            "turbo_secondary": 0.15 * base,
            "turbo_sidebands": 0.1 * base,
            "intake_duct": 0.1 * base,
            "wastegate": pulse,
            "mechanical": 0.2 * base,
        }
    return {
        "exhaust": base,
        "order_family": 0.4 * base,
        "intake": 0.2 * base,
        "mechanical": 0.15 * base,
        "metallic": pulse,
        "lfa_shift_exhaust_reengagement": 0.10 * pulse,
        "lfa_shift_intake_reopen": 0.05 * pulse,
    }


def _render(
    vehicle_id: str,
    *,
    double_count_alias: bool = False,
    include_alias_pressure: bool = False,
) -> SourceRender:
    trace = _trace()
    stems = _stems(vehicle_id, trace.time_s.size)
    contributors = {
        name: value
        for name, value in stems.items()
        if not (vehicle_id == "c63_w204" and name in {"exhaust_left_bank", "exhaust_right_bank", "bark_primary"})
    }
    pressure = sum(contributors.values(), np.zeros_like(next(iter(stems.values()))))
    if include_alias_pressure and vehicle_id == "lfa":
        pressure = pressure + stems["pressure_pulse"] if "pressure_pulse" in stems else pressure
    if double_count_alias and vehicle_id == "c63_w204":
        pressure = pressure + stems["bark_primary"]
    return SourceRender(pressure=pressure, stems=stems, diagnostics={"vehicle_id": vehicle_id, "afterfire_event_count": 999}).validate()


def test_round2_metrics_measure_arrays_and_ignore_diagnostic_claims() -> None:
    metrics = measure_round2_metrics("c63_w204", _render("c63_w204"), _trace(), SAMPLE_RATE_HZ)
    assert metrics["measurement_provenance"] == "actual_arrays_and_trace"
    assert metrics["diagnostics_claims_used"] is False
    assert metrics["event_windows"]["lift"]["start_s"] >= 11.5
    assert metrics["event_count"] == 3
    assert metrics["afterfire_event_count"] == 0
    assert metrics["event_kind"] == "closed_throttle_bark"
    assert metrics["bands_db"]["80_250_hz"] != 0.0


def test_round2_event_windows_anchor_to_trace_event_not_prefix_slice() -> None:
    windows = resolve_round2_event_windows("gtr_r35", _trace(), SAMPLE_RATE_HZ)
    assert windows["lift"].anchor_s >= 11.9
    assert windows["lift"].start_s > 8.0
    assert windows["lift"].source == "trace_throttle_and_load_transition"


def test_round2_pressure_accounting_rejects_double_counted_diagnostic_alias() -> None:
    metrics = measure_round2_metrics("c63_w204", _render("c63_w204", double_count_alias=True), _trace(), SAMPLE_RATE_HZ)
    assert metrics["pressure_accounting"]["passes"] is False
    assert metrics["pressure_accounting"]["unexpected_energy"] > 0.0


def test_round2_pressure_reconcile_removes_lfa_aggregate_alias_once() -> None:
    raw = _render("lfa")
    raw_stems = dict(raw.stems)
    raw_stems["pressure_pulse"] = 0.02 * raw_stems["exhaust"]
    raw = SourceRender(
        pressure=raw.pressure + raw_stems["pressure_pulse"],
        stems=raw_stems,
        diagnostics={},
    ).validate()
    reconciled = reconcile_round2_pressure("lfa", raw)
    metrics = measure_round2_metrics("lfa", reconciled, _trace(), SAMPLE_RATE_HZ)
    assert reconciled.diagnostics["round2_pressure_reconciled"] is True
    assert metrics["pressure_accounting"]["passes"] is True
    assert metrics["pressure_accounting"]["relative_error"] < 1e-12


def test_round2_metrics_measure_coherence_spectral_distance_and_afterfire_from_arrays() -> None:
    trace = _trace()
    render = _render("gtr_r35")
    afterfire = np.zeros_like(render.pressure)
    afterfire[[13_000, 13_250, 13_700], :] = 0.18
    render = SourceRender(
        pressure=render.pressure + afterfire,
        stems={**render.stems, "afterfire": afterfire},
        diagnostics={"afterfire_event_count": 999, "event_sample_indices": (0,)},
    ).validate()
    parent = _render("gtr_r35")
    metrics = measure_round2_metrics("gtr_r35", render, trace, SAMPLE_RATE_HZ, parent_render=parent)
    assert metrics["measurement_provenance"] == "actual_arrays_and_trace"
    assert 0.0 <= metrics["clock_coherence"]["value"] <= 1.0
    assert metrics["spectral_distance"]["band_hz"] == [800.0, 3000.0]
    assert metrics["spectral_distance"]["normalized_l2"] >= 0.0
    afterfire_metrics = metrics["afterfire"]
    assert afterfire_metrics["event_count"] == 3
    assert afterfire_metrics["onset_times_s"] == pytest.approx([13.0, 13.25, 13.7])
    assert afterfire_metrics["amplitude_cv"] >= 0.0
    assert afterfire_metrics["interval_cv"] >= 0.0
    assert afterfire_metrics["decay_90_10_s"] >= 0.0
    assert afterfire_metrics["qualification"]["wrong_condition_event_count"] == 0


@pytest.mark.parametrize(
    ("vehicle_id", "candidate_name"),
    (
        ("c63_w204", "c63_w204_candidate_v2.json"),
        ("gtr_r35", "gtr_r35_candidate_v2.json"),
        ("lfa", "lfa_candidate_v2.json"),
    ),
)
def test_round2_candidate_wrapper_reconciles_actual_render(vehicle_id: str, candidate_name: str) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.render_drive_cycle_v10 import build_drive_cycle_trace
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.candidate_profiles import load_stage_k_candidate

    trace = build_drive_cycle_trace(vehicle_id, duration_s=12.0)
    candidate = load_stage_k_candidate(
        f"tools/sound_sim/s12/acoustic_identity_v015/targets/stage_k_candidates/{candidate_name}"
    )
    rendered = render_round2_candidate(vehicle_id, trace, candidate)
    metrics = measure_round2_metrics(vehicle_id, rendered, trace)
    assert rendered.diagnostics["round2_pressure_reconciled"] is True
    assert metrics["pressure_accounting"]["passes"] is True


@pytest.mark.parametrize("vehicle_id", ROUND2_VEHICLES)
def test_round2_tuning_is_event_gated_and_changes_actual_arrays_after_idle(vehicle_id: str) -> None:
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.named_review import _build_operating_trace
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.candidate_profiles import load_stage_k_candidate
    from tools.sound_sim.s12.acoustic_identity_v015.stage_k.render_candidate import render_stage_k_candidate

    candidate_name = f"tools/sound_sim/s12/acoustic_identity_v015/targets/stage_k_candidates/{vehicle_id}_candidate_v2.json"
    trace = _build_operating_trace(vehicle_id, "high_load", 12.0)
    candidate = load_stage_k_candidate(candidate_name)
    baseline = render_stage_k_candidate(vehicle_id, trace, candidate)
    seed = {name: values[1] for name, values in ROUND2_PARAMETER_GRIDS[vehicle_id].items()}
    tuned = apply_round2_tuning(vehicle_id, baseline, trace, seed)
    idle = trace.time_s <= 8.0
    assert tuned.diagnostics["round2_tuning_active_samples"] > 0
    for name in baseline.stems:
        assert np.array_equal(tuned.stems[name][idle], baseline.stems[name][idle])
    assert any(not np.array_equal(tuned.stems[name][~idle], baseline.stems[name][~idle]) for name in baseline.stems)
    assert tuned.diagnostics["round2_tuning_parameters"] == seed


@pytest.mark.parametrize("vehicle_id", ROUND2_VEHICLES)
def test_round2_each_parameter_perturbation_changes_an_actual_source_array(vehicle_id: str) -> None:
    trace = _trace()
    baseline = _render(vehicle_id)
    seed = {name: values[1] for name, values in ROUND2_PARAMETER_GRIDS[vehicle_id].items()}
    for name, bounds in ROUND2_PARAMETER_GRIDS[vehicle_id].items():
        low = dict(seed)
        high = dict(seed)
        low[name] = bounds[0]
        high[name] = bounds[2]
        low_render = apply_round2_tuning(vehicle_id, baseline, trace, low)
        high_render = apply_round2_tuning(vehicle_id, baseline, trace, high)
        changed = any(
            not np.array_equal(low_render.stems[stem][trace.time_s > 8.0], high_render.stems[stem][trace.time_s > 8.0])
            for stem in baseline.stems
        )
        assert changed, f"Round-2 parameter {vehicle_id}.{name} did not change actual arrays"


def _search_record(candidate_id: str, parameters: dict[str, float], *, passed: bool = True) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "parameters": parameters,
        "probe_results": {name: {"measured": True} for name in ROUND2_PROBES},
        "metrics": {
            "hard_gates": {name: passed for name in REQUIRED_FULL_GATES},
            "user_feedback_error": 0.10 if passed else 0.01,
            "reference_distance": 0.20 if passed else 0.01,
            "relative_v2_delta": 0.10,
            "relative_seed_delta": 0.05,
        },
    }


def test_round2_coordinate_search_is_sequential_and_bounded() -> None:
    seed = {name: values[1] for name, values in ROUND2_PARAMETER_GRIDS["c63_w204"].items()}
    calls: list[dict[str, float]] = []

    def evaluate(parameters: dict[str, float]) -> dict[str, object]:
        calls.append(dict(parameters))
        return _search_record(f"probe_{len(calls):02d}", dict(parameters))

    result = run_round2_coordinate_search("c63_w204", seed, evaluate)
    assert len(calls) == len(ROUND2_PARAMETER_GRIDS["c63_w204"]) * 3
    assert result["probe_names"] == list(ROUND2_PROBES)
    assert len(result["snapshots"]) == len(calls)
    assert result["best_snapshot"]["candidate_id"].startswith("probe_")


def test_round2_ranking_rejects_self_asserted_incomplete_hard_gates() -> None:
    seed = {name: values[1] for name, values in ROUND2_PARAMETER_GRIDS["gtr_r35"].items()}
    incomplete = _search_record("incomplete", seed)
    incomplete["metrics"] = {"hard_gates_pass": True, "user_feedback_error": 0.0}
    complete = _search_record("complete", seed)
    ranked = rank_round2_snapshots([incomplete, complete], "gtr_r35")
    assert [row["candidate_id"] for row in ranked] == ["complete"]


def test_round2_short_package_has_formal_comfort_diagnostics_and_bindings(tmp_path) -> None:
    root = tmp_path / "round2-package"
    manifest = build_stage_k_three_vehicle_round2_review(root, duration_s=12.0)
    assert manifest["package_id"] == ROUND2_PACKAGE_ID
    assert manifest["status"] == "PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY"
    assert manifest["csv_content_read"] is False
    assert set(manifest["vehicles"]) == set(ROUND2_VEHICLES)
    for vehicle_id, vehicle in manifest["vehicles"].items():
        assert set(vehicle["formal"]) == {"parent", "baseline", "candidate", "comfort"}
        assert len(vehicle["diagnostics"]) == 4
        assert vehicle["formal"]["comfort"]["input_sha256"] == vehicle["formal"]["candidate"]["sha256"]
        for record in vehicle["formal"].values():
            assert record["pipeline_order"] == ["frozen_ptr", "edge_fade", "one_fixed_whole_cycle_gain", "pcm24"]
            assert record["pcm_health"]["passes"] is True
        for record in vehicle["diagnostics"].values():
            assert record["source_domain"] is True
            assert record["pcm_health"]["passes"] is True
    assert (root / "SHA256SUMS.txt").is_file()
    assert list(root.glob("*.csv")) == []


@pytest.mark.parametrize("vehicle_id", ROUND2_VEHICLES)
def test_round2_vehicle_contract_does_not_accept_a_different_vehicle_stem_set(vehicle_id: str) -> None:
    other = next(candidate for candidate in ROUND2_VEHICLES if candidate != vehicle_id)
    with pytest.raises(ValueError, match="stem contract"):
        measure_round2_metrics(vehicle_id, _render(other), _trace(), SAMPLE_RATE_HZ)
