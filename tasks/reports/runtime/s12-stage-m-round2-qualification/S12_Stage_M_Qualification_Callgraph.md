# S12 Stage M Qualification Call Graph

## M2 answers

1. Candidate selection starts at `candidate_grid` and reaches `candidate_search` only through caller-supplied metric dictionaries.
2. Source metrics are actual arrays with trace-window bindings where stated in `stage_m_gate_source_matrix.json`.
3. Final PCM checks use the formal PCM path, not the comfort-review copy.
4. `idle_bytes` and `pcm_health` are final-PCM evidence; low/high band and event evidence are source/trace evidence.
5. Trace availability is an explicit hard gate, but not every metric is trace-bound.
6. Review-gain audio is audition-only and is rejected as an analysis input.
7. Round-2 package builders intentionally produce diagnostic packages when gates fail.
8. `reference_distance` is only a supplied/ranking input; it is not in `REQUIRED_FULL_GATES` and is not recomputed by candidate search.
9. Therefore the current selection path cannot prove a provenance/scenario/RPM-bound real-reference identity pass.
10. Stage M does not alter thresholds or profiles; it records the defect and holds all vehicles diagnostic-only pending valid evidence.

## Call graph

```text
candidate_grid -> renderer_source_overlay -> source_metrics -> hard_gates -> candidate_search -> selected_candidate -> review_package -> status_manifest
                                  |                 ^
                                  -> final_pcm_metrics
reference_distance ---------------------------------> candidate_search (rank input only; not a required hard gate)
state_regression -----------------------------------> candidate_search
```

## Source files audited

- `stage_k/candidate_search.py`
- `scripts/qualify_stage_k_candidates.py`
- `round2_propagation.py`
- `round2_legacy_anchors.py`
- `round2_remaining_sources.py`
- `round2_package.py`
- `round2_remaining_package.py`

The machine-readable gate and signal-domain matrices are the controlling evidence.
