# Task 4 whole-branch v2 remediation report

Status: `DONE_WITH_CONCERNS`

Work remained local and fail-closed. No push, merge, PR, Track-P/frozen PTR mathematics change, external media ingestion, Vault write, or full S12 run occurred.

## Source/test/docs commits

- `bc93a653330f63495f29d562529f2940e7a078f0` — actual scheduled afterfire entity/bank/path routing and bounded local PCG64 RNG state with snapshot/restore/reset.
- `5a6485cb1ebdd39ad99c3fac34127e64f6141ae0` — stateful waveguide/P5 boundary documentation and duplicate-test-import cleanup.

RED→GREEN: the routing regression initially proved primary and bank-collector PCM could be identical; after entity/bank routing, Task 4 remediation suite passed `32 passed in 6.74s`. RNG tests prove nonzero bounded jitter is deterministic across snapshot/restore and hard reset.

## Fresh post-source evidence

Evidence was generated after source/docs head `5a6485cb1ebdd39ad99c3fac34127e64f6141ae0`:

- Bakeoff v5: command `python -c "from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import run_hellcat_bakeoff; run_hellcat_bakeoff(r'tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v5', duration_s=0.20)"`; PID `57756`; `2026-08-28T02:01:15.8680452+08:00`–`2026-08-28T02:03:11.3809723+08:00`; exit `0`; validator `[]`; manifest SHA `1e463c4a65168a2131e74ac96017efd8e4453fd3d9ab46a7a6be7a9cde15ab21`.
- RX-7 v5: command `python -c "from tools.sound_sim.s12.acoustic_identity_v015.stage_w.migration import run_preselection_vehicle_migration; run_preselection_vehicle_migration(r'tasks/reports/runtime/s12-stage-w/migration_final_remediation_rx7_v5','rx7_fd',duration_s=0.20)"`; PID `7968`; `2026-08-28T02:03:55.1249870+08:00`–`2026-08-28T02:04:25.2055609+08:00`; exit `0`; validator `[]`; manifest SHA `50619070813b016a47eaf72264b2ba0b111ee067a347070ac37001b0e92d9c12`.
- Ferrari v6: command `python -c "from tools.sound_sim.s12.acoustic_identity_v015.stage_w.migration import run_preselection_vehicle_migration; run_preselection_vehicle_migration(r'tasks/reports/runtime/s12-stage-w/migration_final_remediation_ferrari_v6','ferrari_458',duration_s=0.20)"`; PID `53924`; `2026-08-28T02:04:49.0441843+08:00`–`2026-08-28T02:05:19.1278449+08:00`; exit `0`; validator `[]`; manifest SHA `03c6a81bf40f6783f72952b97fdd263152dffdfce22a8259895686155a490152`.

## Verification

- Remediation: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q` — `32 passed`, exit `0`, `2026-08-28T02:05:52.2555019+08:00`–`02:05:59.5772663+08:00`.
- Affected Stage-W focused: exact 10-file command is stored in `final_remediation_evidence_receipt.json` and `stage_w_focused_task4_current.stdout.log`; PID `19740`; `2026-08-28T02:08:31.9655683+08:00`–`2026-08-28T02:20:13.1005540+08:00`; exit `0`; `83 passed, 1 skipped in 700.53s`; stderr `0`.
- Complete Stage-V focused: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests -k stage_v -q --disable-warnings` — PID `60036`; `2026-08-28T02:06:10.4781857+08:00`–`02:06:45.5834217+08:00`; exit `0`; `31 passed, 570 deselected in 32.26s`; stderr `0`.
- `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015` — exit `0`.
- Fresh JSON scan over exact roots `tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v5/**/*.json`, `migration_final_remediation_rx7_v5/**/*.json`, `migration_final_remediation_ferrari_v6/**/*.json` — `730` files, `0` non-finite.
- Literal validators for bakeoff v5, RX-7 v5, and Ferrari v6 each returned `[]`.
- Track-P source-head guard on `5a6485c`: exit `0`, 180 frozen files/2 symbols, stdout SHA `e5720bca586519e36b2fa2cd1727a1552f0778ee578963590e4746e67e23f83c`; `git diff --check` exit `0`.
- Compact receipt `final_remediation_evidence_receipt.json` was refreshed with fresh output paths/hashes, `selection=null`, local synthetic-only boundary, and prior metadata guard `e926e96`. Receipt commit is separate from source/docs commits. Final receipt-head guard is recorded after that commit.

## Minor documentation and boundary updates

`S12_Stage_W_Waveguide_Teacher.md` now describes stateful frequency-dependent loss and current focused count; `S12_Stage_W_Selected_Architecture.md` permits clean-room synthetic P5 transient output without rights-bound source material while retaining rights requirements for external media; test duplicate `pytest` import removed. Historical timing values remain untouched.

## Concerns

Full S12 remains controller-owned and was not run. No legal synchronized R1 reference exists; selection remains null and `NO_ARCHITECTURE_CANDIDATE_PASSED / NOT_R1_QUALIFIED` remains the only valid outcome. W10, Profile Freeze, OEM reproduction, MATLAB/R1 comparison, and human PASS remain unverified and prohibited.

## Final receipt/evidence update

- Source/test/docs head: `5a6485cb1ebdd39ad99c3fac34127e64f6141ae0`; remediation `32 passed` (`02:05:52.2555019–02:05:59.5772663`, exit `0`); complete Stage-V `31 passed, 570 deselected` (`02:06:10.4781857–02:06:45.5834217`, exit `0`); affected 10-file Stage-W `83 passed, 1 skipped` (`02:08:31.9655683–02:20:13.1005540`, PID `19740`, exit `0`, stderr `0`).
- Fresh evidence generation used literal commands recorded in the receipt/logs: bakeoff v5 PID `57756`, `02:01:15.8680452–02:03:11.3809723`, exit `0`; RX-7 v5 PID `7968`, `02:03:55.1249870–02:04:25.2055609`, exit `0`; Ferrari v6 PID `53924`, `02:04:49.0441843–02:05:19.1278449`, exit `0`.
- Literal fresh validators each returned `[]`: `python -c "from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import validate_bakeoff_manifest; print(validate_bakeoff_manifest(r'tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v5'))"`; `python -c "from tools.sound_sim.s12.acoustic_identity_v015.stage_w.migration import validate_vehicle_migration_manifest; print(validate_vehicle_migration_manifest(r'tasks/reports/runtime/s12-stage-w/migration_final_remediation_rx7_v5'))"`; and the same complete import with `migration_final_remediation_ferrari_v6`.
- Fresh manifest hashes: bakeoff `1e463c4a65168a2131e74ac96017efd8e4453fd3d9ab46a7a6be7a9cde15ab21`; RX-7 `50619070813b016a47eaf72264b2ba0b111ee067a347070ac37001b0e92d9c12`; Ferrari `03c6a81bf40f6783f72952b97fdd263152dffdfce22a8259895686155a490152`. JSON finite scan over exact v5/v6 roots: `730 files, 0 non-finite`; compileall and `git diff --check` exit `0`.
- Source-head Track-P guard: `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`, source head `5a6485cb1ebdd39ad99c3fac34127e64f6141ae0`, `02:06:53.3538470–02:06:54.1376796`, exit `0`, 180 frozen files/2 symbols, stdout SHA `e5720bca586519e36b2fa2cd1727a1552f0778ee578963590e4746e67e23f83c`.
- Compact tracked receipt was refreshed to these fresh roots/hashes and committed separately after source/docs. Final metadata-head Track-P guard is recorded in the receipt/report after that commit.
