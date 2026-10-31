# Formal candidate execution blocked

Status: STOPPED_MATLAB_SESSION_ATTACH_FAILED. The new SLX is an unchanged byte copy, not an integrated formal candidate. No diagram edits or simulations were performed.

## Exact attempted call and result

Tool: `mcp__matlab__evaluate_matlab_code`; `project_path` = `E:\Tesla_speed`.

```matlab
disp(['MATLAB=',version]); disp(['CWD=',pwd]); disp(['OPEN_MODELS=',strjoin(find_system('SearchDepth',0),',')]); disp(['MB_SOURCE=',which('mb_source_frame')]); disp(['SMOKE=',which('mb_smoke_step')]); disp(['FROZEN=',which('S12_Frozen_Radiation_Adapter_v12')]);
```

The tool returned `isError=true`, `failed to attach to MATLAB session`, after 30.0 seconds. The requested MATLAB expressions were not executed; no retry was attempted. A process/session failure is established, but its underlying cause is not established by this response.

## Files created by this attempt

- `isolated-model/S12_hellcat_cabin_formal_candidate.slx`: byte copy of the protected worktree Hellcat V12 model; no wiring or content edits.
- `isolated-model/FORMAL-PLAN.md`: isolated execution checklist and stop review.
- `isolated-model/formal-blocked-receipt.json`: machine-readable failure and selected SHA-256 checks.
- `FORMAL-EXECUTION-BLOCKED.md`: this report.

Source: `E:\Tesla_speed\worktrees\hellcat-state-contract-20261027\tools\sound_sim\s12\playground_v12\vehicles\hellcat_2022_stock\S12_hellcat_2022_stock_v12.slx`

New copy: `E:\Tesla_speed\worktrees\hellcat-state-contract-20261027\reports\app8-cabin-mechanical-bank-candidate-20261030\isolated-model\S12_hellcat_cabin_formal_candidate.slx`

Protected adapter: `E:\Tesla_speed\worktrees\hellcat-state-contract-20261027\tools\sound_sim\s12\playground_v12\common\shared_model\S12_Frozen_Radiation_Adapter_v12.slx`

The source and copy SHA-256 are both `71f8b9899688278e908e244649331352d43c46779e6fd93c0903f86785198a9c`; the adapter SHA-256 is `6079affc48fb9de2cd89e5853967718269427bbb75ddda688879f9c5d81cb644`. These three hashes match the values recorded immediately after copying. This is a selected-file check, not a fresh full protected-tree manifest.

The registered project root has an existing `.satk/reuse-libraries.json` with no configured reusable libraries; the independent worktree has no `.satk` declaration. No library setup was changed.

## Not performed

Formal candidate wiring, cold reload, Update Diagram, Active Compile, `model_check`, 0.04–0.2 s simulation, PCM extraction, screenshots, 90 s simulation, acoustic or device/human qualification. Earlier minimal-smoke evidence does not prove the formal signal path.

A separate project hub revision request for this actual worktree returned `worktree does not belong to the registered repository`; no event was created and no automatic retry was attempted. The parent is responsible for outside-boundary reporting.
