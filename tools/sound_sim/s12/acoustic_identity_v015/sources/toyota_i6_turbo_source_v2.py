"""Reference-balanced Supra source overlay derived from three real recordings.

The recordings provide relative, unsynchronized spectral cues only.  This
variant keeps the existing 2JZ source and shared layers intact, increasing
only the source-local mid-band edge and faint compressor band.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from .toyota_i6_turbo_source import render_supra_jza80


SUPRA_V2_EDGE_SCALE = 1.4
SUPRA_V2_HIBAND_SCALE = 3.4
SUPRA_V2_REFERENCE_BASIS = "supra_jza80_multi_reference_targets_v3"


def render_supra_jza80_v2(
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48_000,
    *,
    edge_scale: float = SUPRA_V2_EDGE_SCALE,
    hiband_scale: float = SUPRA_V2_HIBAND_SCALE,
) -> SourceRender:
    """Render a fixed source-only overlay before the shared realism layers."""
    for name, value in (("edge_scale", edge_scale), ("hiband_scale", hiband_scale)):
        if isinstance(value, bool) or not np.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"{name} must be finite and positive")
    base = render_supra_jza80(trace, sample_rate_hz)
    stems = {name: np.asarray(value, dtype=np.float64).copy() for name, value in base.stems.items()}
    deltas: list[np.ndarray] = []
    for name, scale in (("edge", float(edge_scale)), ("hiband", float(hiband_scale))):
        if name not in stems:
            raise ValueError(f"Supra source stem missing: {name}")
        delta = (float(scale) - 1.0) * stems[name]
        stems[name] *= float(scale)
        deltas.append(delta)
    diagnostics = dict(base.diagnostics)
    diagnostics.update(
        {
            "source_variant": "supra_i6_twin_turbo_realref_v3",
            "source_overlay": {
                "edge_scale": float(edge_scale),
                "hiband_scale": float(hiband_scale),
                "reference_basis": SUPRA_V2_REFERENCE_BASIS,
                "adjustment_domain": "source_only_before_shared_realism_layers",
            },
            "scope": "synthetic; relative real-recording cues; uncalibrated; not OEM reproduction",
        }
    )
    return replace(base, pressure=base.pressure + sum(deltas), stems=stems, diagnostics=diagnostics).validate()


__all__ = (
    "SUPRA_V2_EDGE_SCALE",
    "SUPRA_V2_HIBAND_SCALE",
    "SUPRA_V2_REFERENCE_BASIS",
    "render_supra_jza80_v2",
)
