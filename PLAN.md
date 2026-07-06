# Tesla Simulate Vico — Engineering Plan

> Status: S0.1–S0.5 done, S0.6 verification gate pending

## Goal

ESP32-S3 firmware for Tesla vehicle engine sound simulation.

- OBD-II CAN listen-only (NO transmit)
- RPM-based engine audio synthesis over I2S
- BLE GATT configuration
- SD card persistence, rotary encoder, WS2812 LED, throttle potentiometer

## Execution model

Parent (orchestrator) plans + reviews; child-claude executes scoped narrow tasks;
parent verifies diff before accept. Each child task carries: path boundary, allowed
tools, acceptance criteria, structured JSON reply.

## Phases

### S0 — Repository & verification gate (current)

- [x] S0.1 child-claude: create `.gitignore` + `README.md` + `LICENSE` at prj root
- [x] S0.2 parent: write `PLAN.md` (this file)
- [x] S0.3 parent: `git init` + first commit (`bb705dd`)
- [x] S0.4 credentials: provided via Git Credential Manager (cached)
- [x] S0.5 parent: `git remote add origin https://github.com/Jovifei/Tesla_Simulate_vico.git` + `git push -u origin main`
- [ ] S0.6 parent/child: install PlatformIO, run `pio test -e native` + `pio run -e esp32s3dev`

### S1 — CAN listen-only layer

- [ ] S1.1 child-claude: Tesla CAN frame parser pure logic (0x256 vehicle speed, 0x116 torque) + native tests
- [ ] S1.2 child-claude: `TwaiCanSource` real reception (ESP32-S3 TWAI driver, listen-only, NO transmit API)

### S2 — Audio engine

- [ ] S2.1 child-claude: engine sound synthesizer (RPM-based) + `arduino-audio-tools` I2S output
- [ ] S2.2 child-claude: volume / mute / mixer integration

### S3 — BLE configuration

- [ ] S3.1 child-claude: NimBLE GATT service, `ffe1`–`ffeE` characteristics

### S4 — Peripherals & persistence

- [ ] S4.1 child-claude: SD card config store (load/save runtime config as JSON)
- [ ] S4.2 child-claude: rotary encoder, WS2812 LED, throttle potentiometer drivers

## Pin map (source of truth: `firmware/include/config/pin_map.h`)

| Function | GPIO |
|---|---|
| POT_IO1 (throttle) | 1 |
| I2S BCK / LCK / DIN | 6 / 7 / 12 |
| CAN RX / TX / RS | 13 / 14 / 38 |
| Encoder CLK / DT | 4 / 5 |
| LED_PWR | 21 |
| WS2812 DATA | 48 |
| SD CS / CLK / MOSI / MISO | 45 / 39 / 40 / 41 |

## Hard rules

- CAN listen-only: NO transmit API in any `can/` header or source
- Pin `POT_IO1 = IO1` only; never `GPIO34` or `POT_ADC`
- No MCP2515 as default CAN path (ESP32-S3 TWAI is the default)
- Every child-claude task must specify: path boundary, allowed tools, acceptance, structured reply
- No secrets / tokens in repo files or task slips
- Parent reviews diff and runs verification before marking any phase done
