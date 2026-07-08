# Tesla Simulate Vico Documentation

This directory is the public documentation entry for the ESP-IDF firmware project.
Paths use stable ASCII names for GitHub, scripts, and VSCode. Chinese descriptions are kept in document titles and body text.

## Current Entry Points

- [Firmware roadmap](04-planning/01-firmware-roadmap.md)
- [Firmware backlog](09-backlog/01-firmware-backlog.md)
- [Documentation guide](GUIDE.md)

## Directory Map

| Directory | Purpose | Current rule |
|---|---|---|
| `00-reference` | External datasheets, reference projects, original notes | Raw references only; conclusions belong in planning or architecture docs |
| `01-architecture` | System architecture and module boundaries | Keep aligned with ESP-IDF component layout |
| `02-requirements` | PRD, acceptance criteria, product requirements | Requirement truth before implementation details |
| `03-protocols` | BLE, CAN, MQTT, OTA, USB contracts | UUID/topic/frame contracts must stay stable and explicit |
| `04-planning` | Roadmaps, phase plans, migration plans | Active plan entry lives here |
| `05-execution` | Execution records and migration logs | Use for step-by-step runbooks and bring-up logs |
| `06-testing` | Test plans and hardware acceptance records | Use for board evidence, logs, and screenshots |
| `07-debugging` | Bug analysis and troubleshooting | Use for failures, root cause, and recovery notes |
| `08-reports` | Milestone reports and delivery summaries | Use for release and handoff reports |
| `09-backlog` | Remaining work and technical debt | Active backlog entry lives here |
| `10-learning` | Study notes and experiments | Use for MATLAB/audio-model learning notes |
| `superpowers` | Agent planning/spec artifacts | Keep this path for the local skill workflow |

## Naming Contract

- Directories: `NN-english-kebab`, for example `04-planning`.
- Files: `NN-english-kebab.md`, for example `01-firmware-roadmap.md`.
- Document titles may be Chinese or bilingual.
- Avoid mixed abbreviation and Chinese path names; they are harder to quote, script, and link.

## Current Project Status

- Implemented baseline: ESP-IDF project, CAN listen-only parser, I2S RPM audio baseline, BLE GATT, SD JSON config, encoder, throttle potentiometer, WS2812, and S7 `status/network/iot/ota` layering.
- Pending hardware proof: flash/boot, BLE advertising and read/write, WiFi join, MQTT up/downlink, HTTPS OTA success/failure, SD/I2S/ADC/LED/encoder behavior.
- Known risk: IRAM remains close to the ESP-IDF reported limit and must stay visible until board testing accepts or resolves it.
- Deferred work: product-grade speed/acceleration/load sound model, MATLAB or equivalent tuning workflow, USB CDC, and advanced tuning UI.
