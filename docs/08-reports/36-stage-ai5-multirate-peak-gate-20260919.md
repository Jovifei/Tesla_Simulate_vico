# Stage AI-5 — Multi-rate reconstructed-peak qualification (2026-09-19)

## Why this stage exists

Stage AI-4B repaired the measured RX-7 startup-boundary overshoot with an
explicit, RX-7-only 24-frame fade. The local audit then verified the repaired
ten-scene RX-7 outputs at 4x/8x/16x and found them below 1.0.

However, the reusable runtime qualification path still accepted a candidate
from the historical `peak_estimate_4x` field alone. A synthetic RED case proves
that a waveform can remain below 1.0 at 4x while exceeding 1.0 at 8x/16x.
Therefore the real-material audit was stronger than the code contract used by
future feedback trials.

This stage closes that contract gap. It does **not** change any audio samples.

## Source and scope

Base:
`local/stage-ai4b-audit-20260919@d437e7959e6c04eb61c38a135ca270b8f5924539`

Branch:
`feature/stage-ai5-multirate-peak-gate-20260919`

Scope:

- add an artifact-domain reconstructed-peak receipt at 4x/8x/16x;
- retain the historical 4x field for compatibility;
- require the multi-rate receipt in the reference-feedback numeric gate;
- attach the receipt to remaining-vehicle, four-car, and remediation reports;
- run the new regression in exact-head CI;
- treat missing/malformed peak evidence as failure, not zero;
- keep the AI-4B RX-7 boundary repair opt-in and unchanged.

No DSP, source parameter, IR, Reference, seed, K/C, global gain, output WAV, or
old package is modified by this stage.

## RED case

The new regression contains a fixed stereo vector whose measured values with
the governed interpolation method are approximately:

- 4x: below 1.0;
- 8x: above 1.0;
- 16x: above 1.0.

That is sufficient to demonstrate that a 4x-only numeric gate has a blind
spot. The test vector is synthetic and is not vehicle-fidelity evidence.

## Receipt contract

`reconstruction_peak.py` computes the final decoded-PCM-domain signal with:

- factors: 4 / 8 / 16;
- `scipy.signal.resample_poly`;
- Kaiser beta 5.0;
- `line` boundary;
- threshold 1.0.

The receipt is explicitly
`ENGINEERING_DIAGNOSTIC_NOT_ITU_EBU_CERTIFIED`.

A candidate passes only when all declared factors are present, finite, have
zero threshold exceedance count, and remain at or below 1.0. Missing evidence
fails closed.

The new gate is applied to final decoded PCM float so the decision corresponds
to the actual emitted artifact rather than only an earlier pre-quantized float
buffer.

## Relationship to AI-4B

AI-4B remains the sound-changing repair. AI-5 is evidence hardening only.

The existing AI-4B package remains immutable. Local validation must rerun the
fresh candidate path and confirm:

1. RX-7 ten-scene 4x/8x/16x receipts all pass;
2. Aventador remains unchanged and passes;
3. feedback-off baseline identity remains correct;
4. no old package/WAV/IR/Reference is overwritten;
5. any candidate that previously passed only because 4x was safe is now
   correctly blocked.

## Human / promotion boundary

A multi-rate numeric PASS is not a Human PASS, OEM match, similarity
percentage, or profile-freeze authority. R3 recordings remain unsynchronized
and unverified. Acoustic decisions remain with Jovi after the numerical and
identity evidence is complete.
