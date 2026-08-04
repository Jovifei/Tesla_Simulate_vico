# S12 Acoustic Realism Phase Review 2026-08-04 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a self-contained reviewer package that distinguishes verified synthetic S12 acoustic work, pending human-audition work, and the exact next optimization decisions.

**Architecture:** The package is evidence-first. It copies the formal 30-second continuous drive-cycle artifacts unchanged, snapshots the exact pre-PTR source/layer/publisher/test code used to make them, and adds one Markdown report that ties every claim to current metrics, Git state, and explicit scope boundaries.

**Tech Stack:** Python 3 standard library, NumPy-generated PCM24 artifacts, PowerShell `Compress-Archive`, SHA-256, existing S12 reports and JSON metrics.

## Global Constraints

- Do not modify FVM, PTR core, Radiation Boundary, Runtime latency framework, Android protocol, MATLAB, Simulink, or vehicle-source parameters.
- Keep all conclusions `synthetic / uncalibrated / not OEM reproduction`; automated results remain distinct from Jovi's human audition.
- Do not overwrite the formal drive-cycle package; create a separate dated review package.
- Include only user-scoped project code/artifacts; do not include raw reference media, secrets, caches, or generated Python bytecode.
- Archive must include the three official 30-second WAVs, plots, JSON metrics, reports, code snapshots, a content manifest, and archive SHA-256.

### Task 1: Capture reviewer evidence

**Files:**
- Read: `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-v10-complete-drive-cycle-30s\**`
- Read: `E:\Tesla_speed\worktrees\s12-v12\tools\sound_sim\s12\acoustic_identity_v015\**`
- Read: `E:\Tesla_speed\tasks\todo.md`, `tasks\lessons.md`, and relevant Obsidian project note.
- Create: `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-phase-review-2026-08-04\review_evidence.json`

- [x] Run read-only WAV, JSON, manifest, Git, frozen-adapter, and output-size checks.
- [x] Record exact durations, codec, loudness, peaks, clipping, afterfire counts/energy, fixed gains, relevant source parameters, test totals, Git state, and known evidence gaps.
- [x] Reject any claim whose evidence is not available in the current workspace.

### Task 2: Write the stage review and correction reflection

**Files:**
- Create: `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-phase-review-2026-08-04\S12_Acoustic_Realism_Phase_Review_2026-08-04.md`

- [x] Explain the objective and architecture in plain language.
- [x] List completed mechanisms, formal artifacts, metrics, current parameters, and source-code responsibilities.
- [x] Separate automated PASS, human-review evidence, blocked/prohibited work, and unverified assumptions.
- [x] Analyse Jovi's current Hellcat feedback: identity cue partially succeeds; actual listening loudness remains unverified even though the delivered digital file is -16 LUFS with no clipping.
- [x] Give ranked, authorization-gated next optimization options with exact success criteria and no automatic code change.

### Task 3: Build the compressed reviewer package

**Files:**
- Create: `E:\Tesla_speed\tasks\reports\runtime\s12-acoustic-realism-phase-review-2026-08-04\package_manifest.json`
- Create: `E:\Tesla_speed\tasks\reports\runtime\S12_Acoustic_Realism_Phase_Review_2026-08-04.zip`
- Create: `E:\Tesla_speed\tasks\reports\runtime\S12_Acoustic_Realism_Phase_Review_2026-08-04.zip.sha256`

- [x] Copy formal Ferrari/Hellcat/RX-7 drive-cycle WAVs, metrics JSON, spectrograms, order maps, publication report, and its verified manifest without rewriting their bytes.
- [x] Copy the exact publisher, source models, idle/afterfire/low-frequency/loudness layers, analysis metrics, and regression test into `code_snapshot/`.
- [x] Produce a SHA-256 manifest over all package contents before compression.
- [x] Compress only the staged review directory into the dated ZIP.

### Task 4: Verify the handoff

**Files:**
- Modify: `E:\Tesla_speed\tasks\todo.md`

- [x] Re-open the ZIP and verify every manifest member exists with the recorded SHA-256.
- [x] Verify the ZIP SHA-256 receipt, three WAV paths, report path, code snapshot, no source-tree modifications beyond explicitly recorded report/ledger files, and archive file count.
- [x] Record package location, verification result, and the user-audition/authorization boundary in the task ledger.

## Completion Review

- Final ZIP: `E:\Tesla_speed\tasks\reports\runtime\S12_Acoustic_Realism_Phase_Review_2026-08-04.zip` (`27,436,121` bytes); SHA-256 `d0232c1e773ae47d90eb0526aad0d28d2f946b447929e7d3a5bbec730564c781`.
- The ZIP has 44 entries: 42 manifest-governed files plus `package_manifest.json` and one directory entry. All 42 SHA-256 values recompute exactly. It contains three expected 30-second WAVs totaling `25,920,150` bytes and has no raw-media/cache entries.
- The report records Jovi's current Hellcat feedback but intentionally makes no audio parameter or source-code change. Human audition and next-step authorization remain open.

## Plan Review

- Spec coverage: stage summary, completed/pending/blocked split, reflection, exact audio/parameters, code snapshot, and compressed document are covered by Tasks 1–4.
- Boundary coverage: no source audio or parameter change occurs; review evidence explicitly avoids OEM or human-PASS claims.
- Reviewer deliverable: one ZIP plus a small SHA-256 receipt; no reliance on inaccessible raw media or the incomplete timed-out output directory.
