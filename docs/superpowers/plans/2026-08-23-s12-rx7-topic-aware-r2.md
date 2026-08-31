# S12 主题化听审与 RX-7 清洁参考 R2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Add explicit Chinese listening topics and publish a separate, auditable RX-7 R2 comparison package with one bounded candidate parameter group.

**Architecture:** Keep the existing Dashboard and historical R3 packages immutable as baselines. Add an optional/required-for-new-export `focus_topics` field to vehicle feedback, then build a standalone RX-7 package from the external audited `rx7sim` recordings and an externally rendered Stage-G candidate; merge only metadata and professional receipts into Git.

**Tech Stack:** Python 3, NumPy/SciPy, existing S12 Stage-G renderer, MATLAB R2026a Audio Toolbox, MoSQITo 1.2.1, static HTML/JavaScript, Playwright, pytest.

## Global Constraints

- Raw/copyright audio remains under `E:\Claude_allow\Download`; no WAV/FLAC/OGG/MP4 enters Git.
- RX-7 source remains R2 only: CC BY-NC-SA 4.0, non-commercial, no synchronized RPM/load/throttle/gear/shift.
- `ORDER_COMPARISON_NOT_QUALIFIED`, `automatic_tuning_eligible=false`, and `profile_candidate_ready=false` remain true.
- Do not modify FVM, PTR, Radiation, Runtime, Android, Simulink, MATLAB core, or Track-P frozen files.
- Do not loop, pad, silence-fill, gain-match, EQ, AGC, or resample analysis/reference audio.

---

### Task 1: Lock the topic feedback contract with tests

**Files:**
- Modify: `tools/sound_sim/s12/tests/test_s12_guided_feedback.py`
- Modify: `tools/sound_sim/s12/tests/test_s12_professional_dashboard.py`
- Modify: `tools/sound_sim/s12/real_reference/professional_guided_feedback.py`

**Interfaces:**
- `focus_topics: list[str]` is accepted in v2/v3 vehicle rows; new v3 export requires at least one allowed topic.
- Allowed topics are the seven exact Chinese labels in the design spec.
- Canonical receipts preserve `focus_topics` and set `legacy_feedback_without_topics=true` only for old rows that omit it.

- [ ] Write tests for valid topics, unknown topics, empty v3 topics, and v2 backward compatibility.
- [ ] Run `python -m pytest tools/sound_sim/s12/tests/test_s12_guided_feedback.py tools/sound_sim/s12/tests/test_s12_professional_dashboard.py -q` and observe the new tests fail before implementation.
- [ ] Implement validation and canonicalization without changing audio/SHA/order gates.
- [ ] Re-run the same focused command; expect all tests to pass.

### Task 2: Add Chinese theme controls to both Dashboard pages

**Files:**
- Modify: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/dashboard.js`
- Modify: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/dashboard.css`
- Modify: `tools/sound_sim/s12/tests/dashboard_playwright_smoke.py`

**Interfaces:**
- `window.S12Dashboard.exportFeedback()` emits `focus_topics` for each vehicle row.
- `renderFeedback(pair)` displays clickable `.topic-chip` controls and a read-only `当前窗口主题` line derived from `pair.scenario`.

- [ ] Add a failing Playwright assertion that topic chips exist and the export button stays disabled until one topic is selected per vehicle.
- [ ] Implement topic state collection, rendering, and Chinese scenario-to-topic labels while keeping one submit button.
- [ ] Verify both `index.html` and `long_window.html` export topic arrays of known labels with Playwright.

### Task 3: Build the external RX-7 R2 package and candidate

**Files:**
- Create: `tools/sound_sim/s12/real_reference/rx7_topic_r2.py`
- Create: `tools/sound_sim/s12/tests/test_s12_rx7_topic_r2.py`

**Interfaces:**
- `build_rx7_topic_package(output_root: Path, source_root: Path, candidate_root: Path) -> dict[str, Any]` refuses non-empty output and paths outside `E:\Claude_allow\Download`.
- The returned manifest contains 5 pairs, `reference_class=R2`, native durations, source/license SHA, `parameter_group=rotary_housing_turbo_distribution`, and the bounded candidate payload.

- [ ] Write failing tests for path boundary, five-record manifest, no padding, one parameter group, and locked layers.
- [ ] Implement deterministic candidate profile copy, parameter overrides, native-length candidate rendering, SHA manifest, and provenance report; store all media externally.
- [ ] Run the focused RX-7 package tests and reopen every generated WAV with `scipy.io.wavfile`; expect PASS.

### Task 4: Run professional metrics and build the Chinese RX-7 comparison page

**Files:**
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/rx7_topic_r2.html`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/rx7_topic_r2_data.js`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/rx7_topic_r2_report.md`
- Create: `tasks/reports/runtime/S12_Professional_Comparison_Dashboard_v1/rx7_topic_r2_results.json`
- Modify: `tools/sound_sim/s12/tests/dashboard_playwright_smoke.py`

**Interfaces:**
- `rx7_topic_r2_results.json` merges the package manifest, Legacy Proxy metrics, MATLAB receipt, MoSQITo receipt, and `ORDER_COMPARISON_NOT_QUALIFIED`.
- The page uses the same `dashboard.css` visual language but has its own five-pair data and displays source license and theme availability.

- [ ] Run the RX-7 package builder, Legacy Proxy analysis, MATLAB runner, and MoSQITo runner into fresh external receipt directories.
- [ ] Validate and merge receipts; reject any SHA mismatch or missing professional metric.
- [ ] Generate the page/data/report with no embedded audio bytes.
- [ ] Add Playwright smoke for five players, topic labels, duration/SHA gates, and disabled Order claims.

### Task 5: Full verification and GitHub handoff

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/lessons.md`

- [ ] Run topic/RX-7 focused tests, both existing Dashboard smokes, `node --check`, `compileall`, JSON finite validation, and `git diff --check`.
- [ ] Run full `python -m pytest tools/sound_sim/s12/tests -q`, Track-P pytest, and `assert_track_p_unchanged.py`; record actual counts.
- [ ] Confirm staged names contain no raw media and local/remote branch SHA match after push.
- [ ] Commit in small logical commits and push `agent/s12-stage-q-real-reference-calibration`.
