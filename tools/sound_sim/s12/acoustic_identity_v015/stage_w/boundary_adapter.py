"""Thin stateful bridge to the accepted immutable RuntimePtrAdapter."""

from __future__ import annotations

from collections import deque
import hashlib
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np

_DEMO_ROOT = Path(__file__).resolve().parents[2] / "acoustic_demo"
if str(_DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(_DEMO_ROOT))
from runtime_ptr_adapter import RuntimePtrAdapter  # noqa: E402
from frozen_ptr_contract import (  # noqa: E402
    EXPECTED_RADIATION_PACKAGE_SHA256,
    verify_frozen_radiation_package,
)


class StageWBoundaryAdapter:
    """Apply one frozen adapter per channel while retaining adapter state."""

    EXPECTED_PACKAGE_SHA256 = EXPECTED_RADIATION_PACKAGE_SHA256

    def __init__(self, sample_rate_hz: int = 48000, *, expected_package_sha256: str | None = None) -> None:
        self.sample_rate_hz = int(sample_rate_hz)
        if expected_package_sha256 is not None and expected_package_sha256 != self.EXPECTED_PACKAGE_SHA256:
            raise ValueError("radiation package SHA does not match the frozen Track-S contract")
        receipt = verify_frozen_radiation_package()
        if receipt["radiation_package_sha256"] != self.EXPECTED_PACKAGE_SHA256:
            raise ValueError("radiation package SHA does not match the frozen Track-S contract")
        self.channels = [RuntimePtrAdapter(sample_rate_hz=self.sample_rate_hz) for _ in range(2)]

    def process(self, raw_pcm: np.ndarray) -> np.ndarray:
        values = np.asarray(raw_pcm, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != 2 or not np.all(np.isfinite(values)):
            raise ValueError("frozen PTR input must be finite stereo")
        return np.column_stack(tuple(np.asarray(adapter.process(values[:, index]), dtype=np.float64) for index, adapter in enumerate(self.channels)))

    def provenance(self) -> dict[str, Any]:
        package = self.channels[0].package
        return {
            "adapter": "RuntimePtrAdapter",
            "adapter_path": str(_DEMO_ROOT / "runtime_ptr_adapter.py"),
            "runtime_ptr_adapter_sha256": hashlib.sha256((_DEMO_ROOT / "runtime_ptr_adapter.py").read_bytes()).hexdigest(),
            "radiation_package_sha256": package.sha256,
            "radiation_source_commit": package.source_commit,
            "full_fvm_ptr_network": False,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "s12.stage_w.frozen_ptr_state.v1",
            "channels": [
                {
                    "x0": adapter._x0,
                    "x1": adapter._x1,
                    "upstream": list(adapter._upstream),
                    "downstream": list(adapter._downstream),
                }
                for adapter in self.channels
            ],
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        if snapshot.get("schema_version") != "s12.stage_w.frozen_ptr_state.v1":
            raise ValueError("unsupported frozen PTR snapshot")
        for adapter, state in zip(self.channels, snapshot["channels"]):
            adapter._x0 = float(state["x0"])
            adapter._x1 = float(state["x1"])
            adapter._upstream = deque(float(value) for value in state["upstream"])
            adapter._downstream = deque(float(value) for value in state["downstream"])


class FrozenPtrStereo(StageWBoundaryAdapter):
    """Backward-compatible name for the hash-enforcing Stage-W adapter."""


__all__ = ["FrozenPtrStereo", "StageWBoundaryAdapter"]
