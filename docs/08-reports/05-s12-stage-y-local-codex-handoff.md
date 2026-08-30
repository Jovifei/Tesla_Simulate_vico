# S12 Stage Y — Local Codex Handoff

Use this prompt only in a new isolated worktree based on:

```text
agent/s12-stage-y-closed-loop-remediation
```

Do not reuse the Stage X worktree and do not modify frozen Track-P PTR/FVM/Radiation files.

---

## Prompt for local Codex

You are the execution owner for **S12 Stage Z — Real Reference Hybrid Calibration**.

### 1. Final product goal

Build a repeatable negative-feedback loop that improves a persistent event-domain engine sound against authorized real vehicle references:

```text
authorized recording + synchronized state
→ derived order/timbre map and cycle residuals
→ optional hybrid event-domain source
→ frozen PTR/Radiation
→ candidate WAV
→ Python comparator
→ MATLAB + MoSQITo finalist validation
→ Jovi blinded A/B
→ bounded parameter update
→ regression and evidence
```

The target is not “all tests pass” alone. The target is a candidate whose **real-reference residuals and blinded human judgement both improve** while preserving runtime and frozen-boundary contracts.

### 2. Start-up contract

1. Fetch remote.
2. Verify branch tip and the Stage Y CI receipt.
3. Create a new branch and worktree:

```text
branch: agent/s12-stage-z-real-hybrid-calibration
worktree: E:/Tesla_speed/worktrees/s12-stage-z-real-hybrid-calibration
```

4. Read before changing code:

```text
docs/08-reports/03-s12-stage-y-closed-loop-remediation.md
docs/08-reports/04-s12-stage-y-hybrid-calibration-tooling.md
tools/sound_sim/s12/acoustic_identity_v015/stage_y/
tools/sound_sim/s12/acoustic_identity_v015/stage_x/reference_governance.py
tools/sound_sim/s12/acoustic_identity_v015/stage_x/multi_reference_comparator.py
```

5. Run the focused Stage X/Y tests and Track-P guard. Record exact commands, exit codes and logs.

### 3. Phase Z0 — Verify external input; do not fake it

For each received calibration bundle require:

```text
audio.wav
state.csv
rights.json
recording.json
```

`rights.json` must bind the exact audio SHA-256 and use a supported cleared status. `recording.json` must include exact vehicle/engine, microphone position and AGC/post-processing. `state.csv` must cover the full audio and contain at least time/RPM/load; boost and phase are preferred.

Reject and report, rather than infer, when:

- rights are not cleared;
- audio SHA differs;
- vehicle/trim is ambiguous;
- state coverage is incomplete;
- RPM is guessed from sound alone;
- the recording contains speech/music or strong unrelated traffic;
- stock/modified exhaust state is unknown for a formal case.

### 4. Phase Z1 — Generate real derived assets

Run, per accepted bundle:

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_y.drivers.drive_y2_calibration_bundle `
  --bundle <bundle-dir> `
  --output <runtime-output-dir>
```

Verify:

- harmonic map has observed cells and plausible order ridges;
- cycle bank contains complete cycles and no raw audio copy;
- all output SHA values match;
- rights/source metadata survives into receipts;
- phase reconstruction uses synchronized RPM if explicit phase is absent.

Do not commit private WAV/FLAC or derived NPZ assets unless their licence explicitly permits repository redistribution. Runtime reports may store hashes and feature summaries.

### 5. Phase Z2 — Integrate one anchor vehicle first

Start with **Hellcat only**. Do not parallelize all eight vehicles before one real loop works.

Add an optional configuration-controlled hybrid path:

```text
PersistentEventDomainEngine event source
+ HybridSourceMixer residual layer
→ existing FrozenPtrStereo
```

Rules:

- default remains disabled;
- no reference media bytes inside source code;
- one-shot/block/snapshot equivalence must pass;
- residual phase must stay locked across 20 ms blocks;
- no clipping, NaN, click or reset discontinuity;
- Raw and Monitor remain separate;
- no frozen PTR modification.

Render ten scenarios: hot idle, steady low/mid/high, tip-in, full pull, shift, lift, afterfire and idle return.

### 6. Phase Z3 — Professional comparison

For each finalist run:

1. Stage Y Python comparator.
2. MATLAB order analysis when synchronized RPM exists.
3. MATLAB psychoacoustics.
4. MoSQITo psychoacoustics.
5. Optional ViSQOL only for same-source regression damage, never as OEM identity score.

Feed the SHA-bound receipts into `stage_y/finalist_validation.py`.

Report separately:

- order identity;
- low-frequency body;
- 120–400 Hz attack;
- mid-band congestion;
- mechanical texture;
- forced-induction identity;
- idle life;
- acceleration continuity;
- shift transient;
- afterfire naturalness;
- synthetic tonal artifact;
- dynamic range and runtime cost.

Do not collapse these into one misleading “similarity percentage”.

### 7. Phase Z4 — Bounded negative-feedback tuning

Only tune parameters demonstrated reachable for the target vehicle and scenario. Use two levels:

- inner loop: corrected Python metrics;
- outer gate: MATLAB/MoSQITo and Jovi feedback.

Jovi feedback translations:

- fixed electronic whistle → reduce persistent narrowband tone; improve sideband/broadband distribution;
- low frequency without impact → improve 120–400 Hz pulse attack, not only 20–60 Hz gain;
- idle too quiet → fix state-aware monitor/loudness policy without changing source identity;
- idle too regular → combustion cycle variation and phase/energy variation, not white noise;
- afterfire random → repair state eligibility, reservoir, event timing, route and decay;
- RX-7 sounds like piston engine → repair rotary event timing before EQ.

Maximum two automatic correction rounds before a written failure analysis. Never keep searching indefinitely.

### 8. Phase Z5 — Human review

Generate a Chinese hash-bound blinded package with:

```text
real reference
parent
candidate
low-quality anchor
```

Separate loudness-matched timbre review from raw-dynamic review. Do not reveal the answer key before export. Import only a real completed Jovi/webMUSHRA result; never use fixtures as human feedback.

### 9. Acceptance gates

A Hellcat engineering candidate may advance only when all are true:

- runtime hard gates pass;
- independent legal reference sessions are sufficient;
- corrected multi-reference objective improves by the configured threshold;
- no key dimension regresses beyond limit;
- professional finalist receipts are valid and SHA-consistent;
- Jovi prefers Candidate over Parent in the required anchor scenes;
- focused and full S12 regressions pass;
- Track-P guard passes;
- worktree is clean;
- branch is committed but not merged without authorization.

Formal Profile Freeze additionally requires real R1 evidence and explicit Jovi approval.

### 10. Continuous-execution instruction

Do not stop merely because a subphase passes. Maintain:

```text
tasks/reports/runtime/s12-stage-z/execution_state.json
tasks/reports/runtime/s12-stage-z/EXECUTION_RESUME.md
```

After each phase write status, evidence, failed gates and exact next action. Continue automatically through all independently executable work. Stop only at a genuine external input or human decision gate, and list the exact missing files/fields rather than asking a broad question.

### 11. Required final report

Return:

- branch, worktree and HEAD;
- exact reference bundles accepted/rejected and why;
- derived asset hashes;
- code changes and borrowed-method mapping;
- Parent/Candidate results for all ten scenes;
- MATLAB/MoSQITo/Jovi results;
- tests and Track-P evidence;
- what objectively improved;
- what still failed;
- commits, push/merge status;
- honest terminal state.

Permitted terminal states include:

```text
HELLCAT_R2_ENGINEERING_CANDIDATE_READY_FOR_JOVI
WAITING_FOR_REAL_CALIBRATION_BUNDLE
WAITING_FOR_JOVI_BLIND_REVIEW
NO_CANDIDATE_IMPROVED_MODEL_REDESIGN_REQUIRED
```

Never claim OEM reproduction, calibration, Human PASS or Profile Freeze without the corresponding evidence.
