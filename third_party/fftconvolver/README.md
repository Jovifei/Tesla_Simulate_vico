# FFTConvolver upstream reference

Stage AE absorbs the **partitioned-convolution architecture** from HiFi-LoFi/FFTConvolver for the future portable C++/Android exhaust-transfer adapter.

- Upstream: https://github.com/HiFi-LoFi/FFTConvolver
- Pinned branch: `non-uniform`
- Pinned commit: `f2cdeb04c42141d2caec19ca4f137398b2a76b85`
- License: MIT

No upstream C++ source is vendored in this commit. `stage_ae/partitioned_convolver.py` is an independent Python numerical reference. If the C++ implementation is vendored later, preserve the upstream MIT notice and qualify it against Golden PCM before Android integration.
