# Third-Party Notices

## Engine-Sim research reference

Stage V and later S12 research use a clean-room Python implementation of architecture described by [ange-yaghi/engine-sim](https://github.com/ange-yaghi/engine-sim), pinned at `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630`. The upstream code is MIT licensed.

No Engine-Sim C++ source, `.mr` engine script, impulse response, recording, or audio asset is committed into this repository. Stage AE explicitly treats external IR/WAV provenance separately from the upstream root code license.

## FFTConvolver architecture reference

Stage AE absorbs the partitioned-convolution architecture of [HiFi-LoFi/FFTConvolver](https://github.com/HiFi-LoFi/FFTConvolver), branch `non-uniform`, pinned commit `f2cdeb04c42141d2caec19ca4f137398b2a76b85`, MIT License.

No upstream FFTConvolver C++ implementation is copied in Stage AE. The repository stores its MIT notice under `third_party/fftconvolver/COPYING.txt`, and `stage_ae/partitioned_convolver.py` is an independent Python numerical reference for future C++ equivalence.

## Other method-only references

Vangardo/engine-sim-unity-audio is used as an engineering reference for package-wide gain, manifest/pin/NOTICE discipline and offline-bank qualification. Google Oboe is reserved as the Apache-2.0 Android low-latency audio integration target. BitResonant/EV-engine-sound-sonification is method-only because its CC BY-NC-SA 4.0 license is incompatible with a commercial-capable copied runtime.
