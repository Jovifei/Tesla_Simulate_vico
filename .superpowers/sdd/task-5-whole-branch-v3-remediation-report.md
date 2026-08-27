# Task 5 Whole-Branch v3 Remediation Report

Jovi requested a single final fix wave for the Stage-W worktree. The work stayed
local on `agent/s12-stage-w-ecosystem-bakeoff`; no push, merge, PR, full S12
run, Track-P/frozen PTR mathematics change, external media ingestion, or Vault
write occurred.

## Source and RED/GREEN

- Source/test fixes are committed before current evidence: `bf5c0e9`,
  `9e71da2`, `f8a826a`, and `d33b3ec` (final tested source head
  `d33b3ecf3757ffa084aa43277892f012d48ecaa8`).
- RED: a migration case could remove `P2H/lift/phase_trace.json` and remove it
  from the outer manifest while validation returned `[]`; the focused test
  failed as expected. GREEN: required case inventory, internal SHA
  recomputation, result cross-checks, finite/latency, selection/status,
  afterfire condition, parameter-consumption, click recomputation, and
  raw/monitor separation are now fail-closed.
- RED: tampered saved click metrics were accepted; the focused tamper test
  failed as expected. GREEN: click metrics are recomputed from reopened PCM and
  compared with the saved receipt. The generator now saves metrics after the
  24-bit WAV reopen, avoiding quantization false positives.
- Existing Task 5 tests cover measured collector pressure-to-energy monotonicity,
  sub-block timing, geometry readbacks, bank phase authority, topology restore,
  WaveguideConfig bounds, and validator tamper classes.

## Current verification

All times are Asia/Shanghai local time and all exits are process exits.

- Remediation: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q --disable-warnings`; `05:36:32.8290885`–`05:36:51.1484711`, PID `52624`, exit `0`, `40 passed`.
- Stage-W: the exact ten-file Stage-W command recorded in `tasks/reports/runtime/s12-stage-w/logs/task5_stage_w_final.stdout.log`; `05:19:45.1637485`–`05:32:30.0000000`, PID `33228`, exit `0`, `93 passed, 1 skipped`.
- Stage-V: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests -k stage_v -q --disable-warnings`; `05:33:37.0132066`–`05:34:10.0000000`, PID `23732`, exit `0`, `31 passed, 580 deselected`.
- Bakeoff validator: literal command in `validator_bakeoff_v17.log`; `05:34:40.2009775`–`05:34:42.2637032`, exit `0`, result `[]`.
- RX-7 migration validator: literal command in `validator_migration_rx7_v17.log`; `05:34:51.1405312`–`05:34:52.4944797`, exit `0`, result `[]`.
- Ferrari migration validator: literal command in `validator_migration_ferrari_v18.log`; `05:35:01.1102621`–`05:35:02.4463903`, exit `0`, result `[]`.
- JSON finite scan: every JSON under the three current roots, `05:35:12.4113418`–`05:35:12.5574351`, exit `0`, `730 files`, `0 non-finite`.
- Compileall: `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015`; `05:35:19.8568225`–`05:35:20.0697557`, exit `0`.
- Source-head Track-P guard: `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`; `05:35:34.8186747`–`05:35:35.6611392`, verified head `d33b3ecf3757ffa084aa43277892f012d48ecaa8`, exit `0`, `180` frozen files/`2` frozen symbols, stdout SHA `a7bab032e534d2a7aeb447676d49092998aededc2acf9afdc8dc02f029ac8dfb`.
- `git diff --check`: `05:37:05.6476383`–`05:37:05.7093336`, exit `0`.

## Fresh evidence bound to the final source head

- Bakeoff v17: `tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v17`, manifest SHA `69c9ca2d3ceaf2a677dfe7524c9723616985b6b24cc13124de630857146910f3`, `180` WAV files, generated through `05:16:42`.
- RX-7 v17: `tasks/reports/runtime/s12-stage-w/migration_final_remediation_rx7_v17`, manifest SHA `7a6314f4a71ee8b2dce349dda280850d59f813f7979ace8cc4248674b123208e`, `45` WAV files, generated through `05:17:50`.
- Ferrari v18: `tasks/reports/runtime/s12-stage-w/migration_final_remediation_ferrari_v18`, manifest SHA `f7fc6469a89e5e8c2ede1b89d9f3f1fab79426836a35c43f2bcac13349a8902a`, `45` WAV files, generated through `05:18:56`.
- The compact receipt `.superpowers/sdd/final_remediation_evidence_receipt.json` v4 is the sole current verification block. Older v12–v15 attempts are historical superseded attempts; they are not current evidence.

## Recovery and gates

- `execution_state.json`, `EXECUTION_RESUME.md`, and `obsidian_sync_manifest.json`
  now identify `d33b3ec` and the three current roots; the `24f2c41` full-S12
  result is retained as historical only and is not asserted to cover Task 5.
- `parameter_usage_matrix.json` v2 records truthful geometry, cycle, bank/
  collector, transfer-IR consumption and evidence paths.
- `stage_w_review_package_receipt.json` is explicitly
  `STALE_HISTORICAL_REVIEW_PACKAGE`; current audition is prohibited and no new
  package is generated while selection is null and R1 is closed.
- Remaining external gates: legal synchronized R1 audio/traces and rights
  receipt, formal candidate selection/W10, Profile Freeze, OEM reproduction,
  human PASS, and controller-owned full S12 regression.

## Receipt parse and final receipt-head guard

- Receipt parse: `python -c "import json; from pathlib import Path; d=json.loads(Path(r'.superpowers/sdd/final_remediation_evidence_receipt.json').read_text(encoding='utf-8')); print({'schema':d['schema_version'],'source_head':d['tested_source_head'],'evidence':list(d['current_verification']['fresh_evidence']), 'selection':d['selection']})"`; `05:43:25.0944444`–`05:43:25.1497593`, exit `0`; result schema `s12.stage_w.final_remediation_evidence_receipt.v4`, source `d33b3ecf3757ffa084aa43277892f012d48ecaa8`, evidence keys `source_head/bakeoff_v17/rx7_v17/ferrari_v18`, selection `None`.
- Final receipt-head guard: `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`; verified parent receipt head `0d1f1c4`, `05:43:15.4753333`–`05:43:16.1627327`, exit `0`, 180 frozen files/2 symbols, stdout log SHA `285afa179606524ebff71d18b69b3185c473f83fab9641b801c561325c6814b9`; `git diff --check` at the receipt head exit `0`. This guard log/report commit is intentionally not claimed as self-bound by the receipt.
