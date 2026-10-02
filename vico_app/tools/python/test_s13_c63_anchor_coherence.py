import importlib
import importlib.util

import numpy as np


_MODULE_NAME = "analyze_s13_c63_anchor_coherence"
coherence = (
    importlib.import_module(_MODULE_NAME)
    if importlib.util.find_spec(_MODULE_NAME)
    else None
)


def require_module():
    assert coherence is not None, "C63 anchor-coherence diagnostic is not implemented"
    return coherence


def test_signed_residual_summary_keeps_direction_not_only_absolute_error():
    module = require_module()
    summarize = getattr(module, "summarize_signed_residual", None)
    assert callable(summarize), "phase analysis must inspect residual sign first"

    summary = summarize([1.0, 2.0, 3.0, -1.0, 4.0], minimum_windows=5)

    assert summary["window_count"] == 5
    assert summary["median_signed_db"] == 2.0
    assert summary["positive_fraction"] == 0.8
    assert summary["negative_fraction"] == 0.2


def test_anchor_cross_term_distinguishes_constructive_and_destructive_phase():
    module = require_module()
    cross_term = getattr(module, "coherent_cross_term_db", None)
    assert callable(cross_term), "anchor components must expose the coherent power cross-term"
    time = np.arange(4800) / 48000.0
    tone = 0.1 * np.sin(2.0 * np.pi * 1000.0 * time)

    constructive = cross_term([tone * 0.5, tone * 0.5], sample_rate_hz=48000, band="1000-4000")
    destructive = cross_term([tone * 0.5, -tone * 0.5], sample_rate_hz=48000, band="1000-4000")

    assert abs(constructive - 3.0103) < 0.02
    assert destructive < -40.0


def test_phase_support_gate_requires_signed_residual_and_repeatable_cross_term():
    module = require_module()
    evaluate = getattr(module, "evaluate_anchor_coherence", None)
    assert callable(evaluate), "phase support must be conditional and fail closed"
    residual = {"window_count": 12, "median_signed_db": 4.0, "positive_fraction": 0.83}
    coherent = {"window_count": 12, "median_cross_term_db": 1.2, "positive_fraction": 0.83}
    incoherent = {"window_count": 12, "median_cross_term_db": 0.2, "positive_fraction": 0.58}
    insufficient = {"window_count": 3, "median_cross_term_db": 3.0, "positive_fraction": 1.0}

    assert evaluate(residual, coherent)["status"] == "SUPPORTS_FURTHER_PHASE_ABLATION"
    assert evaluate(residual, incoherent)["status"] == "ANCHOR_COHERENCE_NOT_ESTABLISHED"
    assert evaluate(residual, insufficient)["status"] == "INSUFFICIENT_STABLE_WINDOWS"
    assert evaluate({**residual, "positive_fraction": 0.5}, coherent)["status"] == "RESIDUAL_SIGN_NOT_ESTABLISHED"
