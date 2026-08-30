# Stage Y Resume

- Branch: `agent/s12-stage-y-source-layers-and-reachability`
- Worktree: `E:/Tesla_speed/worktrees/s12-stage-y-source-layers`
- Y0 setup receipt: `9dffb65dc885e4b272f0286a6dc1350b83f66a4d` from base Stage-X `3d433e30f2c0238d65baed321aa70355a626ceb6`.
- Y1 evidence HEAD: `e0436dcdf82d0c6acfcc3a05c7195b91790caffc` (`e0436dc`); the runtime-resolved live HEAD at probe start was the same.
- Y2 fitted harmonic map: `PASS`. The committed map is `tools/sound_sim/s12/acoustic_identity_v015/stage_y/data/hellcat_fixture_timbre_map.json` (file SHA-256 `BA2687E0028F1588D0EFDC09156D096AE099524536B429B56302C8E32D00B491`), built from pre-metadata source HEAD `2601ef7d04a6ffe50a9302580f62fcdab54ffd85`. It is `FIXTURE_ONLY`, `NOT_TUNING_AUTHORITY`, and `NOT_OEM`.
- Current phase: `Y3_CYCLE_SYNC_P4` (`IN_PROGRESS` / `FAIL_REPAIRING`).
- Y3 checkpoint source HEAD is `49ef180f4cb2c351d0583bd0459144781a4da54f`; the uncommitted Y3 patch diff hash recorded in its receipt is `e7570d4becf2827cd252291bf78b74e3eae0aed9`.
- Y3 proved the 720-degree semantic RED/GREEN (`2π` previously returned the fixture start; `4π` now repeats the full fixture cycle) and centralized P4 into the candidate inventories. It is not PASS: persisted run `y3-stage-w-bakeoff` ended `4 failed, 8 passed in 103.06s`. P3's existing fitted-map bakeoff raw peak is `1.989831651`; P4 is `1.989985522` and P5 is `1.989831651`, so PCM24 writing fails closed before P4 stage completion. The `Y4/Y5` snapshot/replay blocker remains separate and untouched. Do not repair raw scaling or the fitted map without a new authorization.
- Y3 receipt: `tasks/reports/runtime/s12-stage-y/y3_cycle_sync_p4/y3_cycle_sync_p4_receipt.json`; persistent logs are in the adjacent `logs/` directory.
- Y2 receipt: `tasks/reports/runtime/s12-stage-y/y2_harmonic_map/y2_harmonic_map_receipt.json`. Final postfix evidence is source HEAD `2dd4ad639617c0c6e2c9a816cfc91d9cecb1ba3d`: the complete Y2 harmonic-map file plus the Y1 P3 parent golden passed `9 passed in 7.75s`; logs are `logs/y2-postfix-9-20260830T112038431Z.stdout.log` and `.stderr.log`, hash-bound in the receipt. The earlier `16 passed, 1 deselected` compatibility run is historical only, not final Y2 postfix evidence.
- Y1 canonical receipt: `tasks/reports/runtime/s12-stage-y/y1_reachability/parameter_reachability.json` (SHA-256 `BB58F993A3863432ADC0FD806C975BFA6886A87DD6BA5908EF4244A13A60CFC5`).

Do not rerun the Y1 long selected-16 probe: the 128-second canonical run completed 16/16 with bilateral finite/SHA/target-movement evidence. A later metadata commit is not the Y1 evidence HEAD.

## Next focused command

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_cycle_sync.py -q
```

## Open blocker carried to Y4/Y5

The pre-existing exact raw-PCM snapshot/replay discrepancy in `test_snapshot_restore_replays_exact_audio_and_reset_starts_new_state` remains assigned to the Y4/Y5 transient/state-chain scope. It was not resolved or reclassified by Y1 reachability evidence.
