# S12 Stage W v26 Checkpointed Bake-Off Recovery Design

## Status

Approved by Jovi on 2026-08-28: `授权 v26 分段恢复实现`.

## Context

The one authorized full v26 launch entered the Hellcat generator, rendered eleven P1 scenes, then was externally interrupted during `P1/complete_cycle_60s` with `0xC000013A`. The v25 root is a separate incomplete historical attempt and must remain unchanged. Scheduler and a 90-second Python liveness probe both succeed, so the recovery must bound each render unit below the agent/session lifetime while preserving a single v26 evidence root.

## Considered approaches

1. Start another full v27 bake-off. This violates the bounded v26 recovery intent, repeats completed work, and risks another long-session interruption.
2. Use an external helper to invoke private rendering functions and manually synthesize summaries. This would create an untested second implementation of bake-off semantics.
3. Add a small public, checkpointed resume API alongside the existing full generator. This retains the existing default API, makes each architecture independently recoverable and testable, and can finalize the normal manifest only after all required architectures exist.

Approach 3 is selected.

## Public interface

`resume_hellcat_bakeoff(output_root, architecture, duration_s=8.0, *, long_window=False)` is added to `stage_w.bakeoff` and exported in `__all__`.

- `architecture` is exactly one of `P1`, `P2`, `P2H`, `P3`, or `P5`.
- The existing `run_hellcat_bakeoff()` signature and non-empty-root refusal remain unchanged.
- Recovery accepts only `reference=None`; R2 diagnostic continuation remains deliberately unsupported rather than mixing unknown reference identity across chunks.
- A completed case is skipped only when all eleven existing case artifacts are present and its inner SHA manifest matches them. An empty case directory is rendered. A non-empty incomplete case is rejected without overwrite.
- Each resumed case renders into a root-external staging directory. It is moved into an empty target case directory only after all artifacts and the inner SHA manifest exist. An interrupted staging directory therefore never pollutes the strict final root.
- The function writes a checkpoint outside the evidence root at `tasks/reports/runtime/s12-stage-w/checkpoints/<root-name>-<canonical-root-id>.resume.json`. The payload binds the resolved root path and root id, preventing same-name roots from sharing state. This preserves the strict final root manifest, whose validator rejects unknown root files.
- The checkpoint records schema, canonical root identity, requested duration, long-window flag, reference/selection status, completed architectures and no selection. A root, duration or long-window mismatch fails closed.

## Data flow

1. Load/reconstruct the sidecar checkpoint and inspect all existing case directories.
2. For the requested architecture, load verified complete scenes and render only missing empty scenes. Candidate architectures obtain their Parent comparator signal from verified P1 post-PTR PCM; they do not re-render an in-memory P1 parent.
3. Write the sidecar checkpoint after the architecture is complete.
4. If any executable architecture remains incomplete, return `IN_PROGRESS` with `selected_architecture=null`; do not write root summaries or `bakeoff_manifest.json`.
5. Once P1/P2/P2H/P3/P5 are complete, reconstruct the standard architecture records from verified case artifacts, write the existing five summaries, and write the unchanged strict final manifest. The normal validator must return `[]`.

## Safety boundaries

- No v25 read, copy, move, delete, or overwrite occurs.
- v26 remains synthetic, uncalibrated, vehicle-inspired, not OEM reproduction, `REFERENCE_TARGET_MISSING`, `selected_architecture=null`, and not R1/Profile Freeze qualified.
- No change to PTR, radiation, Track-P, Stage V behavior, migration semantics, external media, Vault, push, merge or PR.
- The checkpoint is outside the final root specifically because `validate_bakeoff_manifest()` rejects outer files not enumerated in its fixed final inventory.

## Tests and acceptance evidence

New focused tests must prove:

1. staged P1 recovery skips verified scenes, fills only the empty long-cycle directory, and writes no final manifest before all architectures complete;
2. each subsequent architecture can be completed in a separate call, and the final P5 call produces a standard validator-clean root with the usual summaries;
3. a non-empty incomplete case is rejected without overwrite;
4. a checkpoint root/duration/long-window mismatch is rejected;
5. resumed candidate comparison uses the verified P1 post-PTR PCM.

The implementer must observe the new tests fail before source changes, then pass after the minimal implementation. Existing bake-off focused tests, strict validator tests, compileall and `git diff --check` are required before commit. Each actual v26 architecture render is run in a bounded worker/monitor sequence and recorded separately; migrations remain subsequent short tasks.

## Scope review

The interface is narrow: it recovers only synthetic no-reference Hellcat evidence and does not change the behavior of any existing caller. It introduces no new sound algorithm, parameter, selection pathway or external dependency.
