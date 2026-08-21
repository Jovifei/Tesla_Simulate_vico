"""Trace-gated transient diagnostics."""
from __future__ import annotations

import numpy as np


def event_metrics(signal: np.ndarray, eligible_event_mask: np.ndarray | None) -> dict[str, int]:
    envelope = np.abs(signal)
    threshold = max(float(np.quantile(envelope, 0.995)), float(envelope.mean() + 4.0 * envelope.std()))
    starts = np.flatnonzero((envelope >= threshold) & np.r_[True, envelope[:-1] < threshold])
    kept: list[int] = []
    minimum_gap = max(1, signal.size // 100)
    for start in starts:
        if not kept or int(start) - kept[-1] >= minimum_gap:
            kept.append(int(start))
    wrong = 0 if eligible_event_mask is None else sum(not bool(eligible_event_mask[min(sample, eligible_event_mask.size - 1)]) for sample in kept)
    return {"event_count": len(kept), "wrong_condition_event_count": int(wrong)}


def require_trace_gated_events(signal: np.ndarray, eligible_event_mask: np.ndarray | None) -> dict[str, int]:
    metrics = event_metrics(signal, eligible_event_mask)
    if metrics["wrong_condition_event_count"]:
        raise ValueError("event detected outside the trace-authorized state window")
    return metrics
