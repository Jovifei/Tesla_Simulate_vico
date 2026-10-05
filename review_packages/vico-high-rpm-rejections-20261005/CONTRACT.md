# Isolated C63 high-RPM phase-registration experiment

Baseline commit 955b1355839f4b233e56c9ec9213fb86ae1927a6. This is an offline candidate, not a replacement of the installed normal bank or frozen S12 reference emitter.

## Evidence and proposed mechanism

All 16 original C63 loop float32 arrays were reproduced exactly from the pinned Python recipe. At load .92, 5500→6800 RPM source RMS drops 13.4773 dB and bank RMS drops 15.8605 dB. This source/transfer behavior is separate from RPM-layer mixing and is NOT fixed by the candidate below.

A 50-RPM diagnostic scan of the actual Kotlin renderer at .32/.62/.92 load found 6950/.32 path correlation −.6457, 10-second interpolation cancellation −7.5167 dB, worst 500-ms −8.8582 dB relative to the amplitude-weighted endpoint RMS. This comparator is a diagnostic upper envelope, not physical target loudness. Rotating every loop to a calculated source crank origin improved high-RPM cases but degraded some low-RPM cases by .639 dB. That full-bank variant is rejected as a product change.

## Minimal candidate (operator-reported prior agreement; independent chronology receipt unavailable)

Only cyclically rotate the four existing 6800/7200 RPM loops at loads .32/.92. All other loops, including the four previously reviewed low-RPM overlay loops, and every event file retain byte identity. No gain, EQ, source resonator, renderer interpolation law, gear ratio or controller change.

The original 0.52-second source has 24961 frames and the exporter takes its last 17280 frames. The first retained source sample is index7681; source crank phase uses a cumulative increment before that sample, thus phase is (7681+1)*rpm/(120*48000) four-stroke cycles. The original exporter rewrites the first384 samples with its old crossfade. Register at the first whole four-stroke cycle in the unmodified portion: round(ceil((7682+384)*rpm/(120*48000))*120*48000/rpm-7682), giving789 samples at6800 and1118 at7200. The initial all-bank diagnostic used318 at7200; that point lies inside the old crossfade and is rejected as a source-origin contract. The next whole cycle is selected from source provenance before new held-out tests. This uses source provenance, not correlation-maximizing fitted offsets. Rounding error is at most half a sample. The registration only establishes the crop's initial crank origin; it does NOT make an arbitrary .36-second loop an integer-cycle waveform or prove all operating phases are coherent.

Cyclic rotation preserves sample multiset, length, DC, RMS, peak, discrete Fourier magnitude, and periodic frequency grid. It moves the location of existing waveform features; it does not cure the old high-RPM loop seam. The source's high-RPM amplitude weakness remains.

## Admission gates

1. Prove exact baseline identities and the permutation; all original bank files remain untouched. Candidate decoded PCM must equal the exact specified rotation, 17280 finite mono48k samples, same gain metadata and original peak budget−1.5dBFS. No clipping or normalization permitted.
2. Repeat real-renderer broad scan plus held-out RPMs 6830/6890/7020/7090/7170 and held-out loads .47/.77, 30-second windows; include initial and warmed phase windows. Report correlation, full/window cancellation and raw peak counts. For severely cancelling cases (baseline≤−4dB), median improvement must reach3dB; no held-out worst500ms cancellation may regress more than.5dB. These are engineering protection gates, not OEM/acoustic acceptance.
3. Compare magnitude-band error against freshly generated, unchanged Python S12 steady controls. Target/protection RMS/band median andP90 errors must not regress more than.5dB; publish all outcomes, including failures. Do not select a new gain or offset to save a failed gate.
4. At and below5500RPM, actual renderer PCM must remain bit-identical. Above5500, test both new/old layer boundaries, ramp-up/down and the existing REAL 0→144→0 trajectory with events. Raw nonfinite/hardclip/above-contract counts must remain0. Report derivative/window transient changes without asserting a moved periodic feature is eliminated.
5. Keep reference bank/loaders and Python authority untouched. Any product route requires independent review after evidence; this experiment alone provides no installation or human listening approval.
