# Tesla Simulate Vico Engineering Plan

> Status snapshot: 2026-09-04. The project now has two mature but not yet joined tracks: an ESP32-S3 product shell and an S12 acoustic-authoring/validation system. PR #5 has merged; the immediate gate is Stage-AC post-merge truth/smoke closure followed by Jovi's Hellcat V3 blind audition.

## Goal

Build a productizable vehicle engine-sound system that:

- listens to Tesla CAN/OBD in listen-only mode;
- maps live vehicle state into a continuous virtual engine state;
- generates vehicle-specific real-time sound with persistent event/source dynamics;
- preserves a strict separation between physics authority, acoustic authoring, monitor playback, and product adapters;
- exposes configuration/diagnostics through the existing ESP32 BLE/SD/WiFi/IoT/OTA shell;
- reaches a safe external-speaker vehicle pilot without ever transmitting on the vehicle CAN bus.

## Current architecture

See:

- `docs/01-architecture/01-project-system-architecture.md`
- `docs/04-planning/02-project-master-roadmap.md`
- `docs/08-reports/10-project-status-20260904.md`

High level:

```text
Vehicle CAN/OBD
→ VehicleState
→ S12 authoritative sound model
→ Human / Reference qualification
→ AudioParameterPackage
→ Portable C++ realtime core
→ Android/desktop realtime proof
→ ESP32-S3 reduced adapter
→ I2S/DAC/AMP/Speaker
```

The existing ESP32 firmware shell is not discarded; it is the product-control/safety/runtime container into which the approved portable sound core will later be integrated.

## Delivered work

### S0–S7 firmware shell

Implemented in code:

- TWAI CAN listen-only source + current frame parser baseline;
- I2S PCM baseline, volume and overspeed mute;
- NimBLE GATT (`0xfff0` primary, `0xffe0` compatibility);
- SD JSON RuntimeConfig;
- encoder / throttle potentiometer / WS2812;
- `status` / `network` / `iot` / `ota` separation;
- 25 ms `App::tick()` coordination;
- ESP-IDF/OpenSpec build gates.

Board verification remains incomplete.

### S12 acoustic system

Software architecture and evidence have advanced through:

```text
V → W → X → Y → Z → AA → AB / AB-R → AC
```

Delivered capabilities include:

- persistent crank/event state and snapshot/restore;
- per-cylinder/path/bank/collector processing;
- forced induction, mechanical, cycle-sync and transient layers;
- state-gated afterfire;
- pressure/dP audio chain;
- frozen Track-P PTR/Radiation boundary;
- comparator/reference governance;
- open-source method traceability and license boundaries;
- candidate ablation/reachability;
- Hellcat AA-C3 v3 blind-audition package;
- provenance/causality hardening;
- hermetic full remote CI and Track-P frozen guard.

## Current remote truth snapshot

Verified on 2026-09-04:

```text
main = 82c7cb77d26f446251e63d1a6899b08bf08be65b
PR #5 = MERGED at 2026-09-04T13:51:52Z
PR #5 head = 021fe29480aadabd4d9ba4c20bbc111d1c386795
CI run 33703659821 = SUCCESS on exact head
full S12 = 1423 passed, 10 skipped, 232 subtests passed
Track-P = PASS
R1 = MISSING
Human audition = WAITING_FOR_JOVI
Profile Freeze = NOT_AUTHORIZED
```

This is a snapshot, not a hard-coded future truth. Every executing agent must re-fetch the remote state first.

## Immediate execution phase

### S12-AC Post-Merge Closeout

PR #5 is already merged. Current `main=82c7cb77...`; `021fe294...` is its direct ancestor and was exactly qualified by successful run `33703659821`. A metadata-only Stage-AC state commit followed the merge, and no new full workflow run is recorded on current main.

1. Verify current main ancestry and confirm the post-merge-only delta is governance/state metadata rather than renderer/PCM/Track-P math.
2. Run the repository-defined focused post-merge smoke / Track-P frozen guard needed for AC8; do not rerun multi-hour suites without an input change unless the gate explicitly requires it.
3. Update Stage-AC machine truth: AC6 PASS (exact-head CI), AC7 PASS (actual merge), AC8 PASS only after the post-merge smoke/receipt.
4. Keep R1/Profile Freeze/OEM flags unchanged.
5. Reach `WAITING_FOR_JOVI_AUDITION` without any acoustic tuning.

### Human V3 Gate

Package:

`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`

Manifest SHA-256:

`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`

Before feedback:

- no sound tuning;
- no blind-answer reveal;
- no Ferrari/RX-7 propagation;
- no Profile Freeze claim.

After feedback:

- save raw feedback;
- hash it;
- reveal blind identity;
- bind scene/stem/metric/hypothesis;
- either accept AA-C3 or run ONE source-causal Round 2 with at most 3 distinct candidates.

## Productization after Human PASS

1. Freeze Hellcat Engineering Profile (not R1/OEM freeze).
2. Migrate Ferrari 458 and RX-7 using the same method, not the same parameters.
3. Define `AudioParameterPackage`.
4. Produce Golden VehicleState traces and Golden PCM/metrics.
5. Implement portable C++17 realtime core.
6. Prove Python ↔ C++ streaming/snapshot equivalence.
7. Run Android/desktop realtime CPU/memory/latency/underrun proof.
8. Reduce/port the approved runtime to ESP32-S3.
9. Integrate with current CAN/BLE/SD/WiFi/OTA firmware shell.
10. Complete board and CAN listen-only hardware acceptance.
11. Run controlled Tesla vehicle pilot.
12. Perform R1 formal calibration only when legal synchronized data exists.

## Hard boundaries

- CAN product path: listen-only forever.
- Track-P/FVM/PTR/Radiation: frozen unless explicit boundary review.
- Whole-mix/master gain is not a valid source-causal Round-2 fix.
- CI success is software evidence, not human realism acceptance.
- Human acceptance is not OEM/R1 calibration.
- Public media availability does not imply audio rights.
- Do not copy third-party source/media whose license/rights are not explicitly compatible.
- Do not put full CFD/teacher systems directly into mobile/ESP32 runtime.

## Documentation truth

- Overall architecture: `docs/01-architecture/01-project-system-architecture.md`
- Master roadmap: `docs/04-planning/02-project-master-roadmap.md`
- Current audit: `docs/08-reports/10-project-status-20260904.md`
- Master backlog: `docs/09-backlog/02-project-master-backlog.md`
- ESP32 firmware sub-roadmap: `docs/04-planning/01-firmware-roadmap.md`
- ESP32 hardware backlog: `docs/09-backlog/01-firmware-backlog.md`
