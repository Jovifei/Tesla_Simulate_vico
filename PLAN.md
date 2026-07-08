# Tesla Simulate Vico Engineering Plan

> Status: S0~S6 delivered; S7 OTA baseline implemented in code and verification-gated, but still blocked by IRAM headroom and hardware runtime acceptance

## Goal

ESP32-S3 firmware for Tesla vehicle engine sound simulation:

- OBD-II CAN listen-only receive (no transmit)
- RPM-based engine synthesis over I2S
- BLE GATT service + compatibility profile
- SD JSON persistence, rotary encoder, WS2812 status LED, throttle potentiometer

## Environment

- ESP-IDF v5.3.2: `E:\project\ESP_IDF_support\v5.3.2\esp-idf`
- Tools: `E:\project\ESP_IDF_support\tools`
- Python env: `E:\project\ESP_IDF_support\tools\python_env\idf5.3_py3.14_env`
- Target: esp32s3 / 16MB Flash / 8MB PSRAM
- Repo: https://github.com/Jovifei/Tesla_Simulate_vico

## Execution Phases

### S0 Repository + verification
- [x] Workspace baseline established, docs and remote push done
- [x] ESP-IDF compile path verified

### S1 CAN listen-only layer
- [x] S1.1 `components/can/CanFrames.*` (parse Tesla 0x256/0x116)
- [x] S1.2 `components/can/TwaiCanSource.*` (listen-only receive integration, no transmit API)

### S2 Audio engine
- [x] S2.1 I2S synthesis path
- [x] S2.2 runtime volume and overspeed mute integration
- [x] S2.3 engine model + task-level render loop

### S3 BLE configuration
- [x] S3.1 `components/ble/BleService.*` with ESP-IDF NimBLE
- [x] PRD service `0xfff0` and compatibility service `0xffe0`
- [x] Characteristics `ffe1..ffeE` exposed and behavior wired
- [x] Advertising + reconnect lifecycle completed

### S4 Peripherals & persistence
- [x] S4.1 SD card config load/save (runtime config JSON)
- [x] S4.2 encoder, throttle potentiometer, WS2812 status LED

### S5 Firmware integration & loop
- [x] Main tick loop set to 25ms
- [x] BLE snapshot publish from tick path (`publishVehicleState`)
- [x] LED heartbeat isolated at 1s interval
- [x] Build/size/spec verification gates added

### S6 Verification closure
- [x] Build verification snapshot captured
- [x] OpenSpec root aligned to `prj/openspec`
- [x] IRAM risk documented and carried forward explicitly
- [x] Hardware acceptance remains tracked as blocked, not implied complete

### S7 WiFi OTA baseline
- [x] OTA partition layout added: `nvs`, `otadata`, `phy_init`, `ota_0`, `ota_1`
- [x] `components/ota/` added for WiFi STA + HTTPS OTA + status
- [x] `RuntimeConfig` expanded with `wifi_ssid`, `wifi_password`, `ota_url`, `ota_auto_check`
- [x] BLE UUID contract preserved: `ffe8` OTA settings JSON, `ffe5` diagnostics JSON, `ffea` live status
- [x] OTA-related BLE writes persist config for next boot without triggering OTA immediately
- [ ] Release hardening gate: reduce IRAM from `16383 / 16384` (`99.99%`)
- [ ] Hardware acceptance gate: complete BLE checklist on device
- [ ] Hardware acceptance gate: prove WiFi join and OTA runtime on hardware

## Current Verification Gates

- [x] `.\scripts\esp-idf.ps1 build` (pass)
- [x] `.\scripts\esp-idf.ps1 size` (pass)
- [x] `.\scripts\esp-idf.ps1 size-components` (pass)
- [x] `openspec validate --all --strict --json` from `E:\Tesla_speed\prj` (pass `5/5` on `2026-07-08`)

## Documentation Gate

- [x] `prj/PLAN.md` updated to reflect real status
- [x] `prj/README.md` updated (status + BLE service summary)
- [x] `docs/PRD/codex/PRD__prd-v20260522-codex-v4.2-current.md` rebuilt as readable PRD implementation matrix
- [x] `prj/openspec/specs/ble-config/spec.md` schema-correct and passing validation

## S6 Closure Outcome

- Delivery docs are aligned to the active OpenSpec root at `prj/openspec`
- Current verification snapshot for build, size, and spec validation is captured
- BLE runtime acceptance has a manual checklist with explicit hardware-blocked status
- IRAM risk is now bounded and documented: `16383 / 16384` (`99.99%`), with framework libraries as the primary consumers

## S7 OTA Baseline Outcome

- OTA baseline compiles and is represented in the current docs
- S7 is not complete: release hardening remains blocked by IRAM headroom
- S7 is not complete: WiFi join and OTA runtime still require on-device proof

## Next Actions (planned)

- Keep S7 in progress until the IRAM hardening gate is cleared
- Complete the BLE device checklist and prove WiFi join / OTA runtime on hardware
- Start S8 USB CDC / advanced tuning only after S7 hardware acceptance is closed
- Keep PRD progress matrix as the leading source of feature truth after each merge

## Pin map (single source)

| Function | GPIO |
|---|---|
| POT_IO1 (throttle) | 1 |
| I2S BCK / LCK / DIN | 6 / 7 / 12 |
| CAN RX / TX / RS | 13 / 14 / 38 |
| Encoder CLK / DT | 4 / 5 |
| LED_PWR | 21 |
| WS2812 DATA | 48 |
| SD CS / CLK / MOSI / MISO | 45 / 39 / 40 / 41 |
