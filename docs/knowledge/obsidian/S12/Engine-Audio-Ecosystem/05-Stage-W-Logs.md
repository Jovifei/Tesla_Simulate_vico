# Stage W Logs

- W0: independent Stage-V audit — `PARTIAL`.
- W1/W2: persistent 20 ms engine, 3000-call/60 s equivalence, snapshot/restore,
  event torque feedback and firing-order-derived phase — `PASS`.
- W3: frozen PTR adapter and post-PTR raw split — `PASS`.
- W4: waveguide_v1 — `PASS`; ENSIM4 checkout/build attempt — `BLOCKED_TOOLCHAIN`.
- W5: dRPM/ignition-delay/location afterfire — `PASS`.
- W6: harmonic_v1 versus timbre_map_v1 and true `hot_idle_20s`/`complete_cycle_60s`
  windows — `PASS`.
- W9: P1/P2/P2H/P3/P5 bake-off render — `PASS` as diagnostic; selection withheld.

Task5D current validation/source/test head is `fcf74f3`; v24 local evidence was
generated at audio head `5038194` as one fresh 0.20 s block-aligned diagnostic
set (180/45/45 WAVs); historical `bakeoff_long_v3` remains the 20/60 s evidence.
No raw external media is committed.
The current focused verification is `141 passed, 1 skipped`; the 3000-block
gate is documented as `1 passed in 92.50s` (fresh measured run `92.06s`).

The next gate is a rights-bound synchronized Reference and then W10 multi-
reference selection plus human review.

## v27 external staging closure (2026-08-29)

- The rejected in-place v26 resume path was removed; the v27 architecture
  renders one external stage root per architecture (P1/P2/P2H/P3/P5),
  verifies each, assembles an external build root and publishes exactly one
  final root by atomic rename only on a clean strict validator.
- Authoritative current roots: `bakeoff_final_remediation_v27`
  (666 files), `migration_final_remediation_rx7_v27` (167 files) and
  `migration_final_remediation_ferrari_v27` (167 files); manifest SHA-256
  `465cf15f…`, `b57aceb3…`, `67dbf3ef…` respectively.
- Task 6Z first run was blocked at Gate 1 only (historical Task6C output
  whitespace tripped the Track-P guard); Task 6AA repaired it
  configuration-only via `.gitattributes` (commit `803c31f`). Task 6AB reran
  all eight gates green at source head `6ad9bca`: Stage-W focused
  `235 passed, 1 skipped`; Stage-V focused `33 passed`; slow 3000×20 ms
  `1 passed`; v27 validators `[]`; 730 JSON / 270 WAV scans clean; compileall,
  Track-P guard and `git diff --check` exit 0.
- Governed metadata (evidence receipt v7, `execution_state.json`,
  `artifact_manifest.json`, `obsidian_sync_manifest.json`,
  `EXECUTION_RESUME.md`) is bound to the v27 roots. Selection stays `null`;
  status stays `NO_ARCHITECTURE_CANDIDATE_PASSED / NOT_R1_QUALIFIED`.
- Next gate is unchanged: a rights-bound synchronized R1 Reference, then W10
  multi-reference selection plus human review. No raw external media is
  committed.
