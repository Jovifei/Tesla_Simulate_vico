# Tesla Simulate Vico

ESP32-S3 firmware for Tesla vehicle engine sound simulation. Reads vehicle speed via OBD-II CAN in listen-only mode (no transmit), synthesizes RPM-based engine audio over I2S, and exposes a BLE GATT configuration service. Hardware target: ESP32-S3-WROOM-1-N16R8.

## Hardware
- MCU: ESP32-S3-WROOM-1-N16R8
- Framework: ESP-IDF v5.3
- Pin map: see `components/config/include/config/pin_map.h`

## Project Structure
- `main/` - application entry point (`app_main`)
- `components/config/` - pin map and runtime configuration
- `components/domain/` - engine model pure logic (S0.6b, pending)
- `components/can/` - listen-only CAN source (S0.6b, pending)
- `components/audio/` - I2S engine sound synthesis (S0.6b, pending)
- `components/ble/` - GATT configuration service (S0.6b, pending)

## Build
```
idf.py build
```

## Flash & Monitor
```
idf.py -p COMx flash monitor
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

## License
MIT, (c) 2026 JoviF
