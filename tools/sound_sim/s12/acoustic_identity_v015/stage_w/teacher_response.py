"""Transparent stateful reduction of the external ENSIM4 teacher observation."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

# `ensim4_teacher_response_receipt.json`: CFD-on / CFD-off observations.
_TEACHER_GAIN = 0.14841886404915552 / 0.07386597826868908
_TEACHER_SMOOTHING = 175.61687399694765 / 317.3450346424205


class ReducedCfdTeacherResponse:
    """A metric-derived, causal two-channel reduction; never embeds teacher audio."""

    def __init__(self) -> None:
        self._state = np.zeros(2, dtype=np.float64)

    def process(self, stereo: np.ndarray) -> np.ndarray:
        values = np.asarray(stereo, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != 2 or not np.all(np.isfinite(values)):
            raise ValueError("teacher response input must be finite stereo")
        output = np.empty_like(values)
        for index, value in enumerate(values):
            self._state += _TEACHER_SMOOTHING * (value - self._state)
            output[index] = _TEACHER_GAIN * self._state
        return output

    def snapshot(self) -> dict[str, Any]:
        return {"schema_version": "s12.stage_w.reduced_cfd_teacher_state.v1", "state": self._state.copy()}

    def restore(self, payload: Mapping[str, Any]) -> None:
        if payload.get("schema_version") != "s12.stage_w.reduced_cfd_teacher_state.v1":
            raise ValueError("unsupported teacher response snapshot")
        self._state = np.asarray(payload["state"], dtype=np.float64).copy()

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "TEACHER_METRIC_REDUCTION_ONLY",
            "source_receipt": "ensim4_teacher_response_receipt.json",
            "gain_from_cfd_on_off_rms": _TEACHER_GAIN,
            "smoothing_from_cfd_on_off_centroid_ratio": _TEACHER_SMOOTHING,
            "external_audio_embedded": False,
            "runtime_candidate": False,
        }


__all__ = ["ReducedCfdTeacherResponse"]
