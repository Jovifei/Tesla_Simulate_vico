# Stage AE source absorption

## HiFi-LoFi / FFTConvolver
Pinned `non-uniform@f2cdeb04c42141d2caec19ca4f137398b2a76b85`, MIT. Absorbed concept: deterministic uniform/partitioned FIR convolution suitable for later realtime C++ exhaust transfer. Stage AE implements an independent Python numerical reference and stores the MIT notice; no upstream C++ source is copied yet.

## Vangardo / engine-sim-unity-audio
MIT project with a pinned Engine-Sim vendor boundary. Absorbed engineering lessons: manifest-driven generation, one gain policy across an entire RPM/load bank, preserve loudness relationships, pin upstream revisions, preserve NOTICE/PATCHES. We explicitly reject per-scene peak normalization.

## Google Oboe
Apache-2.0. Reserved for the Android phase: low-latency callback, frames-per-burst awareness, device-specific stream negotiation. Not copied into Stage AE Python.

## Engine-Sim
Root code license MIT, but Stage AE does **not** assume every WAV/IR asset has separately verified product redistribution provenance. External IR use is fail-closed through `IrAssetSpec`; unknown/public assets remain research diagnostic only.

## BitResonant EV-engine-sound-sonification
CC BY-NC-SA 4.0. Method-only reference for telemetry interpolation/dropout handling; no code copied into a commercial-capable runtime.

## DiffMoog / DDSP family
Retained as future parameter warm-start/inversion research. They do not replace the canonical S12 renderer or Human Gate.
