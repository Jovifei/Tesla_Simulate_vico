"""Metric-to-parameter recommendations; never recommends protected runtime layers."""
from __future__ import annotations
from .metric_to_parameter_map import METRIC_TO_PARAMETER_MAP
PROTECTED=frozenset(("fvm","ptr","radiation","runtime","android","matlab","simulink"))
def recommend(metric:str,evidence:dict[str,object])->dict[str,object]:
    group,direction,risk=METRIC_TO_PARAMETER_MAP[metric]
    if any(token in group.lower() for token in PROTECTED): raise ValueError("protected parameter recommendation")
    return {"problem":metric,"supporting_metrics":evidence,"parameter_group":group,"direction":direction,"expected_effect":"reduce measured residual","side_effect_risk":risk,"confidence":"high" if risk=="high" else "medium"}
