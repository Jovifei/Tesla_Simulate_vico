# S12 Stage W v27 External Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rejected in-place v26 resume path with concise, independently verifiable v27 architecture stages and one atomic final directory publication.

**Architecture:** Existing `run_hellcat_bakeoff()` remains unchanged. A small stage renderer produces one complete architecture tree per new external stage root. A focused v27 pipeline verifies those trees, assembles an external build root, runs the unchanged strict final validator, and atomically renames the build root to a new v27 final root only after success. v25/v26 remain immutable historical attempts.

**Tech Stack:** Python 3.14, NumPy, pytest, PowerShell/Windows filesystem operations.

## Global Constraints

- Worktree: `E:/Tesla_speed/worktrees/s12-stage-w-ecosystem-bakeoff`.
- Preserve all owner `.gitignore`/Task6D–H logs and v25/v26 bytes; never use v25/v26 as v27 input.
- Keep `run_hellcat_bakeoff` signature, default behavior and strict `validate_bakeoff_manifest` inventory unchanged.
- v27 evidence remains synthetic, uncalibrated, vehicle-inspired, `REFERENCE_TARGET_MISSING`, `REFERENCE_POINTER_ONLY`, `selected_architecture=null`, not R1/W10/Profile Freeze/OEM qualified.
- Stage roots, stage manifests, build roots and assembly receipts are outside the named v27 final root. Only a validator-clean build root may be published by one directory rename.
- No change to PTR/radiation, Stage V, Track-P/frozen PTR, external media, Vault, push, merge or PR.

---

### Task 1: Remove the superseded in-place v26 API

**Files:**

- Modify: `tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py`
- Modify: `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff.py`
- Modify: `tasks/reports/runtime/s12-stage-w/checkpoints/README.md`

- [ ] **Step 1:** Using a reversible `git revert --no-commit` of only commits `c59400a`, `f59eae6`, and `1cbb0a7`, restore these three files byte-for-byte to their `f4a5198` versions. Do not touch `.gitignore`, logs, design/plan docs or runtime roots.
- [ ] **Step 2:** Verify `git diff --no-index`/hashes against `git show f4a5198:<path>`, run the pre-existing bakeoff/validator focused suite, compileall and `git diff --check`.
- [ ] **Step 3:** Commit only the three restored files as `refactor: remove superseded v26 resume path`.

### Task 2: Add a single-architecture external stage renderer

**Files:**

- Modify: `tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py`
- Modify: `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_bakeoff.py`

**Interface:** `render_hellcat_architecture_stage(stage_root, architecture, duration_s=8.0, *, long_window=False, parent_stage_root=None) -> dict[str, Any]`.

- [ ] **Step 1:** Write RED tests for P1 stage completion, candidate requiring verified P1 stage, wrong/non-empty stage rejection, exact twelve-scene stage manifest and P1 parent PCM binding.
- [ ] **Step 2:** Implement the helper using existing `_write_case`, `build_hellcat_bakeoff_trace`, `read_pcm24_wav`, `sha256_file` and `write_json`; write only case trees plus an external-to-final `stage_manifest.json`. Candidate stage must read verified P1 post-PTR PCM scene-by-scene.
- [ ] **Step 3:** Run the new focused tests RED→GREEN, existing bakeoff/validator tests, compileall and diff check; commit only source/test files as `feat(s12): add external architecture stage renderer`.

### Task 3: Add v27 stage verification, assembly and atomic publication

**Files:**

- Create: `tools/sound_sim/s12/acoustic_identity_v015/stage_w/v27_pipeline.py`
- Create: `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_v27_pipeline.py`
- Modify: `tools/sound_sim/s12/acoustic_identity_v015/stage_w/__init__.py` only if existing exports require it.

**Interfaces:**

- `verify_architecture_stage(stage_root, architecture, duration_s, long_window, *, parent_stage_root=None) -> dict[str, Any]`
- `assemble_v27_bakeoff(final_root, stage_roots: Mapping[str, Path], duration_s=8.0, *, long_window=False) -> dict[str, Any]`

- [ ] **Step 1:** Write RED tests for missing/duplicate/tampered stage rejection, wrong duration/long-window rejection, absent-final-root preservation, and final root with no stage/receipt extras.
- [ ] **Step 2:** Implement stage manifest/case verification by reusing existing strict case checks; create a unique external build root; move only verified architecture directories into it; reconstruct the existing five summaries and standard manifest; require `validate_bakeoff_manifest(build_root) == []`.
- [ ] **Step 3:** Publish via one `os.replace(build_root, final_root)` only when `final_root` is absent and validator is clean. Leave failed external build roots for diagnosis; never delete v25/v26.
- [ ] **Step 4:** Run v27 pipeline tests, existing bakeoff/validator tests, compileall and diff check; commit source/tests as `feat(s12): add atomic v27 stage publication`.

### Task 4: Generate bounded v27 evidence

**Files:**

- Create ignored external stage roots under `tasks/reports/runtime/s12-stage-w/v27_stages_<run-id>/`.
- Create ignored external build/final roots `bakeoff_final_remediation_v27/` and `migration_final_remediation_rx7_v27/`, `migration_final_remediation_ferrari_v27/`.
- Create logs under `tasks/reports/runtime/s12-stage-w/logs/task6m_v27_*.log`.

- [ ] **Step 1:** Render P1 once to a fresh stage root with `duration_s=0.20,long_window=True`; record command/PID/start/end/exit and verify stage.
- [ ] **Step 2:** Render P2, P2H, P3 and P5 once each in separate fresh stage roots using the verified P1 stage; verify each before assembly. Do not retry a failed stage without a new diagnosis.
- [ ] **Step 3:** Assemble and publish exactly one v27 final root; require Hellcat duration map `hot_idle_20s=20.0`, `complete_cycle_60s=60.0`, all others `0.20`, strict validator `[]`, complete nested SHA and null selection.
- [ ] **Step 4:** Generate RX-7 and Ferrari v27 migration roots once at `duration_s=0.20`; require their existing migration validators `[]` and preserve unselected status.

### Task 5: Current verification and governed closure

**Files:**

- Modify current Stage W receipts/state/resume/W9/artifact/package/usage/Obsidian repo mirror only after v27 evidence passes.
- Create exact runtime verification logs and Task 6M report.

- [ ] **Step 1:** Run strict v27 validators, finite JSON, WAV reopen/format/clipping, nested SHA, click/afterfire/parameter gates, Task5A/B and Task6A/B/C affected suites, slow 3000, Stage-W/V focused, compileall and Track-P/diff sequentially.
- [ ] **Step 2:** Bind metadata to the v27 final root/current source head; keep selection null and all R1/W10/Profile Freeze/Vault gates fail-closed.
- [ ] **Step 3:** Obtain Task 6M and whole-branch independent reviews, then parent-owned full S12 and Codex-memory Vault sync. No push/merge/PR.

## Plan Review

- Spec coverage: superseded API removal, stage rendering, verified parent binding, strict assembly, atomic publication, v27 evidence, migrations and governed closure are explicit.
- Placeholder scan: no unresolved implementation markers remain.
- Interface consistency: Task 2's stage helper supplies the exact stage roots consumed by Task 3, and Task 3's final root is the sole input to Task 5 metadata.
