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
    trace: VehicleStateTrace, sample_rate_hz: int = 48_000
) -> SourceRender:
    """Render a fixed source-only overlay before the shared realism layers."""
    base = render_supra_jza80(trace, sample_rate_hz)
    stems = {name: np.asarray(value, dtype=np.float64).copy() for name, value in base.stems.items()}
    deltas: list[np.ndarray] = []
    for name, scale in (("edge", SUPRA_V2_EDGE_SCALE), ("hiband", SUPRA_V2_HIBAND_SCALE)):
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
                "edge_scale": SUPRA_V2_EDGE_SCALE,
                "hiband_scale": SUPRA_V2_HIBAND_SCALE,
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
