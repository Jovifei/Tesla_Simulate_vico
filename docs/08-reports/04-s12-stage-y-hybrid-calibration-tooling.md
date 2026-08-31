# S12 Stage Y — Hybrid Calibration Tooling

Date: 2026-08-30
Branch: `agent/s12-stage-y-closed-loop-remediation`

## Why this was added

The Engine-Sim-inspired event-domain implementation solves event timing, phase continuity and exhaust-path structure, but a lightweight synthetic source cannot reproduce every real intake, mechanical and exhaust texture. Stage Y therefore adds an **optional, rights-gated hybrid layer**:

```text
persistent event-domain engine
+ derived harmonic timbre map
+ authorized cycle-synchronous residual
+ identified causal transfer response
→ frozen PTR / renderer
```

The hybrid tools are disabled by default. No third-party audio is committed.

## Implemented modules

### `harmonic_timbre_extractor.py`

Consumes authorized audio and synchronized RPM/load/boost traces. It tracks declared orders at each FFT-frame centre and builds a derived:

```text
RPM × load × boost × order amplitude map
```

The map stores only numerical features and observation counts. It does not store raw audio.

### `cycle_residual_bank.py`

Segments a recording by unwrapped crank/rotor phase, resamples complete cycles to a fixed phase grid, removes configurable low-order harmonic content and keeps the residual texture. Extraction fails unless `rights_status` is explicitly cleared.

This is the clean-room infrastructure required for cycle-synchronous/OLA-style realism without copying an external project or embedding unlicensed audio.

### `hybrid_source.py`

Mixes an event-domain stereo source with an authorized cycle-residual bank. Event timing remains authoritative. The residual layer is phase locked, state/RPM/load selected, gain bounded, snapshot-safe and disabled unless explicitly configured.

### `transfer_response_id.py`

Fits a causal, finite and stable FIR response from a supplied input/output pair. This is the correct future path for ENSIM4/CFD pressure-response sweeps; it is more informative than the historical two-scalar teacher reduction. Identified filters remain non-runtime candidates until independently reviewed.

### `finalist_validation.py`

Requires SHA-bound MATLAB and MoSQITo receipts, plus an RPM-qualified order receipt when formal order comparison is requested. It ranks finalists for human review but can never create Profile Freeze by itself.

### `calibration_bundle.py`

Defines a local fail-closed bundle:

```text
bundle/
  audio.wav
  state.csv
  rights.json
  recording.json
```

It verifies rights, source SHA, recording metadata and full state coverage, then emits:

- `harmonic_timbre_map.json`;
- `cycle_residual_bank.npz`;
- `cycle_residual_manifest.json`;
- `calibration_bundle_receipt.json`.

Raw audio is not copied to the output directory.

## Driver

```powershell
python -m tools.sound_sim.s12.acoustic_identity_v015.stage_y.drivers.drive_y2_calibration_bundle `
  --bundle E:/Tesla_speed/private_references/hellcat/full_pull_01 `
  --output E:/Tesla_speed/tasks/reports/runtime/s12-stage-y/hellcat_full_pull_01
```

## Method sources

- Engine-Sim: https://github.com/ange-yaghi/engine-sim
- MoSQITo: https://github.com/Eomys/MoSQITo
- webMUSHRA: https://github.com/audiolabs/webMUSHRA
- ViSQOL: https://github.com/google/visqol
- MATLAB order map: https://www.mathworks.com/help/signal/ref/rpmordermap.html

## Boundary

Software infrastructure is complete enough to ingest real authorized material. The derived map, residual bank and transfer response cannot be truthfully populated for the target vehicles until the corresponding authorized synchronized inputs exist.

Current status:

```text
HYBRID_TOOLING_IMPLEMENTED
REAL_DERIVED_ASSETS_NOT_GENERATED
R1_REFERENCE_PENDING
HUMAN_REVIEW_PENDING
NOT_PROFILE_FREEZE_READY
```
