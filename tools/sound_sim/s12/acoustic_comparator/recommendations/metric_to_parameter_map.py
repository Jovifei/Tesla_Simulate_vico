"""Authoritative Stage-M metric-to-parameter mapping, excluding protected layers."""
from __future__ import annotations

METRIC_TO_PARAMETER_MAP = {
    "order_ridge_error": ("event timing / events_per_rev / bank pattern", "correct ridge frequency", "medium"),
    "low_band_deficit": ("pressure pulse / exhaust body / rumble", "increase causal low-frequency articulation", "medium"),
    "low_band_attack_deficit": ("120-400 Hz transient envelope", "increase bounded attack only", "medium"),
    "sharpness_excess": ("high-order stem / pre-PTR compensation", "reduce upper-order energy", "medium"),
    "idle_regularity": ("cycle jitter / amplitude variation / mechanical texture", "increase state-locked variation", "medium"),
    "afterfire_ineligible": ("state gate / event centroid / decay", "repair eligibility before timbre", "high"),
    "blower_correlation": ("shaft ratio / lobe-pass family / inertia / bypass", "align whine state coupling", "high"),
    "turbo_correlation": ("onset / shaft state / sideband / BOV", "align turbo timing", "high"),
    "loudness_only": ("post-PTR fixed gain", "adjust only fixed whole-cycle gain", "low"),
}
