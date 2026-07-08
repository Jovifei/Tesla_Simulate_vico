# Tesla Simulate Vico

ESP32-S3 firmware for Tesla vehicle engine sound simulation (buildable baseline, PRD ongoing).
It listens to Tesla OBD-II CAN in listen-only mode, synthesizes engine sound from speed/throttle
over I2S PCM5102A, and exposes BLE GATT config/telemetry.
Current hardware target: ESP32-S3-WROOM-1-N16R8.

## Hardware
- MCU: ESP32-S3-WROOM-1-N16R8
- Framework: ESP-IDF v5.3
- Pin map: see `components/config/include/config/pin_map.h`

## Project Structure
- `main/` - application entry point (`app_main`)
- `components/config/` - pin map and runtime configuration
- `components/domain/` - engine model pure logic
- `components/can/` - listen-only CAN source and Tesla frame parser
- `components/audio/` - I2S engine sound synthesis with runtime volume control
- `components/ble/` - NimBLE GATT configuration service
- `components/storage/` - SD-card JSON runtime configuration persistence
- `components/input/` - rotary encoder and throttle potentiometer input
- `components/ui/` - WS2812 status LED
- `components/ota/` - WiFi STA, HTTPS OTA, and OTA live status

## Build
Recommended from a normal PowerShell terminal:
```
.\scripts\esp-idf.ps1 build
```

The helper script sets `IDF_PATH`, `IDF_TOOLS_PATH`, and `IDF_PYTHON_ENV_PATH`
for the local ESP-IDF v5.3.2 install before invoking `idf.py`.

Inside an ESP-IDF terminal, the raw command also works:
```
idf.py build
```

## Current Implementation Status

- `main` loop: 25ms tick
- BLE GATT: primary service `0xfff0`, legacy compatibility service `0xffe0`
- SD config persistence + encoder + throttle potentiometer + WS2812 LED are integrated
- OTA baseline is implemented in code: partition layout now includes `nvs`, `otadata`, `phy_init`, `ota_0`, and `ota_1`
- `RuntimeConfig` now carries `wifi_ssid`, `wifi_password`, `ota_url`, and `ota_auto_check`
- BLE UUID contract is preserved: `ffe8` OTA settings JSON, `ffe5` diagnostics JSON, `ffea` live status; OTA-related BLE writes persist config for next boot and do not trigger OTA immediately

## Verification Snapshot

- `openspec validate --all --strict --json` passes `5/5` on `2026-07-08`
- `.\scripts\esp-idf.ps1 build` passes in the local ESP-IDF v5.3.2 environment
- `.\scripts\esp-idf.ps1 size` passes
- `.\scripts\esp-idf.ps1 size-components` passes
- IRAM remains `16383 / 16384` (`99.99%`), so the OTA baseline compiles but the release-hardening gate is not yet cleared
- Run OpenSpec from `E:\Tesla_speed\prj`:

```powershell
openspec validate --all --strict --json
```

This project uses `prj/openspec` as the active spec root.
Hardware runtime proof is still blocked on physical ESP32-S3 acceptance: the BLE checklist is not yet completed on device, and WiFi join / OTA runtime have not yet been proven on hardware.

## Flash & Monitor
```
.\scripts\esp-idf.ps1 -p COMx flash monitor
```

## Modules
- `domain` - engine model pure logic (speed/throttle to virtual RPM)
- `can` - listen-only CAN source, NO transmit API
- `audio` - I2S engine sound synthesis
- `ble` - GATT configuration service
- `config` - pin map and runtime configuration

## Safety
- CAN is listen-only: no transmit API exposed anywhere
- Overspeed mute above 180 kph
- Runtime audio volume is clamped to 0..100 percent before scaling PCM samples

## License
MIT, (c) 2026 JoviF
