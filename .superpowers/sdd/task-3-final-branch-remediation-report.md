# Stage W-C final branch remediation report

Status: `DONE_WITH_CONCERNS`

The final remediation wave started at `69a1c9580cab67d1ca751190bb99072eaa169849` and remains fail-closed. No Track-P/frozen PTR mathematics, external copyrighted media, Obsidian Vault, push, merge, PR, or full S12 run was performed.

## Commits by cluster

- Cluster A — `f310e914489a3b7088a7d1cbb27c5862ea362f94` (`fix(s12): protect stage w raw evidence logs`).
- Cluster B — `76b2bd3527e4f6e226fc09b9215bdc8f446e6aab` (`fix(s12): persist afterfire and waveguide state`).
- Cluster C — `519425ffcf8ee057f71137265376fecf5119ec88` (`fix(s12): consume stage w topology and timbre contracts`).
- Cluster D — `8bf2280434c75416d58f1727058d05643a2132af` and `446b845e9526538cf248cdc5aea457b1b27357b7` (click metrics, explicit geometry/timbre contracts, bakeoff/migration gates).
- Cluster E — implemented in `76b2bd3527e4f6e226fc09b9215bdc8f446e6aab` via `StageWBoundaryAdapter` SHA enforcement.
- Cluster F — bounded regenerated evidence is under `tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v1/`, `migration_final_remediation_rx7_v1/`, and `migration_final_remediation_ferrari_v1/`; generated WAV/JSON roots are intentionally local/ignored because their `post_ptr_raw` filenames would be misclassified by the immutable Track-P path guard. This report and command logs are committed.

## Exact source/test files changed

- `.gitattributes`
- `tools/sound_sim/s12/acoustic_identity_v015/event_domain/config_schema.py`
- `tools/sound_sim/s12/acoustic_identity_v015/event_domain/event_scheduler.py`
- `tools/sound_sim/s12/acoustic_identity_v015/event_domain/configs/hellcat_v1.json`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/boundary_adapter.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/waveguide.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/timbre_map.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/migration.py`
- `tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py`

## RED/GREEN evidence

- Cluster A RED: final remediation test had 2 failures (missing scoped `.gitattributes` rule and Track-P `git diff --check` raw-log whitespace errors). GREEN: `3 passed` and committed-head `assert_track_p_unchanged.py` exit `0` (`180` frozen files/`2` symbols unchanged).
- Cluster B RED: missing pending-event diagnostics and scalar waveguide failed spectral attenuation assertion. GREEN: final remediation tests plus existing afterfire/waveguide/persistent suites passed.
- Cluster C RED: missing `crankpin_geometry` and accepted `collector_assignment`/`transfer_ir` had identical PCM. GREEN: geometry/order/rotary and parameter-consumption tests passed.
- Cluster D RED: `TimbreMap4D` import and click metric contracts were absent. GREEN: 4D map, engine click, bakeoff and migration gate tests passed.
- Cluster E RED: `StageWBoundaryAdapter` import absent. GREEN: expected package SHA accepted and mismatched SHA rejected.

Commands/results: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q` → `12 passed`; existing focused afterfire/waveguide/persistent run → `...s` (pass); `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015` → exit `0`.

Final committed-HEAD rerun after the generated-output ignore rule: remediation tests `12 passed`, Track-P guard exit `0`, `git diff --check` exit `0`, and worktree clean.

## Evidence regeneration

- `run_hellcat_bakeoff(..., output_root=bakeoff_final_remediation_v1, duration_s=0.20)` — PID `23116`, `2026-08-27T23:24:10.8503225+08:00` to `2026-08-27T23:29:44.0646271+08:00`, exit `0`; `validate_bakeoff_manifest` → `[]`; status `REFERENCE_TARGET_MISSING`, selection `null`, click gate passed.
- `run_preselection_vehicle_migration(..., rx7_fd, duration_s=0.20)` — PID `59692`, exit `0`; validator → `[]`.
- `run_preselection_vehicle_migration(..., ferrari_458, duration_s=0.20)` — v1 PID `51416`, v2 PID `3672`, v3 PowerShell-job PID `32072`; each exit `0`, each validator → `[]`. v2/v3 are retained versioned deterministic reruns and do not overwrite v1.
- Command records are in `tasks/reports/runtime/s12-stage-w/logs/*final_remediation*.stdout.log`. New synthetic WAV/JSON manifests are local evidence only; no external media was ingested.

## Remaining concerns / unverified gates

- Controller must run the single full S12 regression after review; it was intentionally not run here.
- No legal synchronized R1 reference is present. Therefore selection remains `null`, `NO_ARCHITECTURE_CANDIDATE_PASSED / NOT_R1_QUALIFIED`; W7 remains skipped. W10, Profile Freeze, OEM reproduction, MATLAB/R1 comparison, and human PASS remain unverified and prohibited.
- The existing long pytest process was not duplicated or interrupted; its prior result remains controller-owned evidence.

## Task 3 review addendum rework (2026-08-28)

- Critical receipt correction: the former `track_p_guard_final_remediation.stdout.log` was relabeled to `track_p_guard_pre_fix_failure.stdout.log` and is retained only as the pre-fix failure receipt. A new authoritative PASS receipt is generated after the source-fix commit and committed separately below.
- Addendum source-fix commit: `0077b47fda0ebffd3e75d1580832693949d2e3a8` (`fix(s12): close stage w review addendum`). Boundary/click compatibility correction commit: `ff2646f29b12b0e38735b250cc090a2a1af3f8d9`.
- RED command: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q` → 5 expected failures (missing legacy fallbacks, path schedule, inertia diagnostic, click contract fields, external transient API). GREEN after implementation → `18 passed in 3.64s`; Stage-W core focused run → `32 passed, 1 skipped in 21.16s`.
- Event/path authority now uses declared cycle lengths (`four_stroke_720`, `four_stroke_1080`, `rotary_360`, `rotary_1080`), geometry and firing order for phase, and collector assignment only for derived path slots/readback. Missing `transfer_ir` and `collector_assignment` use explicit identity defaults recorded in `parameter_fallbacks`.
- P5 transient is injected into `PersistentEventDomainEngine.process_with_trace(..., external_transient=...)` before PTR and persistent monitor generation. Bakeoff click metrics use only block-boundary indices for raw, post-PTR and monitor outputs and are stored in top-level `click_metrics`.
- `click_contract.py` defines version `s12.stage_w.click_gate.v1`, threshold `0.35`, block-boundary scope, and provenance `bounded_synthetic_engineering_acceptance_threshold`; this is not an external psychoacoustic standard. Timbre layers apply bypass/load/boost and persistent crank-inertia smoothing.

## Addendum final evidence receipt

`final_remediation_evidence_receipt.json` is the compact tracked receipt for the ignored local synthetic output roots. It binds `tested_code_head=ff2646f29b12b0e38735b250cc090a2a1af3f8d9`, inventories bakeoff (666 files/180 WAVs) and RX-7/Ferrari migration roots (167 files/45 WAVs each), records manifest and sorted WAV-list hashes, validator errors `[]`, click-gate status, selection `null`, and `external_media_ingested=false`. No generated WAV or `post_ptr_raw` path is tracked because those names would violate the Track-P basename guard.

Required focused verification after addendum fixes: `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015` → exit `0`; bakeoff validator → `[]`; RX-7 and Ferrari migration validators → `[]`; remediation tests → `18 passed`; Track-P guard and `git diff --check` are rerun after the final receipt commit. Full S12 remains controller-owned and was not run.

## Addendum authoritative receipt and final verification

- The source-fix parent head was `ff2646f29b12b0e38735b250cc090a2a1af3f8d9`. Track-P was run exactly once at that head: command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`, start `2026-08-28T00:08:27.3623787+08:00`, end `2026-08-28T00:08:28.5221518+08:00`, PID not separately retained by the short command, exit `0`, 180 frozen files/2 frozen symbols, `git diff --check` exit `0`, stdout SHA `aa1fb973990fd68b345db169b254a76c0f0a8fbc70dc285056f3e55bd261a6eb`.
- `final_remediation_evidence_receipt.json` and `track_p_guard_final_pass_v2.stdout.log` were committed in distinct receipt commit `cb991cc7f23d9f9db015acc2bf1c0e174db99414`; the receipt inventories local ignored outputs, manifest/SHA-list hashes, zero validator errors, click-gate scope, selection null, and external-media exclusion.
- Final metadata-head rerun: `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`, start `2026-08-28T00:09:18.0418616+08:00`, end `2026-08-28T00:09:18.9413917+08:00`, head `cb991cc7f23d9f9db015acc2bf1c0e174db99414`, exit `0`; console output is in `tasks/reports/runtime/s12-stage-w/logs/track_p_guard_final_metadata.stdout.log`.
- Addendum RED/GREEN command correction: Stage-V first exposed `KeyError: crankpin_geometry` in `test_all_stage_v_configs_have_complete_provenance`; after explicit validation fallback, `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_v_event_domain.py -q` → `12 passed in 2.10s`.
- New focused checks: remediation `18 passed in 3.64s`; Stage-W core `32 passed, 1 skipped in 21.16s`; compileall exit `0`; bakeoff validator `[]`; RX-7/Ferrari migration validators `[]`; JSON receipt parse exit `0`; `git diff --check` exit `0`.
- Process-control incident: a duplicate Stage-W pytest chain was started at `2026-08-28T00:09:28` as PIDs `54820/56240` while original controller PIDs `64172/61476` (started `00:02:15/00:02:16`) remained healthy. Only the later duplicate chain was terminated; originals were preserved. No further Stage-W focused pytest was started.

## Final addendum correction

- `182ded416fed06715359d9e918aa700cb85e6db4` is the all-source-fixes parent. Its Stage-V event-domain RED exposed `KeyError: crankpin_geometry`; the minimal compatibility fallback restored `12 passed in 2.10s`.
- The authoritative post-fix Track-P receipt binds that parent head: command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`; start `2026-08-28T00:13:53.2654533+08:00`, end `2026-08-28T00:13:54.0466030+08:00`, exit `0`, 180 frozen files/2 frozen symbols, stdout SHA `0bf17ddb206c114508305d13bf17f820830f707f3a65d9d74f5b997e40e0287b`.
- Final receipt commit: `cc1c79590f9e40fb7f8cee41bb3d777fccde6815` (`docs(s12): refresh final remediation receipt`), containing the tracked compact `final_remediation_evidence_receipt.json` and PASS log `track_p_guard_final_pass_v3.stdout.log`. The receipt inventories local ignored evidence and binds manifest/SHA-list hashes with validators `[]`, click gates, selection null, and external-media exclusion.
- Final receipt-commit guard rerun: command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`; start `2026-08-28T00:14:27.9644135+08:00`, end `2026-08-28T00:14:28.7283503+08:00`, verified head `cc1c79590f9e40fb7f8cee41bb3d777fccde6815`, exit `0`; stdout SHA `DD80132ACE1391C6A961FF1DB806EC6D55AE8DCDA0A9C91AABBFC99E2632A8F1` (log `track_p_guard_final_metadata_v2.stdout.log`). `git diff --check` and receipt JSON parse both exit `0`.
- The Stage-W pytest duplicate attempt was stopped at PIDs `54820` and `56240`; controller originals `61476`/`64172` were preserved. No further Stage-W long test was started by this task.

## Task 3 second review addendum rework (2026-08-28)

- RED command: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q` initially exposed 3 failures: no shared click helper, click-contract metadata drift accepted, and supplied inertia did not alter every timbre layer. GREEN after the focused source fix: `22 passed in 5.26s`.
- Migration now uses shared `block_boundary_click_metrics` for raw, post-PTR and monitor outputs; validation enforces all three saved outputs. `TimbreMap4D` applies bounded inertia and bypass gains to harmonic, sideband, broadband, casing, and intake layers. External-transient regression compares identical engines with/without transient and proves both post-PTR and monitor divergence. Click contract rejects version/definition/scope/provenance drift while allowing only finite positive threshold overrides.
- Source fix commit: `fec91bf16faa7a51e97a4c26567c01331611e7b2` (`fix(s12): close second stage w review addendum`).
- Current evidence revalidation: `validate_bakeoff_manifest` → `[]`; RX-7/Ferrari `validate_vehicle_migration_manifest` → `[]`; JSON scan over final-remediation local evidence → `730` JSON files, `0` non-finite; `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015` → exit `0`; `git diff --check` → exit `0`.
- Track-P source-fix-head receipt: command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`; start `2026-08-28T00:34:14.8719714+08:00`, end `2026-08-28T00:34:15.6448537+08:00`, verified head `fec91bf16faa7a51e97a4c26567c01331611e7b2`, exit `0`, 180 frozen files/2 symbols, stdout SHA `88933bece4a310332c5a151109d04359e0112278651e0f72d8416ff61ebd7859`.
- The compact receipt was refreshed to bind `fec91bf` and is committed separately after this source-fix commit. Selection remains `null`; external media remains excluded; full S12 remains controller-owned.
- Receipt-head final guard: command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`; start `2026-08-28T00:35:13.0292390+08:00`, end `2026-08-28T00:35:13.7790077+08:00`, verified metadata head `f5ce8374d8a9854472da62b58a41354e4f1422fa`, exit `0`, stdout SHA `c18ad67f9d3128101dc52e1a39b99cf2cb516f2caa05f2c7e52e314ab3dbedbb`, `git diff --check` exit `0`.

## Task 3 second review final current evidence

- Remediation tests: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q` → `22 passed in 5.26s` (exit `0`).
- Affected Stage-W focused suites: exact command `python -m pytest <10 explicit test_s12_stage_w_*.py paths> -q`, parent PID `49496`, Python PID `17004`, start `2026-08-28T00:36:57.5834369+08:00`, end `2026-08-28T00:49:00.6404587+08:00`, exit `0`, `73 passed, 1 skipped in 722.40s`; stdout log `tasks/reports/runtime/s12-stage-w/logs/stage_w_focused_addendum2.stdout.log`, stderr length `0`.
- Complete Stage-V focused regression: exact command `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests -k stage_v -q --disable-warnings`, PID `21268`, start `2026-08-28T00:53:04.6610595+08:00`, end `2026-08-28T00:53:37.6409815+08:00`, exit `0`, `31 passed, 560 deselected`; stdout SHA256 `EBFAED605E52A45813BB57CFF546006556A1B79D6A092EDA558D11BD374423FD`.
- Compileall: `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015` → exit `0`. JSON finite scan over every current final-remediation local evidence JSON → `730` files, `0` non-finite. Bakeoff validator, RX-7 migration validator, and Ferrari migration validator each returned `[]`. `git diff --check` and committed-head Track-P guard each exited `0`.
- Final source-fix head remains `fec91bf16faa7a51e97a4c26567c01331611e7b2`; receipt metadata is updated and committed separately. Selection remains `null`, generated WAVs remain ignored/local synthetic evidence, external media remains excluded, and full S12 remains controller-owned.
- Final metadata-head guard after receipt commit `ec7c86e6fef73ab0196bc932ab11311be8fbd785`: command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`, start `2026-08-28T00:54:59.9460314+08:00`, end `2026-08-28T00:55:00.7972119+08:00`, exit `0`, stdout SHA `bf5aa3cd93454973f3207ec621a5cc503c401b638c85950b900ab3ebb26beeff`, `git diff --check` exit `0`.

## Task 3 third review addendum rework (2026-08-28)

- RED command: `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py -q` → `25 passed, 3 failed`; failures were the block-end off-by-one metric (`0.4` vs expected `0.3`), NaN threshold acceptance, and +Inf threshold acceptance. GREEN after the focused helper/contract fix: `28 passed in 5.17s` (start `2026-08-28T01:07:58.9777223+08:00`, end `2026-08-28T01:08:04.7629799+08:00`, exit `0`).
- Source/test fix commit: `60b5ce74496a1c8aa77fc8ae16d4543320da4295`. `block_boundary_click_metrics` now compares `values[starts[1:]]` with `values[starts[1:]-1]`; threshold overrides reject NaN, all infinities, zero, and negatives; collector-only path perturbation preserves combustion phase while changing collector slot/path ID.
- Fresh v3 evidence was generated only after that source head: bakeoff v3 (`666` files/`180` WAVs), RX-7 v3 (`167`/`45`), Ferrari v4 (`167`/`45`). Generation commands and times are in `tasks/reports/runtime/s12-stage-w/logs/bakeoff_final_remediation_v3.stdout.log`, `migration_final_remediation_rx7_v3.stdout.log`, and `migration_final_remediation_ferrari_v4.stdout.log`; manifest mtimes are `01:04:12`, `01:05:14.6617182`, and `01:06:26.7330481`, all later than `60b5ce7`.
- Fresh validator commands/results: `python -c "from ...stage_w.bakeoff import validate_bakeoff_manifest; print(validate_bakeoff_manifest(r'tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v3'))"` → `[]`; `python -c "from ...stage_w.migration import validate_vehicle_migration_manifest; print(validate_vehicle_migration_manifest(r'tasks/reports/runtime/s12-stage-w/migration_final_remediation_rx7_v3'))"` → `[]`; same command for `migration_final_remediation_ferrari_v4` → `[]`.
- Exact current focused results: explicit 10-file Stage-W command (the complete command is recorded in the compact receipt and log) → `79 passed, 1 skipped in 771.40s`, PID `33328`, `01:09:34.7502791–01:22:26.8108367`, exit `0`, stderr `0`; complete Stage-V command `python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests -k stage_v -q --disable-warnings` → `31 passed, 566 deselected in 32.67s`, PID `62044`, `01:08:35.4484707–01:09:10.5467374`, exit `0`.
- Compileall command `python -m compileall -q tools/sound_sim/s12/acoustic_identity_v015` → exit `0`; JSON finite scan exact roots `tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v3/**/*.json`, `migration_final_remediation_rx7_v3/**/*.json`, `migration_final_remediation_ferrari_v4/**/*.json` → `730` files, `0` non-finite; `git diff --check` → exit `0`; Track-P source-head guard at `60b5ce7` → exit `0`, 180 frozen files/2 symbols, stdout SHA `93baf1de2214f0916feb0f44b938f50c8fc5b2f4fdff5e320c631909ca8dfd71`.
- Compact receipt `final_remediation_evidence_receipt.json` is refreshed to bind `60b5ce7`, fresh v3/v4 output roots and hashes, freshness mtimes, selection null, validator zero-errors, and external-media exclusion. It is committed separately after this source commit; final metadata-head guard is run afterward and recorded.
- Third-review receipt commit: `4d0113f3aa94fe28514f48cd80dc5ad4b404f6b5` (`docs(s12): record fresh third-review v3 evidence`) contains the refreshed tracked compact receipt and exact generation/focused/validator logs. Fresh manifest hashes are bakeoff `3bcfce5ba56d036b6688f8f1251e79eca4c489cd5157e5d62c8be21b05e79952`, RX-7 `11a8e8b0dffb26566f0decf4e163815b9a0996a75a0cc5e0a7a6c7a8784eecef`, Ferrari `dc3a63cbd8492ec44ea14a88347025a21ee1515676551a93c1e509932f07ab0b`.
- Final receipt-metadata guard: command `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`, start `2026-08-28T01:25:59.6176453+08:00`, end `2026-08-28T01:26:00.4151994+08:00`, verified head `4d0113f3aa94fe28514f48cd80dc5ad4b404f6b5`, exit `0`, stdout SHA `8c865edd0f014434a0dba8f5ce28b59a1596d1e318bbd5aeaacf34b6dffc1165`, `git diff --check` exit `0`.
- **Fourth review addendum:** `block_boundary_click_metrics` now uses `starts[1:]` against `starts[1:]-1`; numeric RMS regression uses nonzero block-end samples. Click scope is `synthetic_stage_w_raw_post_ptr_monitor_outputs`, with versioned bounded-synthetic provenance.
- Fresh post-fix evidence was generated from source head `0896f127cd32e5f5950ca03c26595a4533f35ca5`: bakeoff v4 (`be3bebfa0db74c5cc1b098ace4f748f2fc6205529fb3f9157d52d792752d99eb`), RX-7 v4 (`80ab59ca35b7ad684e1dee3f37769d37902ddb837223f9a9ce1fb3027e60e948`), Ferrari v5 (`27cf7ea64b02638db1c782b82d2b0e46eb5cd16b7eda9d5aaac61651a8b34b28`); all validators returned `[]`, all manifests postdated the source commit.
- Literal fresh validator commands: `python -c "from tools.sound_sim.s12.acoustic_identity_v015.stage_w.bakeoff import validate_bakeoff_manifest; print(validate_bakeoff_manifest(r'tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v4'))"` → `[]`; `python -c "from tools.sound_sim.s12.acoustic_identity_v015.stage_w.migration import validate_vehicle_migration_manifest; print(validate_vehicle_migration_manifest(r'tasks/reports/runtime/s12-stage-w/migration_final_remediation_rx7_v4'))"` → `[]`; same complete import/path command with `migration_final_remediation_ferrari_v5` → `[]`.
- Fresh generation logs record bakeoff PID `52976`, `01:31:17.3854912–01:33:10.0907109`, exit `0`; RX-7 PID `24880`, `01:33:58.3704316–01:34:28.4459338`, exit `0`; Ferrari PID `15864`, `01:34:50.7287295–01:35:20.8203950`, exit `0`.
- Source-head Track-P guard: `python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py`, `01:23:38.3620662–01:23:39.3396872`, head `60b5ce7`, exit `0`, 180/2, stdout SHA `93baf1de2214f0916feb0f44b938f50c8fc5b2f4fdff5e320c631909ca8dfd71`; updated source head for receipt is `0896f12` and is represented by fresh v4/v5 evidence.
- Fourth-review source commit: `0896f127cd32e5f5950ca03c26595a4533f35ca5`. Receipt metadata and fresh evidence are committed separately next; final receipt-head guard and `git diff --check` will be recorded after that commit. Selection remains null and external media remains excluded.
- Fourth-review literal validator runs (each exit `0`, result `[]`): bakeoff command at `01:38:50.1654734–01:38:52.5164654`; RX-7 command at `01:38:52.5224546–01:38:53.9369366`; Ferrari command at `01:38:53.9374046–01:38:55.4272439`. Each command uses the complete Python import and exact fresh v4/v5 output path and its stdout log is bound in the receipt.
- Receipt prior-head binding records `e926e96` as `prior_verified_metadata_head`; new source head is `0896f12`; fresh output roots are `bakeoff_final_remediation_v4`, `migration_final_remediation_rx7_v4`, and `migration_final_remediation_ferrari_v5`. The receipt keeps selection `null`, `external_media_ingested=false`, and all external gates fail-closed.
