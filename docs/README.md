# Tesla Simulate Vico Documentation

This directory is the public documentation entry for the ESP32-S3 vehicle-sound product and the S12 acoustic-authoring/validation work.

Paths use stable ASCII names for GitHub/scripts/VSCode. Chinese descriptions are kept in document titles and body text.

## Read These First

1. [Unified system architecture](01-architecture/01-project-system-architecture.md)
2. [Project master roadmap](04-planning/02-project-master-roadmap.md)
3. [Current project status audit — 2026-09-04](08-reports/10-project-status-20260904.md)
4. [Project master backlog](09-backlog/02-project-master-backlog.md)
5. [Firmware sub-roadmap](04-planning/01-firmware-roadmap.md)
6. [Firmware/hardware backlog](09-backlog/01-firmware-backlog.md)
7. [Documentation guide](GUIDE.md)

## Current Project Truth

The repository contains **two major tracks that are both real but not yet fully joined**:

### ESP32-S3 product shell

Implemented in code:

- CAN/TWAI listen-only receive and parser baseline;
- I2S audio baseline;
- BLE GATT;
- SD JSON persistence;
- encoder / throttle potentiometer / WS2812;
- Network / MQTT / HTTPS OTA / RuntimeStatus layering;
- 25 ms application coordination loop.

Most board-level behavior is still `Blocked` on hardware evidence.

### S12 acoustic-authoring and validation system

The sound work is **not “waiting to start”**. It has progressed through Stage V/W/X/Y/Z/AA/AB/AC and now has:

- persistent event-domain source architecture;
- source/path/transient state;
- comparator/reference governance;
- Track-P frozen-boundary protection;
- Hellcat AA-C3 engineering candidate;
- validated v3 blind-audition package;
- exact-head full-S12 CI closure on PR #5 and subsequent merge;
- explicit human/R1 qualification boundaries.

Current nearest gate:

```text
Stage-AC post-merge truth
→ AC8 pre-human receipt
→ WAITING_FOR_JOVI_AUDITION
→ feedback binding
→ AA-C3 accept OR one source-causal Round 2
```

Current qualification boundary remains:

```text
R1 = MISSING
HUMAN_PASS = false
OEM_CALIBRATION = NOT_AUTHORIZED
PROFILE_FREEZE = NOT_AUTHORIZED
```

## Productization Direction

After a human-accepted Engineering Profile:

```text
S12 Python authority
→ AudioParameterPackage
→ Golden VehicleState / PCM
→ portable C++ realtime core
→ Android/desktop realtime equivalence proof
→ ESP32-S3 resource-reduced adapter
→ existing firmware shell
→ board/CAN/vehicle pilot
```

Android is an intermediate real-time/equivalence host, not a replacement for the existing ESP32-S3 embedded product target.

## S12 Key Reports

- [Stage Z open-source absorption](08-reports/08-s12-stage-z-open-source-absorption.md)
- [Stage AA Hellcat acoustic quality closure](08-reports/09-s12-stage-aa-acoustic-quality-closure.md)
- [2026-09-04 integrated status audit](08-reports/10-project-status-20260904.md)
- [S12 engine-audio knowledge mirror](knowledge/obsidian/S12/Engine-Audio-Ecosystem/00-MOC.md)

## Directory Map

| Directory | Purpose | Current rule |
|---|---|---|
| `00-reference` | External datasheets, reference projects, original notes | Raw references only; conclusions belong in planning or architecture docs |
| `01-architecture` | System architecture and module boundaries | Holds product + S12 + runtime integration architecture |
| `02-requirements` | PRD, acceptance criteria, product requirements | Requirement truth before implementation details |
| `03-protocols` | BLE, CAN, MQTT, OTA, USB contracts | UUID/topic/frame contracts stay explicit |
| `04-planning` | Roadmaps and phase plans | `02-project-master-roadmap.md` is the overall plan; firmware roadmap remains a sub-plan |
| `05-execution` | Execution records and migration logs | Step-by-step runbooks and bring-up records |
| `06-testing` | Test plans and hardware acceptance | Board evidence, logs, screenshots |
| `07-debugging` | Bug analysis and troubleshooting | Failures, root cause, recovery |
| `08-reports` | Milestone reports and delivery summaries | Current state audits and stage reports |
| `09-backlog` | Remaining work and technical debt | Overall and firmware-specific backlog |
| `10-learning` | Study notes and experiments | MATLAB/audio-model learning notes |
| `knowledge` | Curated S12/Obsidian mirror | Do not confuse knowledge notes with qualification truth |
| `superpowers` | Agent planning/spec artifacts | Local skill workflow artifacts |

## Documentation Status Rules

Use these words precisely:

- `Implemented`: code exists and builds.
- `Verified`: fresh software/build/CI evidence exists.
- `Verified-on-board`: fresh hardware evidence exists.
- `Human accepted`: Jovi listening gate passed.
- `R1 qualified`: legal synchronized real-reference gate passed.
- `Blocked`: external hardware/data/human/tool decision is required.
- `Deferred`: intentionally moved later.

Never promote one evidence class into another.
