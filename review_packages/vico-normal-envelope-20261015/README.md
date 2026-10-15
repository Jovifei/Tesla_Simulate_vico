# Bounded normal slow-amplitude shaping

Normal playback retains canonical seam softening and adds a fixed causal envelope shaper **before** original shiftGain and event addition. Energy EMA constants are 50/600ms, amplitude smoothing5ms, warmup250ms and strength.3; effective continuous-sound multiplier is bounded to .97–1.03. `LEGACY_LOCKED` and the previous seam-only mode retain their output. Source WAV, fixed gain, events and original S13/S14 references are unchanged.

This intentionally changes effective normal drymix amplitude. It is not a gain-normalized rescue of rejected regrain, a phase fix or complete de-repetition. Real controlled-bank measurements reduce C63 910RPM target modulation power36–37%, while exact-period ACF stays about.993–.995. Full recurrence removal remains CHANGES_REQUIRED; classification is **LIMITED_AM_DEPTH_AUDITION** following local independent review.

Same-tree local evidence: 48 fixed cases and18 dynamic traces; 73,411,266 sample-stride100ms windows within original±.5dB; original six-car30s S13 bit-exact; Android498passed29skipped0failed, lint0errors6warnings, assembleDebugPASS; Python155passed2Windows-permission skips, JS31passed; actualN2JVM46passed2assumption skips and two exported partitions. No phone/road/acoustic/human acceptance is inferred.

The accompanying verification.json binds implementation file hashes and actual APK identity. The external local delivery manifest at `E:/Tesla_speed/review_packages/normal-envelope-kmh-20261015/manifest.json` records the final commit and hostedCI separately. This repository commit does not contain generated PCM/APK or private phone logs.
