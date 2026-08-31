---
title: DasEtwas Enginesound Research
project: Tesla-Speed-Sound
subproject: S12
stage: Stage-W
document_type: source_note
status: studied_clean_room
source_url: https://github.com/DasEtwas/enginesound
source_commit: e5fcca587397c0c8ba9c9d24874b951fed74d260
license: MIT plus separate notices
s12_git_branch: agent/s12-stage-w-ecosystem-bakeoff
s12_git_commit: 418d16b
created: 2026-08-26
updated: 2026-08-26
tags:
  - S12
  - Open-Source
  - Waveguide

<!-- S12-STAGE-W:AUTO:BEGIN -->
The public Rust source shows cylinder intake/exhaust waveguides, extractor,
delay-line chambers, muffler, warmup and crossfade. S12 uses only the
architecture idea through its independent waveguide_v1; Rust, presets, sample
audio, fonts and GUI are not copied. Docker Cargo reached crates.io but stopped
on TLS certificate validation; no TLS bypass, binary or warmup WAV is claimed.
<!-- S12-STAGE-W:AUTO:END -->
