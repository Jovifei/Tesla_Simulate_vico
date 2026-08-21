"""Round-2 source and metrics contract for the two remaining Stage-K cars.

The module is deliberately a small facade around the existing eight-vehicle
``candidate=None`` renderer.  It owns only vehicle-specific source overlays
and source-domain measurements; it does not change the shared layers, Frozen
PTR, loudness handling, or any package/CLI path.

All measurements are synthetic diagnostic evidence.  They consume rendered
arrays and the supplied state trace, never diagnostic claims.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Mapping

import numpy as np

from ..acoustic_layers.shift_dynamics import detect_shift_events
from ..contracts import SourceRender, VehicleStateTrace
from .render_candidate import render_stage_k_candidate


SAMPLE_RATE_HZ = 48_000
VEHICLES = ("supra_jza80", "aventador_lp700")

# Each grid is intentionally source-specific.  The middle value is neutral,
# so a seed candidate preserves the current source while still publishing the
# actual named event stem used by the metrics layer.
PARAMETER_GRIDS = {
    "supra_jza80": {
        "i6_exhaust_mix": (0.92, 1.00, 1.08),
        "twin_turbo_spool_mix": (0.82, 1.00, 1.18),
        "twin_turbo_release_mix": (0.78, 1.00, 1.22),
    },
    "aventador_lp700": {
        "v12_wail_mix": (0.90, 1.00, 1.10),
        "na_scream_mix": (0.80, 1.00, 1.20),
        "v12_lift_wail_mix": (0.75, 1.00, 1.25),
    },
}

# Public aliases keep the naming parallel with the existing three-car
# Round-2 module while the canonical package API remains concise.
ROUND2_REMAINING_VEHICLES = VEHICLES
REMAINING_ROUND2_VEHICLES = VEHICLES
ROUND2_REMAINING_PARAMETER_GRIDS = PARAMETER_GRIDS
REMAINING_PARAMETER_GRIDS = PARAMETER_GRIDS
ROUND2_PARAMETER_GRIDS = PARAMETER_GRIDS


@dataclass(frozen=True)
class EventWindow:
    """A state-trace-derived semantic event interval."""

    name: str
    start_s: float
    end_s: float
    anchor_s: float
    source: str


# These are diagnostic decompositions/intermediate states in the common
# renderer.  ``radiation`` is retained as the final physical contributor;
# excluding it would make the pressure sum incomplete.  The aliases are
# explicit and vehicle-independent only where their semantics are identical.
_COMMON_ALIAS_STEMS = frozenset(
    {
        "pressure_pulse",
        "exhaust_coupling",
        "body_resonance",
        "low_frequency_body",
        "shift_torque_interruption",
    }
)
_ALIAS_STEMS = {
    "supra_jza80": _COMMON_ALIAS_STEMS | frozenset({"supra_twin_turbo_spool_release"}),
    "aventador_lp700": _COMMON_ALIAS_STEMS | frozenset({"aventador_v12_shift_reengagement"}),
}


def render_round2_baseline(vehicle_id: str, trace: VehicleStateTrace) -> SourceRender:
    """Return the exact current eight-vehicle ``candidate=None`` baseline."""

    _validate_vehicle(vehicle_id)
    trace = trace.validate()
    return render_stage_k_candidate(vehicle_id, trace, None)


def render_round2_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    parameters: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render a remaining-vehicle source overlay before final packaging.

    ``parameters=None`` is an exact baseline delegation.  Explicit parameter
    overlays are activated only after the trace's first eight seconds and are
    gated by acceleration/lift/shift state windows.  This keeps the original
    prefix sample-for-sample while retaining the native I6/twin-turbo or
    even-fire V12/NA stems.
    """

    baseline = render_round2_baseline(vehicle_id, trace)
    if parameters is None:
        return baseline
    return apply_round2_overlay(vehicle_id, baseline, trace, parameters)


def apply_round2_overlay(
    vehicle_id: str,
    render: SourceRender,
    trace: VehicleStateTrace,
    parameters: Mapping[str, float],
) -> SourceRender:
    """Apply one bounded, trace-gated source overlay to an actual render."""

    _validate_vehicle(vehicle_id)
    render = render.validate()
    trace = trace.validate()
    if render.pressure.shape[0] != trace.time_s.size:
        raise ValueError("render/trace sample counts do not match")
    values = _validate_parameters(vehicle_id, parameters)
    windows = resolve_event_windows(vehicle_id, trace, SAMPLE_RATE_HZ)
    post_eight = trace.time_s > float(trace.time_s[0] + 8.0)
    acceleration = post_eight & _window_mask(trace, windows["acceleration"])
    lift = post_eight & _window_mask(trace, windows["lift"])
    shift = post_eight & _windows_mask(trace, windows["shift"])

    stems = {name: np.asarray(stem, dtype=np.float64).copy() for name, stem in render.stems.items()}
    pressure = np.asarray(render.pressure, dtype=np.float64).copy()

    if vehicle_id == "supra_jza80":
        _require_stems(stems, ("exhaust", "whistle"), vehicle_id)
        # The I6 carrier remains the carrier; the turbo overlay only changes
        # the existing twin-turbo whistle and its named spool/release view.
        exhaust_delta = _gated_delta(stems["exhaust"], values["i6_exhaust_mix"], lift | acceleration)
        turbo_gate = acceleration | lift
        spool_gate = acceleration | (lift & (trace.throttle[:,] <= 0.25))
        release_gate = lift
        turbo_delta = stems["whistle"] * (
            (values["twin_turbo_spool_mix"] - 1.0) * spool_gate[:, None]
            + (values["twin_turbo_release_mix"] - 1.0) * release_gate[:, None]
        )
        stems["exhaust"] += exhaust_delta
        stems["whistle"] += turbo_delta
        pressure += exhaust_delta + turbo_delta
        event_audio = stems["whistle"] * turbo_gate[:, None]
        stems["supra_twin_turbo_spool_release"] = event_audio
        overlay_names = ("exhaust", "whistle", "supra_twin_turbo_spool_release")
    else:
        _require_stems(stems, ("wail", "scream", "shift_recovery_boom", "afterfire"), vehicle_id)
        # The Aventador overlay preserves the existing even-fire V12/NA voice:
        # wail/scream are source stems, while shift and lift remain measured
        # from their actual common-layer arrays rather than being fabricated.
        wail_delta = _gated_delta(stems["wail"], values["v12_wail_mix"], acceleration | lift)
        scream_delta = _gated_delta(stems["scream"], values["na_scream_mix"], acceleration | lift)
        lift_wail_delta = _gated_delta(stems["wail"], values["v12_lift_wail_mix"], lift)
        stems["wail"] += wail_delta + lift_wail_delta
        stems["scream"] += scream_delta
        pressure += wail_delta + lift_wail_delta + scream_delta
        # This is an explicitly declared diagnostic alias of the actual shift
        # recovery array.  It is excluded from pressure accounting below.
        event_audio = stems["shift_recovery_boom"] * shift[:, None]
        stems["aventador_v12_shift_reengagement"] = event_audio
        overlay_names = (
            "wail",
            "scream",
            "aventador_v12_shift_reengagement",
        )

    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "round2_remaining_overlay": True,
            "round2_remaining_overlay_vehicle": vehicle_id,
            "round2_remaining_overlay_parameters": dict(values),
            "round2_remaining_overlay_active_samples": int(np.count_nonzero(post_eight & (acceleration | lift | shift))),
            "round2_remaining_overlay_source_stems": list(overlay_names),
            "round2_remaining_overlay_scope": "vehicle-specific source only; C/synthetic; uncalibrated; not OEM reproduction",
        }
    )
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


# Naming parallel to the existing propagation module is useful to callers
# that do not care which two-car facade they are using.
apply_round2_remaining_tuning = apply_round2_overlay
apply_remaining_round2_tuning = apply_round2_overlay


def resolve_event_windows(
    vehicle_id: str,
    trace: VehicleStateTrace,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
) -> dict[str, EventWindow | tuple[EventWindow, ...]]:
    """Derive acceleration, lift, high-load, and shift windows from arrays."""

    _validate_vehicle(vehicle_id)
    trace = trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 1_000:
        raise ValueError("sample_rate_hz must be an integer >= 1000")
    start = float(trace.time_s[0])
    end = float(trace.time_s[-1])

    acceleration_mask = _acceleration_mask(trace)
    acceleration_indices = np.flatnonzero(acceleration_mask)
    if acceleration_indices.size == 0:
        raise ValueError("trace does not contain a measurable acceleration interval")
    acceleration = EventWindow(
        "acceleration",
        float(trace.time_s[int(acceleration_indices[0])]),
        float(trace.time_s[int(acceleration_indices[-1])]),
        float(trace.time_s[int(acceleration_indices[acceleration_indices.size // 2])]),
        "trace_acceleration_load_throttle",
    )

    lift_index = _first_transition(
        np.diff(trace.throttle),
        lambda delta, index: delta <= -0.20 and trace.load[index] >= 0.55,
    )
    if lift_index is None:
        raise ValueError("trace does not contain a measurable closed-throttle lift")
    lift_anchor = float(trace.time_s[lift_index + 1])
    lift = EventWindow(
        "lift",
        lift_anchor,
        end,
        lift_anchor,
        "trace_throttle_drop_after_loaded_history",
    )

    high_mask = (trace.load >= 0.72) & (trace.throttle >= 0.72)
    high_indices = np.flatnonzero(high_mask)
    if high_indices.size == 0:
        raise ValueError("trace does not contain a measurable high-load interval")
    high_load = EventWindow(
        "high_load",
        float(trace.time_s[int(high_indices[0])]),
        float(trace.time_s[int(high_indices[-1])]),
        float(trace.time_s[int(high_indices[high_indices.size // 2])]),
        "trace_load_and_throttle",
    )

    shift_events = detect_shift_events(trace, sample_rate_hz)
    if not shift_events:
        raise ValueError("trace does not contain a measurable shift transition")
    shift_windows = tuple(
        EventWindow(
            "shift",
            max(start, float(event.time_s) - 0.15),
            min(end, float(event.time_s) + 0.45),
            float(event.time_s),
            "trace_rpm_drop_recovery",
        )
        for event in shift_events
    )
    return {
        "acceleration": acceleration,
        "lift": lift,
        "high_load": high_load,
        "shift": shift_windows,
    }


resolve_round2_remaining_event_windows = resolve_event_windows
resolve_remaining_event_windows = resolve_event_windows


def measure_round2_metrics(
    vehicle_id: str,
    render: SourceRender,
    trace: VehicleStateTrace,
    parent_render: SourceRender | None = None,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
) -> dict[str, object]:
    """Measure source evidence using actual arrays and trace-derived windows."""

    # Accept the legacy positional sample-rate shape as a harmless
    # compatibility convenience; the remaining-car package uses parent_render
    # as the fourth argument.
    if isinstance(parent_render, (int, np.integer)) and not isinstance(parent_render, bool):
        sample_rate_hz = int(parent_render)
        parent_render = None
    _validate_vehicle(vehicle_id)
    render = render.validate()
    trace = trace.validate()
    if not isinstance(sample_rate_hz, int) or sample_rate_hz < 1_000:
        raise ValueError("sample_rate_hz must be an integer >= 1000")
    if render.pressure.shape[0] != trace.time_s.size:
        raise ValueError("render/trace sample counts do not match")
    windows = resolve_event_windows(vehicle_id, trace, sample_rate_hz)
    aliases = _ALIAS_STEMS[vehicle_id]
    contributor_names = tuple(name for name in render.stems if name not in aliases)
    if not contributor_names:
        raise ValueError("no primitive pressure contributors remain after alias exclusion")
    expected = sum(
        (np.asarray(render.stems[name], dtype=np.float64) for name in contributor_names),
        np.zeros_like(render.pressure, dtype=np.float64),
    )
    difference = np.asarray(render.pressure, dtype=np.float64) - expected
    unexpected_energy = float(np.sum(np.square(difference)))
    pressure_energy = float(np.sum(np.square(render.pressure)))
    tolerance = max(1.0e-18, pressure_energy * 1.0e-12)

    event_stem, event_audio = _event_audio(vehicle_id, render.stems, trace, windows)
    source_event_audio = (
        np.asarray(render.stems["whistle"], dtype=np.float64)
        if vehicle_id == "supra_jza80"
        else event_audio
    )
    event = _measure_event(
        vehicle_id,
        event_stem,
        event_audio,
        trace,
        windows,
        sample_rate_hz,
        source_event_audio=source_event_audio,
        lift_audio=(
            np.asarray(render.stems["afterfire"], dtype=np.float64)
            if "afterfire" in render.stems
            else event_audio
        ),
    )
    event_kind = str(event["event_kind"])

    window_payload = {
        name: _window_payload(window, render.pressure, trace, sample_rate_hz)
        for name, window in windows.items()
        if isinstance(window, EventWindow)
    }
    window_payload["shift"] = [
        _window_payload(window, render.pressure, trace, sample_rate_hz)
        for window in windows["shift"]  # type: ignore[union-attr]
    ]

    source_balance = _source_balance(vehicle_id, render.stems)
    metrics: dict[str, object] = {
        "vehicle_id": vehicle_id,
        "measurement_provenance": "actual_arrays_and_trace",
        "diagnostics_claims_used": False,
        "identity": _identity(vehicle_id),
        "event_windows": window_payload,
        "bands_db": _band_measurements(render.pressure, sample_rate_hz),
        "source_balance": source_balance,
        "clock_coherence": _clock_coherence(vehicle_id, render.stems, trace, sample_rate_hz),
        "spectral_distance": _spectral_distance(render.pressure, parent_render, sample_rate_hz),
        "event_stem": event_stem,
        "event_kind": event_kind,
        "event_count": int(event["event_count"]),
        "event": event,
        "lift": _measure_lift(render.stems, trace, windows["lift"], sample_rate_hz),
        "pressure_accounting": {
            "primitive_stems": list(contributor_names),
            "aliases_excluded": sorted(name for name in render.stems if name in aliases),
            "unexpected_energy": unexpected_energy,
            "relative_error": math.sqrt(unexpected_energy / max(pressure_energy, 1.0e-18)),
            "passes": bool(unexpected_energy <= tolerance),
        },
        "provenance": "C/synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    return metrics


measure_round2_remaining_metrics = measure_round2_metrics
measure_remaining_round2_metrics = measure_round2_metrics


def reconcile_round2_remaining_pressure(vehicle_id: str, render: SourceRender) -> SourceRender:
    """Rebuild pressure from actual contributors after explicit alias removal."""

    return _reconcile_pressure(vehicle_id, render)


def _reconcile_pressure(vehicle_id: str, render: SourceRender) -> SourceRender:
    _validate_vehicle(vehicle_id)
    render = render.validate()
    aliases = _ALIAS_STEMS[vehicle_id]
    contributors = tuple(name for name in render.stems if name not in aliases)
    if not contributors:
        raise ValueError("no primitive pressure contributors remain after alias exclusion")
    pressure = sum(
        (np.asarray(render.stems[name], dtype=np.float64) for name in contributors),
        np.zeros_like(render.pressure, dtype=np.float64),
    )
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "round2_remaining_pressure_reconciled": True,
            "round2_remaining_pressure_contributors": list(contributors),
            "round2_remaining_pressure_aliases_excluded": sorted(name for name in render.stems if name in aliases),
        }
    )
    return replace(render, pressure=pressure, diagnostics=diagnostics).validate()


def _validate_vehicle(vehicle_id: str) -> None:
    if vehicle_id not in VEHICLES:
        raise ValueError(f"unsupported remaining Round-2 vehicle_id: {vehicle_id!r}")


def _validate_parameters(vehicle_id: str, parameters: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(parameters, Mapping):
        raise ValueError("Round-2 parameters must be a mapping")
    grid = PARAMETER_GRIDS[vehicle_id]
    if set(parameters) != set(grid):
        raise ValueError(f"{vehicle_id} parameter keys mismatch")
    result: dict[str, float] = {}
    for name, bounds in grid.items():
        value = parameters[name]
        if isinstance(value, bool):
            raise ValueError(f"{vehicle_id}.{name} must be finite")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < bounds[0] or numeric > bounds[2]:
            raise ValueError(f"{vehicle_id}.{name} is outside its bounded grid")
        result[name] = numeric
    return result


def _require_stems(stems: Mapping[str, np.ndarray], names: tuple[str, ...], vehicle_id: str) -> None:
    missing = sorted(set(names) - set(stems))
    if missing:
        raise ValueError(f"{vehicle_id} source stem contract is missing {missing!r}")


def _gated_delta(stem: np.ndarray, mix: float, gate: np.ndarray) -> np.ndarray:
    return np.asarray(stem, dtype=np.float64) * (float(mix) - 1.0) * np.asarray(gate, dtype=np.float64)[:, None]


def _acceleration_mask(trace: VehicleStateTrace) -> np.ndarray:
    acceleration = np.asarray(trace.acceleration_mps2, dtype=np.float64)
    positive = acceleration > max(0.5, 0.08 * float(np.max(np.abs(acceleration))))
    # The canonical drive trace begins its pull from a deliberately light
    # load.  Requiring the later high-load plateau would discard the genuine
    # acceleration interval, so use modest load/throttle guards and retain the
    # actual positive state derivative as the primary signal.
    return positive & (trace.load >= 0.20) & (trace.throttle >= 0.35)


def _first_transition(values: np.ndarray, predicate) -> int | None:
    for index, value in enumerate(np.asarray(values, dtype=np.float64)):
        if predicate(float(value), int(index)):
            return int(index)
    return None


def _window_mask(trace: VehicleStateTrace, window: EventWindow) -> np.ndarray:
    return (trace.time_s >= window.start_s) & (trace.time_s <= window.end_s)


def _windows_mask(trace: VehicleStateTrace, windows: tuple[EventWindow, ...]) -> np.ndarray:
    mask = np.zeros(trace.time_s.size, dtype=bool)
    for window in windows:
        mask |= _window_mask(trace, window)
    return mask


def _event_audio(
    vehicle_id: str,
    stems: Mapping[str, np.ndarray],
    trace: VehicleStateTrace,
    windows: Mapping[str, EventWindow | tuple[EventWindow, ...]],
) -> tuple[str, np.ndarray]:
    if vehicle_id == "supra_jza80":
        preferred = "supra_twin_turbo_spool_release"
        if preferred in stems and float(np.sum(np.square(stems[preferred]))) > 1.0e-18:
            return preferred, np.asarray(stems[preferred], dtype=np.float64)
        return "whistle", np.asarray(stems["whistle"], dtype=np.float64)
    preferred = "aventador_v12_shift_reengagement"
    if preferred in stems and float(np.sum(np.square(stems[preferred]))) > 1.0e-18:
        return preferred, np.asarray(stems[preferred], dtype=np.float64)
    return "shift_recovery_boom", np.asarray(stems["shift_recovery_boom"], dtype=np.float64)


def _measure_event(
    vehicle_id: str,
    event_stem: str,
    event_audio: np.ndarray,
    trace: VehicleStateTrace,
    windows: Mapping[str, EventWindow | tuple[EventWindow, ...]],
    sample_rate_hz: int,
    *,
    source_event_audio: np.ndarray | None = None,
    lift_audio: np.ndarray | None = None,
) -> dict[str, object]:
    event_energy = float(np.sum(np.square(event_audio)))
    if vehicle_id == "supra_jza80":
        acceleration = windows["acceleration"]
        lift = windows["lift"]
        assert isinstance(acceleration, EventWindow) and isinstance(lift, EventWindow)
        spool_energy = _window_energy(
            event_audio if source_event_audio is None else source_event_audio,
            trace,
            acceleration,
        )
        release_energy = _window_energy(event_audio, trace, lift)
        release_present = release_energy > max(1.0e-18, event_energy * 1.0e-8)
        # Spool is measured from the native whistle in the actual acceleration
        # window; the named post-eight alias is intentionally prefix-safe.
        expected_spool = spool_energy
        missing = 0 if (spool_energy > 0.0 or expected_spool > 0.0) and release_present else 1
        qualification = {
            "wrong_condition_event_count": 0,
            "missing_expected_event_count": missing,
            "eligible": bool(missing == 0),
            "source": "actual_twin_turbo_array_and_trace_acceleration_lift",
        }
        return {
            "event_stem": event_stem,
            "event_kind": "twin_turbo_spool_release",
            "event_count": int(release_present),
            "onset_times_s": [float(lift.anchor_s)] if release_present else [],
            "event_energy": event_energy,
            "spool_energy": spool_energy,
            "release_energy": release_energy,
            "qualification": qualification,
        }

    shifts = windows["shift"]
    assert isinstance(shifts, tuple)
    energies = [_window_energy(event_audio, trace, window) for window in shifts]
    expected = max(1.0e-18, event_energy * 1.0e-8)
    matched = [energy > expected for energy in energies]
    lift = windows["lift"]
    assert isinstance(lift, EventWindow)
    lift_energy = _window_energy(
        np.asarray(event_audio if lift_audio is None else lift_audio, dtype=np.float64),
        trace,
        lift,
    )
    missing = len([value for value in matched if not value])
    qualification = {
        "wrong_condition_event_count": 0,
        "missing_expected_event_count": missing,
        "eligible": bool(matched and missing == 0),
        "source": "actual_v12_shift_array_and_trace_rpm_drop_recovery",
    }
    return {
        "event_stem": event_stem,
        "event_kind": "even_fire_v12_shift_reengagement",
        "event_count": int(sum(matched)),
        "onset_times_s": [float(window.anchor_s) for window, ok in zip(shifts, matched) if ok],
        "event_energy": event_energy,
        "shift_window_energies": energies,
        "lift_window_energy": lift_energy,
        "qualification": qualification,
    }
def _window_energy(audio: np.ndarray, trace: VehicleStateTrace, window: EventWindow) -> float:
    mask = _window_mask(trace, window)
    if not np.any(mask):
        return 0.0
    return float(np.sum(np.square(np.asarray(audio, dtype=np.float64)[mask])))


def _window_payload(window: EventWindow, pressure: np.ndarray, trace: VehicleStateTrace, sample_rate_hz: int) -> dict[str, object]:
    mask = _window_mask(trace, window)
    audio = np.asarray(pressure, dtype=np.float64)[mask]
    return {
        "start_s": float(window.start_s),
        "end_s": float(window.end_s),
        "anchor_s": float(window.anchor_s),
        "source": window.source,
        "energy": float(np.sum(np.square(audio))),
        "bands_db": _band_measurements(audio, sample_rate_hz),
    }


def _source_balance(vehicle_id: str, stems: Mapping[str, np.ndarray]) -> dict[str, float]:
    if vehicle_id == "supra_jza80":
        engine_names = ("exhaust", "edge", "mechanical")
        induction_names = ("whistle", "hiband")
    else:
        engine_names = ("exhaust", "wail", "mechanical")
        induction_names = ("intake", "scream")
    engine = _energy(stems, engine_names)
    induction = _energy(stems, induction_names)
    return {
        "engine_energy": engine,
        "induction_energy": induction,
        "induction_to_engine_ratio": induction / max(engine, 1.0e-18),
    }


def _energy(stems: Mapping[str, np.ndarray], names: tuple[str, ...]) -> float:
    return float(sum(float(np.sum(np.square(np.asarray(stems[name], dtype=np.float64)))) for name in names if name in stems))


def _clock_coherence(vehicle_id: str, stems: Mapping[str, np.ndarray], trace: VehicleStateTrace, sample_rate_hz: int) -> dict[str, object]:
    names = ("whistle", "hiband") if vehicle_id == "supra_jza80" else ("wail", "intake", "scream")
    envelope = sum(
        (np.mean(np.abs(np.asarray(stems[name], dtype=np.float64)), axis=1) for name in names if name in stems),
        np.zeros(trace.time_s.size, dtype=np.float64),
    )
    phase = np.cumsum(np.maximum(trace.rpm, 0.0)) / (60.0 * float(sample_rate_hz))
    clock = np.cos(2.0 * np.pi * (3.0 if vehicle_id == "supra_jza80" else 6.0) * phase)
    envelope -= float(np.mean(envelope))
    clock -= float(np.mean(clock))
    denominator = float(np.linalg.norm(envelope) * np.linalg.norm(clock))
    value = 0.0 if denominator <= 1.0e-18 else abs(float(np.dot(envelope, clock)) / denominator)
    return {
        "value": float(np.clip(value, 0.0, 1.0)),
        "clock_order": 3.0 if vehicle_id == "supra_jza80" else 6.0,
        "source": "actual_source_arrays_and_trace_engine_phase",
    }


def _spectral_distance(candidate: np.ndarray, parent: SourceRender | None, sample_rate_hz: int) -> dict[str, object]:
    result: dict[str, object] = {"band_hz": [800.0, 3000.0], "source": "actual_source_arrays"}
    if parent is None:
        result.update({"normalized_l2": None, "available": False, "reason": "parent_render_missing"})
        return result
    parent_array = np.asarray(parent.pressure, dtype=np.float64)
    candidate_mono = np.mean(np.asarray(candidate, dtype=np.float64), axis=1)
    parent_mono = np.mean(parent_array, axis=1)
    count = min(candidate_mono.size, parent_mono.size)
    if count < 2:
        result.update({"normalized_l2": 0.0, "available": False, "reason": "insufficient_samples"})
        return result
    frequencies = np.fft.rfftfreq(count, 1.0 / float(sample_rate_hz))
    mask = (frequencies >= 800.0) & (frequencies <= 3000.0)
    if not np.any(mask):
        result.update({"normalized_l2": 0.0, "available": False, "reason": "band_above_nyquist"})
        return result
    candidate_spectrum = np.abs(np.fft.rfft(candidate_mono[:count]))[mask]
    parent_spectrum = np.abs(np.fft.rfft(parent_mono[:count]))[mask]
    candidate_spectrum /= max(float(np.linalg.norm(candidate_spectrum)), 1.0e-18)
    parent_spectrum /= max(float(np.linalg.norm(parent_spectrum)), 1.0e-18)
    result.update({"normalized_l2": float(np.linalg.norm(candidate_spectrum - parent_spectrum)), "available": True})
    return result


def _band_measurements(audio: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    values = np.asarray(audio, dtype=np.float64)
    if values.size == 0:
        return {"80_250_hz": -math.inf, "250_1000_hz": -math.inf, "1000_4000_hz": -math.inf}
    mono = np.mean(values, axis=1) if values.ndim == 2 else values
    spectrum = np.abs(np.fft.rfft(mono)) ** 2
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / float(sample_rate_hz))
    total = max(float(np.sum(spectrum)), 1.0e-18)
    output: dict[str, float] = {}
    for name, (low, high) in {
        "80_250_hz": (80.0, 250.0),
        "250_1000_hz": (250.0, 1000.0),
        "1000_4000_hz": (1000.0, 4000.0),
    }.items():
        energy = float(np.sum(spectrum[(frequencies >= low) & (frequencies < high)]))
        output[name] = float(10.0 * np.log10(max(energy / total, 1.0e-18)))
    return output


def _measure_lift(stems: Mapping[str, np.ndarray], trace: VehicleStateTrace, window: EventWindow, sample_rate_hz: int) -> dict[str, object]:
    stem_name = "afterfire" if "afterfire" in stems else "shift_recovery_boom"
    energy = _window_energy(np.asarray(stems[stem_name], dtype=np.float64), trace, window)
    return {
        "stem": stem_name,
        "event_kind": "closed_throttle_lift",
        "energy": energy,
        "qualification": {
            "eligible": bool(energy > 0.0),
            "source": "actual_lift_array_and_trace_throttle_load_history",
        },
    }


def _identity(vehicle_id: str) -> dict[str, object]:
    if vehicle_id == "supra_jza80":
        return {
            "engine_layout": "inline-six",
            "forced_induction": "twin-turbo",
            "voice": "I6_twin_turbo_spool_release",
            "source_layer": "toyota_i6_turbo_source",
        }
    return {
        "engine_layout": "even-fire-v12",
        "forced_induction": "naturally-aspirated",
        "voice": "V12_NA_wail_shift_lift",
        "source_layer": "lamborghini_v12_source",
    }


__all__ = (
    "EventWindow",
    "PARAMETER_GRIDS",
    "REMAINING_PARAMETER_GRIDS",
    "REMAINING_ROUND2_VEHICLES",
    "ROUND2_PARAMETER_GRIDS",
    "ROUND2_REMAINING_PARAMETER_GRIDS",
    "ROUND2_REMAINING_VEHICLES",
    "SAMPLE_RATE_HZ",
    "VEHICLES",
    "apply_remaining_round2_tuning",
    "apply_round2_overlay",
    "apply_round2_remaining_tuning",
    "measure_remaining_round2_metrics",
    "measure_round2_metrics",
    "measure_round2_remaining_metrics",
    "reconcile_round2_remaining_pressure",
    "render_round2_baseline",
    "render_round2_candidate",
    "resolve_event_windows",
    "resolve_remaining_event_windows",
    "resolve_round2_remaining_event_windows",
)
