# Tasks: peripherals

## S4 — Local Peripherals (SD config, encoder, WS2812, throttle pot)

- [x] **T1: SdConfigStore — SPI + FATFS mount** — Create `components/storage/` with `SdConfigStore` (`include/storage/SdConfigStore.h` + `.cpp`). Initialize the SPI bus and mount the SD card via `esp_vfs_fat_sdspi_mount("/sdcard", ...)` using pins from `config/pin_map.h` (CS=45, CLK=39, MOSI=40, MISO=41). `begin()` returns `true` on successful mount, `false` + `ESP_LOGE` otherwise.

- [x] **T2: SdConfigStore — JSON load/save of RuntimeConfig** — Implement `load(config::RuntimeConfig&)` (parse `/sdcard/config.json` with cJSON, fall back to `kDefaultRuntimeConfig` when file/card missing or JSON invalid) and `save(const config::RuntimeConfig&)` (serialize to JSON, write atomically). Round-trip is lossless for all persisted fields.

- [x] **T3: Encoder — quadrature decode + debounce** — Create `components/input/` with `Encoder` (`include/input/Encoder.h` + `.cpp`). Configure CLK=4 / DT=5 as pulled-up inputs, decode quadrature transitions with debounce, and expose `poll()` returning the signed detent delta since the last call.

- [x] **T4: ThrottlePot — ADC1 oneshot read** — Add `ThrottlePot` to `components/input/`. Configure ADC1 oneshot on `ADC_CHANNEL_0` (GPIO1), and expose `read()` returning a smoothed, clamped throttle value normalized to `0.0..1.0`.

- [x] **T5: Ws2812Led — RMT status LED** — Create `components/ui/` with `Ws2812Led` (`include/ui/Ws2812Led.h` + `.cpp`). Drive the single WS2812 on GPIO48 via the RMT driver and expose `set(Status)` mapping Booting / Running / Muted / Fault to distinct colors.

- [x] **T6: Extend RuntimeConfig (additive)** — Add any fields needed for persistence (e.g. active engine profile index) to `config::RuntimeConfig`, keeping the change additive with sensible defaults in `kDefaultRuntimeConfig`.

- [x] **T7: Wire peripherals into App** — Update `components/app/include/app/App.h`: in `begin()` init storage/input/ui, load persisted config (fallback to defaults), set LED to Booting; in `tick()` apply encoder deltas to volume/profile, feed the throttle value to the engine model, update the status LED, and persist config on change (debounced dirty flag).

- [x] **T8: Build integration** — Add `CMakeLists.txt` for `components/storage/`, `components/input/`, `components/ui/` with correct `SRCS`/`REQUIRES` (fatfs, sdmmc, sdspi, json, esp_driver_gpio, esp_adc, esp_driver_rmt, config, domain as applicable). Ensure `sdkconfig.defaults` enables FATFS long filenames / SDSPI as needed.

- [x] **T9: Build verification** — `idf.py build` succeeds with no errors from the new components. Confirm `App` compiles and links against storage/input/ui and the frozen CAN/audio/BLE/domain surfaces.

- [x] **T10: Commit** — Commit with the comet-build message convention. Verify the build is clean.
