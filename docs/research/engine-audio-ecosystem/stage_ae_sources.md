# Stage AE source absorption

## HiFi-LoFi / FFTConvolver

- Upstream: `https://github.com/HiFi-LoFi/FFTConvolver`
- Pinned: `non-uniform@f2cdeb04c42141d2caec19ca4f137398b2a76b85`
- License: MIT
- Absorbed: deterministic partitioned FIR-convolution architecture suitable for later portable C++ exhaust transfer.
- Local implementation: independent Python numerical reference in `stage_ae/partitioned_convolver.py`; no upstream C++ source copied in Stage AE.

## Vangardo / engine-sim-unity-audio

- Upstream: `https://github.com/Vangardo/engine-sim-unity-audio`
- Pinned: `main@77080ca72765e72123038b916af9950e29793728`
- License: MIT
- Absorbed: manifest-driven generation, pin/NOTICE/PATCH discipline, and most importantly **one gain policy across a whole RPM/load bank** instead of per-clip normalization.
- Local consequence: Stage AE uses one attenuation-only gain per vehicle package, preserving idle/cruise/WOT relative energy.

## Google Oboe

- Upstream: `https://github.com/google/oboe`
- Pinned research snapshot: `main@2a45aa2d9e94d209c4636eec4014dd83cda110f4`
- License: Apache-2.0
- Absorbed now: future Android interface assumptions only (low-latency callback, frames-per-burst/device negotiation).
- No Oboe source is copied into Stage AE Python. Actual integration belongs to the Android phase after Golden Evidence/C++ equivalence.

## Engine-Sim

- Pinned research commit: `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630`
- Root code license: MIT.
- Stage AE keeps the successful event/blowdown/path concepts, but does **not** assume every WAV/IR asset has independently verified redistribution provenance.
- External IRs are fail-closed through `IrAssetSpec`; unknown public IRs remain research diagnostic only.
- The Stage-AD `EngineAcoustics` implementation is now teacher/diagnostic, not production authority.

## BitResonant / EV-engine-sound-sonification

- License: CC BY-NC-SA 4.0.
- Method-only reference for low-rate telemetry interpolation, dropout/late-frame handling and control/audio-rate separation.
- No copied runtime code is accepted into the commercial-capable product path.

## DiffMoog / DDSP family

Retained for future parameter warm-start/inversion research. Their role is proposal generation only:

```text
Reference → proposal/warm-start θ → canonical S12 renderer → governed comparator → Human Gate
```

They do not replace the canonical renderer, evidence hierarchy, or Human Gate.
