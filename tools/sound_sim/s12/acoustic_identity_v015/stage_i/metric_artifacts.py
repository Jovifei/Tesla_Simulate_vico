"""Deterministic, headless Stage-I metric review artifacts."""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
from pathlib import Path

import numpy as np

from ..acoustic_analysis.engine_identity_metrics import compute_order_map
from ..acoustic_analysis.plotting import _pyplot, write_order_map, write_spectrogram
from ..contracts import SourceRender, VehicleStateTrace


_CANDIDATE_IDS = (
    "I6-A Balanced",
    "I6-B Whine Forward",
    "I6-C Softer Mechanical",
)
_STATE_RATIO_KEYS = (
    "blower_to_exhaust_ratio_idle_db",
    "blower_to_exhaust_ratio_acceleration_db",
    "blower_to_exhaust_ratio_full_pull_db",
)
_TRANSIENT_KEYS = (
    "boost_attack_10_90_s",
    "boost_release_90_10_s",
    "bypass_decay_90_10_s",
)
_CANDIDATE_REQUIRED = _STATE_RATIO_KEYS + _TRANSIENT_KEYS + (
    "sideband_to_main_ratio",
    "upper_band_short_time_peak",
)


def write_stage_i_metric_artifacts(
    output_directory: str | Path,
    candidate_pcm: Mapping[str, np.ndarray],
    candidate_renders: Mapping[str, SourceRender],
    trace: VehicleStateTrace,
    candidate_metrics: Mapping[str, Mapping[str, object]],
    stage_h_baseline_metrics: Mapping[str, object],
    sample_rate_hz: int = 48000,
) -> dict[str, Path]:
    """Write the four fixed review PNGs and canonical comparison JSON.

    Validation is completed before the output directory is created.  The
    representative spectrogram and order map use the final PCM for the
    Balanced candidate, while the other two figures compare all three
    candidates with the explicit Stage-H baseline metrics.
    """
    output = Path(output_directory)
    payload = _validate_and_build_payload(
        candidate_pcm,
        candidate_renders,
        trace,
        candidate_metrics,
        stage_h_baseline_metrics,
        sample_rate_hz,
    )
    representative = np.asarray(candidate_pcm[_CANDIDATE_IDS[0]], dtype=np.float64)
    normalized_baseline = payload["stage_h_baseline"]
    assert isinstance(normalized_baseline, Mapping)
    order_map = compute_order_map(representative, trace, sample_rate_hz=sample_rate_hz)

    paths = {
        "order_map": output / "order_map.png",
        "spectrogram": output / "spectrogram.png",
        "state_ratio_map": output / "state_ratio_map.png",
        "transient_response": output / "transient_response.png",
        "candidate_comparison_metrics": output / "candidate_comparison_metrics.json",
    }
    write_order_map(paths["order_map"], order_map)
    write_spectrogram(paths["spectrogram"], representative, sample_rate_hz)
    _write_grouped_metric_plot(
        paths["state_ratio_map"],
        "Stage I state-local blower/exhaust ratios",
        ("idle", "acceleration", "full pull"),
        _STATE_RATIO_KEYS,
        "dB",
        candidate_metrics,
        normalized_baseline,
    )
    _write_grouped_metric_plot(
        paths["transient_response"],
        "Stage I observed whine transient response",
        ("attack 10-90", "release 90-10", "bypass 90-10"),
        _TRANSIENT_KEYS,
        "seconds",
        candidate_metrics,
        normalized_baseline,
    )
    paths["candidate_comparison_metrics"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if paths["candidate_comparison_metrics"].stat().st_size == 0:
        raise RuntimeError("failed to write candidate comparison metrics")
    return paths


def _validate_and_build_payload(
    candidate_pcm: Mapping[str, np.ndarray],
    candidate_renders: Mapping[str, SourceRender],
    trace: VehicleStateTrace,
    candidate_metrics: Mapping[str, Mapping[str, object]],
    baseline: Mapping[str, object],
    sample_rate_hz: int,
) -> dict[str, object]:
    if not isinstance(sample_rate_hz, int) or sample_rate_hz != 48000:
        raise ValueError("Stage-I metric artifacts require 48 kHz")
    required_ids = set(_CANDIDATE_IDS)
    if set(candidate_pcm) != required_ids or set(candidate_renders) != required_ids or set(candidate_metrics) != required_ids:
        raise ValueError("PCM, SourceRender and metric candidate IDs must exactly match Stage-I A/B/C IDs")
    trace.validate()
    normalized_baseline = dict(baseline)
    for key in _STATE_RATIO_KEYS:
        _finite_number(baseline, key, "Stage-H baseline metrics")
    for key in _TRANSIENT_KEYS:
        if key not in baseline or baseline[key] is None:
            normalized_baseline[key] = None
        else:
            normalized_baseline[key] = _finite_number(baseline, key, "Stage-H baseline metrics")

    candidates: dict[str, object] = {}
    expected_count: int | None = None
    for candidate_id in _CANDIDATE_IDS:
        pcm = np.asarray(candidate_pcm[candidate_id], dtype=np.float64)
        if pcm.ndim != 2 or pcm.shape[1:] != (2,) or pcm.shape[0] == 0 or not np.all(np.isfinite(pcm)):
            raise ValueError(f"final PCM for {candidate_id!r} must be finite nonempty stereo")
        if expected_count is None:
            expected_count = pcm.shape[0]
        elif pcm.shape[0] != expected_count:
            raise ValueError("all final candidate PCM arrays must have equal lengths")
        render = candidate_renders[candidate_id].validate()
        if render.pressure.shape[0] != pcm.shape[0]:
            raise ValueError(f"SourceRender and final PCM length differ for {candidate_id!r}")
        metrics = candidate_metrics[candidate_id]
        for key in _CANDIDATE_REQUIRED:
            _finite_number(metrics, key, f"metrics for {candidate_id}")
        _json_finite(metrics, f"metrics for {candidate_id}")
        candidates[candidate_id] = {
            "metrics": dict(metrics),
            "final_pcm_energy": float(np.sum(np.square(pcm))),
            "source_stem_energy": {
                "blower": _stem_energy(render, "blower"),
                "exhaust": _stem_energy(render, "exhaust"),
            },
        }
    assert expected_count is not None
    required_duration = (expected_count - 1) / sample_rate_hz
    available_duration = float(trace.time_s[-1] - trace.time_s[0])
    if available_duration + 1.0 / sample_rate_hz < required_duration:
        raise ValueError("VehicleStateTrace does not cover the final PCM duration")
    _json_finite(normalized_baseline, "Stage-H baseline metrics")
    return {
        "schema_version": "s12-stage-i-metric-artifacts-1",
        "scope": "synthetic / uncalibrated / Hellcat-inspired / not OEM reproduction",
        "sample_rate_hz": sample_rate_hz,
        "representative_candidate_id": _CANDIDATE_IDS[0],
        "stage_h_baseline": normalized_baseline,
        "candidates": candidates,
    }


def _write_grouped_metric_plot(
    path: Path,
    title: str,
    labels: tuple[str, ...],
    keys: tuple[str, ...],
    ylabel: str,
    candidate_metrics: Mapping[str, Mapping[str, object]],
    baseline: Mapping[str, object],
) -> None:
    pyplot = _pyplot()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = pyplot.subplots(figsize=(8, 4), dpi=120)
    series = (("Stage H v5", baseline),) + tuple((candidate_id, candidate_metrics[candidate_id]) for candidate_id in _CANDIDATE_IDS)
    positions = np.arange(len(keys), dtype=np.float64)
    width = 0.18
    for index, (name, metrics) in enumerate(series):
        values = [
            float("nan")
            if name == "Stage H v5" and key in _TRANSIENT_KEYS and metrics.get(key) is None
            else _finite_number(metrics, key, name)
            for key in keys
        ]
        axis.bar(positions + (index - 1.5) * width, values, width=width, label=name)
    axis.set_xticks(positions, labels)
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.legend(fontsize=7)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, format="png", metadata={"Software": "S12 acoustic identity v0.15"})
    pyplot.close(figure)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"failed to write nonempty PNG: {path}")


def _finite_number(source: Mapping[str, object], key: str, label: str) -> float:
    if key not in source:
        raise ValueError(f"{label} missing required field {key!r}")
    value = source[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} field {key!r} must be finite")
    return float(value)


def _json_finite(value: object, label: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} must use string keys")
            _json_finite(child, label)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _json_finite(child, label)
    elif isinstance(value, bool) or value is None or isinstance(value, str):
        return
    elif isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError(f"{label} must not contain NaN or infinity")
    else:
        raise ValueError(f"{label} contains a non-JSON value of type {type(value).__name__}")


def _stem_energy(render: SourceRender, stem_name: str) -> float:
    stem = render.stems.get(stem_name)
    return 0.0 if stem is None else float(np.sum(np.square(np.asarray(stem, dtype=np.float64))))


__all__ = ("write_stage_i_metric_artifacts",)
