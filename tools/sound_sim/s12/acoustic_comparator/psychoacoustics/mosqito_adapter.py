"""Versioned real MoSQITo calls for isolated fixture execution."""
from __future__ import annotations

import argparse
import hashlib
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


def analyze_project_inputs(input_root: Path, *, progress: Any | None = None) -> dict[str, object]:
    """Run real MoSQITo functions on all hash-bound Stage-N project inputs.

    The input manifest is produced by the Stage-N MATLAB-input preparation
    step. This function rechecks every MAT SHA before any measurement and
    reports candidate metrics only: an external-reference residual remains
    unavailable without a lawful reference waveform and RPM/state metadata.
    """

    try:
        from scipy.io import loadmat
    except ImportError as exc:  # pragma: no cover - exercised by isolated runtime
        raise RuntimeError("SciPy is required to read Stage-N MATLAB project inputs.") from exc
    manifest_path = input_root / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records")
    if manifest.get("status") != "PREPARED_NOT_EXECUTED_IN_MATLAB" or not isinstance(records, list) or len(records) != 8:
        raise ValueError("expected eight hash-bound Stage-N MATLAB project inputs")
    vehicles: dict[str, object] = {}
    for index, record in enumerate(sorted(records, key=lambda item: str(item["vehicle_id"])), start=1):
        if not isinstance(record, dict):
            raise ValueError("MATLAB input manifest record must be an object")
        vehicle_id = str(record["vehicle_id"])
        mat_path = input_root / str(record["mat_file"])
        actual_sha = hashlib.sha256(mat_path.read_bytes()).hexdigest()
        if actual_sha != record["mat_sha256"]:
            raise ValueError(f"MATLAB input SHA mismatch: {vehicle_id}")
        values = loadmat(mat_path, variable_names=("signal_pcm24", "sample_rate_hz", "rpm", "state_trace"))
        pcm24 = np.asarray(values.get("signal_pcm24"))
        rpm = np.asarray(values.get("rpm"), dtype=np.float64).reshape(-1)
        state_trace = np.asarray(values.get("state_trace")).reshape(-1)
        sample_rate_hz = int(np.asarray(values.get("sample_rate_hz"), dtype=np.float64).reshape(-1)[0])
        if (
            sample_rate_hz != 48_000
            or pcm24.ndim != 2
            or pcm24.shape[1] != 2
            or pcm24.shape[0] != int(record["frame_count"])
            or rpm.size != pcm24.shape[0]
            or state_trace.size != pcm24.shape[0]
            or not np.issubdtype(pcm24.dtype, np.integer)
            or np.any(pcm24 < -(1 << 23))
            or np.any(pcm24 > (1 << 23) - 1)
            or not np.all(np.isfinite(rpm))
            or np.any(rpm <= 0)
        ):
            raise ValueError(f"MATLAB input contract failed: {vehicle_id}")
        signal = np.mean(pcm24.astype(np.float64), axis=1) / float(1 << 23)
        del pcm24
        if progress is not None:
            progress(index, len(records), vehicle_id)
        metrics = compute_mosqito_metrics(signal, sample_rate_hz)
        del signal
        vehicles[vehicle_id] = {
            "scenario": str(record["scenario"]),
            "candidate_sha256": str(record["candidate_sha256"]),
            "trace_sha256": str(record["trace_sha256"]),
            "mat_file": str(record["mat_file"]),
            "mat_sha256": actual_sha,
            "channel_policy": str(record["channel_policy"]),
            "metrics": metrics,
            "reference_comparison": "REFERENCE_RPM_UNAVAILABLE / ORDER_COMPARISON_NOT_QUALIFIED",
        }
    return {
        "schema_version": "s12-stage-n-mosqito-project-analysis-1",
        "status": "EXECUTED_ON_PROJECT_DATA",
        "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "input_calibration": "digital-domain relative; no full-scale-to-Pascal calibration or absolute SPL claim",
        "vehicle_count": len(vehicles),
        "vehicles": vehicles,
        "limitation": "candidate metrics only; no lawful external reference waveform contains matching RPM/state metadata",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Stage-N MoSQITo fixture evidence in its isolated interpreter.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", action="store_true", help="run the fixed direction fixture suite")
    mode.add_argument("--project-input-root", type=Path, help="run all hash-bound current S12 candidate inputs")
    parser.add_argument("--output", type=Path, required=True, help="JSON receipt path")
    arguments = parser.parse_args(argv)
    if arguments.output.exists():
        raise FileExistsError(f"refusing to overwrite MoSQITo receipt: {arguments.output}")
    if arguments.fixture:
        receipt = fixture_suite()
    else:
        receipt = analyze_project_inputs(
            arguments.project_input_root,
            progress=lambda index, total, vehicle: print(f"[{index}/{total}] MoSQITo {vehicle}", flush=True),
        )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
