# S12 Stage J Three-Vehicle Acoustic Identity Implementation Plan

> Luna must use isolated git worktree, TDD, executing-plans/subagent-driven-development, and verification-before-completion.

**Goal:** Build independent, event-driven acoustic identity candidates for C63 W204, GT-R R35, and Lexus LFA, then publish louder named review copies for Jovi.

**Architecture:** Existing Stage C is the immutable baseline. Stage J candidate rendering uses new v2 sources and candidate overlays before the shared Pre-PTR/frozen PTR boundary. Formal metrics use the normal `-16 LUFS / -1.5 dBFS` PCM; only named review copies request linear gain `1.25` (`+1.938200260161128 dB`) with a common peak-safe cap.

## Global constraints

- Base commit: `d8b8c24530eafc354d420c95e1ff071034e51707`; branch: `agent/s12-stage-j-three-vehicle-identity`.
- Vehicles: `c63_w204`, `gtr_r35`, `lfa`; stock-clear-balanced, synthetic, uncalibrated, not OEM reproduction.
- Do not modify FVM, PTR, Radiation, Runtime, Android/ESP32, MATLAB/Simulink, Track-P guard, public EQ/LF/Rumble, loudness manager, or existing vehicle bytes.
- Existing target JSON and SHA are numeric truth; B/R2 references are relative only. Do not download or ingest new audio.
- `candidate=None` must be Stage C bit-identical; every tunable parameter must report real `active/inactive/unused` usage.
- Do not claim Human PASS, Approved Profile, calibrated, OEM reproduction, push, merge, or Simulink integration.

## Tasks

### J0 — Freeze baseline and evidence

Run the exact base/clean/branch/remote checks, focused Stage I, full S12, Track-P, and `git diff --check`; save actual output and SHA-256 of Stage I evidence. Stop on drift.

### J1 — Reconcile references

Create a three-vehicle target matrix. Treat the target JSON as numeric authority. Correct the contradictory LFA idle-centroid note and verify GT-R bank-angle facts against an official source before encoding them. Keep all external sources qualitative and record provenance.

### J2 — Candidate contracts

Create `stage_j/{candidate_profiles,render_candidate,perceptual_metrics,reference_distance,feedback_contract,named_review}.py`, `stage_j_candidate_profile.schema.json`, and three v1 candidates. Add exact-key schema, finite/range/provenance/base-SHA/reference-SHA checks, locked-layer fingerprints, and parameter usage instrumentation.

### J3 — Independent sources

Create `mercedes_na_v8_source_v2.py`, `nissan_twin_turbo_v6_source_v2.py`, and `lexus_high_rev_v10_source_v2.py` with RED tests first. C63 must use cross-plane bank/event timing and event-driven NA bark; GT-R must use twin turbo state, wastegate/lift, and DCT interruption; LFA must use 5/10/15 RPM-tracked V10 orders and event-excited intake modes, never fixed-tone/high-shelf scream.

### J4 — Qualification

Use final PCM, fixed four bands, idle/acceleration/afterfire windows, the existing distance formula, no-worse state rule, identity separation, order tracking, turbo correlation, PCM24/peak/clipping, deterministic SHA, and eight-vehicle isolation. Failed automatic candidates remain diagnostic-only.

### J5 — Named review package

Generate Stage C baseline and Stage J candidate 60-second cycles plus identity/shift/lift diagnostic stems, plots, metrics, feedback CSV, README, manifest, and SHA sums under `E:\Tesla_speed\review_packages\s12-stage-j-three-vehicle-identity-v1\`. Apply the common review gain request `1.25`; cap by `-1.5 dBFS`, record requested/applied/headroom-limited values, and never alter formal PCM metrics.

### J6 — Feedback loop

Stop at `WAITING_FOR_JOVI_STAGE_J_NAMED_REVIEW` or `PARTIAL / AUTOMATED_GATE_FAIL + UNQUALIFIED_DIAGNOSTIC_ONLY`. After real feedback, allow v1→v2→v3, one failed vehicle at a time, with other vehicle PCM SHA unchanged. Stop after three failed rounds with `PARTIAL / HUMAN_AUDITION_FAIL`.

### J7 — Reports, Obsidian, commits

Write Stage J report/evidence, update `tasks/todo.md` and `tasks/lessons.md`, add the Stage J Obsidian note and update project/vehicle cards. Commit tests, each source, package/report/docs separately. Keep all commits local.

## Required verification

Run all Stage J focused tests, full `tools/sound_sim/s12/tests` plus acoustic tests, Track-P guard script and pytest, `git diff --check`, JSON finite/duplicate-key validation, manifest SHA verification, and final clean-status/HEAD/remote checks. Report actual counts; never reuse historical counts.
