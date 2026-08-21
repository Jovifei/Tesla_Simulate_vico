# Third-party acoustic tools

| Project | Version observed | License | Purpose | Integration |
|---|---:|---|---|---|
| librosa | 0.11.0 release documented | ISC | STFT, resampling, onset and optional DTW | Optional adapter; absent in this worktree |
| MoSQITo | current documentation | Apache-2.0 | loudness, sharpness, roughness, fluctuation strength | Optional adapter; absent in this worktree |
| pyfar | 0.6.1 documentation observed | BSD-3-Clause | acoustic signal/filter helpers | Optional adapter; absent in this worktree |
| Essentia | 2.1 beta documentation | AGPL-3.0 / commercial alternative | optional feature extraction | External subprocess only; no dependency or vendored code |
| ViSQOL | not installed | Apache-2.0 upstream project | same-model old/new degradation only | Optional external runner; excluded from vehicle identity score |
| webMUSHRA | not embedded | MIT upstream project | compatible test configuration only | Configuration/readme only; no vendored source |

All built-in Stage-M metrics are digital-domain and relative unless a calibrated SPL contract is supplied. No third-party reference recording or project source code is copied into this repository.
