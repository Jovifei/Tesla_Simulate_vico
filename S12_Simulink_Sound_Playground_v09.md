# S12 Simulink Sound Playground v0.9

## Current state

```text
generated but not validated
NOT_READY_FOR_CONTROLLED_REBUILD
```

`tools/sound_sim/s12/playground/S12_Sound_Playground.slx` is
`PRE_REPAIR_INVALID_AUDIT_EVIDENCE`, SHA-256
`FA91F46A2F8F6D78586FAE407E795BCEB99AD529F76925A4AF806F9AC73595C0`.
It must not be opened, rebuilt, overwritten, repaired incrementally, renamed as
a repaired model, or used as simulation/audio evidence.

## Offline repair boundary

The source now prepares a separate repaired-candidate path and the following
future gate order:

```text
Build temporary candidate -> structure inspection -> compile/dimensions
-> simulation/PCM -> sensitivity -> repeatability -> candidate promotion
```

No gate after source preparation has run. In particular, there is no current
evidence for Simulink compile, simulation, Audio Device Writer playback, PCM
output, parameter sensitivity, cold-load repeatability, or v0.8 runtime
equivalence.

Qualification mode is designed to disable device output and log PCM. Interactive
mode is designed for device output, but no Dashboard HMI binding is validated.
The direct MATLAB renderer is only `direct_matlab_reference`; it is not Simulink
evidence. All source and parameters remain synthetic, uncalibrated, offline,
and not realtime-qualified.

The frozen FVM, PTR/radiation, and runtime numerical cores remain out of scope.
Only a new independent review returning `READY_FOR_CONTROLLED_REBUILD` may
authorize a visible-Desktop rebuild attempt.
