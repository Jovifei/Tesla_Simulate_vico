---
title: Markeasting Engine Audio Research Boundary
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-Y
document_type: source_note
status: method_only_audio_rights_unverified
source_url: https://github.com/markeasting/engine-audio
source_commit: b8cf9887c914f17c2f006d68427080e39d02d0b0
license: MIT_REPOSITORY_LICENSE_AUDIO_RIGHTS_UNVERIFIED
license_sha256: 99E303F33F8EC31D38E009A5A6A616142903602A8B1A15BA3202F49982F4C4B8
checkout_path: E:/Claude_allow/Download/s12-stage-y-research/engine-audio
updated: 2026-08-31
---

<!-- S12-STAGE-Y:AUTO:BEGIN -->
# Markeasting Engine Audio research boundary

The intake-pinned sparse checkout is at
`E:/Claude_allow/Download/s12-stage-y-research/engine-audio`, with current
HEAD `b8cf9887c914f17c2f006d68427080e39d02d0b0`. Its repository `LICENSE` is
MIT and has SHA-256
`99E303F33F8EC31D38E009A5A6A616142903602A8B1A15BA3202F49982F4C4B8`; that
repository license does not verify individual rights for the tracked audio
files. No install or build was run, no fetch/checkout mutation was made, and
the intake records `materialized_audio_files=0` for S12 ingestion.

## Method reference only

The README exposes a public browser demo but does not establish a reusable
audio-data license or a source-to-S12 compatibility contract. The repository
may therefore inform only high-level authoring/runtime questions such as
state-conditioned layered playback and UI-to-audio control separation. It is
not a source, WAV, recording, preset, or asset dependency of S12.

The current S12 analogues are the cumulative stem contract in
[`stage_y/package.py`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_y/package.py)
and the stateful monitor/source split in
[`PersistentEventDomainEngine`](../../../../../tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py).
Those are independent clean-room software paths and remain synthetic,
uncalibrated and not OEM reproduction.

The intake record is [stage-y-research-intake.json](../../../../../.superpowers/sdd/stage-y-research-intake.json);
the machine-readable registry is [`source_registry.json`](../../../../research/engine-audio-ecosystem/source_registry.json).
<!-- S12-STAGE-Y:AUTO:END -->
