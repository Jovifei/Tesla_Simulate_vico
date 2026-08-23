# S12 Stage U True Comparator-Driven Acoustic Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Each task has a regression gate before the next task.

**Goal:** Render and compare Reference/Parent/Candidate grids with measurable professional before/after evidence, reject unclean/unreachable/incompatible inputs, and publish a three-player ABX review package.

**Architecture:** Add a Track-S-only Stage U orchestration layer under `tools/sound_sim/s12/real_reference/`. It consumes existing Stage-G candidate renderers and Stage-N/Professional metrics without changing frozen cores. All audio packages are generated outside Git; repository outputs are receipt metadata, schemas, reports and the review-page source.

**Tech Stack:** Python 3 + NumPy/SciPy, existing S12 Stage-G renderers, MATLAB R2026a Audio Toolbox, MoSQITo 1.2.1 isolated venv, Silero VAD, AudioCommons timbral_models isolated venv, optional OpenL3, static HTML/JS, Playwright, pytest.

## Global Constraints

- Base commit must stay `b1d500c7c37a71728020c39e6dc115a0cd6743d5` until Stage U commits start.
- No raw reference or candidate audio enters Git.
- FVM/PTR/Radiation/Runtime/Android/Simulink/Track-P, R1 qualification and Stage-N receipts remain unchanged.
- No Order/event timing optimisation without real synchronized state.
- Every candidate must differ in SHA from its Parent and retain a complete requested/consumed parameter receipt.

---

### Task 1: Baseline and reference-quality gates (U0–U1)

**Files:**
- Create: `tools/sound_sim/s12/real_reference/stage_u_baseline.py`
- Create: `tools/sound_sim/s12/real_reference/stage_u_reference_quality.py`
- Create: `tools/sound_sim/s12/tests/test_s12_stage_u_baseline.py`
- Create: `tools/sound_sim/s12/tests/test_s12_stage_u_reference_quality.py`

**Interfaces:**
- `audit_stage_u_baseline(repo_root: Path) -> dict[str, Any]`
- `validate_reference_quality(records: Sequence[Mapping[str, Any]], vad: Callable) -> list[dict[str, Any]]`
- A rejected speech record has `status="REFERENCE_SPEECH_CONTAMINATED"`; a trace mismatch has `status="SCENARIO_NOT_COMPARABLE"`.

- [ ] Write failing tests for baseline state, continuous speech rejection, missing SHA, incompatible scene and same-candidate multi-scene rejection.
- [ ] Implement baseline audit and VAD/quality contract without rendering any candidate.
- [ ] Run `python -m pytest tools/sound_sim/s12/tests/test_s12_stage_u_baseline.py tools/sound_sim/s12/tests/test_s12_stage_u_reference_quality.py -q`; expect PASS.

### Task 2: Feature adapters and restricted DTW (U2)

**Files:**
- Create: `tools/sound_sim/s12/real_reference/stage_u_features.py`
- Create: `tools/sound_sim/s12/real_reference/run_stage_u_audio_features.m`
- Create: `tools/sound_sim/s12/tests/test_s12_stage_u_features.py`

**Interfaces:**
- `extract_stage_u_features(signal, sample_rate_hz, scenario_id, state_window) -> dict[str, Any]`
- `bounded_dtw(reference_features, candidate_features, reference_context, candidate_context) -> dict[str, Any]`
- Optional third-party outputs must include `OPTIONAL_RESEARCH_METRIC`, version/commit and `NOT_HARD_GATE`.

- [ ] Write failing fixture tests for identical audio, −6 dB gain, high shelf, low pass, 70 Hz AM and cross-scenario DTW rejection.
- [ ] Implement raw feature contracts and MATLAB feature receipt runner; install optional environments only under approved external roots.
- [ ] Run focused feature tests and validate explicit unsupported/optional statuses.

### Task 3: Renderer parameter mappings and reachability (U3)

**Files:**
- Modify: `tools/sound_sim/s12/acoustic_identity_v015/stage_g/candidate_profiles.py`
- Modify: `tools/sound_sim/s12/acoustic_identity_v015/stage_f/render_candidate.py`
- Modify: `tools/sound_sim/s12/acoustic_identity_v015/sources/rotary_turbo_source.py`
- Create: `tools/sound_sim/s12/real_reference/stage_u_reachability.py`
- Create: `tools/sound_sim/s12/tests/test_s12_stage_u_reachability.py`

**Interfaces:**
- `probe_parameter_reachability(vehicle_id, scenario, parameter_id, minus, baseline, plus) -> ReachabilityRecord`
- Ferrari abstract controls map to explicit metallic/mid/texture source/stem overrides.
- Hellcat abstract controls map to pressure/blower/intake overrides.
- RX-7 provides true `rotary_pulse_width_scale` width semantics and one housing control (`housing_gain_scale`, `housing_decay_scale`, or `housing_order_weight_scale`).

- [ ] Write failing single-variable tests for all three vehicle parameter groups and an unreachable-parameter rejection.
- [ ] Implement only Track-S override paths and parameter usage receipts; leave frozen layers untouched.
- [ ] Run reachability tests; reject the grid if any requested parameter is unused or affects non-target stems beyond contract.

### Task 4: External grid rendering and integrity gates (U4)

**Files:**
- Create: `tools/sound_sim/s12/real_reference/stage_u_grid.py`
- Create: `tools/sound_sim/s12/tests/test_s12_stage_u_grid.py`

**Interfaces:**
- `render_candidate_grid(qualified_records, reachability, output_root) -> dict[str, Any]`
- Each record contains Parent/Candidate WAV+PCM SHA, trace SHA, stems, health, usage and vehicle isolation SHA.

- [ ] Write failing tests for Parent=Candidate, missing usage, clipping, wrong-condition events and candidate reused for incompatible scenarios.
- [ ] Implement deterministic per-scenario Parent/Candidate rendering with at most 64 candidates/vehicle under `E:\Claude_allow\Download`.
- [ ] Reopen WAVs and verify all hard gates before emitting candidate-grid metadata.

### Task 5: Triad professional comparison and selection (U5–U6)

**Files:**
- Create: `tools/sound_sim/s12/real_reference/stage_u_comparator.py`
- Create: `tools/sound_sim/s12/real_reference/stage_u_selection.py`
- Create: `tools/sound_sim/s12/tests/test_s12_stage_u_comparator.py`
- Create: `tools/sound_sim/s12/tests/test_s12_stage_u_selection.py`

**Interfaces:**
- `compare_reference_parent_candidate(record) -> TriadComparisonRecord`
- `select_candidates(triad_results) -> dict[str, Any]`
- Result states include `NO_MEASURABLE_IMPROVEMENT` rather than a forced winner.

- [ ] Write failing tests for identical distance, gain/timbre separation, no-improvement rejection and qualifying median/worst-case selection.
- [ ] Merge raw professional and optional descriptor metrics; create separate loudness-matched audition copies with their own SHA.
- [ ] Run selection tests and require 2/3 Ferrari/Hellcat or 3/5 RX-7 clean-reference improvement before publication.

### Task 6: Three-player ABX package and Stage U report (U7)

**Files:**
- Create: `tools/sound_sim/s12/real_reference/stage_u_review_package.py`
- Create: `tasks/reports/runtime/s12-stage-u-true-regression/S12_Stage_U_True_Regression_Report.md`
- Create: `tasks/reports/runtime/s12-stage-u-true-regression/*.json`
- Create: `tasks/reports/runtime/s12-stage-u-true-regression/Jovi_Reference_Parent_Candidate_Review/index.html`
- Create: `tools/sound_sim/s12/tests/test_s12_stage_u_review_package.py`

**Interfaces:**
- Review page has Reference/Parent/Candidate players plus randomised Parent/Candidate ABX and binds each result to SHA.
- The package emits the final files named in the Stage U specification.

- [ ] Write failing Playwright tests for duration/canplaythrough/SHA, different Parent/Candidate SHA and required professional receipts.
- [ ] Implement the external audio package and repository-only review metadata/page.
- [ ] Verify the review page against generated external audio and export a fail-closed Jovi response JSON.

### Task 7: Full regression, audit and GitHub handoff (U8)

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/lessons.md`

- [ ] Run Stage U focused, Stage N professional, Stage Q/R/S, full S12, Track-P guard, JSON/WAV/ZIP/SHA validation and `git diff --check`.
- [ ] Verify staged names contain no raw media, check exact frozen file/symbol summaries, commit only after evidence exists.
- [ ] Push `agent/s12-stage-u-true-comparator-calibration` and verify local/remote SHA equality.
