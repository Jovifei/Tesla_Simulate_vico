# Tesla Simulate Vico Engineering Plan

> Status: S0-S6 delivered. S7 BLE / Network / IoT / OTA architecture migration is in progress: code layers exist, final build/size/OpenSpec gates and hardware acceptance are still open.

## Goal

ESP32-S3 firmware for Tesla vehicle engine sound simulation:

- OBD-II / CAN listen-only receive, with no firmware transmit API.
- RPM-based I2S audio baseline that can later evolve into speed/acceleration/load-aware sound modeling.
- BLE GATT service for runtime configuration, telemetry, diagnostics, and OTA/IoT settings.
- SD JSON persistence for runtime configuration.
- Local peripherals: rotary encoder, throttle potentiometer, WS2812 status LED.
- S7 network architecture: WiFi link state, MQTT cloud interaction, request-driven HTTPS OTA, and unified runtime diagnostics.

## Environment

- ESP-IDF v5.3.2: `E:\project\ESP_IDF_support\v5.3.2\esp-idf`
- Tools: `E:\project\ESP_IDF_support\tools`
- Python env: `E:\project\ESP_IDF_support\tools\python_env\idf5.3_py3.14_env`
- Target: esp32s3 / 16MB Flash / 8MB PSRAM
- Repo: `https://github.com/Jovifei/Tesla_Simulate_vico`

## Execution Phases

### S0 Repository + Verification

- [x] Workspace baseline established
- [x] ESP-IDF compile path verified
- [x] Remote GitHub push path verified

### S1 CAN Listen-Only Layer

- [x] `components/can/CanFrames.*` parses current Tesla `0x256` / `0x116` baseline frames
- [x] `components/can/TwaiCanSource.*` integrates TWAI listen-only receive
- [x] No CAN transmit API exposed by the application layer

### S2 Audio Engine

- [x] I2S PCM output path
- [x] Runtime volume scaling
- [x] Overspeed mute
- [x] Engine model and render loop baseline
- [ ] Product sound model with speed/acceleration/load layers and MATLAB or equivalent tuning evidence

### S3 BLE Configuration

- [x] ESP-IDF NimBLE GATT server
- [x] Primary service `0xfff0`
- [x] Compatibility service `0xffe0`
- [x] Characteristics `ffe1..ffee` exposed under the primary service
- [x] `ffe8` retained as the configuration entry point
- [ ] Hardware proof for advertising, reconnect, read/write, and notify flows

### S4 Peripherals & Persistence

- [x] SD card JSON config load/save
- [x] Encoder, throttle potentiometer, WS2812 status LED code path
- [ ] Hardware proof for SD/encoder/pot/LED/I2S behavior

### S5 Firmware Integration & Loop

- [x] Main tick loop set to 25 ms
- [x] BLE vehicle snapshot publish from tick path
- [x] LED heartbeat/state update separated from blocking work
- [x] Build/size/spec gates introduced

### S6 Verification Closure

- [x] Build and OpenSpec snapshots captured
- [x] IRAM risk documented and carried forward explicitly
- [x] Hardware acceptance tracked as blocked instead of implied complete

### S7 BLE / IoT / OTA Architecture Migration

Locked decisions:

- BLE UUID contract remains unchanged.
- `ffe8` carries WiFi / OTA / IoT JSON configuration.
- WiFi, MQTT, and OTA do not run as blocking operations inside the 25 ms App tick.
- OTA is request-driven and runs in a background OTA worker task.
- USB CDC and advanced tuning remain deferred to S8/S9.

Implementation scope:

- [x] `components/status`: `status::RuntimeStatus` model and diagnostics JSON helper
- [x] `RuntimeConfig`: WiFi, OTA, IoT, MQTT, device ID, and product ID fields
- [x] `SdConfigStore`: load/save new fields while accepting older config files with missing keys
- [x] BLE `ffe8`: read/write WiFi / OTA / IoT JSON while preserving the UUID contract
- [x] `components/network`: WiFi STA manager with EventGroup state bits and reconnect API
- [x] `components/iot`: MQTT manager with uplink publishing and `ota_start` downlink parsing
- [x] `components/ota`: request-driven HTTPS OTA worker with status/progress reporting
- [x] `components/app`: App composes status/network/iot/ota and publishes unified BLE diagnostics
- [ ] Verification gate: build / size / size-components / OpenSpec re-run after final fixes
- [ ] Hardware gate: BLE, WiFi, MQTT, and OTA on-device acceptance
- [ ] IRAM gate: reduce or explicitly accept the current IRAM headroom risk

### S8 Sound Modeling

- [ ] Define target sound scenes: idle, gentle acceleration, hard acceleration, cruise, deceleration, overspeed mute
- [ ] Add acceleration/dynamics model design
- [ ] Tune in MATLAB or equivalent simulation/probing workflow
- [ ] Port bounded parameters to firmware
- [ ] Verify bench listening and CPU/heap safety

### S9 USB CDC / Advanced Tuning

- [ ] Freeze command schema
- [ ] Implement read-only status first
- [ ] Add writable tuning parameters after S7 hardware acceptance

### S10 Product Delivery

- [ ] Release bin / bootloader / partition table package
- [ ] Flash command and version/commit record
- [ ] Hardware acceptance report
- [ ] Known-risk list

## Current Verification Gates To Run Before Commit

```powershell
cd E:\Tesla_speed\prj
.\scripts\esp-idf.ps1 build
.\scripts\esp-idf.ps1 size
.\scripts\esp-idf.ps1 size-components
openspec validate --all --strict --json
git diff --check
```

## Pin Map

| Function | GPIO |
|---|---|
| POT_IO1 throttle | 1 |
| I2S BCK / LCK / DIN | 6 / 7 / 12 |
| CAN RX / TX / RS | 13 / 14 / 38 |
| Encoder CLK / DT | 4 / 5 |
| LED_PWR | 21 |
| WS2812 DATA | 48 |
| SD CS / CLK / MOSI / MISO | 45 / 39 / 40 / 41 |

## Next Actions

1. Finish S7 source/doc/OpenSpec synchronization.
2. Run fresh build, size, size-components, OpenSpec, and whitespace gates.
3. Commit and push the verified migration baseline.
4. Move to hardware acceptance: BLE, WiFi, MQTT, OTA, SD, I2S, CAN.
5. Start S8 sound modeling only after S7 risk and hardware gates are understood.
