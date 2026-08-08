"""Per-state 4-band spectral-target injection shared by every anchor source.

Extracted verbatim from `sources/flat_plane_v8_source.py` (Task 3.1) so Hellcat
and RX-7 can reuse the same injection instead of each source hand-tuning
harmonic weights against six states x four bands. The extraction is behaviour
preserving: `flat_plane_v8_source` re-imports the same private names, so the
Ferrari path is byte-for-byte identical to before.

The reachability floor comment in the original already anticipated this reuse:
the criterion is on the MEASURED share, not on rpm or any vehicle-specific
parameter, so it generalises across vehicles unchanged.
"""

from __future__ import annotations

import numpy as np

from ..acoustic_analysis.spectral_targets import BAND_EDGES
from ..contracts import SourceRender, VehicleStateTrace
from ..tuning.deep_realism import _labels_on_render_grid, load_tuning_manifest


# ---------------------------------------------------------------------------
# Per-state spectral-target injection (Track S; design.md D1)
# ---------------------------------------------------------------------------
# The manifest gives, per state, the fraction of total energy that must fall in
# each of the four `BAND_EDGES` bands. A static gain g_b on band b maps that
# band's energy E_b = s_b * E_total to g_b^2 * E_b, so
#
#     g_b = sqrt(target_b / s_b)
#
# lands band b exactly on its target share. Because the manifest targets are
# normalised (sum_b target_b == 1, locked by ManifestIntegrityTests), the total
# energy after shaping is sum_b g_b^2 E_b = E_total * sum_b target_b = E_total:
# **the shaping is energy-preserving**, which is what keeps
# `test_ferrari_rms_stays_bounded_from_idle_to_redline` intact.
#
# Two implementation properties matter:
#
# * The equaliser is applied through an STFT overlap-add so that a trace which
#   crosses states gets each frame shaped by ITS OWN state's curve, crossfaded
#   by the 75%-overlap Hann windows -- no step in the gain, no click.
# * The SAME curve is applied to `pressure` and to every stem. Because the
#   operator is linear, `pressure == left_bank + right_bank + metallic` is
#   preserved exactly instead of having to be re-derived. (`SourceRender.
#   validate()` only checks shape/finiteness, but the additive stem semantics
#   are relied on downstream, e.g. `high.pressure - high.stems["blower"]`.)

_SHAPE_FRAME = 2048
_SHAPE_OVERLAP = 4
_EDGE_BLEND_OCTAVES = 1.0 / 6.0
_MAX_SHAPE_DB = 24.0
_SHAPE_REFINEMENTS = 32
_SHAPE_TOLERANCE = 0.002
_GAIN_FRAME_SMOOTHING = 5
_MIN_SHAPE_SAMPLES = 256

# Reachability floor: a band whose original (pre-shaping) share falls below
# this is physically absent at the current operating point (its tiny non-zero
# value is Hann-window spectral leakage, not signal). Even +_MAX_SHAPE_DB
# cannot lift it to any manifest target, so leaving it in the target
# competition saturates the gain clip; the saturated value then enters the
# mean-subtraction `corrected - corrected.mean()` and drags every healthy
# band below the clip floor -- that is the >7500 rpm band0 collapse.
#
# The floor sits in the ~30x gap between (a) the largest "unreachable" share
# observed -- 2.4e-5, band0 at 7600 rpm where the 2nd combustion order has
# moved above 250 Hz and the band contains only window leakage -- and (b) the
# smallest "reachable" share at any calibration point -- 6.8e-4, idle band3
# (target 0.0077, needs only +10.5 dB, well inside the 24 dB clip). The 4.2x
# / 6.8x margins keep the criterion off both sides of the gap. Because it is
# on the measured share (not on rpm or any vehicle-specific parameter) it
# generalises to Hellcat / RX-7 when the same injection pattern is reused.
_UNREACHABLE_SHARE_FLOOR = 1e-4


def _band_blend_weights(frequencies: np.ndarray) -> np.ndarray:
    """Smooth partition of unity over `BAND_EDGES`, shape [5, n_bins].

    Rows 0..3 are the four measured bands. Row 4 collects everything OUTSIDE
    `BAND_EDGES` (below 20 Hz and above 12 kHz) and is always driven at unit
    gain. That outer roll-off matters: without it a boost aimed at the
    4-12 kHz band keeps rising all the way to Nyquist, so most of the added
    energy lands where `band_energy_shares` cannot see it. The denominator
    inflates, every share deflates, and the targeted band gets further away
    instead of closer.

    Each edge is a smoothstep crossfade spanning +/-`_EDGE_BLEND_OCTAVES` in
    log frequency rather than a hard rectangular mask (which would ring). The
    five rows sum to 1.0 at every bin, so a unit gain vector reproduces a flat
    curve exactly.
    """
    log_frequency = np.log2(np.maximum(np.asarray(frequencies, dtype=np.float64), 1e-6))
    ramps = []
    for edge_hz in [BAND_EDGES[0][0]] + [hi for _, hi in BAND_EDGES]:
        centre = np.log2(edge_hz)
        position = np.clip(
            (log_frequency - (centre - _EDGE_BLEND_OCTAVES)) / (2.0 * _EDGE_BLEND_OCTAVES), 0.0, 1.0
        )
        ramps.append(position * position * (3.0 - 2.0 * position))
    bands = [ramps[index] - ramps[index + 1] for index in range(len(BAND_EDGES))]
    return np.stack(bands + [(1.0 - ramps[0]) + ramps[-1]])


def _band_power_of(mono: np.ndarray, sample_rate_hz: int) -> tuple[np.ndarray, float]:
    """Band energies and total energy, measured exactly like `band_energy_shares`."""
    signal = np.asarray(mono, dtype=np.float64)
    power = np.square(np.abs(np.fft.rfft(signal * np.hanning(signal.size))))
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / sample_rate_hz)
    bands = np.array(
        [float(power[(frequencies >= lo) & (frequencies <= hi)].sum()) for lo, hi in BAND_EDGES]
    )
    return bands, float(power.sum()) or 1e-30


def _frame_curves(
    frame_states: np.ndarray, shape: dict, level: dict, weights: np.ndarray
) -> np.ndarray:
    """Per-frame gain curves [n_frames, n_bins] from per-state shape x level.

    The trailing column is the out-of-band row of `_band_blend_weights`: it
    carries LEVEL only, so sub-20 Hz and super-12 kHz content is re-levelled
    with the rest of the render but never spectrally re-shaped.

    Gains are smoothed along the FRAME axis in the log domain so a state change
    ramps the equaliser over ~`_GAIN_FRAME_SMOOTHING` hops instead of switching
    abruptly. For a single-state render this is a no-op (all rows identical).
    """
    scale = np.asarray([level[state] for state in frame_states], dtype=np.float64)
    per_frame = np.column_stack(
        [np.stack([shape[state] for state in frame_states]) * scale[:, np.newaxis], scale]
    )
    columns = per_frame.shape[1]
    if _GAIN_FRAME_SMOOTHING > 1 and per_frame.shape[0] > 1:
        window = min(_GAIN_FRAME_SMOOTHING, per_frame.shape[0])
        kernel = np.full(window, 1.0 / window)
        lead = window // 2
        padded = np.pad(np.log(np.maximum(per_frame, 1e-12)), ((lead, window - 1 - lead), (0, 0)), mode="edge")
        per_frame = np.exp(
            np.stack([np.convolve(padded[:, band], kernel, mode="valid") for band in range(columns)], axis=1)
        )
    return per_frame @ weights


def _overlap_add(signal: np.ndarray, curves: np.ndarray, frame: int, hop: int, pad: int, starts: np.ndarray) -> np.ndarray:
    """Apply per-frame spectral gain curves to every channel of `signal` [N, C].

    Hann analysis + Hann synthesis at 75% overlap; the accumulated squared
    window is divided out, so a unit gain curve reconstructs the input exactly
    (including at the edges).
    """
    count, channels = signal.shape
    total = pad + count + frame + hop
    padded = np.zeros((total, channels), dtype=np.float64)
    padded[pad : pad + count] = signal
    window = np.hanning(frame + 1)[:frame]
    accumulator = np.zeros((total, channels), dtype=np.float64)
    window_sum = np.zeros(total, dtype=np.float64)
    squared = window * window
    for index, start in enumerate(starts):
        segment = padded[start : start + frame] * window[:, np.newaxis]
        spectrum = np.fft.rfft(segment, axis=0) * curves[index][:, np.newaxis]
        accumulator[start : start + frame] += np.fft.irfft(spectrum, n=frame, axis=0) * window[:, np.newaxis]
        window_sum[start : start + frame] += squared
    accumulator /= np.maximum(window_sum, 1e-12)[:, np.newaxis]
    return accumulator[pad : pad + count]


def _inject_state_spectral_targets(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace,
    sample_rate_hz: int = 48000,
    manifest: dict | None = None,
) -> SourceRender:
    """Shape `render` so each state's band shares match the manifest targets.

    Returns a new `SourceRender`; the input is not modified. Renders shorter
    than `_MIN_SHAPE_SAMPLES` are returned untouched (too short to estimate a
    spectrum from).
    """
    manifest = manifest or load_tuning_manifest()
    try:
        states = manifest["vehicles"][vehicle_id]["states"]
    except KeyError as error:
        raise KeyError(f"deep realism manifest has no vehicle {vehicle_id!r}") from error

    pressure = np.asarray(render.pressure, dtype=np.float64)
    count = pressure.shape[0]
    if count < _MIN_SHAPE_SAMPLES:
        return render

    frame = _SHAPE_FRAME
    while frame > count:
        frame //= 2
    hop = max(frame // _SHAPE_OVERLAP, 1)
    pad = frame
    starts = np.arange(0, pad + count + hop, hop)

    labels = _labels_on_render_grid(trace, count, sample_rate_hz)
    centres = np.clip(starts + frame // 2 - pad, 0, count - 1)
    frame_states = labels[centres]

    weights = _band_blend_weights(np.fft.rfftfreq(frame, 1.0 / sample_rate_hz))
    shape_limit = _MAX_SHAPE_DB / 20.0 * np.log(10.0)

    present = list(np.unique(labels))
    for state in present:
        if state not in states:
            raise KeyError(f"deep realism manifest for {vehicle_id!r} has no state {state!r}")
    shape = {state: np.ones(4) for state in present}
    level = {state: 1.0 for state in present}
    masks = {state: labels == state for state in present}

    mono = pressure.mean(axis=1)[:, np.newaxis]
    # Refine against the ACTUAL overlap-add output rather than trusting the
    # single-shot analytic estimate: the band-edge crossfades and the frame
    # decomposition both perturb the realised shares slightly.
    # The bands are not independent: the band-edge crossfades and ordinary
    # spectral leakage mean a gain applied to one band moves its neighbours too
    # (a loud mode sitting in a crossfade is the worst case). One analytic shot
    # is therefore not enough, so this is run as a fixed-point iteration that
    # stops as soon as every state is comfortably inside `_SHAPE_TOLERANCE`.
    #
    # Band SHARES are ratios, so they leave the overall gain scale free. The
    # gain is therefore split into an explicitly separated SHAPE (relative,
    # bounded) and LEVEL (scalar, unbounded):
    #
    # * LEVEL is re-pinned every iteration so each state keeps exactly the
    #   energy it had before shaping. The injection is then energy-preserving
    #   by construction, which is what leaves
    #   `test_ferrari_rms_stays_bounded_from_idle_to_redline` untouched.
    # * SHAPE is normalised to unit geometric mean and bounded to
    #   +/-`_MAX_SHAPE_DB`. A band equaliser can only redistribute energy that
    #   exists, so when a target is physically unreachable (e.g. at 8000 rpm the
    #   2nd combustion order has moved ABOVE 250 Hz and the 20-250 Hz band is
    #   nearly empty) the bound stops the iteration from crushing every other
    #   band by 40 dB in a doomed attempt to satisfy the ratio. Such a state
    #   simply retains a residual instead of destroying the render.
    raw_energy = {}
    raw_shares = {}
    for state in present:
        if int(masks[state].sum()) >= frame:
            bands, total = _band_power_of(mono[masks[state], 0], sample_rate_hz)
            raw_energy[state] = total
            raw_shares[state] = bands / total

    # Reachability analysis: for each state, measure the original (pre-shaping)
    # band shares and flag any band whose share is below _UNREACHABLE_SHARE_FLOOR
    # as physically absent. The flagged band is removed from target competition
    # and its target share is redistributed proportionally over the remaining
    # reachable bands (renormalised to sum=1), so the healthy bands keep their
    # intended relative balance instead of being crushed by a saturated gain.
    effective_target = {}
    reachable_mask = {}
    for state in present:
        target = np.asarray(states[state]["band_shares_target"], dtype=np.float64)
        if state in raw_shares:
            mask = raw_shares[state] >= _UNREACHABLE_SHARE_FLOOR
        else:
            mask = np.ones(4, dtype=bool)
        if mask.any() and not mask.all():
            reachable = target[mask]
            effective = np.zeros(4, dtype=np.float64)
            effective[mask] = reachable / reachable.sum()
            effective_target[state] = effective
        else:
            effective_target[state] = target
        reachable_mask[state] = mask

    residual = float("inf")
    iterations = 0
    for iterations in range(1, _SHAPE_REFINEMENTS + 1):
        curves = _frame_curves(frame_states, shape, level, weights)
        shaped = _overlap_add(mono, curves, frame, hop, pad, starts)[:, 0]
        residual = 0.0
        for state in present:
            if state not in raw_energy:
                continue
            bands, total = _band_power_of(shaped[masks[state]], sample_rate_hz)
            measured = bands / total
            target = effective_target[state]
            mask = reachable_mask[state]
            # Residual is computed only over reachable bands; an unreachable
            # band has no target to hit and is left at its natural level.
            if mask.any():
                residual = max(residual, float(np.max(np.abs(measured[mask] - target[mask]))))
            # Bound EACH reachable band before removing the mean, never after.
            # A band whose target is physically unreachable wants an unbounded
            # gain; if that raw value is allowed into the mean it drags all
            # healthy bands onto the clip floor and wrecks the render. Clipping
            # first caps how far one saturated band can shift the others to
            # `_MAX_SHAPE_DB / n_bands`. Unreachable bands are held at unity
            # (corrected=0) so the mean-subtraction only couples the healthy
            # bands; the geometric mean of all four gains stays 1.0, so the
            # shape remains energy-preserving and `pressure == sum(stems)`
            # is preserved.
            corrected = np.zeros(4, dtype=np.float64)
            corrected[mask] = np.log(shape[state][mask]) + 0.5 * np.log(
                target[mask] / np.maximum(measured[mask], 1e-12)
            )
            corrected = np.clip(corrected, -shape_limit, shape_limit)
            corrected[~mask] = 0.0
            new_shape = np.ones(4, dtype=np.float64)
            if mask.any():
                new_shape[mask] = np.exp(corrected[mask] - corrected[mask].mean())
            shape[state] = new_shape
            level[state] = level[state] * np.sqrt(raw_energy[state] / total)
        if residual <= _SHAPE_TOLERANCE:
            break

    curves = _frame_curves(frame_states, shape, level, weights)
    names = list(render.stems)
    stack = np.concatenate([pressure] + [np.asarray(render.stems[name], dtype=np.float64) for name in names], axis=1)
    shaped_stack = _overlap_add(stack, curves, frame, hop, pad, starts)

    diagnostics = dict(render.diagnostics)
    unreachable_diagnostics = {}
    for state in present:
        mask = reachable_mask.get(state, np.ones(4, dtype=bool))
        if state in raw_shares and not mask.all():
            unreachable_diagnostics[str(state)] = {
                "unreachable_bands": [int(i) for i in range(4) if not mask[i]],
                "original_shares": [round(float(s), 6) for s in raw_shares[state]],
                "effective_target": [round(float(t), 6) for t in effective_target[state]],
            }
    diagnostics.update(
        {
            "state_spectral_targets_applied": True,
            "state_spectral_target_frame": int(frame),
            "state_spectral_target_hop": int(hop),
            "state_spectral_refinement_iterations": int(iterations),
            "state_spectral_residual_band_share": float(residual),
            "state_spectral_band_gains_db": {
                str(state): [
                    round(float(20.0 * np.log10(max(gain * level[state], 1e-12))), 3) for gain in shape[state]
                ]
                for state in present
            },
            "state_spectral_unreachable_bands": unreachable_diagnostics,
            "state_spectral_injection": (
                "state-keyed linear band EQ via STFT overlap-add; identical curve on "
                "pressure and every stem, so pressure == sum(stems) is preserved"
            ),
        }
    )
    return SourceRender(
        pressure=shaped_stack[:, :2],
        stems={name: shaped_stack[:, 2 * (index + 1) : 2 * (index + 2)] for index, name in enumerate(names)},
        diagnostics=diagnostics,
    ).validate()
