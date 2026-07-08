# Proposal: peripherals

## Why

Through S3 the firmware turns real Tesla CAN traffic into an RPM-tracked engine tone and exposes runtime configuration over BLE, but the device still has no local persistence, no physical controls, and no visible status. `config::RuntimeConfig` lives only in RAM, so every power cycle reverts to `kDefaultRuntimeConfig` — a BLE-tuned volume or profile is lost the moment the car is switched off. There is no way to change volume or select an engine profile without a phone, no local throttle input to drive the engine model when CAN is absent (bench testing, listen-only fallback), and no indicator to tell the user whether the simulator is booting, running, muted, or faulted. The board already routes the pins for all four peripherals (SD SPI on 45/39/40/41, rotary encoder on 4/5, WS2812 on 48, throttle pot on IO1) but no firmware drives them. S4 makes the simulator standalone-usable: config that survives reboot, on-device input, and at-a-glance status.

## What Changes

- Add `SdConfigStore` (new component `components/storage/`) that mounts the SD card over SPI (CS=45, CLK=39, MOSI=40, MISO=41) with FATFS and loads/saves `config::RuntimeConfig` as a JSON file (`/sdcard/config.json`). On boot it loads persisted values (falling back to `kDefaultRuntimeConfig` when the card or file is absent); on config change it saves the current `RuntimeConfig`.
- Add `Encoder` (new component `components/input/`) that reads the rotary encoder (CLK=4, DT=5) with debounced quadrature decoding and reports relative steps, used to adjust `audio_volume_pct` and to cycle the active engine sound profile.
- Add `Ws2812Led` (new component `components/ui/`) driving the single WS2812 on GPIO48 via the ESP-IDF RMT driver, showing device status (booting / running / muted / fault) as distinct colors.
- Add `ThrottlePot` (part of `components/input/`) reading the throttle potentiometer on GPIO1 via ADC1 channel 0 (oneshot), producing a smoothed normalized throttle value in the range 0.0–1.0.
- Wire the four peripherals into `app::App`: `begin()` initializes storage/input/ui alongside the existing CAN/audio/BLE bring-up and loads persisted config; `tick()` applies encoder deltas to volume/profile, feeds the throttle value into the engine model, updates the status LED, and persists config on change.
- Extend `config::RuntimeConfig` as needed for the persisted fields (e.g. active profile index) — additive only. Pin assignments in `config/pin_map.h` are already present and used, not changed. S1/S2/S3 (CAN, audio, BLE, `domain::VehicleState`) remain frozen; peripherals consume/produce config and state through the existing surfaces.

## Capabilities

- peripherals (NEW)
