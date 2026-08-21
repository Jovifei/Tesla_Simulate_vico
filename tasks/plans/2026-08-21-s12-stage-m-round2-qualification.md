# S12 Stage M Round-2 Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Independently audit the eight Stage-K Round-2 candidates, make qualification and comparison evidence reproducible, and stop at a valid named-feedback gate.

**Architecture:** Add a small Python `stage_m` evidence layer beside `stage_k`. It consumes only actual arrays, trace windows, unaltered final PCM, manifests and SHA records; review-gain WAVs are audition-only. It writes only new evidence under `tasks/reports/runtime/s12-stage-m-round2-qualification/`.

**Tech Stack:** Python, NumPy, pytest, `wave`, `zipfile`, `hashlib`; existing Stage-K renderer and Track-P guard.

## Global Constraints

- Worktree `E:\Tesla_speed\worktrees\s12-stage-m-round2-qualification`, branch `agent/s12-stage-m-round2-qualification-comparator`, base `5e316934536b0cd018d286daa720422afb338c8c`.
- No merge, push, PR, Profile Freeze, MATLAB/Simulink/Runtime/Android, OEM claim, sealed-key access, historic-package overwrite, or Track-P change.
- Remain fail-closed as `PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY` without newly measured passing evidence and a valid Jovi named response.

### Task 1: M0 baseline and M1 replay

**Files:** create `S12_Stage_M_Baseline_Audit.md` and `stage_m_replay_evidence.json` in the Stage-M runtime directory; modify `tasks/todo.md`.

- [ ] Record HEAD, branch, `origin/main`, status, diff check, worktrees, submodules and untracked files; assert HEAD `5e316934...` and origin/main `c08eb4c...`.
- [ ] Replay focused Round-2, all Stage-K, Track-P pytest/guard, diff check, and both package validations fresh.
- [ ] Reopen each delivered WAV and verify 48 kHz, stereo, PCM24, finite, unclipped, manifest frames/duration/SHA, and ZIP CRC.

### Task 2: M2 call graph and gate-origin matrix

**Files:** create `stage_m/__init__.py`, `stage_m/callgraph.py`, `tests/test_s12_stage_m_callgraph.py`, `S12_Stage_M_Qualification_Callgraph.md`, `stage_m_gate_source_matrix.json`.

- [ ] RED: reject a hard gate sourced from diagnostics, a review-gain copy, a missing trace window, or an unbound final-PCM/reference comparison.
- [ ] GREEN: `audit_qualification_callgraph() -> dict[str, object]` maps candidate grid → renderer → source metrics → final PCM → reference → gates → regression/search → package/manifest, identifying origin/domain/window/fail-closed status.
- [ ] Report all ten M2 questions, including whether reference distance actually reaches a hard gate.

### Task 3: M3 eight-vehicle attribution

**Files:** create `stage_m/attribution.py`, `tests/test_s12_stage_m_attribution.py`, `stage_m_eight_vehicle_failure_attribution.json`, `S12_Stage_M_Automated_Gate_Diagnosis.md`.

- [ ] RED: a missing/misaligned reference cannot be portrayed as vehicle deterioration.
- [ ] GREEN: `attribute_vehicle_failure(...)` emits target, actual parent/candidate values, absolute error, relative improvement, gate result, nonempty categories A–J, evidence, and next action.
- [ ] Serialize Ferrari, Hellcat, RX-7, Supra, Aventador, C63, GT-R and LFA deterministically without changing thresholds, targets, or scenes.

### Task 4: M4 comparator and report writer

**Files:** create `stage_m/comparator.py`, `stage_m/report.py`, `scripts/qualify_stage_m_round2.py`, `tests/test_s12_stage_m_comparator.py`, `stage_m_comparator_results.json`.

- [ ] RED: reject review-gain signal for analysis; require upper-band warning and trace-aligned events.
- [ ] GREEN: `compare_pcm(unaltered_pcm, trace, sample_rate_hz, *, audition_pcm=None)` produces the eight required bands, idle modulation/pulse/crest/centroid/roughness/fluctuation, acceleration ridge/envelope/attack/load, shift timing/dip/impact/recovery, and lift event timing/state/centroid/bandwidth/decay.
- [ ] Flag 5.5–12 kHz as upstream perceptual compensation outside validated radiation band; output residual/radar vectors, not a total realism score.

### Task 5: M5 named feedback and M7 matrix

**Files:** create `stage_m/feedback.py`, `tests/test_s12_stage_m_feedback.py`, `stage_m_human_feedback_receipt.json`, `stage_m_gate_matrix.json`, `S12_Stage_M_Profile_Freeze_Review.md`.

- [ ] RED: absent CSV, duplicate answer, unknown file, SHA mismatch, and blank scores all reject without human pass.
- [ ] GREEN: `validate_named_feedback(path, manifests)` validates exact Stage-M schema and IDs/SHA; `build_gate_matrix(...)` uses only the five prescribed status enums.
- [ ] Without Jovi input, emit `WAITING_FOR_JOVI_NAMED_REVIEW`, `content_read=false`, `human_pass=false`, and all `DIAGNOSTIC_ONLY`; do not create an approved profile candidate.

### Task 6: Verify, commit locally, stop bounded

**Files:** create `S12_Stage_M_Round2_Qualification_Report.md` and `stage_m_artifact_manifest.json`; modify `tasks/todo.md`.

- [ ] Re-run M1 plus all S12 Python regression, package/WAV/CRC validation, Track-P guard and `git diff --check`; report actual command outputs and Git state.
- [ ] Commit coherent audit, comparator, and feedback/report units locally. Do not push or merge.
- [ ] Stop at `WAITING_FOR_JOVI_NAMED_REVIEW` unless Jovi supplies valid named feedback; M6/M8 require that external input.

## Plan Review

- M0–M5/M7 are covered. M6/M8 are intentionally deferred until a valid named feedback file exists.
- Formal analysis is bound to unaltered final PCM or actual arrays/trace; review copies cannot enter gate calculations.
