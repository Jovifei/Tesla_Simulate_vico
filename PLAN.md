# Tesla Simulate Vico — Engineering Plan

> Status: S0 done (build verified), S1 next

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

## Environment

- ESP-IDF v5.3.2 at `E:\project\ESP_IDF_support\v5.3.2\esp-idf`
- Tools at `E:\project\ESP_IDF_support\tools` (xtensa-esp-elf 13.2.0, cmake 3.30.2, ninja)
- Python env `idf5.3_py3.14_env` (pip mirror: mirrors.aliyun.com)
- Target: esp32s3, flash 16MB, octal PSRAM
- GitHub mirror via ghfast.top (GitHub direct SSL unstable)
- VSCode ESP-IDF extension configured (`.vscode/settings.json`)
- Repo: https://github.com/Jovifei/Tesla_Simulate_vico

## Phases

### S0 — Repository & verification gate (DONE)

- [x] S0.1 child-claude: `.gitignore` + `README.md` + `LICENSE`
- [x] S0.2 parent: `PLAN.md`
- [x] S0.3 parent: `git init` + first commit (`bb705dd`)
- [x] S0.4 credentials via Git Credential Manager
- [x] S0.5 parent: remote + push to Tesla_Simulate_vico
- [x] S0.6a child-claude: ESP-IDF v5.3 skeleton + config component
- [x] S0.6b child-claude: migrate domain/can/audio/ble/app to ESP-IDF components
- [x] S0.6c parent: build verification — `tesla_simulate_vico.bin` (246KB) + `bootloader.bin` generated, exit=0

Build fixes applied (commit `018d4e4`):
- `can`: REQUIRES domain (CanSource includes VehicleState)
- `config`: REQUIRES esp_driver_gpio (pin_map uses gpio_num_t)
- `pin_map.h`: uint8_t → gpio_num_t
- `sdkconfig.defaults`: 16MB flash size, fix string quotes
- micro-ecc working dir restored via `git reset --hard`

ESP-IDF install notes (for reference):
- esp-idf source cloned from gitee mirror (GitHub SSL unstable)
- toolchain downloaded via curl + ghfast.top (Python urllib SSL fails on large files)
- `IDF_MIRROR_PREFIX_MAP=https://github.com,https://ghfast.top/https://github.com`
- `PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/`
- submodule URLs in `.git/config` rewritten from gitee to ghfast.top proxy

### S1 — CAN listen-only layer (next)

- [ ] S1.1 child-claude: Tesla CAN frame parser pure logic
  - Parse 0x256 (vehicle speed), 0x116 (torque) frames
  - Pure C++ logic, no HAL dependency, testable on host
  - Unit tests with unity (ESP-IDF test component or host)
  - Path: `components/can/include/can/CanFrames.h` + `components/can/CanFrames.cpp`
- [ ] S1.2 child-claude: `TwaiCanSource` real reception
  - ESP32-S3 TWAI driver (`driver/twai.h`)
  - Listen-only mode (`TWAI_MODE_LISTEN_ONLY`)
  - NO transmit API anywhere
  - Wire parser → `VehicleState`

### S2 — Audio engine

- [ ] S2.1 child-claude: engine sound synthesizer (RPM-based) + I2S output
  - Use ESP-IDF `driver/i2s_std.h` (NOT arduino-audio-tools — ESP-IDF framework)
- [ ] S2.2 child-claude: volume / mute / mixer integration

### S3 — BLE configuration

- [ ] S3.1 child-claude: NimBLE GATT service, `ffe1`–`ffeE` characteristics
  - Use `esp-nimble` (ESP-IDF built-in component, NOT NimBLE-Arduino)

### S4 — Peripherals & persistence

- [ ] S4.1 child-claude: SD card config store (load/save runtime config as JSON)
- [ ] S4.2 child-claude: rotary encoder, WS2812 LED, throttle potentiometer drivers

## Pin map (source of truth: `components/config/include/config/pin_map.h`)

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
- Audio: use ESP-IDF I2S API (`driver/i2s_std.h`), not Arduino audio libs
- BLE: use `esp-nimble` (ESP-IDF component), not NimBLE-Arduino
- Every child-claude task must specify: path boundary, allowed tools, acceptance, structured reply
- No secrets / tokens in repo files or task slips
- Parent reviews diff and runs verification before marking any phase done

## S1.1 dispatch plan (next child-claude task)

Task: Tesla CAN frame parser — pure logic
Path boundary:
- CREATE: `components/can/include/can/CanFrames.h`, `components/can/CanFrames.cpp`
- EDIT: `components/can/CMakeLists.txt` (add CanFrames.cpp to SRCS)
- NOT ALLOWED: modify TwaiCanSource.h/cpp, CanSource.h, any other component
Acceptance:
- `CanFrames::parseSpeed(0x256, data, len) -> float kph` (Tesla v4 speed format)
- `CanFrames::parseTorque(0x116, data, len) -> float [0,1]` (torque normalized)
- Unit tests (unity) covering: valid frame, wrong id, truncated data, zero speed
- `idf.py build` passes
Reply: raw JSON {summary, files_changed, risks}
