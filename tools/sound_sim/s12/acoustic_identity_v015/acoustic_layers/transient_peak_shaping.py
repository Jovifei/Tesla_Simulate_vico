"""State-dependent PTR-front transient shaping for the Hellcat candidate only."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace

if TYPE_CHECKING:
    from ..stage_d.candidate_profiles import StageDCandidateProfile


def apply_transient_peak_shaping(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace,
    candidate: "StageDCandidateProfile | None" = None,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Shape only named short transient stems; non-Hellcat is bit-identical."""
    trace.validate()
    if vehicle_id != "hellcat" or candidate is None:
        return render
    shaper = candidate.payload["loudness"]["transient_peak_shaper"]
    if not shaper["enabled"]:
        return render
    result = render
    # Steady blower energy is an identity carrier, not a transient.  Only a
    # separately named attack stem may be shaped; older renders without that
    # stem therefore pass through unchanged.
    for stem_name in ("shift_impact", "shift_recovery_boom", "afterfire", "blower_attack"):
        result = _shape_stem(result, stem_name, float(shaper["attack_ms"]), float(shaper["release_ms"]), float(shaper["max_reduction_db"]), sample_rate_hz)
    return result


def _shape_stem(render: SourceRender, name: str, attack_ms: float, release_ms: float, max_reduction_db: float, sample_rate_hz: int) -> SourceRender:
    if name not in render.stems:
        return render
    stem = np.asarray(render.stems[name], dtype=np.float64)
    magnitude = np.max(np.abs(stem), axis=1)
    envelope = np.zeros_like(magnitude)
    attack_alpha = 1.0 - math.exp(-1.0 / max(attack_ms * 0.001 * sample_rate_hz, 1.0))
    release_alpha = 1.0 - math.exp(-1.0 / max(release_ms * 0.001 * sample_rate_hz, 1.0))
    for index in range(1, magnitude.size):
        alpha = attack_alpha if magnitude[index] >= envelope[index - 1] else release_alpha
        envelope[index] = envelope[index - 1] + alpha * (magnitude[index] - envelope[index - 1])
    threshold = max(float(np.percentile(envelope, 75.0)), 1e-12)
    excess = np.clip(envelope / threshold - 1.0, 0.0, 1.0)
    floor = 10.0 ** (-max_reduction_db / 20.0)
    gain = 1.0 - excess * (1.0 - floor)
    replacement = stem * gain[:, None]
    stems = dict(render.stems)
    stems[name] = replacement
    return SourceRender(pressure=render.pressure + replacement - stem, stems=stems, diagnostics=render.diagnostics).validate()
