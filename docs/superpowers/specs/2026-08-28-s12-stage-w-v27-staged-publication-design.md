# S12 Stage W v27 External Staging and Atomic Publication Design

## Status

Approved by Jovi on 2026-08-28 by selecting option `1` after review of the in-place v26 recovery design.

## Goal

Produce a fresh, complete v27 synthetic Hellcat bake-off and two vehicle diagnostics without modifying v25/v26 or exposing a partially assembled strict evidence root.

## Why the architecture changes

The v26 in-place resume implementation accumulated transaction/provenance edge cases across three independent review cycles. The v27 design moves the transaction boundary outward: every architecture is an independently complete stage, final assembly occurs in a distinct external build root, and a single directory rename publishes only a validator-clean final root. The existing all-architecture generator remains unchanged.

## Components

### 1. Architecture-stage renderer

Add a small public helper beside the existing bake-off API:

`render_hellcat_architecture_stage(stage_root, architecture, duration_s=8.0, *, long_window=False, parent_stage_root=None) -> dict[str, Any]`

- `architecture` is exactly one of P1/P2/P2H/P3/P5.
- `reference` is absent/None for this synthetic run.
- `stage_root` must be new or empty; a non-empty root is rejected without overwrite.
- The helper renders all twelve scenes using existing `_write_case` behavior. P2/P2H/P3/P5 require a verified, complete P1 stage and pass its scene-matched post-PTR PCM into candidate comparison.
- Cases are written under `stage_root/<architecture>/<scene>/` using the existing eleven-file contract.
- A stage manifest is written at `stage_root/stage_manifest.json`, outside the architecture directory that will later be published. It records canonical stage path/id, architecture, duration map, all case hashes, status/reference/selection and source head.
- Stage output is never interpreted as a final bake-off root; it is explicitly `STAGE_COMPLETE`, `REFERENCE_TARGET_MISSING`, and unselected.

### 2. Stage verifier and assembler

Add `assemble_v27_bakeoff(final_root, stage_roots, duration_s=8.0, *, long_window=False) -> dict[str, Any]` in a focused `stage_w/v27_pipeline.py` module.

- It requires exactly one verified stage for each P1/P2/P2H/P3/P5, validates every stage manifest and every case hash/PCM/scene identity, and rejects duplicate/missing/wrong-parameter stages.
- It creates a unique external build root beside `final_root`, moves only the verified architecture directories into it, reconstructs the existing five summaries and standard manifest, and runs the unchanged `validate_bakeoff_manifest(build_root)`.
- It publishes only after validation returns `[]` and `final_root` is absent, using one `os.replace(build_root, final_root)` directory rename. A partial build root never becomes the named final root.
- `stage_manifest.json` files and assembly receipts remain outside the final root, so strict root inventory remains unchanged.
- A failed or interrupted build root remains an external diagnostic artifact; no function deletes v25/v26 or an unexplained root.

### 3. Migration runner

The existing `run_preselection_vehicle_migration` remains unchanged. v27 RX-7 and Ferrari roots are new, unique output roots generated once after bake-off publication; their status remains `UNSELECTED_CANDIDATE_MIGRATION`.

## Data and safety flow

```text
P1 stage -> verify
             |
P2/P2H/P3/P5 stages (each receives verified P1 post-PTR)
             |
verify all 5 stages -> external build root -> strict validator []
                                              |
                                  atomic directory publish -> v27 final root
```

- v25 and v26 are read-only historical evidence and are never inputs to v27.
- No stage or build file is placed inside the named final root until publication.
- Final status remains `REFERENCE_TARGET_MISSING`, reference `REFERENCE_POINTER_ONLY`, selection null, no R1/W10/Profile Freeze/OEM claim.

## Testing

Use TDD before implementation:

1. A stage renders all twelve cases and its manifest is complete; an incomplete/non-empty stage is rejected.
2. A candidate stage cannot render without a verified P1 stage and its parent/candidate RMS is bound to the P1 post-PTR PCM.
3. Assembly rejects missing/duplicate/tampered stages and leaves an absent final root untouched.
4. A validator-clean external build is published by one directory rename; the final root has the exact existing strict manifest inventory and no stage/receipt extras.
5. Existing full bake-off and strict validator tests remain green; the default all-architecture generator signature and behavior are unchanged.

## Scope

Only the small stage helper, focused pipeline module, tests, and v27 runtime/evidence metadata are in scope. The rejected in-place resume API and its tests are removed before this implementation. No PTR/radiation/audio algorithm, Track-P, external media, Vault, remote or branch integration changes are allowed.
