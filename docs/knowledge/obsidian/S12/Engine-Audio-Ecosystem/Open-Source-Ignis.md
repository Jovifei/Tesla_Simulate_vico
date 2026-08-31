---
title: Ignis Engine Simulation Research Boundary
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-Y
document_type: source_note
status: method_only_reuse_blocked
source_url: https://github.com/xevrion/ignis
source_commit: a618baeede8caed46ada304ed06c4ea01a835aa6
license: NONE_FOUND_IN_TRACKED_TREE
checkout_path: E:/Claude_allow/Download/s12-stage-y-research/ignis
updated: 2026-08-31
---

<!-- S12-STAGE-Y:AUTO:BEGIN -->
# Ignis research boundary

The intake-pinned sparse checkout is at
`E:/Claude_allow/Download/s12-stage-y-research/ignis`, with current HEAD
`a618baeede8caed46ada304ed06c4ea01a835aa6`. The tracked tree has no
`LICENSE`; treat the repository as all-rights-reserved for reuse decisions.
No build or test was run, no fetch/checkout mutation was made, and the intake
records `materialized_audio_files=0` for the S12 research boundary.

## Method reference only

The README describes a real-time internal-combustion simulation in which a
constraint solver drives crank/rod/piston state, a lumped gas/combustion model
produces cylinder pressure, and the exhaust note is synthesized sample by
sample from that simulated pressure. Those descriptions are useful vocabulary
for a simulation-coupled pressure-to-audio architecture; they are not a claim
that Ignis is a validated CFD or acoustic model for S12.

S12 keeps its own implementation in [`PersistentEventDomainEngine`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py),
[`event_domain/`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/event_domain/),
and the Stage-Y [`PressureAudioChain`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_y/audio_chain_dp.py).
There is no Ignis source, C++ file, demo media, preset, or asset copied into
S12. Do not promote this note into a Runtime replacement, OEM identity proof,
or license grant.

The intake record is [stage-y-research-intake.json](../../../../../.superpowers/sdd/stage-y-research-intake.json);
the machine-readable registry is [`source_registry.json`](../../../../research/engine-audio-ecosystem/source_registry.json).
<!-- S12-STAGE-Y:AUTO:END -->
