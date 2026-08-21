"""Round-2 source and measurement contracts for the two legacy anchors.

The module is intentionally a view over the existing Stage-G v4 candidates.
It does not change a Stage-G profile, a shared acoustic layer, the frozen PTR,
or the final PCM chain.  A candidate overlay is allowed only after eight
seconds and only where the synchronized state trace says that the relevant
source is active.

Ferrari uses the actual flat-plane bank/metallic and DCT shift stems.  RX-7
uses the actual rotary, sequential turbo and blow-off stems.  The generic
``afterfire`` stem is measured separately and is never used as either car's
Round-2 event source.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import math
from pathlib import Path
from typing import Mapping

import numpy as np

from ..acoustic_layers.shift_dynamics import ShiftEvent, detect_shift_events
from ..contracts import SourceRender, VehicleStateTrace
from ..stage_g.candidate_profiles import load_stage_g_candidate
from ..stage_g.render_candidate import render_stage_g_candidate


SAMPLE_RATE_HZ = 48_000
VEHICLES = ("ferrari_458", "rx7_fd")

# Each grid is vehicle-local.  The middle element is the deterministic seed;
# the outer elements are the bounded probe limits used by callers.
PARAMETER_GRIDS: dict[str, dict[str, tuple[float, float, float]]] = {
    "ferrari_458": {
        "flat_plane_high_load_gain": (0.92, 1.00, 1.08),
        "flat_plane_shift_gain": (0.82, 1.00, 1.18),
        "flat_plane_lift_gain": (0.86, 1.00, 1.14),
    },
    "rx7_fd": {
        "rotary_high_load_gain": (0.92, 1.00, 1.08),
        "sequential_primary_gain": (0.82, 1.00, 1.18),
        "sequential_secondary_gain": (0.80, 1.00, 1.20),
        "blow_off_release_gain": (0.78, 1.00, 1.22),
    },
}

# Compatibility spellings make the source/metrics layer easy to consume from
# the existing Stage-K scripts without widening their vehicle set.
ROUND2_VEHICLES = VEHICLES
ROUND2_PARAMETER_GRIDS = PARAMETER_GRIDS
ROUND2_LEGACY_VEHICLES = VEHICLES
ROUND2_LEGACY_PARAMETER_GRIDS = PARAMETER_GRIDS


@dataclass(frozen=True)
class EventWindow:
    """A state-trace-derived window and its measured transition anchor."""

    name: str
    start_s: float
    end_s: float
    anchor_s: float
    source: str


_CANDIDATE_FILENAMES = {
    "ferrari_458": "Ferrari_candidate_v4.json",
    "rx7_fd": "RX7_candidate_v4.json",
}

# These are explicit aliases or intermediate nodes, not independent pressure
# contributors.  ``radiation`` is retained once because it is the final
# pressure-chain output; ``low_frequency_body`` is its historical alias.
_ALIAS_STEMS = {
    "ferrari_458": frozenset(
        {
            "low_frequency_body",
            "pressure_pulse",
            "exhaust_coupling",
            "body_resonance",
            "shift_torque_interruption",
        }
    ),
    "rx7_fd": frozenset(
        {
            "lift",  # historical alias of the actual ``blow_off`` array
            "low_frequency_body",
            "pressure_pulse",
            "exhaust_coupling",
            "body_resonance",
            "shift_torque_interruption",
        }
    ),
}

_ALLOWED_PRIMITIVE_STEMS = {
    "ferrari_458": frozenset(
        {
            "left_bank",
            "right_bank",
            "metallic",
            "radiation",
            "idle_combustion_variation",
            "idle_accessory",
            "idle_valvetrain",
            "idle_crank",
            "afterfire",
            "exhaust_rumble",
            "shift_impact",
            "shift_recovery_boom",
        }
    ),
    "rx7_fd": frozenset(
        {
            "rotary",
            "rotor_housing",
            "exhaust",
            "turbo",
            "turbine",
            "blow_off",
            "radiation",
            "idle_loud",
            "idle_combustion_variation",
            "idle_accessory",
            "idle_valvetrain",
            "idle_crank",
            "afterfire",
            "exhaust_rumble",
            "shift_impact",
            "shift_recovery_boom",
            # The historical RX-7 source applies a state envelope to its
            # source pressure before later layers.  Round-2 makes that
            # contributor explicit without changing Stage-G bytes.
            "rx7_source_level_envelope",
        }
    ),
}

_REQUIRED_STEMS = {
    "ferrari_458": frozenset({"left_bank", "right_bank", "metallic", "shift_recovery_boom"}),
    "rx7_fd": frozenset({"rotary", "exhaust", "turbo", "turbine", "blow_off"}),
}

_EVENT_STEMS = {"ferrari_458": "shift_recovery_boom", "rx7_fd": "blow_off"}
_EVENT_KINDS = {
    "ferrari_458": "flat_plane_shift_reengagement",
    "rx7_fd": "sequential_turbo_blow_off",
}

_ENGINE_STEMS = {
    "ferrari_458": ("left_bank", "right_bank", "metallic"),
    "rx7_fd": ("rotary", "exhaust"),
}
_INDUCTION_STEMS = {
    "ferrari_458": ("metallic",),
    "rx7_fd": ("turbo", "turbine", "blow_off"),
}

_BANDS_HZ = {
    "80_250_hz": (80.0, 250.0),
    "250_1000_hz": (250.0, 1000.0),
    "1000_4000_hz": (1000.0, 4000.0),
}


def render_round2_baseline(vehicle_id: str, trace: VehicleStateTrace) -> SourceRender:
    """Render the Stage-G v4 candidate and expose a reconciled source view."""

    _validate_vehicle(vehicle_id)
    trace = trace.validate()
    profile = _load_stage_g_profile(vehicle_id)
    rendered = render_stage_g_candidate(vehicle_id, trace, profile)
    return _reconcile_pressure(vehicle_id, rendered, trace)


def render_round2_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    parameters: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render the Stage-G baseline plus a trace-gated Round-2 source overlay."""

    baseline = render_round2_baseline(vehicle_id, trace)
    values = _validated_parameters(vehicle_id, parameters)
    return apply_round2_source_overlay(vehicle_id, baseline, trace, values)


def apply_round2_source_overlay(
    vehicle_id: str,
    render: SourceRender,
    trace: VehicleStateTrace,
    parameters: Mapping[str, float],
) -> SourceRender:
    """Apply only vehicle-specific named-source changes after the 8 s freeze."""

    _validate_vehicle(vehicle_id)
    render = render.validate()
    trace = trace.validate()
    if render.pressure.shape[0] != trace.time_s.size:
        raise ValueError("render/trace sample counts do not match")
    values = _validated_parameters(vehicle_id, parameters)

    active_tail = (
        (trace.time_s > 8.0)
        & (trace.load >= 0.60)
        & (trace.throttle >= 0.55)
    )
    windows = resolve_round2_event_windows(vehicle_id, trace, SAMPLE_RATE_HZ)
    shift_mask = _window_mask(trace.time_s, windows["shift"])
    lift_mask = _window_mask(trace.time_s, windows["lift"])
    stems = {name: np.asarray(stem, dtype=np.float64).copy() for name, stem in render.stems.items()}
    pressure = np.asarray(render.pressure, dtype=np.float64).copy()
    touched: list[str] = []
    active = np.zeros(trace.time_s.size, dtype=bool)

    def scale(name: str, gain: float, mask: np.ndarray) -> None:
        nonlocal pressure
        if name not in stems:
            raise ValueError(f"{vehicle_id} overlay requires actual stem {name!r}")
        mask = np.asarray(mask, dtype=bool)
        old = stems[name]
        replacement = np.where(mask[:, np.newaxis], old * float(gain), old)
        stems[name] = replacement
        # Update only active rows.  Rebuilding the whole array as
        # ``pressure + replacement - old`` introduces tiny floating-point
        # round-off into the frozen prefix even where the gain is neutral.
        # Round-2's 0-8 s contract is byte identity, so untouched rows must
        # never participate in arithmetic.
        if np.any(mask):
            pressure[mask] += replacement[mask] - old[mask]
        if float(gain) != 1.0 and np.any(mask & (np.max(np.abs(old), axis=1) > 1.0e-15)):
            touched.append(name)
            active[:] |= mask

    if vehicle_id == "ferrari_458":
        # Flat-plane bank energy is a source-level, high-load overlay.
        scale("left_bank", values["flat_plane_high_load_gain"], active_tail)
        scale("right_bank", values["flat_plane_high_load_gain"], active_tail)
        # This is the actual DCT shift recovery array, never generic afterfire.
        scale("shift_recovery_boom", values["flat_plane_shift_gain"], shift_mask & (trace.time_s > 8.0))
        scale("shift_impact", values["flat_plane_shift_gain"], shift_mask & (trace.time_s > 8.0))
        # Metallic is a real flat-plane lift texture; it is not used as a
        # continuous carrier for event qualification.
        scale("metallic", values["flat_plane_lift_gain"], lift_mask & (trace.time_s > 8.0))
    else:
        # Rotary and exhaust remain separate from the sequential turbo stems.
        scale("rotary", values["rotary_high_load_gain"], active_tail)
        scale("exhaust", values["rotary_high_load_gain"], active_tail)
        scale("turbo", values["sequential_primary_gain"], active_tail)
        scale("turbine", values["sequential_secondary_gain"], active_tail)
        # This is the actual blow-off array emitted by the Stage-G source.
        scale("blow_off", values["blow_off_release_gain"], lift_mask & (trace.time_s > 8.0))

    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "round2_baseline": "stage_g_v4_candidate",
            "round2_tuning_vehicle": vehicle_id,
            "round2_tuning_parameters": dict(values),
            "round2_tuning_active_samples": int(np.count_nonzero(active)),
            "round2_tuning_source": "actual_named_sources_trace_gated_after_8s",
            "round2_event_stem": _EVENT_STEMS[vehicle_id],
            "round2_event_kind": _EVENT_KINDS[vehicle_id],
            "round2_event_source": "actual_named_source_array",
            "round2_tuning_changed_stems": sorted(set(touched)),
        }
    )
    return replace(render, pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def resolve_round2_event_windows(
    vehicle_id: str,
    trace: VehicleStateTrace,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
) -> dict[str, EventWindow]:
    """Resolve acceleration, shift, high-load and lift windows from arrays."""

    _validate_vehicle(vehicle_id)
    trace = trace.validate()
    if int(sample_rate_hz) <= 0:
        raise ValueError("sample_rate_hz must be positive")
    start = float(trace.time_s[0])
    end = float(trace.time_s[-1])
    windows: dict[str, EventWindow] = {
        "idle": EventWindow("idle", start, min(end, start + 8.0), start, "trace_start"),
    }

    acceleration = (trace.acceleration_mps2 > 0.10) & (trace.load >= 0.30) & (trace.throttle >= 0.30)
    acceleration_indices = np.flatnonzero(acceleration)
    if acceleration_indices.size == 0:
        raise ValueError("trace does not contain a measurable acceleration interval")
    acceleration_start = float(trace.time_s[int(acceleration_indices[0])])
    acceleration_end = float(trace.time_s[int(acceleration_indices[-1])])
    windows["acceleration"] = EventWindow(
        "acceleration",
        acceleration_start,
        max(acceleration_start, acceleration_end),
        (acceleration_start + acceleration_end) * 0.5,
        "trace_acceleration_mps2_and_load",
    )

    shifts = _detect_round2_shift_events(trace, int(sample_rate_hz))
    if not shifts:
        raise ValueError("trace does not contain a measurable shift transition")
    shift = shifts[0]
    windows["shift"] = _window(
        "shift",
        float(shift.time_s),
        0.15,
        0.55,
        start,
        end,
        "trace_rpm_drop_recovery",
    )

    high = (trace.load >= 0.72) & (trace.throttle >= 0.72)
    high_indices = np.flatnonzero(high)
    if high_indices.size == 0:
        raise ValueError("trace does not contain a measurable high-load interval")
    high_start = float(trace.time_s[int(high_indices[0])])
    high_end = float(trace.time_s[int(high_indices[-1])])
    windows["high_load"] = EventWindow(
        "high_load",
        high_start,
        max(high_start, high_end),
        (high_start + high_end) * 0.5,
        "trace_load_and_throttle",
    )

    throttle_delta = np.diff(trace.throttle)
    lift_index = _first_transition(
        throttle_delta,
        predicate=lambda delta, index: delta <= -0.25 and trace.load[index] >= 0.60,
    )
    if lift_index is None:
        raise ValueError("trace does not contain a measurable closed-throttle lift")
    lift_anchor = float(trace.time_s[lift_index + 1])
    windows["lift"] = _window(
        "lift",
        lift_anchor,
        0.25,
        1.20,
        start,
        end,
        "trace_throttle_and_load_transition",
    )
    return windows


def measure_round2_metrics(
    vehicle_id: str,
    render: SourceRender,
    trace: VehicleStateTrace,
    parent_render: SourceRender | None = None,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
) -> dict[str, object]:
    """Measure source arrays and synchronized state, never diagnostic claims."""

    _validate_vehicle(vehicle_id)
    render = render.validate()
    trace = trace.validate()
    if int(sample_rate_hz) <= 0:
        raise ValueError("sample_rate_hz must be positive")
    if render.pressure.shape[0] != trace.time_s.size:
        raise ValueError("render/trace sample counts do not match")
    windows = resolve_round2_event_windows(vehicle_id, trace, sample_rate_hz)
    accounting = _pressure_accounting(vehicle_id, render)

    payload_windows: dict[str, dict[str, object]] = {}
    for name, window in windows.items():
        mask = (trace.time_s >= window.start_s) & (trace.time_s <= window.end_s)
        if int(np.count_nonzero(mask)) < 2:
            raise ValueError(f"round2 window {name!r} is empty")
        pressure_window = render.pressure[mask]
        payload_windows[name] = {
            "start_s": window.start_s,
            "end_s": window.end_s,
            "anchor_s": window.anchor_s,
            "source": window.source,
            "bands_db": _band_measurements(pressure_window, sample_rate_hz),
            "energy": float(np.sum(np.square(pressure_window))),
            "mean_acceleration_mps2": float(np.mean(trace.acceleration_mps2[mask])),
        }

    event_stem = _EVENT_STEMS[vehicle_id]
    event_audio = np.asarray(render.stems.get(event_stem), dtype=np.float64)
    if event_stem not in render.stems:
        raise ValueError(f"stem contract for {vehicle_id} is missing event stem {event_stem!r}")
    event_metrics = _measure_named_event(vehicle_id, event_audio, trace, windows, sample_rate_hz)
    afterfire = _measure_afterfire(render.stems.get("afterfire"), trace, windows, sample_rate_hz)
    spectral_distance = _spectral_distance(render.pressure, parent_render, sample_rate_hz)
    engine_energy = _energy(render.stems, _ENGINE_STEMS[vehicle_id])
    induction_energy = _energy(render.stems, _INDUCTION_STEMS[vehicle_id])

    provenance = {
        "baseline": "stage_g_v4_candidate",
        "source": "actual_named_source_arrays",
        "trace": "VehicleStateTrace.time_s/rpm/load/throttle/acceleration_mps2",
        "acceleration_window": "trace_acceleration_mps2_and_load",
        "lift_window": "trace_throttle_and_load_transition",
        "shift_window": "trace_rpm_drop_recovery",
        "event_source": "actual_named_source_array",
        "event_stem": event_stem,
        "pressure_accounting": "primitive_stems_single_sum_fail_closed_with_explicit_alias_exclusion",
        "diagnostics_claims_used": False,
    }
    return {
        "vehicle_id": vehicle_id,
        "measurement_provenance": "actual_arrays_and_trace",
        "diagnostics_claims_used": False,
        "provenance": provenance,
        "event_windows": payload_windows,
        "acceleration_window": payload_windows["acceleration"],
        "lift_window": payload_windows["lift"],
        "shift_window": payload_windows["shift"],
        "bands_db": _band_measurements(render.pressure, sample_rate_hz),
        "source_balance": {
            "engine_energy": engine_energy,
            "induction_energy": induction_energy,
            "induction_to_engine_ratio": induction_energy / max(engine_energy, 1.0e-18),
        },
        "clock_coherence": _clock_coherence(render.stems, trace, sample_rate_hz),
        "spectral_distance": spectral_distance,
        "event_stem": event_stem,
        "event_kind": _EVENT_KINDS[vehicle_id],
        "event_count": int(event_metrics["event_count"]),
        "afterfire_event_count": int(afterfire["event_count"]),
        "event": event_metrics,
        "afterfire": afterfire,
        "pressure_accounting": accounting,
    }


def reconcile_round2_pressure(
    vehicle_id: str,
    render: SourceRender,
    trace: VehicleStateTrace | None = None,
) -> SourceRender:
    """Return the explicit Round-2 pressure view without changing the input."""

    _validate_vehicle(vehicle_id)
    render = render.validate()
    if trace is not None:
        trace.validate()
        if render.pressure.shape[0] != trace.time_s.size:
            raise ValueError("render/trace sample counts do not match")
    return _reconcile_pressure(vehicle_id, render, trace)


def _reconcile_pressure(
    vehicle_id: str,
    render: SourceRender,
    trace: VehicleStateTrace | None,
) -> SourceRender:
    aliases = _ALIAS_STEMS[vehicle_id]
    stems = dict(render.stems)
    primitive_names = [
        name
        for name in render.stems
        if name in _ALLOWED_PRIMITIVE_STEMS[vehicle_id] and name not in aliases
    ]
    if vehicle_id == "rx7_fd" and "rx7_source_level_envelope" not in render.stems:
        # The Stage-G RX-7 source intentionally keeps its high-rpm source
        # envelope in ``pressure`` but not in the historical stem dictionary.
        # Preserve those exact bytes by naming the residual in this Round-2
        # view.  The later accounting layer can then prove a single sum.
        if trace is None:
            raise ValueError("RX-7 pressure reconciliation requires the state trace")
        expected = _sum_stems(render.stems, primitive_names)
        envelope = np.asarray(render.pressure, dtype=np.float64) - expected
        stems["rx7_source_level_envelope"] = envelope
        primitive_names.append("rx7_source_level_envelope")
    pressure = _sum_stems(stems, primitive_names)
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "round2_pressure_reconciled": True,
            "round2_pressure_contributors": list(primitive_names),
            "round2_pressure_aliases_excluded": sorted(name for name in stems if name in aliases),
            "round2_pressure_reconciliation": (
                "rx7_trace_bound_source_level_envelope" if vehicle_id == "rx7_fd" else "explicit_primitive_sum"
            ),
        }
    )
    return replace(render, pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def _pressure_accounting(vehicle_id: str, render: SourceRender) -> dict[str, object]:
    aliases = _ALIAS_STEMS[vehicle_id]
    allowed = _ALLOWED_PRIMITIVE_STEMS[vehicle_id]
    available = set(render.stems)
    missing = sorted(_REQUIRED_STEMS[vehicle_id] - available)
    unknown = sorted(available - aliases - allowed)
    primitive_names = [name for name in render.stems if name in allowed and name not in aliases]
    expected = _sum_stems(render.stems, primitive_names)
    difference = np.asarray(render.pressure, dtype=np.float64) - expected
    unexpected_energy = float(np.sum(np.square(difference)))
    pressure_energy = float(np.sum(np.square(render.pressure)))
    relative_error = math.sqrt(unexpected_energy / max(pressure_energy, 1.0e-18))
    tolerance = max(1.0e-18, pressure_energy * 1.0e-12)
    return {
        "primitive_stems": list(primitive_names),
        "excluded_alias_stems": sorted(name for name in render.stems if name in aliases),
        "unknown_stems": unknown,
        "missing_required_stems": missing,
        "unexpected_energy": unexpected_energy,
        "relative_error": relative_error,
        "passes": bool(not missing and not unknown and unexpected_energy <= tolerance),
    }


def _validated_parameters(vehicle_id: str, parameters: Mapping[str, float] | None) -> dict[str, float]:
    _validate_vehicle(vehicle_id)
    expected = PARAMETER_GRIDS[vehicle_id]
    if parameters is None:
        return {name: bounds[1] for name, bounds in expected.items()}
    if not isinstance(parameters, Mapping) or set(parameters) != set(expected):
        raise ValueError(f"Round-2 {vehicle_id} parameter keys mismatch")
    values: dict[str, float] = {}
    for name, raw in parameters.items():
        if isinstance(raw, bool):
            raise ValueError(f"Round-2 parameter {name!r} must be numeric")
        value = float(raw)
        low, _seed, high = expected[name]
        if not np.isfinite(value) or value < low or value > high:
            raise ValueError(f"Round-2 parameter {name!r} is outside its bounded grid")
        values[name] = value
    return values


@lru_cache(maxsize=2)
def _load_stage_g_profile(vehicle_id: str):
    path = Path(__file__).resolve().parents[1] / "targets" / "stage_g_candidates" / _CANDIDATE_FILENAMES[vehicle_id]
    return load_stage_g_candidate(path)


def _measure_named_event(
    vehicle_id: str,
    audio: np.ndarray,
    trace: VehicleStateTrace,
    windows: Mapping[str, EventWindow],
    sample_rate_hz: int,
) -> dict[str, object]:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    onsets = _event_onsets(mono, sample_rate_hz)
    onset_times = [float(trace.time_s[index]) for index in onsets]
    event_window = windows["shift"] if vehicle_id == "ferrari_458" else windows["lift"]
    selected = [
        index
        for index in onsets
        if event_window.start_s <= float(trace.time_s[index]) <= event_window.end_s
    ]
    selected_times = [float(trace.time_s[index]) for index in selected]
    wrong_condition = 0
    for index in selected:
        if vehicle_id == "ferrari_458":
            if float(trace.throttle[index]) <= 0.30:
                wrong_condition += 1
        elif float(trace.load[min(index, trace.load.size - 1)]) < 0.45:
            wrong_condition += 1
    expected = _detect_round2_shift_events(trace, sample_rate_hz) if vehicle_id == "ferrari_458" else ()
    missing_expected = 0
    if expected:
        missing_expected = int(
            sum(
                not any(abs(float(event.time_s) - onset) <= 0.20 for onset in selected_times)
                for event in expected
            )
        )
    amplitudes = [float(np.max(np.abs(mono[index : min(mono.size, index + max(1, int(0.25 * sample_rate_hz)))]))) for index in selected]
    return {
        "event_stem": _EVENT_STEMS[vehicle_id],
        "event_kind": _EVENT_KINDS[vehicle_id],
        "event_count": len(selected),
        "all_array_event_count": len(onsets),
        "onset_times_s": selected_times,
        "all_onset_times_s": onset_times,
        "amplitudes": amplitudes,
        "amplitude_cv": _coefficient_of_variation(amplitudes),
        "qualification": {
            "wrong_condition_event_count": wrong_condition,
            "missing_expected_event_count": missing_expected,
            "eligible": bool(selected and wrong_condition == 0 and missing_expected == 0),
            "source": "actual_named_source_array_and_trace_window",
        },
    }


def _measure_afterfire(
    audio: object,
    trace: VehicleStateTrace,
    windows: Mapping[str, EventWindow],
    sample_rate_hz: int,
) -> dict[str, object]:
    if audio is None:
        return {
            "available": False,
            "event_count": 0,
            "event_kind": "generic_afterfire_measured_separately",
            "qualification": {"eligible": False, "source": "afterfire_stem_missing"},
        }
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    onsets = _event_onsets(mono, sample_rate_hz)
    wrong = 0
    for index in onsets:
        history_start = max(0, index - int(round(3.0 * sample_rate_hz)))
        history = trace.load[history_start:index]
        if history.size == 0 or float(np.max(history)) < 0.60 or float(trace.throttle[index]) > 0.25:
            wrong += 1
    return {
        "available": True,
        "event_count": len(onsets),
        "event_kind": "generic_afterfire_measured_separately",
        "onset_times_s": [float(trace.time_s[index]) for index in onsets],
        "qualification": {
            "wrong_condition_event_count": wrong,
            "eligible": bool(onsets and wrong == 0),
            "source": "actual_afterfire_array_and_trace_history",
        },
    }


def _event_onsets(audio: np.ndarray, sample_rate_hz: int) -> list[int]:
    array = np.asarray(audio, dtype=np.float64)
    mono = np.mean(array, axis=1) if array.ndim == 2 else array
    magnitude = np.abs(mono)
    peak = float(np.max(magnitude)) if magnitude.size else 0.0
    if peak <= 1.0e-15:
        return []
    threshold = peak * 0.45
    starts = np.flatnonzero((magnitude >= threshold) & (np.r_[False, magnitude[:-1] < threshold]))
    minimum_gap = max(1, int(round(0.05 * sample_rate_hz)))
    kept: list[int] = []
    for start in starts:
        start = int(start)
        if not kept or start - kept[-1] >= minimum_gap:
            kept.append(start)
    return kept


def _detect_round2_shift_events(trace: VehicleStateTrace, sample_rate_hz: int) -> tuple[ShiftEvent, ...]:
    """Detect normal shifts, with a bounded fallback for short trace steps.

    Stage-G's detector intentionally rejects instantaneous or relatively long
    RPM steps.  The Round-2 source layer also accepts the compact 8--12 s
    traces used by metrics tests, so a trace-derived transition fallback is
    needed for those arrays.  It still requires a throttle-gated RPM drop,
    minimum drop and subsequent RPM recovery; diagnostics are never used.
    """

    try:
        detected = detect_shift_events(trace, int(sample_rate_hz))
    except ValueError:
        detected = ()
    if detected:
        return detected

    time_s = np.asarray(trace.time_s, dtype=np.float64)
    rpm = np.asarray(trace.rpm, dtype=np.float64)
    throttle = np.asarray(trace.throttle, dtype=np.float64)
    if rpm.size < 3:
        return ()
    derivative = np.gradient(rpm, time_s)
    candidates = (derivative < -1500.0) & (throttle > 0.30)
    indices = np.flatnonzero(candidates)
    if not indices.size:
        return ()
    groups: list[tuple[int, int]] = []
    start = previous = int(indices[0])
    for raw_index in indices[1:]:
        index = int(raw_index)
        if index != previous + 1:
            groups.append((start, previous))
            start = index
        previous = index
    groups.append((start, previous))

    dt = float(np.median(np.diff(time_s)))
    if not np.isfinite(dt) or dt <= 0.0:
        return ()
    events: list[ShiftEvent] = []
    last_time = -float("inf")
    for group_start, group_end in groups:
        local = group_start + int(np.argmin(derivative[group_start : group_end + 1]))
        anchor = float(time_s[local])
        before_count = max(1, int(round(0.050 / dt)))
        after_count = max(1, int(round(0.050 / dt)))
        before_start = max(0, local - before_count)
        after_end = min(rpm.size, local + after_count + 1)
        rpm_before = float(np.median(rpm[before_start : max(local, before_start + 1)]))
        rpm_after = float(np.median(rpm[min(local + 1, rpm.size - 1) : after_end]))
        drop = rpm_before - rpm_after
        if drop < max(250.0, 0.04 * max(rpm_before, 1.0)):
            continue
        recovery_end = min(rpm.size, local + max(1, int(round(0.60 / dt))) + 1)
        if float(np.max(rpm[local : recovery_end])) - rpm_after < 0.30 * drop:
            continue
        if anchor - last_time < 0.50:
            continue
        events.append(
            ShiftEvent(
                anchor,
                int(round(anchor * int(sample_rate_hz))),
                rpm_before,
                rpm_after,
                drop,
            )
        )
        last_time = anchor
    return tuple(events)


def _clock_coherence(stems: Mapping[str, object], trace: VehicleStateTrace, sample_rate_hz: int) -> dict[str, object]:
    induction = sum(
        (
            np.mean(np.abs(np.asarray(stems[name], dtype=np.float64)), axis=1)
            for name in _INDUCTION_STEMS[_vehicle_from_stems(stems)]
            if name in stems
        ),
        np.zeros(trace.time_s.size, dtype=np.float64),
    )
    phase = np.cumsum(np.maximum(trace.rpm, 0.0)) / (60.0 * float(sample_rate_hz))
    clock = np.cos(2.0 * np.pi * 2.0 * phase)
    induction = induction - float(np.mean(induction))
    clock = clock - float(np.mean(clock))
    denominator = float(np.linalg.norm(induction) * np.linalg.norm(clock))
    value = 0.0 if denominator <= 1.0e-18 else abs(float(np.dot(induction, clock)) / denominator)
    return {"value": float(np.clip(value, 0.0, 1.0)), "clock_order": 2.0, "source": "actual_induction_arrays_and_trace_crank_phase"}


def _spectral_distance(candidate: np.ndarray, parent: SourceRender | None, sample_rate_hz: int) -> dict[str, object]:
    result: dict[str, object] = {"band_hz": [800.0, 3000.0], "source": "actual_source_arrays"}
    if parent is None:
        result.update({"available": False, "normalized_l2": None, "reason": "parent_render_missing"})
        return result
    parent = parent.validate()
    count = min(candidate.shape[0], parent.pressure.shape[0])
    candidate_mono = np.mean(candidate[:count], axis=1)
    parent_mono = np.mean(parent.pressure[:count], axis=1)
    frequencies = np.fft.rfftfreq(count, 1.0 / float(sample_rate_hz))
    mask = (frequencies >= 800.0) & (frequencies <= 3000.0)
    candidate_spectrum = np.abs(np.fft.rfft(candidate_mono))[mask]
    parent_spectrum = np.abs(np.fft.rfft(parent_mono))[mask]
    candidate_spectrum /= max(float(np.linalg.norm(candidate_spectrum)), 1.0e-18)
    parent_spectrum /= max(float(np.linalg.norm(parent_spectrum)), 1.0e-18)
    result.update({"available": True, "normalized_l2": float(np.linalg.norm(candidate_spectrum - parent_spectrum))})
    return result


def _band_measurements(audio: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    if mono.size == 0:
        return {name: float("-inf") for name in _BANDS_HZ}
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / float(sample_rate_hz))
    power = np.square(np.abs(np.fft.rfft(mono))) / max(1, mono.size)
    return {
        name: float(10.0 * np.log10(max(float(np.sum(power[(frequencies >= low) & (frequencies < high)])), 1.0e-24)))
        for name, (low, high) in _BANDS_HZ.items()
    }


def _energy(stems: Mapping[str, object], names: tuple[str, ...]) -> float:
    return float(sum(float(np.sum(np.square(np.asarray(stems[name], dtype=np.float64)))) for name in names if name in stems))


def _sum_stems(stems: Mapping[str, object], names: list[str]) -> np.ndarray:
    if not names:
        raise ValueError("primitive pressure contributor set is empty")
    first = np.asarray(stems[names[0]], dtype=np.float64)
    return sum((np.asarray(stems[name], dtype=np.float64) for name in names), np.zeros_like(first))


def _window_mask(time_s: np.ndarray, window: EventWindow) -> np.ndarray:
    return (np.asarray(time_s, dtype=np.float64) >= window.start_s) & (np.asarray(time_s, dtype=np.float64) <= window.end_s)


def _window(name: str, anchor: float, before: float, after: float, start: float, end: float, source: str) -> EventWindow:
    return EventWindow(name, max(start, anchor - before), min(end, anchor + after), anchor, source)


def _first_transition(values: np.ndarray, *, predicate) -> int | None:
    for index, value in enumerate(np.asarray(values, dtype=np.float64)):
        if predicate(float(value), index):
            return int(index)
    return None


def _vehicle_from_stems(stems: Mapping[str, object]) -> str:
    if "left_bank" in stems:
        return "ferrari_458"
    return "rx7_fd"


def _coefficient_of_variation(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = float(np.mean(values))
    return 0.0 if abs(mean) <= 1.0e-18 else float(np.std(values) / abs(mean))


def _validate_vehicle(vehicle_id: str) -> None:
    if vehicle_id not in VEHICLES:
        raise ValueError(f"legacy Round-2 is limited to Ferrari/RX-7: {vehicle_id!r}")


__all__ = (
    "EventWindow",
    "PARAMETER_GRIDS",
    "ROUND2_LEGACY_PARAMETER_GRIDS",
    "ROUND2_LEGACY_VEHICLES",
    "ROUND2_PARAMETER_GRIDS",
    "ROUND2_VEHICLES",
    "VEHICLES",
    "apply_round2_source_overlay",
    "measure_round2_metrics",
    "reconcile_round2_pressure",
    "render_round2_baseline",
    "render_round2_candidate",
    "resolve_round2_event_windows",
)
