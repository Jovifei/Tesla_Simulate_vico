# S12 Engine-Audio Ecosystem Map

Stage W separates ecosystem evidence into five architectural families:

1. **Event/physics source:** Engine-Sim, SIVE, ENSIM4, DasEtwas. These inform
   chamber/pipe/waveguide boundaries; ENSIM4 is an offline teacher only.
2. **Cycle-synchronous resynthesis:** PSOLA/OLA, Crankcase REV, AudioMotors.
   These inform phase-aligned grain traversal but require rights-bound recordings.
3. **State-conditioned parametric DSP:** PTR, EONE, DDSP, Fubos, QNX. These
   inform RPM/torque/load maps, harmonic/noise separation and runtime lookup
   boundaries; proprietary or non-commercial assets stay outside S12.
4. **Hybrid authoring/runtime:** VehicleNoiseSynthesizer, Krotos, EVx, Ansys.
   These inform authoring contracts, audition paths and measurement workflows.
5. **Embedded fallback:** ESP32 RC and FiveM schema ideas inform bounded state
   machines only; their code/assets/licensing are not imported.

The current Stage-W paths are `P2H candidate`, `P3 candidate` and `P5
candidate`: persistent event source plus localized afterfire, waveguide/timbre
experiments, a clean-room one-shot residual and the frozen PTR adapter. No path
is selected. P4/P6 remain blocked paths until comparable raw/post-PTR evidence
exists.
External references remain R2/R3 diagnostic pointers, not OEM truth.

`reduced_cfd_teacher_v1` is a separate metric-derived teacher experiment. It
uses the ENSIM CFD ON/OFF receipt without embedding teacher media and is not a
candidate architecture or a numerical CFD parameter fit.
