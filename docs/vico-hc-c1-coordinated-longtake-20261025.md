# HC-C1: Coordinated long-take continuous voice — predeclared engineering contract

Parent: `66132e8e594e244348a51b369a3b779d272666ef` (PR40). Separate Draft PR dependent on `codex-hellcat-realism-20261024`; never main. No real sound or original bank replacement is approved by this contract.

## Evidence and limits

The Hellcat t8/t9 GDC2019 private recordings (96 kHz PCM24, ~233.265 s) remain solely in the controlled local evidence location. There is **no synchronized RPM/load/gear/720° phase**, no independent held-out run and no confirmed public product distribution of the source/derivative audio. This stage NEVER imports, uploads, packages or derives PCM from them. Prior top32-noise and integer64 coherent-residual prototypes remain REJECTED (975 RPM slow envelope 4.56x/34.60x and RMS out of ±0.5 dB); no seed/phase/gain search and no resurrection of the rejected bank.

The next practical increment is an opt-in **single-take, phase-coordinate long-window decoder** usable by the actual Web AudioWorklet and Android normal renderer. It uses fixed explicit per-region reference RPM/load/cycle alignment, one shared 720° clock, bounded crossfade on region selection, continuous source cursors, fail-closed metadata/samples and original event path. It does not infer RPM from raw audio or declare a reference aligned. The default remains the existing short-bank normal route, startup and fixed vehicle gain; adding this code does not install a new sound asset.

### Locked engineering trial and budgets (before any trial)

- Trial count: ONE fixed deterministic *synthetic-only* fixture (two 2-s regions from one generated take), plus four controlled scenarios (low/high steady, ascending/descending RPM); no adaptive fitting or random search, candidate_count=1 for this new HC-C1 package only. Legacy frozen source budgets remain 0. Test vectors are created from equations inside source tests and are explicitly NOT Hellcat recordings.
- Region constraints: exact Hellcat vehicle key; 48kHz; 2..8 regions; non-overlapping 1..12s spans from ONE mono bounded take (total ≤60s); fixed finite RPM/load/cycles; explicitly labelled `SYNTHETIC_TEST_ONLY` OR `PRODUCT_REVIEWED` with independent source and approved distribution/phase/RPM/load/held-out metadata. Tests use SYNTHETIC_TEST_ONLY; no product asset can be shipped by this stage.
- Renderer controls: sample-clocked 720° phase shared by all regions; one cursor phase coordinate, 120ms source-region crossfade only at controlled region selection; no parameter/clock randomization; no automatic gain normalization. No real-time file/decoder/network/FFT.
- Safety: bounded PCM sample absolute magnitude, no non-finite values, bounded output/event peak and explicit counters; region changes min 250ms dwell; mute, owner stop, input mode changes and invalid input never start/resume private audio. No unapproved source fallback claimed as validated voice.
- Verification: no-source defaults bit-identical, 1/17/128/960/997-frame partition invariance, onset and region transitions (click jump, phase, owner), fixed shift/afterfire once, requested readhead wraps, redline controls, tampering / missing metadata, same controlled input trace, Web/Android synthetic output checks, CI fresh code compile/test. New synthetic voice audio quality is **NOT_EVALUATED** and MUST NOT be treated as old-bank ±0.5dB compatible: the old-bank same-material compatibility gate still applies to unchanged legacy route; an approved new real voice requires predeclared independent measured-source/acoustic gates.
- Held-out: segment windows for rendering must be disjoint from held-out material; provenance and capture state locked before promotion. Training/validation/held-out source groups never determined by overlapping 50% proxy windows; the existing 16 weak-stationary windows are 5 union regions of ONE take, not 16 independent examples.
- Release: no Web/Android end-user UI switch, no on-disk product recorded PCM, no default algorithm/asset route change. The optional API accepts only a fully explicit caller-verified candidate before the session and is exercised end-to-end by synthetic app/test callers. Physical device, actual GDC alignment, true source distribution, acoustic and Jovi hearing gates remain NOT_RUN/NOT_EVALUATED.

## License and architectural research

- [Sonniss GDC bundle license v2.0](https://sonniss.com/gdc-bundle-license/), effective 2026-08-27: permits project sync use subject to restrictions and explicitly prohibits repackaging sound effects as sound effects and AI technology development/training/enhancement. **No GDC PCM is present in this repository or sent to this assistant.** Written, context-specific distribution approval remains a separate human gate.
- [engine-sim](https://github.com/ange-yaghi/engine-sim) has MIT source but its author warns that it is not a scientific engineering model; only conceptual oscillator timing informed this wholly original implementation, no source copied.
- [MDN AudioWorkletProcessor.process](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletProcessor/process): output block size must be read from the actual array, not hard-coded to 128. Existing Worklet behavior is preserved.

## Scope and source ownership

New `CoordinatedLongTakeVoice` implementations in Web and Kotlin; actual `LiveEngine/BankRenderer/AudioSession/AudioWorklet` and Android `MatlabStatefulBankRenderer/MatlabV6SoundBankEngine` accept opt-in candidate with explicit provenance. No PCM embedded in source. Tests must prove direct connected consumption; a standalone helper alone is not stage completion. Asset SHA verification belongs upstream of the real-time thread; in-memory candidate validator also hashes F32LE at preparation and rejects mismatches. Only recorded-trace loader with authorized local fixture may call the opt-in API; absent that, no new playback.

Existing public startup attribution, Hellcat fixed gain, original WAVs, C63 overlay, S13/S14, Owner/V4, main and real user data are immutable. Keep old A/B failures unchanged. Deliver exact feature-branch SHA, Draft PR, tests and native acceptance instructions after implementation.

## Exit status bookkeeping

- Implementation and deterministic CI will be recorded with exact commit and commands, failures included.
- Actual copyrighted recorded-voice viability requires approved legal distribution + full synced RPM/load/phase, real PCM features, held-out pass, listening and device tests. **None** of these can be inferred from synthetic checks.
