"""Track S post-PTR per-state loudness compensation (design.md D1 / Task 3.1).

Why this layer exists
---------------------
The Track S source EQ ``_inject_state_spectral_targets`` shapes each state's
band-energy shares onto the ``deep_realism_tuning_manifest.json`` targets. That
EQ is **source-energy preserving** (per-state level is re-pinned to the raw
energy every iteration), so ``render.pressure`` keeps its RMS and the
``test_ferrari_rms_stays_bounded_from_idle_to_redline`` source-level gate is
untouched.

But the frozen PTR/radiation adapter is a steep low-cut (band 0 ~ -25 dB, band 1
~ -13 dB, band 2 ~ -3 dB, band 3 ~ -1 dB). Redistributing source energy into or
out of band 0 therefore changes the **post-PTR** loudness by a different amount
in every state, so the shaped post-PTR integrated-LUFS spread across the
fixed-load rpm probes blows up from 2.11 dB (baseline) to 12.19 dB -- breaking
``test_same_load_rpm_probes_change_timbre_without_gross_level_spread``.

What this layer does
--------------------
It restores the **pre-shaping** post-PTR loudness profile with a single per-clip
scalar make-up gain::

    gain_dB = LUFS(reference_post_ptr) - LUFS(shaped_post_ptr)   (clamped)

where ``reference_post_ptr`` is the SAME source rendered with the state EQ
disabled, put through the SAME frozen PTR. Because it is a single scalar:

  * band shares are left EXACTLY invariant (a scalar cannot move a ratio), so the
    per-state band-share targets that the source EQ just hit are preserved;
  * it multiplies the POST-PTR signal only, never ``render.pressure``, so the
    source-level RMS/HF gates are unaffected;
  * the frozen PTR core, ``render_identity_v02._health`` and the
    ``manage_bundle_loudness`` signature are all untouched -- this is a new Track
    S module, not an edit to any frozen boundary.

For an un-shaped vehicle the reference render equals the shaped render, so the
make-up gain is ~0 dB and the layer is a no-op.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import measure_loudness

# Post-PTR make-up is a corrective, not a creative, layer: it should only ever
# undo the shaping-induced level swing (measured at most ~+5 / -5 dB on the
# Ferrari probes). The clamp keeps a pathological reference/silence ratio from
# turning into an unbounded boost that would blow the downstream peak limiter.
_MAX_GAIN_DB = 12.0


def post_ptr_makeup_gain_db(
    shaped_ptr: np.ndarray,
    reference_ptr: np.ndarray,
    sample_rate_hz: int = 48000,
    max_gain_db: float = _MAX_GAIN_DB,
) -> float:
    """Scalar make-up gain (dB) that lands ``shaped_ptr`` on ``reference_ptr`` LUFS.

    Returns 0.0 (a no-op) whenever either integrated loudness is not finite
    (e.g. a silent clip), so the layer can never introduce a non-finite gain.
    """
    reference_lufs = measure_loudness(np.asarray(reference_ptr, dtype=np.float64), sample_rate_hz).integrated_lufs
    shaped_lufs = measure_loudness(np.asarray(shaped_ptr, dtype=np.float64), sample_rate_hz).integrated_lufs
    if not (np.isfinite(reference_lufs) and np.isfinite(shaped_lufs)):
        return 0.0
    return float(np.clip(reference_lufs - shaped_lufs, -max_gain_db, max_gain_db))


def apply_post_ptr_compensation(
    shaped_ptr: np.ndarray,
    reference_ptr: np.ndarray,
    sample_rate_hz: int = 48000,
    max_gain_db: float = _MAX_GAIN_DB,
) -> tuple[np.ndarray, float]:
    """Return ``(compensated_audio, gain_db)`` for a shaped post-PTR clip.

    ``compensated_audio`` is ``shaped_ptr`` scaled by the make-up gain; a new
    array is always returned so the caller's buffer is never mutated.
    """
    gain_db = post_ptr_makeup_gain_db(shaped_ptr, reference_ptr, sample_rate_hz, max_gain_db)
    scaled = np.asarray(shaped_ptr, dtype=np.float64) * (10.0 ** (gain_db / 20.0))
    return scaled, gain_db


def render_baseline_source(
    renderer: Callable[..., SourceRender],
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """Render a source with the per-state band EQ disabled (the loudness reference).

    Renderers that expose ``apply_state_shaping`` (currently the Ferrari
    flat-plane source) are asked to skip the state EQ; renderers that have no
    state EQ yet (Hellcat, RX-7) are rendered normally, in which case the
    reference equals the shaped render and the make-up gain is ~0 dB.
    """
    try:
        return renderer(trace, sample_rate_hz=sample_rate_hz, apply_state_shaping=False)
    except TypeError:
        return renderer(trace, sample_rate_hz=sample_rate_hz)
