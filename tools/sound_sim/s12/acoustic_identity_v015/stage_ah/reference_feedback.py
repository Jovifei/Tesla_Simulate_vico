"""Bounded analysis-by-synthesis, separate from human score/tag feedback.

R3 references permit relative spectral-shape experiments, not OEM similarity.
The objective pools power, not phase; exported audio is never normalized to a
reference. Validation sources are used ONCE after training, never for search.
This module is independent of any particular vehicle renderer.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

import numpy as np
from scipy.signal import welch

SCHEMA = "s12.stage_ah.reference_feedback.v1"
METRIC = "multires_relative_band_power_tv_v1"
SR = 48_000
BAND_EDGES = np.geomspace(20.0, 16_000.0, 49)


def pcm_float(audio: np.ndarray) -> np.ndarray:
    """Validate PCM and convert its declared dtype, without peak normalization."""
    a = np.asarray(audio)
    if np.iscomplexobj(a) or a.dtype.kind not in "iuf":
        raise ValueError("real PCM required")
    if a.dtype == np.uint8:
        a = (a.astype(np.float64) - 128.0) / 128.0
    elif a.dtype.kind == "i":
        a = a.astype(np.float64) / float(2 ** (8 * a.dtype.itemsize - 1))
    elif a.dtype.kind == "u":
        raise ValueError("only unsigned 8-bit PCM is supported")
    else:
        a = a.astype(np.float64)
    if a.ndim == 1:
        a = a[:, None]
    if a.ndim != 2 or a.shape[1] not in (1, 2) or len(a) < 64:
        raise ValueError("at least 64 mono/stereo frames required")
    if not np.all(np.isfinite(a)):
        raise ValueError("non-finite PCM")
    if np.max(np.abs(a)) > 1.0 + 1e-7:
        raise ValueError("PCM exceeds full scale")
    return a


def audio_sha(audio: np.ndarray) -> str:
    a = pcm_float(audio)
    header = json.dumps(list(a.shape)).encode("ascii")
    return hashlib.sha256(header + np.ascontiguousarray(a, dtype="<f8").tobytes()).hexdigest()


def spectral_features(audio: np.ndarray, sr: int = SR) -> np.ndarray:
    """Three-resolution normalized power bands, averaged across channels.

    Channel powers are pooled AFTER Welch, so anti-phase stereo does not cancel.
    Fixed bands intentionally do not claim to estimate synchronized RPM/orders.
    """
    if isinstance(sr, bool) or not isinstance(sr, (int, np.integer)) or sr != SR:
        raise ValueError("feature contract requires 48000 Hz")
    a = pcm_float(audio)
    a = a - np.mean(a, axis=0, keepdims=True)
    if np.sqrt(np.mean(a * a)) < 1e-7:
        raise ValueError("silent/DC-only reference or candidate")
    # Common scalar scaling here is analysis-only; it never reaches rendering.
    a = a / np.max(np.abs(a))
    features = []
    for wanted in (1024, 4096, 8192):
        size = min(wanted, len(a))
        f, p = welch(a, fs=sr, window="hann", nperseg=size,
                     noverlap=size // 2, axis=0, detrend=False)
        power = np.mean(p, axis=1)
        bands = np.array([np.sum(power[(f >= lo) & (f < hi)])
                          for lo, hi in zip(BAND_EDGES[:-1], BAND_EDGES[1:])])
        total = float(np.sum(bands))
        if not math.isfinite(total) or total <= 1e-20:
            raise ValueError("no usable in-band energy")
        features.append(bands / total)
    return np.stack(features)


def feature_distance(left: np.ndarray, right: np.ndarray) -> float:
    """Total variation of power shape. Never convert this into similarity %."""
    return float(np.mean(0.5 * np.sum(np.abs(left - right), axis=1)))


@dataclass(frozen=True)
class ReferenceCase:
    case_id: str
    scene: str
    source_id: str
    source_sha256: str
    split: str
    audio: np.ndarray
    candidate_window_s: tuple[float, float]
    comparable: bool
    comparability_note: str


@dataclass
class Rendered:
    audio: np.ndarray
    numeric_ok: bool
    diagnostics: Mapping[str, Any]


@dataclass(frozen=True)
class SearchConfig:
    max_trials: int = 25
    rounds: int = 4
    initial_step_fraction: float = 0.15
    min_step_fraction: float = 0.01
    regression_fraction: float = 0.03
    min_improvement: float = 1e-5

    def validate(self) -> None:
        for value in (self.max_trials, self.rounds):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("budgets must be positive integers")
        if self.max_trials > 129 or self.rounds > 16:
            raise ValueError("offline search budget exceeds bounded policy")
        for value in (self.initial_step_fraction, self.min_step_fraction,
                      self.regression_fraction, self.min_improvement):
            if isinstance(value, bool) or not math.isfinite(float(value)):
                raise ValueError("non-finite configuration")
        if not 0 < self.min_step_fraction <= self.initial_step_fraction <= 0.5:
            raise ValueError("invalid normalized step bounds")
        if not 0 <= self.regression_fraction <= 0.10 or self.min_improvement <= 0:
            raise ValueError("invalid acceptance thresholds")


def validate_parameters(values: Mapping[str, float], bounds: Mapping[str, Sequence[float]]) -> dict[str, float]:
    if not bounds or set(values) != set(bounds):
        raise ValueError("parameter whitelist must match exactly")
    result = {}
    for name in sorted(bounds):
        lo, hi = bounds[name]
        raw = values[name]
        if isinstance(raw, (bool, str)) or not all(math.isfinite(float(v)) for v in (lo, hi, raw)):
            raise ValueError(f"invalid parameter: {name}")
        if not lo < hi or not lo <= float(raw) <= hi:
            raise ValueError(f"parameter outside bounds: {name}")
        result[name] = float(raw)
    return result


def _validate_cases(cases: Sequence[ReferenceCase]) -> None:
    if not cases or len({c.case_id for c in cases}) != len(cases):
        raise ValueError("reference cases must be nonempty and unique")
    groups: dict[str, str] = {}
    for c in cases:
        if c.split not in ("train", "validation"):
            raise ValueError("v1 accepts train/validation only; no held-out-test claim")
        if not c.case_id or not c.scene or not c.source_id:
            raise ValueError("case/scene/source identity required")
        if len(c.source_sha256) != 64 or any(x not in "0123456789abcdef" for x in c.source_sha256):
            raise ValueError("original source SHA-256 required")
        if c.comparable is not True or not c.comparability_note.strip():
            raise ValueError(f"coarse operating-state review required: {c.case_id}")
        start, stop = c.candidate_window_s
        if not all(math.isfinite(float(x)) for x in (start, stop)) or not 0 <= start < stop:
            raise ValueError("invalid candidate window")
        for key in ("id:" + c.source_id, "sha:" + c.source_sha256, "pcm:" + audio_sha(c.audio)):
            if key in groups and groups[key] != c.split:
                raise ValueError("source/recording leakage across train and validation")
            groups[key] = c.split
        spectral_features(c.audio)
    if {c.split for c in cases} != {"train", "validation"}:
        raise ValueError("independent train and validation sources required")


def _group_mean(losses: Mapping[str, float], cases: Sequence[ReferenceCase]) -> float:
    # One long recording cut into many clips must not dominate the objective.
    groups: dict[str, list[float]] = {}
    for case in cases:
        groups.setdefault(case.source_sha256, []).append(losses[case.case_id])
    return float(np.mean([np.mean(v) for v in groups.values()]))


def _no_regression(current: Mapping[str, float], anchor: Mapping[str, float], fraction: float) -> bool:
    return current.keys() == anchor.keys() and all(
        math.isfinite(v) and v <= anchor[k] * (1 + fraction) + 1e-10
        for k, v in current.items()
    )


def optimize_reference_feedback(
    baseline: Mapping[str, float], bounds: Mapping[str, Sequence[float]],
    cases: Sequence[ReferenceCase],
    render: Callable[[Mapping[str, float], str], Rendered],
    *, config: SearchConfig = SearchConfig(),
) -> dict[str, Any]:
    """Search measured +/- source perturbations, then one-shot validation.

    Search never chooses a direction from a human tag. Every accepted training
    trial must reduce measured error AND preserve each training case's guard.
    Validation rejection returns baseline parameters, not the rejected fit.
    """
    config.validate()
    baseline = validate_parameters(baseline, bounds)
    _validate_cases(cases)
    train = [c for c in cases if c.split == "train"]
    validation = [c for c in cases if c.split == "validation"]
    targets = {c.case_id: spectral_features(c.audio) for c in cases}
    cache: dict[tuple[Any, ...], tuple[dict[str, float], dict[str, str]]] = {}
    render_calls = 0

    def measure(params, selected):
        nonlocal render_calls
        key = (tuple(sorted(params.items())), tuple(c.case_id for c in selected))
        if key in cache:
            return cache[key]
        losses, hashes, audio_by_scene = {}, {}, {}
        for case in selected:
            if case.scene not in audio_by_scene:
                r = render(dict(params), case.scene)
                render_calls += 1
                if r.numeric_ok is not True:
                    raise ValueError(f"numeric gate failed: {case.scene}")
                audio_by_scene[case.scene] = pcm_float(r.audio)
            a = audio_by_scene[case.scene]
            start, stop = (int(round(x * SR)) for x in case.candidate_window_s)
            if not 0 <= start < stop <= len(a) or stop - start < 64:
                raise ValueError(f"candidate window outside scene: {case.case_id}")
            clip = a[start:stop]
            losses[case.case_id] = feature_distance(spectral_features(clip), targets[case.case_id])
            hashes[case.case_id] = audio_sha(clip)
        cache[key] = (losses, hashes)
        return losses, hashes

    initial, initial_hash = measure(baseline, train)
    current, current_losses = dict(baseline), dict(initial)
    score = _group_mean(initial, train)
    history: list[dict[str, Any]] = [{"trial": 0, "parameters": dict(baseline),
                                    "train_loss": score, "case_losses": initial,
                                    "pcm_sha256": initial_hash, "decision": "BASELINE"}]
    tested = {tuple(sorted(baseline.items()))}
    step = config.initial_step_fraction
    stop_reason = "ROUND_BUDGET"
    for round_id in range(config.rounds):
        improved = False
        for name in sorted(bounds):
            anchor_params = dict(current)
            choice = None
            for direction in (-1, 1):
                if len(history) >= config.max_trials:
                    break
                trial = dict(anchor_params)
                lo, hi = bounds[name]
                trial[name] = float(np.clip(trial[name] + direction * step * (hi - lo), lo, hi))
                key = tuple(sorted(trial.items()))
                if key in tested:
                    continue
                tested.add(key)
                row = {"trial": len(history), "round": round_id, "parameter": name,
                       "direction": direction, "step_fraction": step, "parameters": trial}
                try:
                    losses, hashes = measure(trial, train)
                    value = _group_mean(losses, train)
                    row.update(train_loss=value, case_losses=losses, pcm_sha256=hashes)
                    if hashes == initial_hash:
                        row["decision"] = "NO_OBSERVABLE_CHANGE_FROM_BASELINE"
                    elif not _no_regression(losses, initial, config.regression_fraction):
                        row["decision"] = "TRAIN_REGRESSION_REJECTED"
                    elif value >= score - config.min_improvement:
                        row["decision"] = "NO_IMPROVEMENT"
                    else:
                        row["decision"] = "IMPROVING_PROPOSAL"
                        if choice is None or value < choice[0]:
                            choice = (value, trial, losses, row)
                except (ValueError, FloatingPointError) as exc:
                    row.update(decision="INVALID_TRIAL_REJECTED", reason=str(exc))
                history.append(row)
            if choice is not None:
                score, current, current_losses, selected_row = choice
                selected_row["decision"] = "TRAIN_ACCEPTED"
                improved = True
            if len(history) >= config.max_trials:
                stop_reason = "TRIAL_BUDGET"
                break
        if len(history) >= config.max_trials:
            break
        if not improved:
            step *= 0.5
            if step < config.min_step_fraction:
                stop_reason = "MIN_STEP_NO_IMPROVEMENT"
                break

    # No validation data has entered the search loop above.
    validation_initial, _ = measure(baseline, validation)
    validation_final = dict(validation_initial)
    proposed = dict(current)
    status = "NO_IMPROVEMENT"
    validation_reason = None
    if current != baseline:
        try:
            validation_final, _ = measure(current, validation)
            accepted = (_no_regression(validation_final, validation_initial, config.regression_fraction)
                        and _group_mean(validation_final, validation)
                        <= _group_mean(validation_initial, validation) + 1e-10)
            status = "RELATIVE_IMPROVEMENT_VALIDATED" if accepted else "VALIDATION_REJECTED_ROLLED_BACK"
        except (ValueError, FloatingPointError) as exc:
            validation_final = {}
            validation_reason = str(exc)
            status = "VALIDATION_INVALID_ROLLED_BACK"
        if status != "RELATIVE_IMPROVEMENT_VALIDATED":
            current = dict(baseline)
    return {
        "schema": SCHEMA, "metric": METRIC, "status": status,
        "trial_pcm_hash_policy": "shape_header_plus_canonical_float64_PCM",
        "baseline_parameters": baseline, "proposed_parameters": proposed,
        "selected_parameters": dict(current),
        "parameter_delta": {k: current[k] - baseline[k] for k in baseline},
        "baseline_train_loss": _group_mean(initial, train),
        "proposed_train_loss": _group_mean(current_losses, train),
        "selected_train_loss": score if current != baseline else _group_mean(initial, train),
        "validation_baseline": validation_initial, "validation_proposed": validation_final,
        "validation_reason": validation_reason, "validation_used_for_search": False,
        "validation_policy": "ONE_SHOT_SOURCE_DISJOINT_NONREGRESSION_AND_NONINCREASING_MEAN",
        "independent_test_status": "NOT_EVALUATED", "stop_reason": stop_reason,
        "trial_count": len(history), "render_calls": render_calls, "history": history,
        "reference_cases": [{"case_id": c.case_id, "scene": c.scene, "source_id": c.source_id,
                             "source_sha256": c.source_sha256, "split": c.split,
                             "candidate_window_s": list(c.candidate_window_s),
                             "comparability_note": c.comparability_note} for c in cases],
        "promotable": False, "human_status": "NOT_EVALUATED",
        "measurement_status": "R3_RELATIVE_SHAPE_ONLY_NOT_OEM_SIMILARITY",
    }
