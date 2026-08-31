# S12 Stage M Qualification Call Graph

## M2 machine-readable answers

1. **hard_gate_data_source** — The ten REQUIRED_FULL_GATES are caller-supplied metrics: source-array, trace, final-PCM and isolation checks. reference_distance is not among them.
2. **actual_arrays_and_trace** — Named event and band metrics originate in actual source arrays; event eligibility is bound to trace windows. pressure_accounting and PCM/isolation checks have their stated non-trace origins.
3. **domain_mixing** — Source, final-PCM and audition domains are separately labeled. Stage M rejects diagnostic/review/unbound sources as hard-gate evidence.
4. **formal_vs_review_copy** — Formal PCM follows frozen_ptr -> edge_fade -> fixed whole-cycle gain -> PCM24. The 1.25x comfort/review copy is post-PCM audition-only.
5. **reference_distance_hard_gate** — No. reference_distance is neither recomputed by candidate_search nor required by REQUIRED_FULL_GATES; it is a post-gate rank input.
6. **diagnostic_package_on_failure** — Round-2 package builders intentionally serialize transport-valid diagnostic evidence when automatic gates fail, preserving investigation without declaring qualification.
7. **best_failing_candidate** — Yes for diagnostics only: run_round2_coordinate_search returns snapshots[-1] as BEST_DIAGNOSTIC_ONLY when no qualified snapshot exists. rank_round2_snapshots never calls it qualified.
8. **baseline_candidate_trace_window_rate_chain** — Package receipts bind each vehicle's formal parent/candidate to one canonical trace SHA and 48 kHz PCM chain; no raw external recording/window exists to prove an external-reference equivalence.
9. **loudness_copy_raw_analysis** — No. loudness_matched_audition_signal is forbidden by the comparator and signal-domain matrix for raw band, loudness, and transient analysis.
10. **named_events_actual_stems** — Yes. The R2 receipts cite actual named source arrays plus trace alignment; e.g. LFA lfa_shift_exhaust_reengagement, Ferrari shift_recovery_boom, RX-7 blow_off, Supra spool_release and Aventador V12 re-engagement.

## Call graph

```text
parameter_grid -> renderer_source_overlay -> source_stems -> source_metrics
                                   -> common_acoustic_layers -> frozen_ptr -> final_pcm -> analysis_copy
                                                                                 -> review_gain_copy (audition only)
source_metrics + final_pcm + state_regression -> hard_gates -> candidate_search -> selected_candidate -> review_package -> status_manifest
reference_distance ---------------------------> candidate_search (rank input only; not a required hard gate)
```

## Source files audited

- `stage_k/candidate_search.py`
- `scripts/qualify_stage_k_candidates.py`
- `stage_k/round2_propagation.py`
- `stage_k/round2_legacy_anchors.py`
- `stage_k/round2_remaining_sources.py`
- `stage_k/round2_package.py`
- `stage_k/round2_remaining_package.py`

The machine-readable gate and signal-domain matrices are the controlling evidence.
