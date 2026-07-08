# Build Plan: peripherals

change: peripherals
design-doc: docs/superpowers/specs/2026-07-08-peripherals-design.md

## Scope

Implement S4 local peripherals: SD config store, rotary encoder, throttle
potentiometer, WS2812 status LED, and wire them into `app::App`. Frozen: CAN,
audio, BLE, `domain::VehicleState`.

## Work items (maps to tasks.md T1–T10)

1. **config** — add additive `profile_index` field to `config::RuntimeConfig` (T6).
2. **components/storage/** — `SdConfigStore` (SPI2 bus + sdspi + FATFS mount; cJSON
   load/save of `RuntimeConfig`; atomic temp+rename) + CMakeLists
   `REQUIRES fatfs sdmmc driver json config` (T1, T2).
3. **components/input/** — `Encoder` (GPIO 4/5 pull-up, polled quadrature, 20 ms
   debounce, signed detents) + `ThrottlePot` (ADC1 oneshot ch0/GPIO1, EMA, 0..1)
   + CMakeLists `REQUIRES driver esp_driver_gpio esp_adc config` (T3, T4).
4. **components/ui/** — `Ws2812Led` (RMT TX on GPIO48, GRB frame, Status→color)
   + CMakeLists `REQUIRES driver esp_driver_rmt` (T5).
5. **components/app/** — wire the four peripherals into `App::begin()`/`tick()`;
   update `app/CMakeLists.txt` REQUIRES to add storage input ui (T7).
6. **build** — `idf.py build` exits 0; degrade version-sensitive driver APIs to
   compile-passing `ESP_LOGI` stubs if needed (T8, T9).
7. **commit** — comet-build message convention (T10).

## Acceptance

`idf.py build` succeeds; `App` compiles and links against storage/input/ui and the
frozen CAN/audio/BLE/domain surfaces. All tasks.md items checked.

## Path boundary

`components/storage/`, `components/input/`, `components/ui/`,
`components/app/include/app/App.h`, `components/app/CMakeLists.txt`,
`components/config/include/config/runtime_config.h`,
`openspec/changes/peripherals/`, `docs/superpowers/specs/`.
