# Tesla Simulate Vico

ESP32-S3 firmware for Tesla vehicle engine sound simulation. Reads vehicle speed via OBD-II CAN in listen-only mode (no transmit), synthesizes RPM-based engine audio over I2S, and exposes a BLE GATT configuration service. Hardware target: ESP32-S3-WROOM-1-N16R8.

## Hardware
- MCU: ESP32-S3-WROOM-1-N16R8
- Pin map: see `firmware/include/config/pin_map.h`

## Project Structure
- `firmware/src/` - application entry point
- `firmware/include/` - module headers (domain, can, audio, ble, config, app)
- `firmware/test/native/` - native pure-logic tests

## Build
pio run -e esp32s3dev

## Test
pio test -e native

## Modules
- `domain` - engine model pure logic (speed/throttle to virtual RPM)
- `can` - listen-only CAN source, NO transmit API
- `audio` - I2S engine sound synthesis
- `ble` - GATT configuration service
- `config` - pin map and runtime configuration
- `app` - module wiring and main loop

## Safety
- CAN is listen-only: no transmit API exposed anywhere
- Overspeed mute above 180 kph

## License
MIT, (c) 2026 JoviF
