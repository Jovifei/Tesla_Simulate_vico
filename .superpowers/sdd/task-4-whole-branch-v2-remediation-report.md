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

## Final receipt-head guard

- Final metadata head after receipt and local-output ignore commit: `8ae069f5d1e0c4c6c04a848708beaad3a10ff3e1`. Guard command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py` ran `2026-08-28T02:24:28.2201119+08:00`–`2026-08-28T02:24:29.1908948+08:00`, exit `0`, 180 frozen files/2 frozen symbols, stdout SHA `afbb9b19a3a20467334bcb71ccda30f775fc2916043e30c091f71a4453992a5f`; `git diff --check` exit `0`.
- Receipt commit: `574ffb333c2887ea979b2124df79ac285283251c`; source/docs commits: `bc93a65`, `5a6485c`; local evidence roots remain ignored/untracked by design and are hash-validated in the receipt.

## Task 4 review addendum rework

- RED: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -k bakeoff_validator -q` initially showed two state-validation failures (non-null selection and unexpected manifest status/reference). GREEN after fail-closed cross-file validation: `4 passed, 32 deselected`.
- Additional direct route/RNG coverage passed in the source/test commit `8d88208cd513170764d465af2a1cf1e41f2cf920`; central afterfire contribution is symmetric L/R, primary and bank-collector contributions are bank-dependent, and bounded PCG64 jitter snapshots/restores/resets deterministically.
- Fresh evidence was regenerated after source head `8d88208cd513170764d465af2a1cf1e41f2cf920`: bakeoff v7 PID `36632`, `02:49:41.8342783–02:51:33.7132243`, exit `0`; RX-7 v7 PID `54564`, `02:52:27.0661464–02:52:57.1371439`, exit `0`; Ferrari v8 PID `6020`, `02:53:25.5696833–02:53:55.6680483`, exit `0`. Manifest validators each returned `[]`.
- Fresh manifest SHA-256: bakeoff v7 `e74ee12ae86d1856da40e7d71aa96230f47c0ad09beaeebe522596beed4fc5b9`; RX-7 v7 `08381b3ee96e6ee9dc89ee6c2788247c7e8f719cbc982d3fca45a6ced21101fd`; Ferrari v8 `5a7a5eabff006710b83413d5884771ee7e7ec70231a19f1a7a7324dc8c2c5dc9`.
- Current focused verification: remediation `32 passed` (`02:05:52.2555019–02:05:59.5772663`, exit `0`); Stage-W `83 passed, 1 skipped` (`02:08:31.9655683–02:20:13.1005540`, exit `0`); Stage-V `31 passed, 570 deselected` (`02:06:10.4781857–02:06:45.5834217`, exit `0`); compileall exit `0`; JSON scan `730 files, 0 non-finite`; `git diff --check` exit `0`.
- Task 4 source-head Track-P: command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`, head `8d88208cd513170764d465af2a1cf1e41f2cf920`, `02:56:11.3298634–02:56:12.1043945`, exit `0`, 180 frozen files/2 symbols, stdout SHA `74f8ac8aa1970e346f3e84d7c11487a0b85b15dd996c26509cac5892d6dba366`.
- The compact tracked receipt was refreshed with prior `e926e96`, source head `8d88208`, fresh v7/v8 roots/hashes, explicit selection null, and local synthetic-only evidence. Receipt metadata is committed separately; final receipt-head Track-P/diff guard follows.

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

## Task 4 review addendum final evidence

- Validator RED→GREEN: four bakeoff state-tamper tests first exposed two unreported contradictions; cross-file validation now rejects non-null selection, unexpected status/reference, missing state files, and contradictory summaries. Final remediation suite: `32 passed`.
- Source/test commits: `bc93a65`, `5a6485c`, `8d88208`, and `81166df3910a9c18f5f0b1bf3796c53b4624aaa7`; fresh evidence was generated after source head `8d88208`.
- Fresh outputs: bakeoff v7 (`666 files/180 WAVs`, manifest SHA `e74ee12ae86d1856da40e7d71aa96230f47c0ad09beaeebe522596beed4fc5b9`), RX-7 v7 (`167/45`, SHA `08381b3ee96e6ee9dc89ee6c2788247c7e8f719cbc982d3fca45a6ced21101fd`), Ferrari v8 (`167/45`, SHA `5a7a5eabff006710b83413d5884771ee7e7ec70231a19f1a7a7324dc8c2c5dc9`); validators each returned `[]`.
- Current checks: remediation `32 passed` (`02:05:52.2555019–02:05:59.5772663`), Stage-W `83 passed, 1 skipped` (`02:08:31.9655683–02:20:13.1005540`, PID `19740`), Stage-V `31 passed, 570 deselected` (`02:06:10.4781857–02:06:45.5834217`, PID `60036`), compileall exit `0`, JSON finite `730 files/0 non-finite`, and `git diff --check` exit `0`.
- Source-head Track-P command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py` on `8d88208`: `02:56:11.3298634–02:56:12.1043945`, exit `0`, 180 frozen files/2 symbols, stdout SHA `74f8ac8aa1970e346f3e84d7c11487a0b85b15dd996c26509cac5892d6dba366`.
- Separate receipt commit `5b61ec1003bafcc7e50189c8a139a21eb4f01e1a` binds prior verified metadata `e926e96`, fresh evidence, selection null, and external-media exclusion. Final receipt-head guard on `5b61ec1`: `02:57:33.8851135–02:57:34.6752242`, exit `0`, stdout SHA `3ea919a35afa4962c34881ce91358b58d203d3a7a9369407464e8b46c340535a`, `git diff --check` exit `0`.

## Task 4 final re-review addendum

- RED→GREEN state validation: non-null selection, unexpected status/reference, missing state file, and contradictory summary tests were added; `validate_bakeoff_manifest` now cross-checks all four state JSON files and accepts only `REFERENCE_TARGET_MISSING`/`REFERENCE_POINTER_ONLY` with selection null. Direct stereo tests prove central collector route deltas are symmetric while primary and bank-collector deltas are bank-dependent.
- Source/test head before fresh evidence: `8d88208cd513170764d465af2a1cf1e41f2cf920`; validator implementation is included in the source history before fresh evidence roots. Fresh outputs: bakeoff v8 (manifest SHA `d65f94c4729ffcdb54dedd9f044aa52d5168ce2be49b3c575c1eb75165d07972`), RX-7 v8 (`3bc75da527a158014d3ce2732c1a5e5a59412305b10e117c54abe141f95c4376`), Ferrari v9 (`3e9b10a892dc96c9c0763df0640136c26fb8c1f31eccc51fee86314747c7b36e`). All validators returned `[]`; each root is local/ignored synthetic evidence.
- Fresh generation commands/logs: bakeoff PID `34536`, `02:58:58.5576568–03:00:50.2934182`, exit `0`; RX-7 PID `42152`, `03:01:35.8355786–03:02:05.9187748`, exit `0`; Ferrari PID `23376`, `03:02:33.1864920–03:03:03.2573637`, exit `0`.
- Current verification: remediation `37 passed in 11.44s` (`03:04:18.5684074–03:04:30.9624879`, exit `0`); Stage-V `31 passed, 566 deselected` (`01:08:35.4484707–01:09:10.5467374`, exit `0`); compileall exit `0`; JSON finite `730 files/0 non-finite`; literal bakeoff/RX-7/Ferrari validators exit `0` with `[]`; source-head Track-P at `8d88208` exit `0` (`02:56:11.3298634–02:56:12.1043945`, 180 files/2 symbols); `git diff --check` exit `0`.
- Receipt metadata commit is separate from source/test/docs; final receipt-head Track-P/diff guard is performed after commit and recorded below. Full S12 remains controller-owned and is not run.
