# Stage W-C final branch remediation report

Status: `DONE_WITH_CONCERNS`

The final remediation wave started at `69a1c9580cab67d1ca751190bb99072eaa169849` and remains fail-closed. No Track-P/frozen PTR mathematics, external copyrighted media, Obsidian Vault, push, merge, PR, or full S12 run was performed.

## Commits by cluster

- Cluster A — `f310e914489a3b7088a7d1cbb27c5862ea362f94` (`fix(s12): protect stage w raw evidence logs`).
- Cluster B — `76b2bd3527e4f6e226fc09b9215bdc8f446e6aab` (`fix(s12): persist afterfire and waveguide state`).
- Cluster C — `519425ffcf8ee057f71137265376fecf5119ec88` (`fix(s12): consume stage w topology and timbre contracts`).
- Cluster D — `8bf2280434c75416d58f1727058d05643a2132af` and `446b845e9526538cf248cdc5aea457b1b27357b7` (click metrics, explicit geometry/timbre contracts, bakeoff/migration gates).
- Cluster E — implemented in `76b2bd3527e4f6e226fc09b9215bdc8f446e6aab` via `StageWBoundaryAdapter` SHA enforcement.
- Cluster F — bounded regenerated evidence is under `tasks/reports/runtime/s12-stage-w/bakeoff_final_remediation_v1/`, `migration_final_remediation_rx7_v1/`, and `migration_final_remediation_ferrari_v1/`; this report and command logs are committed with the evidence.

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

## Evidence regeneration

- `run_hellcat_bakeoff(..., output_root=bakeoff_final_remediation_v1, duration_s=0.20)` — PID `23116`, `2026-08-27T23:24:10.8503225+08:00` to `2026-08-27T23:29:44.0646271+08:00`, exit `0`; `validate_bakeoff_manifest` → `[]`; status `REFERENCE_TARGET_MISSING`, selection `null`, click gate passed.
- `run_preselection_vehicle_migration(..., rx7_fd, duration_s=0.20)` — PID `59692`, exit `0`; validator → `[]`.
- `run_preselection_vehicle_migration(..., ferrari_458, duration_s=0.20)` — v1 PID `51416`, v2 PID `3672`, v3 PowerShell-job PID `32072`; each exit `0`, each validator → `[]`. v2/v3 are retained versioned deterministic reruns and do not overwrite v1.
- Command records are in `tasks/reports/runtime/s12-stage-w/logs/*final_remediation*.stdout.log`. New synthetic WAV/JSON manifests are local evidence only; no external media was ingested.

## Remaining concerns / unverified gates

- Controller must run the single full S12 regression after review; it was intentionally not run here.
- No legal synchronized R1 reference is present. Therefore selection remains `null`, `NO_ARCHITECTURE_CANDIDATE_PASSED / NOT_R1_QUALIFIED`; W7 remains skipped. W10, Profile Freeze, OEM reproduction, MATLAB/R1 comparison, and human PASS remain unverified and prohibited.
- The existing long pytest process was not duplicated or interrupted; its prior result remains controller-owned evidence.
