"""Measured Round-2 contracts shared by the three non-Hellcat Stage-K cars.

This module is deliberately source-domain only.  It does not replace the
vehicle renderers, common layers, Frozen PTR, or the Stage-K package builder.
It provides the small set of measurements needed to prevent the Round-2
lessons from becoming declarative diagnostics: windows are found from the
trace, pressure is reconciled from primitive contributors, and named event
counts come from arrays rather than diagnostic claims.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Mapping

import numpy as np

from ..acoustic_layers.shift_dynamics import detect_shift_events
from ..contracts import SourceRender, VehicleStateTrace


ROUND2_VEHICLES = ("c63_w204", "gtr_r35", "lfa")
ROUND2_BANDS_HZ = {
    "80_250_hz": (80.0, 250.0),
    "250_1000_hz": (250.0, 1000.0),
    "1000_4000_hz": (1000.0, 4000.0),
}

# Vehicle-specific bounded grids.  They intentionally reuse the existing
# source-domain primitives rather than importing Hellcat controls into the
# other three cars.  The middle value is the seed used by the first probe.
ROUND2_PARAMETER_GRIDS = {
    "c63_w204": {
        "bark_body_gain": (1.00, 1.10, 1.20),
        "bark_upper_mix": (0.65, 0.80, 0.95),
        "mechanical_high_load_gain": (0.90, 0.98, 1.06),
    },
    "gtr_r35": {
        "exhaust_high_load_gain": (1.00, 1.08, 1.16),
        "turbo_high_load_mix": (0.70, 0.82, 0.94),
        "bov_release_mix": (0.80, 0.90, 1.00),
    },
    "lfa": {
        "order_high_load_mix": (0.88, 0.95, 1.02),
        "intake_high_load_mix": (0.80, 0.90, 1.00),
        "metallic_event_mix": (0.78, 0.88, 0.98),
        "reengagement_gain": (0.85, 1.00, 1.15),
    },
}


@dataclass(frozen=True)
class EventWindow:
    """A trace-derived window and its measured event anchor."""

    name: str
    start_s: float
    end_s: float
    anchor_s: float
    source: str


# Diagnostic bank/partial stems are intentionally excluded from pressure.
_REQUIRED_SOURCE_STEMS = {
    "c63_w204": ("exhaust", "bark", "mechanical", "closed_throttle_tail"),
    "gtr_r35": (
        "exhaust",
        "order_family",
        "turbo_primary",
        "turbo_secondary",
        "turbo_sidebands",
        "intake_duct",
        "wastegate",
        "mechanical",
    ),
    "lfa": (
        "exhaust",
        "order_family",
        "intake",
        "mechanical",
        "metallic",
        "lfa_shift_exhaust_reengagement",
    ),
}

# These are decompositions of another contributor, not additional pressure
# contributors.  Every other actual stem returned by the renderer (including
# afterfire, body, rumble and shift stems) is counted exactly once.
_DIAGNOSTIC_ALIAS_STEMS = {
    "c63_w204": frozenset((
        "exhaust_left_bank", "exhaust_right_bank", "bark_primary",
        "pressure_pulse", "exhaust_coupling", "body_resonance", "low_frequency_body",
        "shift_torque_interruption",
    )),
    "gtr_r35": frozenset((
        "pressure_pulse", "exhaust_coupling", "body_resonance", "low_frequency_body",
        "shift_torque_interruption",
    )),
    "lfa": frozenset((
        "pressure_pulse", "exhaust_coupling", "body_resonance", "low_frequency_body",
        "lfa_shift_torque_cut", "lfa_intake_lift_decay",
    )),
}

_ENGINE_STEMS = {
    "c63_w204": ("exhaust", "bark"),
    "gtr_r35": ("exhaust", "order_family", "mechanical"),
    "lfa": ("exhaust", "order_family", "mechanical"),
}

_INDUCTION_STEMS = {
    "c63_w204": ("mechanical",),
    "gtr_r35": ("turbo_primary", "turbo_secondary", "turbo_sidebands", "intake_duct", "wastegate"),
    "lfa": ("intake", "metallic"),
}


def resolve_round2_event_windows(
    vehicle_id: str,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48_000,
) -> dict[str, EventWindow]:
    """Find idle, post-shift, high-load and lift windows from state arrays.

    The method intentionally does not inspect ``render.diagnostics``.  A
    trace without a real transition fails closed instead of silently falling
    back to a prefix slice.
    """

    _validate_vehicle(vehicle_id)
    trace = trace.validate()
    if int(sample_rate_hz) <= 0:
        raise ValueError("sample_rate_hz must be positive")
    start = float(trace.time_s[0])
    end = float(trace.time_s[-1])
    idle_end = min(end, start + 8.0)
    windows: dict[str, EventWindow] = {
        "idle": EventWindow("idle", start, idle_end, start, "trace_start"),
    }

    shift_index = _first_transition(
        np.diff(trace.rpm),
        # The canonical trace models a finite shift drop as a short ramp, not
        # a one-sample discontinuity.  A small per-sample threshold therefore
        # catches both the real ramp and the synthetic test transition.
        predicate=lambda delta, index: delta < -0.15 and trace.throttle[index] > 0.45,
    )
    if shift_index is None:
        raise ValueError("trace does not contain a measurable shift transition")
    shift_anchor = float(trace.time_s[shift_index])
    windows["post_shift"] = _window(
        "post_shift", shift_anchor, 0.45, 1.55, start, end, "trace_rpm_drop",
    )

    high = (trace.load >= 0.72) & (trace.throttle >= 0.72)
    high_indices = np.flatnonzero(high)
    if high_indices.size == 0:
        raise ValueError("trace does not contain a measurable high-load interval")
    high_start = float(trace.time_s[int(high_indices[0])])
    high_end = float(trace.time_s[int(high_indices[-1])])
    high_anchor = (high_start + high_end) * 0.5
    windows["high_load"] = EventWindow(
        "high_load", high_start, max(high_start, high_end), high_anchor,
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
        "lift", lift_anchor, 0.25, 10.0, start, end,
        "trace_throttle_and_load_transition",
    )
    return windows


def measure_round2_metrics(
    vehicle_id: str,
    render: SourceRender,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48_000,
    *,
    parent_render: SourceRender | None = None,
) -> dict[str, object]:
    """Measure three-car Round-2 source evidence from arrays and trace only."""

    _validate_vehicle(vehicle_id)
    render = render.validate()
    trace = trace.validate()
    windows = resolve_round2_event_windows(vehicle_id, trace, sample_rate_hz)
    count = int(render.pressure.shape[0])
    if count != trace.time_s.size:
        raise ValueError("render/trace sample counts do not match")

    required = set(_REQUIRED_SOURCE_STEMS[vehicle_id])
    available = set(render.stems)
    if not required.issubset(available):
        missing = sorted(required - available)
        raise ValueError(f"stem contract for {vehicle_id} is missing {missing!r}")

    contributor_names = tuple(name for name in render.stems if name not in _DIAGNOSTIC_ALIAS_STEMS[vehicle_id])
    expected = sum(
        (np.asarray(render.stems[name], dtype=np.float64) for name in contributor_names),
        np.zeros_like(render.pressure, dtype=np.float64),
    )
    difference = np.asarray(render.pressure, dtype=np.float64) - expected
    unexpected_energy = float(np.sum(np.square(difference)))
    pressure_energy = float(np.sum(np.square(render.pressure)))
    tolerance = max(1e-18, pressure_energy * 1e-12)

    window_payload: dict[str, dict[str, object]] = {}
    for name, window in windows.items():
        mask = (trace.time_s >= window.start_s) & (trace.time_s <= window.end_s)
        if int(np.count_nonzero(mask)) < 2:
            raise ValueError(f"round2 window {name!r} is empty")
        pressure_window = np.asarray(render.pressure[mask], dtype=np.float64)
        window_payload[name] = {
            "start_s": window.start_s,
            "end_s": window.end_s,
            "anchor_s": window.anchor_s,
            "source": window.source,
            "bands_db": _band_measurements(pressure_window, sample_rate_hz),
            "energy": float(np.sum(np.square(pressure_window))),
        }

    event_stem = _event_stem(vehicle_id, render.stems)
    event_audio = np.asarray(render.stems[event_stem], dtype=np.float64)
    event_count = _count_array_events(event_audio, sample_rate_hz)
    engine_energy = _energy(render.stems, _ENGINE_STEMS[vehicle_id])
    induction_energy = _energy(render.stems, _INDUCTION_STEMS[vehicle_id])
    event_metrics = _measure_afterfire(
        event_audio,
        trace,
        sample_rate_hz,
        event_stem=event_stem,
        qualification_mode="shift_alignment" if vehicle_id == "lfa" else "closed_throttle_history",
    )
    event_kind = {
        "afterfire": "afterfire",
        "closed_throttle_tail": "closed_throttle_bark",
        "wastegate": "boost_history_bov",
        "lfa_shift_exhaust_reengagement": "asg_shift_reengagement",
    }.get(event_stem, event_stem)
    event_metrics["event_kind"] = event_kind
    if "afterfire" in render.stems:
        afterfire = _measure_afterfire(
            np.asarray(render.stems["afterfire"], dtype=np.float64),
            trace,
            sample_rate_hz,
            event_stem="afterfire",
        )
        afterfire["event_kind"] = "existing_stage_k_afterfire"
    else:
        afterfire = {
            "available": False,
            "event_kind": "afterfire_unavailable",
            "event_count": 0,
            "qualification": {
                "wrong_condition_event_count": 0,
                "eligible": False,
                "source": "no_afterfire_stem_in_vehicle_render",
            },
        }
    spectral_distance = _spectral_distance(
        np.asarray(render.pressure, dtype=np.float64),
        None if parent_render is None else np.asarray(parent_render.pressure, dtype=np.float64),
        sample_rate_hz,
    )
    return {
        "vehicle_id": vehicle_id,
        "measurement_provenance": "actual_arrays_and_trace",
        "diagnostics_claims_used": False,
        "event_windows": window_payload,
        "bands_db": _band_measurements(render.pressure, sample_rate_hz),
        "source_balance": {
            "engine_energy": engine_energy,
            "induction_energy": induction_energy,
            "induction_to_engine_ratio": induction_energy / max(engine_energy, 1e-18),
        },
        "clock_coherence": _clock_coherence(
            render.stems,
            trace,
            sample_rate_hz,
            induction_names=_INDUCTION_STEMS[vehicle_id],
        ),
        "spectral_distance": spectral_distance,
        "event_stem": event_stem,
        "event_kind": event_kind,
        "event_count": event_count,
        "afterfire_event_count": int(afterfire.get("event_count", 0)),
        "event": event_metrics,
        "afterfire": afterfire,
        "pressure_accounting": {
            "primitive_stems": list(contributor_names),
            "unexpected_energy": unexpected_energy,
            "relative_error": math.sqrt(unexpected_energy / max(pressure_energy, 1e-18)),
            "passes": bool(unexpected_energy <= tolerance),
        },
    }


def _clock_coherence(
    stems: Mapping[str, object],
    trace: VehicleStateTrace,
    sample_rate_hz: int,
    *,
    induction_names: tuple[str, ...],
) -> dict[str, object]:
    """Compare an actual induction envelope with a trace-derived crank clock."""

    count = trace.time_s.size
    induction = sum(
        (
            np.mean(np.abs(np.asarray(stems[name], dtype=np.float64)), axis=1)
            for name in induction_names
            if name in stems
        ),
        np.zeros(count, dtype=np.float64),
    )
    rpm = np.asarray(trace.rpm, dtype=np.float64)
    dt = 1.0 / float(sample_rate_hz)
    phase = np.cumsum(np.maximum(rpm, 0.0)) * dt / 60.0
    # The second crank order is a conservative shared proxy; no fixed audio
    # tone is introduced, and the phase is entirely trace-derived.
    clock = np.cos(2.0 * np.pi * 2.0 * phase)
    window = max(1, int(round(0.025 * sample_rate_hz)))
    if window > 1:
        kernel = np.ones(window, dtype=np.float64) / float(window)
        envelope = np.convolve(induction, kernel, mode="same")
    else:
        envelope = induction
    envelope = envelope - float(np.mean(envelope))
    clock = clock - float(np.mean(clock))
    denominator = float(np.linalg.norm(envelope) * np.linalg.norm(clock))
    value = 0.0 if denominator <= 1.0e-18 else abs(float(np.dot(envelope, clock)) / denominator)
    return {
        "value": float(np.clip(value, 0.0, 1.0)),
        "clock_order": 2.0,
        "source": "actual_induction_arrays_and_trace_crank_phase",
    }


def _spectral_distance(
    candidate: np.ndarray,
    parent: np.ndarray | None,
    sample_rate_hz: int,
) -> dict[str, object]:
    result: dict[str, object] = {
        "band_hz": [800.0, 3000.0],
        "source": "actual_pcm_or_source_arrays",
    }
    if parent is None:
        result.update({"normalized_l2": None, "available": False, "reason": "parent_render_missing"})
        return result
    candidate_mono = np.mean(candidate, axis=1)
    parent_mono = np.mean(parent, axis=1)
    count = min(candidate_mono.size, parent_mono.size)
    candidate_mono = candidate_mono[:count]
    parent_mono = parent_mono[:count]
    frequencies = np.fft.rfftfreq(count, 1.0 / float(sample_rate_hz))
    mask = (frequencies >= 800.0) & (frequencies <= 3000.0)
    if not np.any(mask):
        result.update({"normalized_l2": 0.0, "available": False, "reason": "band_above_nyquist"})
        return result
    candidate_spectrum = np.abs(np.fft.rfft(candidate_mono))[mask]
    parent_spectrum = np.abs(np.fft.rfft(parent_mono))[mask]
    candidate_spectrum /= max(float(np.linalg.norm(candidate_spectrum)), 1.0e-18)
    parent_spectrum /= max(float(np.linalg.norm(parent_spectrum)), 1.0e-18)
    result.update(
        {
            "normalized_l2": float(np.linalg.norm(candidate_spectrum - parent_spectrum)),
            "available": True,
        }
    )
    return result


def _measure_afterfire(
    audio: np.ndarray,
    trace: VehicleStateTrace,
    sample_rate_hz: int,
    *,
    event_stem: str,
    qualification_mode: str = "closed_throttle_history",
) -> dict[str, object]:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    magnitude = np.abs(mono)
    onset_indices = _event_onsets(magnitude, sample_rate_hz)
    onset_times = [float(trace.time_s[min(index, trace.time_s.size - 1)]) for index in onset_indices]
    amplitudes: list[float] = []
    decay_values: list[float] = []
    centroids: list[float] = []
    for position, onset in enumerate(onset_indices):
        end = onset_indices[position + 1] if position + 1 < len(onset_indices) else min(magnitude.size, onset + max(1, int(round(0.25 * sample_rate_hz))))
        segment = magnitude[onset:end]
        if segment.size == 0:
            continue
        amplitudes.append(float(np.max(segment)))
        peak_index = int(np.argmax(segment))
        decay_values.append(_decay_90_10(segment[peak_index:], sample_rate_hz))
        complex_spectrum = np.fft.rfft(mono[onset:end])
        power = np.square(np.abs(complex_spectrum))
        frequencies = np.fft.rfftfreq(max(1, end - onset), 1.0 / float(sample_rate_hz))
        centroids.append(float(np.sum(frequencies * power) / max(float(np.sum(power)), 1.0e-18)))
    intervals = np.diff(onset_times)
    amplitude_cv = _coefficient_of_variation(amplitudes)
    interval_cv = _coefficient_of_variation(intervals.tolist())
    if qualification_mode == "closed_throttle_history":
        wrong_condition = 0
        for onset in onset_indices:
            history_start = max(0, onset - max(1, int(round(3.0 * sample_rate_hz))))
            history_load = trace.load[min(history_start, trace.load.size - 1): min(onset, trace.load.size)]
            closed = trace.throttle[min(onset, trace.throttle.size - 1)] <= 0.25
            if history_load.size == 0 or float(np.max(history_load)) < 0.60 or not closed:
                wrong_condition += 1
        missing_expected = 0
        qualification_source = "actual_event_array_and_trace_history"
    elif qualification_mode == "shift_alignment":
        shift_events = detect_shift_events(trace, sample_rate_hz)
        expected_times = tuple(float(event.time_s) for event in shift_events)
        tolerance_s = 0.05
        wrong_condition = 0
        matched_expected: set[int] = set()
        for onset_time in onset_times:
            if not expected_times:
                wrong_condition += 1
                continue
            nearest = int(np.argmin(np.abs(np.asarray(expected_times) - onset_time)))
            trace_index = int(np.argmin(np.abs(trace.time_s - onset_time)))
            aligned = abs(expected_times[nearest] - onset_time) <= tolerance_s
            throttle_open = float(trace.throttle[trace_index]) > 0.30
            if aligned and throttle_open:
                matched_expected.add(nearest)
            else:
                wrong_condition += 1
        missing_expected = len(expected_times) - len(matched_expected)
        qualification_source = "actual_event_array_and_trace_shift_alignment"
    else:
        raise ValueError(f"unsupported event qualification mode: {qualification_mode!r}")
    return {
        "event_stem": event_stem,
        "event_count": len(onset_indices),
        "onset_times_s": onset_times,
        "amplitudes": amplitudes,
        "amplitude_cv": amplitude_cv,
        "interval_cv": interval_cv,
        "spectral_centroid_hz": float(np.mean(centroids)) if centroids else 0.0,
        "decay_90_10_s": float(np.mean(decay_values)) if decay_values else 0.0,
        "qualification": {
            "wrong_condition_event_count": wrong_condition,
            "missing_expected_event_count": missing_expected,
            "eligible": bool(onset_indices and wrong_condition == 0 and missing_expected == 0),
            "source": qualification_source,
        },
    }


def _event_onsets(magnitude: np.ndarray, sample_rate_hz: int) -> list[int]:
    peak = float(np.max(magnitude)) if magnitude.size else 0.0
    if peak <= 0.0:
        return []
    threshold = peak * 0.45
    starts = np.flatnonzero((magnitude >= threshold) & (np.r_[False, magnitude[:-1] < threshold]))
    minimum_gap = max(1, int(round(sample_rate_hz * 0.05)))
    kept: list[int] = []
    for value in starts:
        value = int(value)
        if not kept or value - kept[-1] >= minimum_gap:
            kept.append(value)
    return kept


def _coefficient_of_variation(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = float(np.mean(values))
    return 0.0 if abs(mean) <= 1.0e-18 else float(np.std(values) / abs(mean))


def _decay_90_10(segment: np.ndarray, sample_rate_hz: int) -> float:
    if segment.size == 0:
        return 0.0
    peak = float(np.max(segment))
    if peak <= 1.0e-18:
        return 0.0
    index_90 = np.flatnonzero(segment <= peak * 0.90)
    index_10 = np.flatnonzero(segment <= peak * 0.10)
    if index_90.size == 0 or index_10.size == 0:
        return 0.0
    return max(0.0, float(index_10[0] - index_90[0]) / float(sample_rate_hz))


def reconcile_round2_pressure(vehicle_id: str, render: SourceRender) -> SourceRender:
    """Return a Round-2 view with aliases removed from the pressure sum.

    The historical LFA ASG layer rebuilds ``pressure`` from every named stem,
    including ``pressure_pulse``.  That stem is an aggregate decomposition of
    the low-frequency body and must not be counted as a second contributor.
    Round-2 renders use this explicit reconciliation boundary; the historical
    Stage-K render object remains untouched and therefore remains a valid
    frozen baseline for byte comparisons.
    """

    _validate_vehicle(vehicle_id)
    render = render.validate()
    contributor_names = tuple(
        name for name in render.stems if name not in _DIAGNOSTIC_ALIAS_STEMS[vehicle_id]
    )
    pressure = sum(
        (np.asarray(render.stems[name], dtype=np.float64) for name in contributor_names),
        np.zeros_like(render.pressure, dtype=np.float64),
    )
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "round2_pressure_reconciled": True,
            "round2_pressure_contributors": list(contributor_names),
            "round2_pressure_aliases_excluded": sorted(
                name for name in render.stems if name in _DIAGNOSTIC_ALIAS_STEMS[vehicle_id]
            ),
        }
    )
    return replace(render, pressure=pressure, diagnostics=diagnostics).validate()


def render_round2_candidate(
    vehicle_id: str,
    trace: VehicleStateTrace,
    candidate: object,
    parameters: Mapping[str, float] | None = None,
) -> SourceRender:
    """Render a three-car candidate through the Round-2 pressure boundary.

    The existing Stage-K renderer remains the implementation of each vehicle's
    source model.  This wrapper is deliberately narrow: it adds no Hellcat
    layers and applies no global gain; it only makes the Round-2 pressure
    contributor contract explicit before measurement/search code consumes the
    render.
    """

    _validate_vehicle(vehicle_id)
    from .render_candidate import render_stage_k_candidate

    rendered = render_stage_k_candidate(vehicle_id, trace, candidate)
    if parameters is not None:
        return apply_round2_tuning(vehicle_id, rendered, trace, parameters)
    return reconcile_round2_pressure(vehicle_id, rendered)


def apply_round2_tuning(
    vehicle_id: str,
    render: SourceRender,
    trace: VehicleStateTrace,
    parameters: Mapping[str, float],
) -> SourceRender:
    """Apply a gated vehicle-specific Round-2 source overlay.

    The overlay starts only after the first eight seconds and only in a
    measurable load/throttle region.  It therefore cannot alter the frozen
    idle primitives.  Each change is a scale of an existing source array; no
    fixed-frequency tone, white noise, compressor or post-PTR EQ is introduced.
    """

    _validate_vehicle(vehicle_id)
    render = render.validate()
    trace = trace.validate()
    if render.pressure.shape[0] != trace.time_s.size:
        raise ValueError("render/trace sample counts do not match")
    if not isinstance(parameters, Mapping):
        raise ValueError("Round-2 tuning parameters must be a mapping")
    expected = set(ROUND2_PARAMETER_GRIDS[vehicle_id])
    if set(parameters) != expected:
        raise ValueError(f"Round-2 {vehicle_id} parameter keys mismatch")
    values: dict[str, float] = {}
    for name, raw in parameters.items():
        value = float(raw)
        low, _seed, high = ROUND2_PARAMETER_GRIDS[vehicle_id][name]
        if not np.isfinite(value) or value < low or value > high:
            raise ValueError(f"Round-2 parameter {name!r} is outside its bounded grid")
        values[name] = value

    active = (
        (trace.time_s > 8.0)
        & (trace.load >= 0.60)
        & (trace.throttle >= 0.55)
    )
    mask = active.astype(np.float64)[:, None]
    def event_mask(stem_name: str) -> np.ndarray:
        if stem_name not in render.stems:
            return np.zeros(render.pressure.shape[0], dtype=bool)
        values = np.max(np.abs(np.asarray(render.stems[stem_name], dtype=np.float64)), axis=1)
        return (trace.time_s > 8.0) & (values > 1.0e-12)

    stems = {name: np.asarray(stem, dtype=np.float64).copy() for name, stem in render.stems.items()}
    if vehicle_id == "c63_w204":
        primary = stems["bark_primary"]
        upper = stems["bark"] - primary
        bark = values["bark_body_gain"] * primary + values["bark_upper_mix"] * upper
        stems["bark"] = np.where(mask == 1.0, bark, stems["bark"])
        stems["bark_primary"] = np.where(
            mask == 1.0,
            values["bark_body_gain"] * primary,
            stems["bark_primary"],
        )
        mechanical = stems["mechanical"] * values["mechanical_high_load_gain"]
        stems["mechanical"] = np.where(mask == 1.0, mechanical, stems["mechanical"])
    elif vehicle_id == "gtr_r35":
        exhaust = stems["exhaust"] * values["exhaust_high_load_gain"]
        stems["exhaust"] = np.where(mask == 1.0, exhaust, stems["exhaust"])
        for name in ("turbo_primary", "turbo_secondary", "turbo_sidebands", "intake_duct"):
            scaled = stems[name] * values["turbo_high_load_mix"]
            stems[name] = np.where(mask == 1.0, scaled, stems[name])
        bov = stems["wastegate"] * values["bov_release_mix"]
        bov_mask = event_mask("wastegate")[:, None]
        stems["wastegate"] = np.where(bov_mask, bov, stems["wastegate"])
    else:
        order = stems["order_family"] * values["order_high_load_mix"]
        intake = stems["intake"] * values["intake_high_load_mix"]
        metallic = stems["metallic"] * values["metallic_event_mix"]
        stems["order_family"] = np.where(mask == 1.0, order, stems["order_family"])
        stems["intake"] = np.where(mask == 1.0, intake, stems["intake"])
        metallic_mask = event_mask("metallic")[:, None] | (mask == 1.0)
        stems["metallic"] = np.where(metallic_mask, metallic, stems["metallic"])
        for name in ("lfa_shift_exhaust_reengagement", "lfa_shift_intake_reopen"):
            if name in stems:
                scaled = stems[name] * values["reengagement_gain"]
                reengagement_mask = event_mask(name)[:, None]
                stems[name] = np.where(reengagement_mask, scaled, stems[name])

    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "round2_tuning_vehicle": vehicle_id,
            "round2_tuning_parameters": values,
            "round2_tuning_active_samples": int(np.count_nonzero(active)),
            "round2_tuning_source": "existing_vehicle_primitives_trace_gated_after_8s",
        }
    )
    return reconcile_round2_pressure(
        vehicle_id,
        replace(render, stems=stems, diagnostics=diagnostics).validate(),
    )


def _validate_vehicle(vehicle_id: str) -> None:
    if vehicle_id not in ROUND2_VEHICLES:
        raise ValueError(f"Round-2 propagation is limited to C63/GT-R/LFA: {vehicle_id!r}")


def _first_transition(values: np.ndarray, *, predicate) -> int | None:
    for index, value in enumerate(np.asarray(values, dtype=np.float64)):
        if predicate(float(value), index):
            return int(index)
    return None


def _window(name: str, anchor: float, before: float, after: float, start: float, end: float, source: str) -> EventWindow:
    return EventWindow(
        name=name,
        start_s=max(start, anchor - before),
        end_s=min(end, anchor + after),
        anchor_s=anchor,
        source=source,
    )


def _event_stem(vehicle_id: str, stems: Mapping[str, object]) -> str:
    preferred = {
        "c63_w204": "closed_throttle_tail",
        "gtr_r35": "wastegate",
        "lfa": "lfa_shift_exhaust_reengagement",
    }[vehicle_id]
    if preferred not in stems:
        raise ValueError(f"stem contract for {vehicle_id} is missing event stem {preferred!r}")
    return preferred


def _count_array_events(stem: object, sample_rate_hz: int) -> int:
    mono = np.mean(np.asarray(stem, dtype=np.float64), axis=1)
    magnitude = np.abs(mono)
    peak = float(np.max(magnitude))
    if peak <= 0.0:
        return 0
    threshold = peak * 0.45
    starts = np.flatnonzero((magnitude >= threshold) & (np.r_[False, magnitude[:-1] < threshold]))
    if starts.size <= 1:
        return int(starts.size)
    minimum_gap = max(1, int(round(sample_rate_hz * 0.05)))
    kept = [int(starts[0])]
    for start in starts[1:]:
        if int(start) - kept[-1] >= minimum_gap:
            kept.append(int(start))
    return len(kept)


def _band_measurements(audio: np.ndarray, sample_rate_hz: int) -> dict[str, float]:
    mono = np.mean(np.asarray(audio, dtype=np.float64), axis=1)
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / float(sample_rate_hz))
    power = np.square(np.abs(np.fft.rfft(mono))) / max(1, mono.size)
    result: dict[str, float] = {}
    for name, (low_hz, high_hz) in ROUND2_BANDS_HZ.items():
        mask = (frequencies >= low_hz) & (frequencies < high_hz)
        energy = float(np.sum(power[mask]))
        result[name] = float(10.0 * np.log10(max(energy, 1e-24)))
    return result


def _energy(stems: Mapping[str, object], names: tuple[str, ...]) -> float:
    return float(sum(float(np.sum(np.square(np.asarray(stems[name], dtype=np.float64)))) for name in names))


__all__ = (
    "EventWindow",
    "ROUND2_BANDS_HZ",
    "ROUND2_PARAMETER_GRIDS",
    "ROUND2_VEHICLES",
    "measure_round2_metrics",
    "apply_round2_tuning",
    "reconcile_round2_pressure",
    "render_round2_candidate",
    "resolve_round2_event_windows",
)
