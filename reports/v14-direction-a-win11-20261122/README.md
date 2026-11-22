# v1.4 Direction A Step 1 on Windows 11

The PR #42 package at `9ca635f754476503d2bbd1e0c5ad6ab1c4d18bc6` compiled on Windows 11 with the VS 2022 x64 Release toolchain. Its offline executable captured the 2-second generic cross-plane V8 scene. The verifier confirmed finite streams, positive absolute pressures, clockwise rotation and expected sample timing. It recorded 592 clipped samples and a normalized peak of 1.0. [Host receipt](host-receipt.json) · [Capture verification](verification.json)

| Stream | Frames | Bytes |
| --- | ---: | ---: |
| Pressure | 20,000 | 1,440,000 |
| Signed angular velocity | 20,000 | 80,000 |
| Six native float audio taps | 88,200 | 2,116,800 |

The host exported all 17 byte-verified package files. The engine pin `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630` resolves the solver gitlink to `e009f4ff1c9c4c5874e865e893cdb62e208fb2b3`, which matched the actual solver checkout. The two original repositories retained their starting HEADs and status. The package's 23 synthetic fixture tests also passed on this host.

The local PowerShell wrapper bound verified paths and recorded the four native exit codes. Its exit-code instrumentation inadvertently removed their immediate stop checks. All four command exits were 0. The original export, source identity, solver and repository guards ran, and a separate invocation of the exact capture verifier reproduced the verification JSON. The binary and data support the offline smoke result. A verbatim HOST-RUNBOOK execution remains unverified.

The RX-7 capability check is `MODEL_INCOMPLETE` per the approved v1.4 plan. `direction-a-step1-20261112/model_builder.cpp` creates pistons and connecting rods, and the pinned `upstream/src/engine.cpp` instantiates `PistonEngineSimulator`. The smoke entry provides no dedicated two-rotor chamber volume, side intake, peripheral exhaust or sequential twin-turbo model. The historical `classic_rotary` template is a registry reference. RX-7 runtime and acoustic qualification are `NOT_RUN`.

Original host evidence is under `E:\Tesla_speed\experiments\direction-a-step1-20261112`. The readback and wrapper logs are in `E:\Tesla_speed\experiments\v14-local-handoff-20261122`. The receipt binds the source identity, executable, logs and all capture files by SHA-256. Acoustic qualification, Jovi's audition, device playback, static cabin and dynamic vehicle checks are `NOT_RUN`.
