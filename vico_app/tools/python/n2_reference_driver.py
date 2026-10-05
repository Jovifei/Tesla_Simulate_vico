"""Offline diagnostics for actual N2 export files, never acoustic acceptance evidence.

No reference audio, objective evaluation, budget consumption or gain changes occur.
This intentionally does not manufacture a reference_result.v2 from incomplete inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from struct import error as struct_error

import numpy as np
import scipy
from scipy.signal import welch

if __package__:
    from .n2_reference_export import BRANCHES, CHANNELS, compare_partitions, measure, read_export
else:
    from n2_reference_export import BRANCHES, CHANNELS, compare_partitions, measure, read_export

RATE = 48000
BANDS = ((20., 200.), (200., 4000.), (4000., 12000.))


def band_power(samples):
    """Existing build_c63_hybrid_targets.features absolute PSD contract, without gain normalization.

    8192-point Hann Welch, 6144 overlap, no detrend, density integrated in
    half-open bands. At least 24000 samples, matching that feature extractor.
    """
    x = np.asarray(samples, dtype=np.float64)
    measured = measure(x)
    if x.size < RATE // 2 or measured["rms"] <= 1e-10:
        raise ValueError("protected-band window must contain at least 24000 non-silent samples")
    with np.errstate(over="ignore", invalid="ignore"):
        f, psd = welch(x, fs=RATE, window="hann", nperseg=8192, noverlap=6144,
                       detrend=False, scaling="density")
    powers = [float(np.sum(psd[(f >= lo) & (f < hi)]) * RATE / 8192) for lo, hi in BANDS]
    if not all(math.isfinite(v) and v >= 0 for v in powers):
        raise ValueError("nonfinite protected-band energy")
    return powers


def _db_ratio(after, before, factor):
    # Do not floor a silent/undefined denominator into apparently qualified dB.
    if not math.isfinite(after) or not math.isfinite(before) or min(after, before) <= 0:
        raise ValueError("undefined dB comparison: nonpositive/nonfinite energy")
    value = factor * (math.log10(after) - math.log10(before))
    if not math.isfinite(value):
        raise ValueError("nonfinite dB comparison")
    return value


def protected_comparison(baseline_pcm, candidate_pcm, baseline_bark, candidate_bark):
    """One explicit window; these field names match the existing hard gate.

    This is neither the full fixture-matrix maximum nor a reference acceptance.
    The bark stem is source-time, before all frozen downstream processing.
    """
    arrays = [np.asarray(x) for x in (baseline_pcm, candidate_pcm, baseline_bark, candidate_bark)]
    if any(x.ndim != 1 for x in arrays) or len({x.size for x in arrays}) != 1:
        raise ValueError("protected comparison requires aligned mono arrays")
    before, after = band_power(arrays[0]), band_power(arrays[1])
    delta = [_db_ratio(b, a, 10) for a, b in zip(before, after)]
    source_before, source_after = (measure(x)["rms"] for x in arrays[2:])
    return {"low_max_db": abs(delta[0]), "low_median_db": abs(delta[0]), "low_p90_db": abs(delta[0]),
            "mid_max_rise_db": delta[1],
            "source_rms_change_db": _db_ratio(source_after, source_before, 20),
            "baseline_band_power": before, "candidate_band_power": after,
            "signed_band_delta_db": delta, "baseline_bark_rms": source_before,
            "candidate_bark_rms": source_after, "window_count": 1}


def _branch_observations(export):
    branches = export.branches
    same = lambda a, b, columns: np.array_equal(branches[a]["taps"][:, columns], branches[b]["taps"][:, columns])
    continuous = [0, 2, 3, 4, 5, 6, 7, 8]
    if not same("t_event_on", "s_event_on", continuous):
        raise ValueError("S changed a non-bark source channel")
    non_event = [0, 1, 2, 3, 5, 6, 7]
    for old, new in (("t_event_on", "e_event_on"), ("s_event_on", "se_event_on")):
        if not same(old, new, non_event):
            raise ValueError("event replacement changed a non-event source channel")
    effects = {}
    for mode in ("e", "se"):
        on, off = mode + "_event_on", mode + "_event_off"
        if not same(on, off, [i for i in range(9) if i != 4]):
            raise ValueError("event-off changed a non-event source channel")
        if np.any(branches[off]["taps"][:, 4] != 0):
            raise ValueError("event-off afterfire stem is not silent")
        for key in ("raw_arrivals_reported", "impulse_frames", "pending_frames_reported"):
            if branches[on][key] != branches[off][key]:
                raise ValueError("event-off changed occurrence/pending observations")
        # Convert before subtracting, to avoid Float32 subtraction overflow/roundoff.
        effect = branches[on]["pcm"].astype(np.float64) - branches[off]["pcm"].astype(np.float64)
        effects[mode.upper()] = {"on_minus_off_pcm": measure(effect),
                                 "afterfire_source": branches[on]["stem_measurements"]["afterfire"],
                                 "impulse_frames": branches[on]["impulse_frames"],
                                 "raw_arrivals_reported": branches[on]["raw_arrivals_reported"],
                                 "event_distance": "NOT_RUN_NO_BOUND_REFERENCE_PROTOCOL"}
    for event in ("on", "off"):
        if not same("e_event_" + event, "se_event_" + event, continuous):
            raise ValueError("SE changed a non-bark source channel relative to E")
    return effects


def inspect_exports(directory, comparison=None, start_frame=0, stop_frame=None):
    export = read_export(directory)
    frames = int(export.metadata["frames"])
    stop = frames if stop_frame is None else stop_frame
    if (type(start_frame) is not int or type(stop) is not int
            or not 0 <= start_frame < stop <= frames or stop - start_frame < RATE // 2):
        raise ValueError("analysis window must be an in-range half-open interval of at least 24000 frames")
    other = read_export(comparison) if comparison is not None else None
    partition = compare_partitions(export, other) if other is not None else None
    effects = _branch_observations(export)
    if other is not None:
        _branch_observations(other)
    comparisons = {}
    for label, old, new in (("T_to_S", "t_event_on", "s_event_on"),
                            ("E_OFF_to_SE_OFF", "e_event_off", "se_event_off")):
        baseline, candidate = export.branches[old], export.branches[new]
        window = slice(start_frame, stop)
        comparisons[label] = protected_comparison(baseline["pcm"][window], candidate["pcm"][window],
                                                  baseline["taps"][window, 1], candidate["taps"][window, 1])
    return {
        "schema": "c63.n2.render_metrics.v1",
        "status": "MEASURED_DIAGNOSTIC_ONLY_NOT_QUALIFICATION",
        "candidate": "C63_N2_CONTINUOUS_V1", "objective_evaluated": False,
        "budget_reserved": False, "heldout_used_for_fitting": False,
        "source_receipts": {"manifest_sha256": export.manifest_sha256,
                            "comparison_manifest_sha256": other.manifest_sha256 if other else None,
                            "payload_sha256": export.payload_sha256, "metadata": export.metadata},
        "analysis_window": {"start_frame": start_frame, "stop_frame_exclusive": stop,
                            "scope": "ONE_EXPLICIT_DIAGNOSTIC_WINDOW_NOT_QUALIFICATION_MATRIX"},
        "evidence": {"sample_count": frames * len(BRANCHES), "finite": True, "energy_finite": True},
        "branches": {name: {k: v for k, v in branch.items() if k not in ("pcm", "taps")}
                     for name, branch in export.branches.items()},
        "continuous": comparisons["T_to_S"], "controlled_comparisons": comparisons,
        "event_observations": effects,
        "partition_invariant": partition,
        "qualification": {"reference_result_v2": "NOT_PRODUCED", "reference_provenance": "NOT_RUN",
                          "event_distance": "NOT_RUN", "heldout_comparison": "NOT_RUN",
                          "snapshot_replay": "NOT_RUN", "baseline_t_identity": "NOT_RUN",
                          "state_continuity": "NOT_RUN", "full_matrix": "NOT_RUN",
                          "device": "NOT_RUN", "human": "NOT_RUN"},
        "implementation": {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
                           "source_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                             for name in ("n2_reference_driver.py", "n2_reference_export.py", "n2_artifact_gate.py")}},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True, dest="directory")
    parser.add_argument("--compare-export", type=Path)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--stop-frame", type=int)
    parser.add_argument("--out", type=Path, required=True, help="new diagnostic JSON file; never overwritten")
    args = parser.parse_args(argv)
    try:
        result = inspect_exports(args.directory, args.compare_export, args.start_frame, args.stop_frame)
        data = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(data)
        print(json.dumps({"status": result["status"], "output_sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
                          "partition_invariant": result["partition_invariant"]}, sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, OverflowError, struct_error) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}, allow_nan=False))
        return 2

if __name__ == "__main__":
    sys.exit(main())
