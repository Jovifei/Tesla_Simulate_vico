# Stage AG — Vehicle Identity Separation / Open-Source Method Study

Date: 2026-09-08
Status: `METHOD_ADOPTION / DIAGNOSTIC_ONLY`

## Problem being solved

The existing S12 `EngineAcoustics` renderer has a strong common mechanical/oil-car character, but multiple vehicle configurations can still sound too related because substantial late-stage body treatment is shared. Stage AG therefore targets **vehicle identity**, not generic realism.

The design rule is:

```text
same mechanical realism core
+ different firing/order/topology identity
+ different induction/noise identity
!= one common sound with different EQ
```

Hellcat remains the protected listening anchor. Stage AG does not replace it.

## Sources studied

### 1. AngeTheGreat / engine-sim

Repository: `https://github.com/ange-yaghi/engine-sim`

Existing project pin: `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630`
License: MIT for repository code; audio/assets remain separately governed.

Useful method:
- cylinder/firing topology is part of sound identity;
- per-cylinder firing phase and path propagation matter;
- engine geometry and exhaust path should create different signatures rather than using one late EQ preset.

Stage AG adoption:
- retain the existing event-domain / firing-order S12 core;
- make identity explicitly keyed to engine orders implied by the vehicle topology.

No engine-sim source, `.mr`, presets, IR or recordings are copied by Stage AG.

### 2. SenaTaka / engine-simulator

Repository: `https://github.com/SenaTaka/engine-simulator`
Studied pin already recorded by S12: `c03a43e7da473a693f2b2079ce0eaca00b3042f8`

Public project behavior separates:
- harmonic synthesis;
- mechanical/intake/combustion noise;
- resonance;
- engine-specific modes such as Turbo / VTEC / Boxer.

Useful method:
- do not expect cylinder count alone to create identity;
- engine-specific tonal/noise/resonance structure needs an explicit profile layer.

Stage AG only adopts this architecture idea. It does not copy JavaScript source or presets.

### 3. Robin Doerfler et al. — EONE / parametric engine sound representation

Paper: `Gradient-Based Learning of Parametric Engine Sound Representations for Real-Time Resynthesis and Tuning on Embedded Systems`
arXiv: `2606.21521`

Useful method:
- automotive identity can be represented by compact per-engine-order plus broadband timbral parameters across operating state;
- authoring can be richer while runtime remains interpretable and lightweight.

Stage AG adoption:
- explicit per-vehicle engine-order weights;
- bounded broadband identity source;
- no neural model or weight dependency in runtime.

Paper/data/model rights remain separate; no weights or proprietary EVx assets are used.

### 4. rdoerfler / ptr-model

Repository: `https://github.com/rdoerfler/ptr-model`
Existing S12 pin: `af026403458309b3a27dcdc0320ddb485033d4aa`
License: CC BY-NC 4.0.

Useful method:
- engine sound should stay anchored to firing-aligned pulse structure rather than become a free harmonic synthesizer;
- resonant/broadband additions should remain tied to the combustion lifecycle.

Stage AG adoption:
- order layer phase is derived from RPM/crank phase;
- broadband source is amplitude-modulated by the primary engine order so it is not generic hiss.

Because the upstream license is non-commercial, Stage AG copies no upstream code, model weights, dataset or audio.

### 5. ATG-Simulator / VehicleNoiseSynthesizer

Repository: `https://github.com/ATG-Simulator/VehicleNoiseSynthesizer`
Existing S12 pin: `4241caca5a18be0d47f0b8586df93b1b42d7020d`
Code license: MIT; recordings/integrations are separate rights.

Useful method:
- vehicle sound identity is state/layer dependent;
- intake/exhaust/transmission sources should not be collapsed into one undifferentiated loop.

Stage AG does not change S12 into a sample bank. Only the layered-identity engineering lesson is retained.

## Local Stage AG implementation

`tools/sound_sim/s12/acoustic_identity_v015/stage_ag/vehicle_identity.py`

Modes:

```text
legacy
vehicle_identity_v1
```

`legacy` returns the existing `EngineAcoustics` bytes unchanged.

`vehicle_identity_v1` currently applies:

- Hellcat: zero delta; protected current authority;
- Ferrari 458: E4-centered flat-plane family with strong E8/E12 edge and deliberately weak E2 rumble;
- Lexus LFA: E5-centered V10 family with dense E10/E15/E20 upper structure and very weak E2.5 sub-order;
- GT-R R35: E3-centered V6 family with E6/E9 and modest E1.5 body plus more load-tied broadband energy.

The layer is a bounded convex source blend. There is no additional master/global gain, post-EQ matching or product normalization.

## Why this is only Stage AG v1

These parameters are **engineering hypotheses**, not OEM truth. They are derived from engine topology and source-method research, not measured synchronized R1 data.

Required next proof:

```text
legacy vs identity_v1 probe
→ per-vehicle Reference A/B where allowed
→ cross-vehicle identity listening matrix
→ Jovi Human Gate
→ only then decide whether identity_v1 enters the next fit/profile schema
```

Do not automatically use the new identity layer for final Android profiles and do not claim OEM matching.
