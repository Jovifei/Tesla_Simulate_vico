"""Optional event-domain plus authorized cycle-residual hybrid source.

Engine-Sim-style event timing remains authoritative.  A rights-cleared
cycle-synchronous residual bank may add the timbral detail that a lightweight
physical model cannot reproduce.  The layer is disabled unless a caller
explicitly supplies a bank and gains; it never changes the frozen PTR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .cycle_residual_bank import CycleResidualBank
from .transfer_response_id import CausalFirFilter

HYBRID_SCHEMA = "s12.stage_y.hybrid_source.v1"


def _stereo(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or result.shape[1] != 2 or result.shape[0] == 0 or not np.all(np.isfinite(result)):
        raise ValueError("event source must be finite non-empty stereo")
    return result


def _aligned(values: np.ndarray | float, length: int, label: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim == 0:
        result = np.full(length, float(result), dtype=np.float64)
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{label} must be scalar or sample-aligned")
    return result


@dataclass(frozen=True)
class HybridSourceResult:
    audio: np.ndarray
    event_stem: np.ndarray
    residual_stem: np.ndarray
    diagnostics: dict[str, Any]


class HybridSourceMixer:
    """Streaming-capable hybrid mixer; residual and FIR are explicit options."""

    def __init__(
        self,
        residual_bank: CycleResidualBank | None = None,
        *,
        residual_gain: float = 0.0,
        stereo_width: float = 0.18,
        transfer_taps: np.ndarray | None = None,
        peak_guard: float = 0.98,
    ) -> None:
        if not np.isfinite(residual_gain) or not 0.0 <= residual_gain <= 4.0:
            raise ValueError("residual_gain must be in [0, 4]")
        if not np.isfinite(stereo_width) or not 0.0 <= stereo_width <= 1.0:
            raise ValueError("stereo_width must be in [0, 1]")
        if not np.isfinite(peak_guard) or not 0.1 <= peak_guard < 1.0:
            raise ValueError("peak_guard must be in [0.1, 1.0)")
        self.residual_bank = residual_bank
        self.residual_gain = float(residual_gain)
        self.stereo_width = float(stereo_width)
        self.peak_guard = float(peak_guard)
        self._left_filter = CausalFirFilter(transfer_taps) if transfer_taps is not None else None
        self._right_filter = CausalFirFilter(transfer_taps) if transfer_taps is not None else None
        self.processed_samples = 0

    def process(
        self,
        event_stereo: np.ndarray,
        *,
        phase_rad: np.ndarray,
        rpm: np.ndarray | float,
        load: np.ndarray | float,
        state: str,
        residual_gain_envelope: np.ndarray | float = 1.0,
    ) -> HybridSourceResult:
        event = _stereo(event_stereo)
        length = event.shape[0]
        phase = _aligned(phase_rad, length, "phase_rad")
        rpm_values = _aligned(rpm, length, "rpm")
        load_values = np.clip(_aligned(load, length, "load"), 0.0, 1.0)
        gain_envelope = np.clip(_aligned(residual_gain_envelope, length, "residual_gain_envelope"), 0.0, 2.0)
        if np.any(rpm_values <= 0.0):
            raise ValueError("RPM must be positive")

        residual_stereo = np.zeros_like(event)
        residual_enabled = self.residual_bank is not None and self.residual_gain > 0.0
        if residual_enabled:
            mono = self.residual_bank.render(phase, rpm_values, load_values, state, gain=1.0)
            # Residual detail should grow with combustion load but stay audible
            # at idle.  A one-sample phase-derived decorrelation avoids dual-mono
            # collapse without inventing a random spatial field.
            state_gain = 0.35 + 0.65 * np.sqrt(load_values)
            mono = mono * gain_envelope * state_gain * self.residual_gain
            delayed = np.concatenate(([mono[0]], mono[:-1]))
            residual_stereo[:, 0] = (1.0 - self.stereo_width) * mono + self.stereo_width * delayed
            residual_stereo[:, 1] = (1.0 - self.stereo_width) * mono - self.stereo_width * delayed

        mixed = event + residual_stereo
        transfer_applied = self._left_filter is not None and self._right_filter is not None
        if transfer_applied:
            mixed = np.column_stack((self._left_filter.process(mixed[:, 0]), self._right_filter.process(mixed[:, 1])))
        pre_guard_peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
        guard_gain = 1.0 if pre_guard_peak <= self.peak_guard else self.peak_guard / max(pre_guard_peak, 1e-12)
        audio = mixed * guard_gain
        self.processed_samples += length
        diagnostics = {
            "schema": HYBRID_SCHEMA,
            "residual_enabled": residual_enabled,
            "residual_gain": self.residual_gain,
            "residual_bank_records": len(self.residual_bank.records) if self.residual_bank is not None else 0,
            "transfer_response_applied": transfer_applied,
            "pre_guard_peak": pre_guard_peak,
            "guard_gain": guard_gain,
            "output_peak": float(np.max(np.abs(audio))),
            "clipping_samples": int(np.count_nonzero(np.abs(audio) >= 1.0)),
            "processed_samples": self.processed_samples,
            "frozen_ptr_modified": False,
            "runtime_default_enabled": False,
            "scope": "authorized residual sweetener around an event-domain source; not OEM reproduction",
        }
        return HybridSourceResult(audio, event.copy(), residual_stereo, diagnostics)

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "s12.stage_y.hybrid_source_state.v1",
            "processed_samples": self.processed_samples,
            "left_filter": self._left_filter.snapshot() if self._left_filter is not None else None,
            "right_filter": self._right_filter.snapshot() if self._right_filter is not None else None,
        }

    def restore(self, payload: dict[str, Any]) -> None:
        if payload.get("schema") != "s12.stage_y.hybrid_source_state.v1":
            raise ValueError("unsupported hybrid source snapshot")
        count = payload.get("processed_samples")
        if type(count) is not int or count < 0:
            raise ValueError("invalid processed_samples")
        if (self._left_filter is None) != (payload.get("left_filter") is None) or (self._right_filter is None) != (payload.get("right_filter") is None):
            raise ValueError("hybrid filter topology differs from snapshot")
        if self._left_filter is not None:
            self._left_filter.restore(payload["left_filter"])
            self._right_filter.restore(payload["right_filter"])
        self.processed_samples = count


__all__ = ["HYBRID_SCHEMA", "HybridSourceMixer", "HybridSourceResult"]
