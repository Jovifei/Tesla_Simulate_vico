"""Causal FIR identification for ENSIM4/CFD or measured transfer responses.

The previous S12 teacher reduction used only two scalar ratios.  This module
provides the data-driven path that can replace that reduction once pressure or
impulse-response pairs are supplied.  FIR models are finite, causal and stable
by construction; they remain outside the frozen PTR until explicitly reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

import numpy as np

IDENTIFICATION_SCHEMA = "s12.stage_y.fir_identification.v1"


def _signal(values: np.ndarray, label: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim == 2:
        result = np.mean(result, axis=1)
    if result.ndim != 1 or result.size < 64 or not np.all(np.isfinite(result)):
        raise ValueError(f"{label} must be a finite one-dimensional signal")
    return result


def _design_matrix(source: np.ndarray, tap_count: int) -> np.ndarray:
    rows = source.size - tap_count + 1
    if rows <= 0:
        raise ValueError("signal is shorter than tap_count")
    # X[n] = [x[n], x[n-1], ..., x[n-tap_count+1]].
    windows = np.lib.stride_tricks.sliding_window_view(source, tap_count)
    return np.asarray(windows[:, ::-1], dtype=np.float64)


def _nrmse(reference: np.ndarray, estimate: np.ndarray) -> float:
    error = float(np.sqrt(np.mean(np.square(reference - estimate))))
    scale = float(np.sqrt(np.mean(np.square(reference - np.mean(reference)))))
    return error / max(scale, 1e-12)


@dataclass(frozen=True)
class FirIdentificationResult:
    taps: np.ndarray
    sample_rate_hz: int
    regularization: float
    fit_nrmse: float
    validation_nrmse: float
    input_sha256: str
    output_sha256: str
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        taps = np.asarray(self.taps, dtype=np.float64)
        if taps.ndim != 1 or taps.size < 1 or not np.all(np.isfinite(taps)):
            raise ValueError("FIR taps must be finite and one-dimensional")
        if self.sample_rate_hz <= 0 or self.regularization < 0.0:
            raise ValueError("invalid sample rate or regularization")
        if not np.isfinite(self.fit_nrmse) or not np.isfinite(self.validation_nrmse):
            raise ValueError("identification errors must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": IDENTIFICATION_SCHEMA,
            "model_type": "causal_fir",
            "taps": np.asarray(self.taps, dtype=np.float64).tolist(),
            "tap_count": int(np.asarray(self.taps).size),
            "sample_rate_hz": int(self.sample_rate_hz),
            "regularization": float(self.regularization),
            "fit_nrmse": float(self.fit_nrmse),
            "validation_nrmse": float(self.validation_nrmse),
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "stable_by_construction": True,
            "causal": True,
            "metadata": dict(self.metadata),
            "runtime_candidate": False,
            "frozen_ptr_modified": False,
        }


class CausalFirFilter:
    """Streaming-safe FIR renderer with snapshot/restore."""

    def __init__(self, taps: np.ndarray) -> None:
        self.taps = np.asarray(taps, dtype=np.float64)
        if self.taps.ndim != 1 or self.taps.size < 1 or not np.all(np.isfinite(self.taps)):
            raise ValueError("taps must be finite and one-dimensional")
        self.history = np.zeros(max(0, self.taps.size - 1), dtype=np.float64)

    def process(self, values: np.ndarray) -> np.ndarray:
        source = _signal(np.asarray(values, dtype=np.float64), "FIR input")
        joined = np.concatenate((self.history, source))
        full = np.convolve(joined, self.taps, mode="full")
        start = self.history.size
        output = full[start : start + source.size]
        if self.history.size:
            self.history = joined[-self.history.size :].copy()
        return np.asarray(output, dtype=np.float64)

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "s12.stage_y.causal_fir_state.v1",
            "taps_sha256": hashlib.sha256(np.ascontiguousarray(self.taps).tobytes()).hexdigest(),
            "history": self.history.tolist(),
        }

    def restore(self, payload: Mapping[str, Any]) -> None:
        if payload.get("schema") != "s12.stage_y.causal_fir_state.v1":
            raise ValueError("unsupported FIR snapshot")
        expected = hashlib.sha256(np.ascontiguousarray(self.taps).tobytes()).hexdigest()
        if payload.get("taps_sha256") != expected:
            raise ValueError("FIR topology differs from snapshot")
        history = np.asarray(payload.get("history"), dtype=np.float64)
        if history.shape != self.history.shape or not np.all(np.isfinite(history)):
            raise ValueError("FIR history differs from snapshot")
        self.history = history.copy()


def apply_fir(values: np.ndarray, taps: np.ndarray) -> np.ndarray:
    """One-shot causal FIR output with the same length as the input."""
    source = _signal(values, "FIR input")
    coefficients = np.asarray(taps, dtype=np.float64)
    if coefficients.ndim != 1 or coefficients.size < 1 or not np.all(np.isfinite(coefficients)):
        raise ValueError("FIR taps must be finite and one-dimensional")
    return np.convolve(source, coefficients, mode="full")[: source.size]


def identify_fir_response(
    input_signal: np.ndarray,
    output_signal: np.ndarray,
    sample_rate_hz: int,
    *,
    tap_count: int = 128,
    regularization: float = 1e-5,
    training_fraction: float = 0.75,
    provenance: dict[str, Any] | None = None,
) -> FirIdentificationResult:
    """Fit a causal FIR using ridge least squares and held-out validation."""
    source = _signal(input_signal, "input_signal")
    target = _signal(output_signal, "output_signal")
    length = min(source.size, target.size)
    source = source[:length]
    target = target[:length]
    if not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    if tap_count < 2 or tap_count > min(4096, length // 4):
        raise ValueError("tap_count is outside the supported range")
    if not np.isfinite(regularization) or regularization < 0.0:
        raise ValueError("regularization must be finite and non-negative")
    if not 0.55 <= training_fraction <= 0.90:
        raise ValueError("training_fraction must be in [0.55, 0.90]")

    design = _design_matrix(source, tap_count)
    aligned_target = target[tap_count - 1 :]
    split = int(design.shape[0] * training_fraction)
    if split <= tap_count or design.shape[0] - split < 16:
        raise ValueError("signals are too short for fit and validation")
    train_x, valid_x = design[:split], design[split:]
    train_y, valid_y = aligned_target[:split], aligned_target[split:]
    gram = train_x.T @ train_x
    scale = float(np.trace(gram) / max(tap_count, 1))
    penalty = regularization * max(scale, 1e-12)
    taps = np.linalg.solve(gram + penalty * np.eye(tap_count), train_x.T @ train_y)
    fit = train_x @ taps
    validation = valid_x @ taps
    metadata = {
        "training_samples": int(train_x.shape[0]),
        "validation_samples": int(valid_x.shape[0]),
        "training_fraction": float(training_fraction),
        "source": "pressure/response pair supplied by caller",
        "provenance": dict(provenance or {}),
        "qualification_note": "requires independent response-domain review before Runtime or frozen PTR integration",
    }
    return FirIdentificationResult(
        taps=np.asarray(taps, dtype=np.float64),
        sample_rate_hz=sample_rate_hz,
        regularization=float(regularization),
        fit_nrmse=_nrmse(train_y, fit),
        validation_nrmse=_nrmse(valid_y, validation),
        input_sha256=hashlib.sha256(np.ascontiguousarray(source).tobytes()).hexdigest(),
        output_sha256=hashlib.sha256(np.ascontiguousarray(target).tobytes()).hexdigest(),
        metadata=metadata,
    )


__all__ = [
    "CausalFirFilter",
    "FirIdentificationResult",
    "IDENTIFICATION_SCHEMA",
    "apply_fir",
    "identify_fir_response",
]
