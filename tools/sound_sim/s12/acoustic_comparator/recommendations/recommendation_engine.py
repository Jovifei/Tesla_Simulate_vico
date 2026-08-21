"""Metric-to-parameter recommendations; never recommends protected runtime layers."""
from __future__ import annotations
PROTECTED=frozenset(("fvm","ptr","radiation","runtime","android","matlab","simulink"))
MAP={"order_ridge_error":("event timing / events_per_rev / bank pattern","correct ridge frequency","medium"),"low_band_deficit":("pressure pulse / exhaust body / rumble","increase causal low-frequency articulation","medium"),"sharpness_excess":("high-order stem / pre-PTR compensation","reduce upper-order energy","medium"),"idle_regularity":("cycle jitter / amplitude variation / mechanical texture","increase state-locked variation","medium"),"afterfire_ineligible":("state gate / event centroid / decay","repair eligibility before timbre","high"),"blower_correlation":("shaft ratio / lobe-pass family / inertia / bypass","align whine state coupling","high"),"turbo_correlation":("onset / shaft state / sideband / BOV","align turbo timing","high"),"loudness_only":("post-PTR fixed gain","adjust only fixed whole-cycle gain","low")}
def recommend(metric:str,evidence:dict[str,object])->dict[str,object]:
    group,direction,risk=MAP[metric]
    if any(token in group.lower() for token in PROTECTED): raise ValueError("protected parameter recommendation")
    return {"problem":metric,"supporting_metrics":evidence,"parameter_group":group,"direction":direction,"expected_effect":"reduce measured residual","side_effect_risk":risk,"confidence":"high" if risk=="high" else "medium"}
