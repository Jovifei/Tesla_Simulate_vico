"""Versioned real MoSQITo calls for isolated fixture execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def _scalar(value: Any) -> float | None:
    """Reduce a MoSQITo scalar/vector/cell-like result to a documented mean."""

    if isinstance(value, tuple):
        value = value[0]
    array = np.asarray(value, dtype=object)
    flattened: list[float] = []
    for item in array.ravel():
        try:
            flattened.extend(np.asarray(item, dtype=np.float64).ravel().tolist())
        except (TypeError, ValueError):
            continue
    finite = [item for item in flattened if np.isfinite(item)]
    return float(np.mean(finite)) if finite else None


def _import_metrics() -> tuple[str, Any]:
    try:
        import mosqito
        from mosqito import sq_metrics
    except ImportError as error:  # pragma: no cover - exercised by external venv evidence
        raise RuntimeError(f"MoSQITo import unavailable: {error}") from error
    return str(mosqito.__version__), sq_metrics


def compute_mosqito_metrics(signal: np.ndarray, sample_rate_hz: int) -> dict[str, object]:
    """Invoke functions exposed by MoSQITo 1.2.1; no internal proxy fallback."""

    version, metrics = _import_metrics()
    value = np.asarray(signal, dtype=np.float64)
    if value.ndim != 1 or value.size < sample_rate_hz:
        raise ValueError("MoSQITo input must be a finite mono signal of at least one second")
    if not np.isfinite(value).all() or sample_rate_hz <= 0:
        raise ValueError("MoSQITo input must be finite with a positive sample rate")
    loudness, loudness_specific, loudness_bark = metrics.loudness_zwst(value, sample_rate_hz, field_type="free")
    sharpness = metrics.sharpness_din_st(value, sample_rate_hz, weighting="din", field_type="free")
    roughness, roughness_specific, roughness_bark, roughness_time = metrics.roughness_dw(value, sample_rate_hz, overlap=0.5)
    tnr_global, tnr, tnr_prominent, tnr_frequency = metrics.tnr_ecma_st(value, sample_rate_hz, prominence=True)
    prominence_global, prominence, prominence_flags, prominence_frequency = metrics.pr_ecma_st(value, sample_rate_hz, prominence=True)
    return {
        "tool": "MoSQITo",
        "mosqito_version": version,
        "functions": {
            "loudness": "loudness_zwst(signal, fs, field_type='free')",
            "sharpness": "sharpness_din_st(signal, fs, weighting='din', field_type='free')",
            "roughness": "roughness_dw(signal, fs, overlap=0.5)",
            "tone_to_noise_ratio": "tnr_ecma_st(signal, fs, prominence=True)",
            "prominence_ratio": "pr_ecma_st(signal, fs, prominence=True)",
        },
        "parameters": {"sample_rate_hz": sample_rate_hz, "field_type": "free", "sharpness_weighting": "din", "roughness_overlap": 0.5},
        "input_calibration": "digital-domain relative input; full-scale-to-Pascal calibration was not supplied; no absolute SPL claim",
        "results": {
            "loudness_sone": _scalar(loudness),
            "sharpness_acum": _scalar(sharpness),
            "roughness_asper": _scalar(roughness),
            "tone_to_noise_ratio_db": _scalar(tnr),
            "tone_to_noise_frequency_hz": _scalar(tnr_frequency),
            "tone_to_noise_prominent": bool(np.any(tnr_prominent)),
            "prominence_ratio_db": _scalar(prominence),
            "prominence_frequency_hz": _scalar(prominence_frequency),
            "prominence_present": bool(np.any(prominence_flags)),
            "global_tnr_db": _scalar(tnr_global),
            "global_prominence_ratio_db": _scalar(prominence_global),
            "loudness_specific_bark_available": _scalar(loudness_specific) is not None,
            "loudness_bark_axis_available": _scalar(loudness_bark) is not None,
            "roughness_specific_bark_available": _scalar(roughness_specific) is not None,
            "roughness_time_available": _scalar(roughness_time) is not None,
        },
    }


def fixture_suite() -> dict[str, object]:
    """Run the direction fixtures in the invoking isolated MoSQITo environment."""

    sample_rate_hz = 48_000
    time = np.arange(sample_rate_hz * 2, dtype=np.float64) / sample_rate_hz
    base = 0.02 * np.sin(2.0 * np.pi * 1_000.0 * time)
    fixtures = {
        "base": base,
        "gain": 2.0 * base,
        "high_frequency_boost": base + 0.08 * np.sin(2.0 * np.pi * 7_000.0 * time),
        "fast_am": (1.0 + 0.7 * np.sin(2.0 * np.pi * 70.0 * time)) * base,
        "tonality_noise_floor": 0.01 * np.random.default_rng(17).normal(size=time.size),
        "prominent_tone": 0.01 * np.random.default_rng(17).normal(size=time.size) + 0.15 * np.sin(2.0 * np.pi * 1_000.0 * time),
    }
    measured = {name: compute_mosqito_metrics(signal, sample_rate_hz) for name, signal in fixtures.items()}
    base_metrics = measured["base"]["results"]
    noise_tnr = measured["tonality_noise_floor"]["results"]["tone_to_noise_ratio_db"]
    prominent_tnr = measured["prominent_tone"]["results"]["tone_to_noise_ratio_db"]
    validation = {
        "gain_increases_loudness": measured["gain"]["results"]["loudness_sone"] > base_metrics["loudness_sone"],
        "high_frequency_increases_sharpness": measured["high_frequency_boost"]["results"]["sharpness_acum"] > base_metrics["sharpness_acum"],
        "fast_am_increases_roughness": measured["fast_am"]["results"]["roughness_asper"] > base_metrics["roughness_asper"],
        "prominent_tone_reports_tonality": prominent_tnr is not None and (noise_tnr is None or prominent_tnr > noise_tnr),
    }
    validation["passed"] = all(validation.values())
    return {
        "schema_version": "s12-stage-n-mosqito-validation-1",
        "status": "VALIDATED" if validation["passed"] else "EXECUTED_ON_FIXTURE",
        "fixtures": measured,
        "validation": validation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Stage-N MoSQITo fixture evidence in its isolated interpreter.")
    parser.add_argument("--fixture", action="store_true", help="run the fixed direction fixture suite")
    parser.add_argument("--output", type=Path, required=True, help="JSON receipt path")
    arguments = parser.parse_args(argv)
    if not arguments.fixture:
        parser.error("only --fixture is supported by this standalone real-call runner")
    receipt = fixture_suite()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
