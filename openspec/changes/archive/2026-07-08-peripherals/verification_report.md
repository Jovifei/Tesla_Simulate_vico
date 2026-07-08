# Verification Report: peripherals (S4)

- **Change:** peripherals
- **Branch:** feature/peripherals
- **Build commit:** 4e57ddf
- **Base ref:** a00ec79
- **Verified at:** 2026-07-08
- **Verdict:** PASS (with deferred runtime tests)

## Build

- Command: `idf.py build`
- Result: exit code 0
- Artifact: `tesla_simulate_vico.bin`
- Size: 0xb3730 bytes (~735 KB), ~82% flash free
- Target: ESP32-S3

## Spec Coverage

All four ADDED requirements from `specs/peripherals/spec.md` are implemented and
compile-verified against the ESP-IDF v5.3 toolchain:

| Requirement | Component | Pins / Peripheral | Status |
| --- | --- | --- | --- |
| SD card configuration persistence | `SdConfigStore` (`components/storage/`) | SPI CS=45, CLK=39, MOSI=40, MISO=41; FATFS `/sdcard`; cJSON `/sdcard/config.json` | Compile-verified |
| Rotary encoder input | `Encoder` (`components/input/`) | Quadrature CLK=GPIO4, DT=GPIO5, pulled-up, debounced | Compile-verified |
| WS2812 status indication | `Ws2812Led` (`components/ui/`) | RMT driver, GPIO48, status→color mapping | Compile-verified |
| Throttle potentiometer ADC input | `ThrottlePot` (`components/input/`) | ADC1 oneshot, `ADC_CHANNEL_0` (GPIO1), smoothed 0.0–1.0 | Compile-verified |

`app::App` is rewired: `begin()` brings up storage/input/ui alongside CAN/audio/BLE
and loads persisted config (falling back to `kDefaultRuntimeConfig`); `tick()` applies
encoder deltas to volume/profile, feeds throttle into the engine model, updates the
status LED, and persists config on change.

## Tests

- **Compile-verification:** PASS — full firmware links with all four peripherals
  wired into `App`; no unresolved symbols, no ABI/API mismatch against ESP-IDF v5.3
  drivers (SPI/FATFS, RMT, ADC oneshot, GPIO).
- **Runtime tests:** DEFERRED — SD mount/load/save, encoder detent decoding, ADC
  full-scale response, and RMT WS2812 frame timing require physical hardware and are
  deferred to on-target bring-up.

## Known Gaps

1. **Runtime peripheral test pending** — no hardware available; SD/encoder/ADC/RMT
   behavior is compile-verified only. Requires on-target validation.
2. **Persist-on-dirty has no debounce** — `save()` is triggered on each config change;
   rapid encoder rotation could produce frequent SD writes. Acceptable for S4; a
   debounce/throttle on persistence is a follow-up.
3. **ADC full-scale uncalibrated** — `ThrottlePot::read()` normalizes to 0.0–1.0 with
   nominal full-scale assumptions; endpoint calibration against the actual pot/divider
   is deferred to hardware bring-up.

## Verdict

**PASS** — build clean (exit 0), all spec requirements compile-verified and wired into
the application. Runtime peripheral validation is explicitly deferred to hardware.
Proceed to archive.
