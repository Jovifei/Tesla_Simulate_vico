# Stage Y Resume

- Branch: `agent/s12-stage-y-source-layers-and-reachability`
- Worktree: `E:/Tesla_speed/worktrees/s12-stage-y-source-layers`
- Y0 setup receipt: `9dffb65dc885e4b272f0286a6dc1350b83f66a4d` from base Stage-X `3d433e30f2c0238d65baed321aa70355a626ceb6`.
- Y1 evidence HEAD: `e0436dcdf82d0c6acfcc3a05c7195b91790caffc` (`e0436dc`); the runtime-resolved live HEAD at probe start was the same.
- Current phase: `Y2_HARMONIC_MAP` (`IN_PROGRESS`).
- Y1 canonical receipt: `tasks/reports/runtime/s12-stage-y/y1_reachability/parameter_reachability.json` (SHA-256 `BB58F993A3863432ADC0FD806C975BFA6886A87DD6BA5908EF4244A13A60CFC5`).

Do not rerun the Y1 long selected-16 probe: the 128-second canonical run completed 16/16 with bilateral finite/SHA/target-movement evidence. A later metadata commit is not the Y1 evidence HEAD.

## Next focused command

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_harmonic_map.py -q
```

## Open blocker carried to Y4/Y5

The pre-existing exact raw-PCM snapshot/replay discrepancy in `test_snapshot_restore_replays_exact_audio_and_reset_starts_new_state` remains assigned to the Y4/Y5 transient/state-chain scope. It was not resolved or reclassified by Y1 reachability evidence.
