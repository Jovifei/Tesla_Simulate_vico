# Y1-C final evidence report

Status: `DONE_WITH_CONCERNS`

## Scope

This report closes only Stage-Y Y1 parameter reachability. The probe is synthetic, uncalibrated, vehicle-inspired, and not an OEM reproduction. It does not select an architecture or qualify Y2-Y6, R1, human audition, hardware, or a vehicle.

## Canonical execution

- Evidence HEAD / runtime-resolved live HEAD at probe start: `e0436dcdf82d0c6acfcc3a05c7195b91790caffc`.
- Branch/worktree: `agent/s12-stage-y-source-layers-and-reachability` / `E:/Tesla_speed/worktrees/s12-stage-y-source-layers`.
- Run id: `y1c-canonical-16-20260830T183025350+0800`.
- Start/end: `2026-08-30T10:30:25.4177991Z` / `2026-08-30T10:32:33.3060331Z` (128 s).
- Exit code: `0`.
- Exact command: `& 'D:\Python\Python3.14\python.exe' 'E:\Tesla_speed\worktrees\s12-stage-y-source-layers\.superpowers\sdd\run_y1c_canonical_probe.py' 'E:\Tesla_speed\worktrees\s12-stage-y-source-layers\tasks\reports\runtime\s12-stage-y\tmp\y1c-canonical-16-20260830T183025350+0800'`.
- Runner SHA-256: `D070E428C04351BD61B751628D2EDBD2EE1B261C08AC51D268FF920A05608C71`.

The runner selected exactly these 16 controls: `crank_inertia`, `idle_governor`, `primary_attenuation_spread`, `blower_sideband_mix`, `blower_broadband_mix`, `blower_casing_mix`, `boost_attack`, `boost_release`, `bypass_threshold`, `monitor_attack`, `monitor_release`, `monitor_max_makeup`, `afterfire_reservoir_rate`, `afterfire_ignition_delay`, `afterfire_location_mix`, and `afterfire_energy`.

It rendered only to the unique temporary root. Exit 0 stdout reports `16/16`; an independent JSON parser then confirmed finite values, exactly the ordered 16 names, `reachable_count=16`, `unreachable=[]`, and for every parameter/direction: `finite=true`, `sha_changed=true`, and `target_movement > 0.02`.

## Publication and hashes

The generated temporary receipt was copied once, without rerendering, to `tasks/reports/runtime/s12-stage-y/y1_reachability/parameter_reachability.json`. Temporary and published SHA-256 are both `BB58F993A3863432ADC0FD806C975BFA6886A87DD6BA5908EF4244A13A60CFC5`.

| Artifact | SHA-256 |
| --- | --- |
| pre-run metadata | `29BC562970E6B2BC8EFA60F01275AE2155B6AD5745402E39EB9FBE3E84C5C349` |
| run metadata | `A3E22D5E9E528CAE839F0D5E287DBAB4F7350D4EC6CB24EDC52C35A14B64B543` |
| stdout log | `F3797EF6C3A9E5163A8FD66DF09FD90AF8BA33567A567DB0BA1F11EFE7CFBF5D` |
| stderr log | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |

The initial use of unsupported `Copy-Item -NoClobber` created an empty target directory but copied no receipt. The target file was then explicitly verified absent before one ordinary `Copy-Item`; the resulting published SHA equals the temporary SHA. No second probe ran.

## State transition

`Y0_SETUP` is `PASS`, bound to the real setup ledger commit `9dffb65dc885e4b272f0286a6dc1350b83f66a4d`; `Y1_REACHABILITY` is `PASS`, bound to its tested evidence HEAD rather than the future metadata commit. The active phase is `Y2_HARMONIC_MAP` (`IN_PROGRESS`), and Y3-Y6 remain `NOT_STARTED`.

## Concerns

- The pre-existing exact raw-PCM snapshot/replay failure is still an open Y4/Y5 transient/state-chain blocker.
- This evidence is not R1, OEM, real-device, or human-audition proof.
