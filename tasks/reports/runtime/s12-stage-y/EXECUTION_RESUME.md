# Stage Y Resume

- HEAD SHA: `3d433e30f2c0238d65baed321aa70355a626ceb6` (`3d433e3`)
- Branch: `agent/s12-stage-y-source-layers-and-reachability`
- Worktree: `E:/Tesla_speed/worktrees/s12-stage-y-source-layers`
- Current phase: `Y0_SETUP`
- Work is on the Stage Y branch, not Stage X (`agent/s12-stage-x-r2-engineering-selection`).
- Do not restart Stage V.

## Next command

Task 1 pytest for inertia / governor / spread (from this worktree):

```
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_crank_inertia_changes_post_ptr_sha_on_idle tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_idle_governor_changes_post_ptr_sha_on_idle tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_primary_attenuation_spread_changes_post_ptr_sha -q
```
