# Third-party acoustic tools

| Project | Version observed | License | Purpose | Integration | Required? |
|---|---:|---|---|---|---|
| librosa | 0.11.0 release documented | ISC | STFT, resampling, onset and optional DTW | Optional adapter; absent in this worktree | Optional |
| MoSQITo | current documentation | Apache-2.0 | loudness, sharpness, roughness, fluctuation strength | Optional adapter; absent in this worktree | Optional |
| pyfar | 0.6.1 documentation observed | BSD-3-Clause | acoustic signal/filter helpers | Optional adapter; absent in this worktree | Optional |
| Essentia | 2.1 beta documentation | AGPL-3.0 / commercial alternative | optional feature extraction | External subprocess only; no dependency or vendored code | Optional, subprocess only |
| ViSQOL | not installed | Apache-2.0 upstream project | same-model old/new degradation only | Optional external runner; excluded from vehicle identity score | Optional, same-model only |
| webMUSHRA | not embedded | MIT upstream project | compatible test configuration only | Configuration/readme only; no vendored source | Optional, local configuration only |

All built-in Stage-M metrics are digital-domain and relative unless a calibrated SPL contract is supplied. No third-party reference recording or project source code is copied into this repository.
