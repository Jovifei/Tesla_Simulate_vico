"""Rights-gated cycle-synchronous residual extraction and rendering.

This is the clean-room infrastructure needed to borrow the useful method from
sample/cycle based engine-sound systems without embedding unlicensed media.
A bank can be created only when the caller supplies a cleared rights status.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Sequence

import numpy as np

BANK_SCHEMA = "s12.stage_y.cycle_residual_bank.v1"
CLEARED_RIGHTS = {"CLEARED", "OWNER_AUTHORIZED", "PROJECT_OWNED", "CC0", "CC_BY_COMPATIBLE"}


def _mono(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float64)
    if values.ndim == 2:
        values = np.mean(values, axis=1)
    if values.ndim != 1 or values.size < 64 or not np.all(np.isfinite(values)):
        raise ValueError("audio must be a finite mono/stereo array")
    return values


def _vector(values: np.ndarray, length: int, label: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{label} must be a finite sample-aligned vector")
    return result


def _phase_resample(values: np.ndarray, phase: np.ndarray, phase_samples: int) -> np.ndarray:
    relative = phase - phase[0]
    span = float(relative[-1])
    if span <= 0.0:
        raise ValueError("cycle phase must increase")
    normalized = relative / span
    target = np.linspace(0.0, 1.0, phase_samples, endpoint=False)
    return np.interp(target, normalized, values)


def _remove_low_orders(cycle: np.ndarray, order_count: int) -> np.ndarray:
    spectrum = np.fft.rfft(np.asarray(cycle, dtype=np.float64))
    reconstructed = np.zeros_like(spectrum)
    keep = min(order_count + 1, spectrum.size)
    reconstructed[:keep] = spectrum[:keep]
    low = np.fft.irfft(reconstructed, n=cycle.size)
    residual = cycle - low
    residual -= float(np.mean(residual))
    peak = float(np.max(np.abs(residual))) if residual.size else 0.0
    if peak > 0.999:
        residual = residual * (0.999 / peak)
    return residual


@dataclass(frozen=True)
class CycleResidualRecord:
    rpm: float
    load: float
    state: str
    waveform: np.ndarray
    source_sha256: str
    source_cycle_index: int
    rights_status: str

    def __post_init__(self) -> None:
        waveform = np.asarray(self.waveform, dtype=np.float64)
        if waveform.ndim != 1 or waveform.size < 32 or not np.all(np.isfinite(waveform)):
            raise ValueError("cycle residual waveform must be finite and one-dimensional")
        if not np.isfinite(self.rpm) or self.rpm <= 0.0 or not np.isfinite(self.load):
            raise ValueError("cycle residual RPM/load must be finite")
        if not self.state:
            raise ValueError("cycle residual state must be non-empty")
        if len(self.source_sha256) != 64:
            raise ValueError("cycle residual source SHA-256 is required")
        if self.rights_status not in CLEARED_RIGHTS:
            raise ValueError("cycle residual record requires cleared rights")

    def to_metadata(self) -> dict[str, Any]:
        return {
            "rpm": float(self.rpm),
            "load": float(self.load),
            "state": self.state,
            "phase_samples": int(self.waveform.size),
            "waveform_sha256": hashlib.sha256(np.ascontiguousarray(self.waveform).tobytes()).hexdigest(),
            "source_sha256": self.source_sha256,
            "source_cycle_index": int(self.source_cycle_index),
            "rights_status": self.rights_status,
        }


class CycleResidualBank:
    """Nearest-state, interpolated cycle-residual renderer."""

    def __init__(self, records: Sequence[CycleResidualRecord], *, phase_samples: int | None = None) -> None:
        self.records = tuple(records)
        if not self.records:
            raise ValueError("cycle residual bank requires at least one record")
        inferred = int(self.records[0].waveform.size)
        self.phase_samples = inferred if phase_samples is None else int(phase_samples)
        if self.phase_samples < 32 or any(record.waveform.size != self.phase_samples for record in self.records):
            raise ValueError("all residual records must use the same phase grid")
        self.states = tuple(sorted({record.state for record in self.records}))

    def _candidates(self, state: str) -> tuple[CycleResidualRecord, ...]:
        exact = tuple(record for record in self.records if record.state == state)
        return exact or self.records

    def select_pair(self, rpm: float, load: float, state: str) -> tuple[CycleResidualRecord, CycleResidualRecord, float]:
        """Return the two nearest records and a bounded interpolation weight."""
        candidates = sorted(
            self._candidates(state),
            key=lambda record: abs(record.rpm - rpm) / max(record.rpm, rpm, 1.0) + 0.6 * abs(record.load - load),
        )
        first = candidates[0]
        second = candidates[1] if len(candidates) > 1 else first
        first_distance = abs(first.rpm - rpm) / max(first.rpm, rpm, 1.0) + 0.6 * abs(first.load - load)
        second_distance = abs(second.rpm - rpm) / max(second.rpm, rpm, 1.0) + 0.6 * abs(second.load - load)
        total = first_distance + second_distance
        weight_second = 0.0 if total <= 1e-12 else float(np.clip(first_distance / total, 0.0, 1.0))
        return first, second, weight_second

    def render(
        self,
        phase_rad: np.ndarray,
        rpm: np.ndarray | float,
        load: np.ndarray | float,
        state: str,
        *,
        gain: float = 1.0,
    ) -> np.ndarray:
        """Render a mono residual locked to the supplied continuous phase."""
        phase = np.asarray(phase_rad, dtype=np.float64)
        if phase.ndim != 1 or phase.size == 0 or not np.all(np.isfinite(phase)):
            raise ValueError("phase_rad must be a finite one-dimensional vector")
        rpm_value = float(np.median(np.asarray(rpm, dtype=np.float64)))
        load_value = float(np.median(np.asarray(load, dtype=np.float64)))
        if not np.isfinite(rpm_value) or rpm_value <= 0.0 or not np.isfinite(load_value):
            raise ValueError("render RPM/load must be finite")
        if not np.isfinite(gain) or abs(float(gain)) > 8.0:
            raise ValueError("gain must be finite and bounded")
        first, second, weight_second = self.select_pair(rpm_value, load_value, state)
        waveform = (1.0 - weight_second) * first.waveform + weight_second * second.waveform
        position = np.mod(phase, 2.0 * np.pi) / (2.0 * np.pi) * self.phase_samples
        left = np.floor(position).astype(np.int64) % self.phase_samples
        fraction = position - np.floor(position)
        right = (left + 1) % self.phase_samples
        return float(gain) * ((1.0 - fraction) * waveform[left] + fraction * waveform[right])

    def to_manifest(self) -> dict[str, Any]:
        return {
            "schema": BANK_SCHEMA,
            "record_count": len(self.records),
            "phase_samples": self.phase_samples,
            "states": list(self.states),
            "records": [record.to_metadata() for record in self.records],
            "raw_audio_embedded": False,
            "runtime_default_enabled": False,
            "scope": "authorized derived residuals only; not an OEM reproduction claim",
        }


def build_cycle_residual_bank(
    audio: np.ndarray,
    *,
    phase_rad: np.ndarray,
    rpm: np.ndarray,
    load: np.ndarray,
    state_labels: Sequence[str] | str,
    source_sha256: str,
    rights_status: str,
    phase_samples: int = 512,
    remove_low_order_count: int = 8,
    minimum_cycle_samples: int = 48,
    maximum_records: int = 256,
) -> CycleResidualBank:
    """Segment sample-aligned audio by crank/rotor cycles and derive residuals."""
    if rights_status not in CLEARED_RIGHTS:
        raise PermissionError("authorized rights status is required before extracting a residual bank")
    signal = _mono(audio)
    phase = _vector(phase_rad, signal.size, "phase_rad")
    rpm_values = _vector(rpm, signal.size, "rpm")
    load_values = _vector(load, signal.size, "load")
    if np.any(rpm_values <= 0.0) or np.any(np.diff(phase) < 0.0):
        raise ValueError("phase must be unwrapped/non-decreasing and RPM must be positive")
    if phase_samples < 32 or remove_low_order_count < 0 or minimum_cycle_samples < 16 or maximum_records < 1:
        raise ValueError("invalid residual extraction settings")
    if isinstance(state_labels, str):
        labels = np.full(signal.size, state_labels, dtype=object)
    else:
        labels = np.asarray(tuple(state_labels), dtype=object)
        if labels.shape != (signal.size,) or any(not str(value) for value in labels):
            raise ValueError("state_labels must be one label or a sample-aligned sequence")

    cycle_number = np.floor((phase - phase[0]) / (2.0 * np.pi)).astype(np.int64)
    boundaries = np.flatnonzero(np.diff(cycle_number) > 0) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [signal.size]))
    records: list[CycleResidualRecord] = []
    for cycle_index, (start, end) in enumerate(zip(starts, ends)):
        if len(records) >= maximum_records:
            break
        if end - start < minimum_cycle_samples or phase[end - 1] - phase[start] < 1.6 * np.pi:
            continue
        cycle = _phase_resample(signal[start:end], phase[start:end], phase_samples)
        residual = _remove_low_orders(cycle, remove_low_order_count)
        state_values, counts = np.unique(labels[start:end], return_counts=True)
        state = str(state_values[int(np.argmax(counts))])
        records.append(
            CycleResidualRecord(
                rpm=float(np.median(rpm_values[start:end])),
                load=float(np.median(load_values[start:end])),
                state=state,
                waveform=residual,
                source_sha256=source_sha256,
                source_cycle_index=cycle_index,
                rights_status=rights_status,
            )
        )
    if not records:
        raise ValueError("no complete cycles satisfied the residual extraction contract")
    return CycleResidualBank(records, phase_samples=phase_samples)


__all__ = [
    "BANK_SCHEMA",
    "CLEARED_RIGHTS",
    "CycleResidualBank",
    "CycleResidualRecord",
    "build_cycle_residual_bank",
]
