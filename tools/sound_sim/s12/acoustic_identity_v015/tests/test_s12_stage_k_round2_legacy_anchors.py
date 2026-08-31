"""TDD contracts for the Ferrari 458 and RX-7 FD Round-2 source view."""

from __future__ import annotations

import numpy as np
import pytest

from tools.sound_sim.s12.acoustic_identity_v015.contracts import SourceRender, VehicleStateTrace
from tools.sound_sim.s12.acoustic_identity_v015.stage_k.round2_legacy_anchors import (
    PARAMETER_GRIDS,
    VEHICLES,
    measure_round2_metrics,
    render_round2_baseline,
    render_round2_candidate,
    resolve_round2_event_windows,
)


SAMPLE_RATE_HZ = 1_000
ACTUAL_SAMPLE_RATE_HZ = 48_000


def _trace(duration_s: float = 12.0) -> VehicleStateTrace:
    time_s = np.arange(0.0, duration_s, 1.0 / SAMPLE_RATE_HZ, dtype=np.float64)
    rpm = np.where(time_s < 8.0, 1_200.0 + 320.0 * time_s, 4_700.0)
    rpm = np.where((time_s >= 8.0) & (time_s < 8.35), 2_900.0, rpm)
    throttle = np.where(time_s < 10.0, 0.92, 0.05)
    throttle = np.where(time_s < 8.0, 0.35 + 0.07 * time_s, throttle)
    load = np.where(time_s < 10.0, 0.88, 0.08)
    acceleration = np.gradient(rpm, time_s) / 60.0
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


def _high_rate_trace(duration_s: float = 8.5) -> VehicleStateTrace:
    """A compact renderer-sized trace with a measurable post-8 s event."""

    time_s = np.arange(0.0, duration_s, 1.0 / ACTUAL_SAMPLE_RATE_HZ, dtype=np.float64)
    rpm = np.where(time_s < 8.0, 1_200.0 + 320.0 * time_s, 4_700.0)
    ramp = (time_s >= 8.0) & (time_s < 8.10)
    rpm = np.where(ramp, 4_700.0 - 18_000.0 * (time_s - 8.0), rpm)
    rpm = np.where((time_s >= 8.10) & (time_s < 8.35), 2_900.0, rpm)
    throttle = np.where(time_s < 8.20, 0.92, 0.05)
    throttle = np.where(time_s < 8.0, 0.35 + 0.07 * time_s, throttle)
    load = np.where(time_s < 8.20, 0.88, 0.08)
    acceleration = np.gradient(rpm, time_s) / 60.0
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


def _stems(vehicle_id: str, count: int) -> dict[str, np.ndarray]:
    time_s = np.arange(count, dtype=np.float64) / SAMPLE_RATE_HZ
    base = np.column_stack(
        (
            0.08 * np.sin(2.0 * np.pi * 42.0 * time_s),
            0.07 * np.sin(2.0 * np.pi * 42.0 * time_s),
        )
    )
    event = np.zeros((count, 2), dtype=np.float64)
    event[[8_100, 8_250, 8_700], :] = 0.25
    lift = np.zeros((count, 2), dtype=np.float64)
    lift[[10_000, 10_250], :] = 0.30
    if vehicle_id == "ferrari_458":
        return {
            "left_bank": 0.40 * base,
            "right_bank": 0.30 * base,
            "metallic": 0.20 * base,
            "radiation": 0.10 * base,
            "shift_recovery_boom": event,
            "shift_impact": 0.10 * event,
            "low_frequency_body": 0.10 * base,
            "pressure_pulse": 0.02 * base,
            "exhaust_coupling": 0.01 * base,
            "body_resonance": 0.01 * base,
            "shift_torque_interruption": np.zeros_like(base),
        }
    return {
        "rotary": 0.40 * base,
        "rotor_housing": 0.10 * base,
        "exhaust": 0.30 * base,
        "turbo": 0.08 * base,
        "turbine": 0.06 * base,
        "blow_off": lift,
        "lift": lift,
        "radiation": 0.05 * base,
        "shift_recovery_boom": 0.05 * event,
        "shift_impact": 0.05 * event,
        "low_frequency_body": 0.05 * base,
        "pressure_pulse": 0.02 * base,
        "exhaust_coupling": 0.01 * base,
        "body_resonance": 0.01 * base,
        "shift_torque_interruption": np.zeros_like(base),
    }


def _render(vehicle_id: str, *, alias_in_pressure: bool = False) -> SourceRender:
    stems = _stems(vehicle_id, _trace().time_s.size)
    aliases = {
        "low_frequency_body",
        "pressure_pulse",
        "exhaust_coupling",
        "body_resonance",
        "shift_torque_interruption",
    }
    if vehicle_id == "rx7_fd":
        aliases.add("lift")
    contributors = [name for name in stems if name not in aliases]
    pressure = sum((stems[name] for name in contributors), np.zeros_like(next(iter(stems.values()))))
    if alias_in_pressure:
        pressure = pressure + stems["low_frequency_body"]
    return SourceRender(pressure=pressure, stems=stems, diagnostics={"event_count": 999}).validate()


def test_legacy_round2_exposes_distinct_vehicle_grids_and_trace_windows() -> None:
    assert VEHICLES == ("ferrari_458", "rx7_fd")
    assert set(PARAMETER_GRIDS) == set(VEHICLES)
    assert PARAMETER_GRIDS["ferrari_458"] != PARAMETER_GRIDS["rx7_fd"]
    windows = resolve_round2_event_windows("ferrari_458", _trace(), SAMPLE_RATE_HZ)
    assert windows["acceleration"].source == "trace_acceleration_mps2_and_load"
    assert windows["lift"].anchor_s >= 9.9
    assert windows["shift"].source == "trace_rpm_drop_recovery"


@pytest.mark.parametrize("vehicle_id", VEHICLES)
def test_legacy_metrics_use_named_actual_event_and_complete_provenance(vehicle_id: str) -> None:
    metrics = measure_round2_metrics(vehicle_id, _render(vehicle_id), _trace())
    assert metrics["measurement_provenance"] == "actual_arrays_and_trace"
    assert metrics["diagnostics_claims_used"] is False
    assert metrics["provenance"]["event_source"] == "actual_named_source_array"
    assert metrics["event_kind"] in {"flat_plane_shift_reengagement", "sequential_turbo_blow_off"}
    assert metrics["event_stem"] in {"shift_recovery_boom", "blow_off"}
    assert metrics["event_count"] > 0
    assert metrics["afterfire_event_count"] == 0
    assert set(metrics["bands_db"]) == {"80_250_hz", "250_1000_hz", "1000_4000_hz"}


@pytest.mark.parametrize("vehicle_id", VEHICLES)
def test_legacy_pressure_accounting_is_fail_closed_and_excludes_aliases(vehicle_id: str) -> None:
    metrics = measure_round2_metrics(vehicle_id, _render(vehicle_id), _trace())
    assert metrics["pressure_accounting"]["passes"] is True
    assert "low_frequency_body" in metrics["pressure_accounting"]["excluded_alias_stems"]
    failed = measure_round2_metrics(vehicle_id, _render(vehicle_id, alias_in_pressure=True), _trace())
    assert failed["pressure_accounting"]["passes"] is False
    assert failed["pressure_accounting"]["unexpected_energy"] > 0.0


def test_legacy_candidate_keeps_stage_g_baseline_bytes_before_eight_seconds() -> None:
    trace = _high_rate_trace()
    baseline = render_round2_baseline("ferrari_458", trace)
    candidate = render_round2_candidate(
        "ferrari_458",
        trace,
        {
            "flat_plane_high_load_gain": 1.05,
            "flat_plane_shift_gain": 1.10,
            "flat_plane_lift_gain": 1.05,
        },
    )
    prefix = trace.time_s <= 8.0
    assert np.array_equal(candidate.pressure[prefix], baseline.pressure[prefix])
    for name in baseline.stems:
        assert np.array_equal(candidate.stems[name][prefix], baseline.stems[name][prefix])
    assert any(
        not np.array_equal(candidate.stems[name][~prefix], baseline.stems[name][~prefix])
        for name in baseline.stems
    )
