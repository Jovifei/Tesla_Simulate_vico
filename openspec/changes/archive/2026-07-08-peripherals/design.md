# Design: peripherals

**Change:** peripherals
**Date:** 2026-07-08
**Status:** Deepened (design phase)

## 1. Overview

S4 adds the four local peripherals the board is already wired for but no
firmware drives: SD-card config persistence, a rotary encoder for on-device
input, a WS2812 status LED, and a throttle potentiometer as a local engine
input. Together they make the simulator standalone-usable without a phone —
config survives a power cycle, volume/profile are adjustable at the knob,
status is visible at a glance, and the engine model can be driven from a local
throttle when CAN is absent.

Pin assignments come from `config/pin_map.h` (already present, unchanged):
SD `CS=45 / CLK=39 / MOSI=40 / MISO=41`, encoder `CLK=4 / DT=5`,
WS2812 `WS_DATA=48`, throttle pot `POT_IO1=1`. ESP-IDF v5.3, C++17.
S1/S2/S3 (CAN, audio, BLE, `domain::VehicleState`) stay frozen.

**Target components / files:**
- `components/storage/` — `SdConfigStore` (SPI + FATFS mount, JSON load/save of `config::RuntimeConfig`)
- `components/input/` — `Encoder` (quadrature + debounce) and `ThrottlePot` (ADC1 oneshot)
- `components/ui/` — `Ws2812Led` (RMT driver, status colors)
- `components/app/include/app/App.h` — wire the four peripherals into `begin()`/`tick()`
- `components/config/include/config/runtime_config.h` — additive fields for persisted state (e.g. active profile index)

## 2. Architecture

```
App::begin()
  ├─ storage_.begin()        // mount SD (SPI bus + FATFS), returns ok
  │     └─ if ok: storage_.load(cfg_)   // /sdcard/config.json → RuntimeConfig
  │        else:  cfg_ = kDefaultRuntimeConfig
  ├─ encoder_.begin()        // config GPIO 4/5, edge ISR or polled quadrature
  ├─ pot_.begin()            // adc1 unit + oneshot channel on GPIO1 (ch0)
  ├─ led_.begin()            // RMT TX channel on GPIO48, encoder = WS2812
  │     └─ led_.set(Status::Booting)
  └─ (existing) can_/audio_/ble_ begin()

App::tick()
  ├─ int steps = encoder_.poll()     // signed detent delta since last poll
  │     └─ apply to cfg_.audio_volume_pct (or profile when in profile mode)
  ├─ float thr = pot_.read()         // 0.0..1.0 smoothed
  ├─ state = can_.poll(...) or synthesized from thr when CAN idle
  ├─ state = engine_.update(state)
  ├─ audio_.setMuted(state.overspeed_mute); audio_.render(state)
  ├─ led_.set(status derived from state: Running / Muted / Fault)
  └─ if (cfg_ changed) storage_.save(cfg_)   // debounced persist
```

## 3. Component sketches (concrete API-level design)

### 3.1 SdConfigStore (`components/storage/`)

**Bring-up (`begin()`):**
1. Build `spi_bus_config_t` from `pin_map.h`: `mosi_io_num = SD_MOSI (40)`,
   `miso_io_num = SD_MISO (41)`, `sclk_io_num = SD_CLK (39)`, quadwp/quadhd = -1,
   `max_transfer_sz = 4000`.
2. `spi_bus_initialize(SPI2_HOST, &bus_cfg, SDSPI_DEFAULT_DMA)`.
3. Build `sdspi_device_config_t slot = SDSPI_DEVICE_CONFIG_DEFAULT()`;
   `slot.gpio_cs = SD_CS (45)`; `slot.host_id = SPI2_HOST`.
4. `sdmmc_host_t host = SDSPI_HOST_DEFAULT()`; `host.slot = SPI2_HOST`.
5. `esp_vfs_fat_sdspi_mount("/sdcard", &host, &slot, &mount_cfg, &card_)` where
   `mount_cfg = { .format_if_mount_failed = false, .max_files = 4,
   .allocation_unit_size = 16 * 1024 }`. On non-`ESP_OK` → `ESP_LOGE`, cache
   `mounted_ = false`, return `false`. On success → `sdmmc_card_print_info`,
   `mounted_ = true`, return `true`.

**`load(config::RuntimeConfig&)`:** guard on `mounted_`; `fopen("/sdcard/config.json","r")`,
read into a heap buffer, `cJSON_Parse`, then for each key
(`can_bitrate`, `can_listen_only`, `audio_sample_rate`, `audio_volume_pct`,
`profile_index`) copy into the struct only if the JSON item is present and the
right type. `cJSON_Delete`, `fclose`. Return `false` (leaving caller's defaults
untouched) whenever unmounted / file missing / parse fails; `true` on a good parse.

**`save(const config::RuntimeConfig&)`:** guard on `mounted_`; build a `cJSON`
object with the five fields, `cJSON_PrintUnformatted`, write to a temp path
`/sdcard/config.tmp`, `fflush`+`fclose`, then `rename("/sdcard/config.tmp",
"/sdcard/config.json")` for atomic replace. Return the success bool.

- REQUIRES: `fatfs`, `sdmmc`, `driver` (sdspi lives in `driver`), `json` (cJSON), `config`.

### 3.2 Encoder (`components/input/`)

- `begin()`: `gpio_config_t` with `pin_bit_mask = (1ULL<<ENC_CLK)|(1ULL<<ENC_DT)`,
  `mode = GPIO_MODE_INPUT`, `pull_up_en = GPIO_PULLUP_ENABLE`, no interrupts.
  Seed `prev_state_` from the two pin levels.
- `poll()`: polled quadrature decode. Read CLK/DT, form 2-bit `state`, index a
  16-entry transition table `((prev_state_<<2)|state)` → {-1,0,+1}. Accumulate
  into a sub-detent counter; emit one signed step per 4 sub-steps (one detent).
  Debounce: ignore transitions closer than 20 ms via `esp_timer_get_time()`.
  Returns signed detents since the previous call, `0` when idle.

### 3.3 ThrottlePot (`components/input/`)

- `begin()`: `adc_oneshot_new_unit(ADC_UNIT_1, ...)`; `adc_oneshot_config_channel`
  on `ADC_CHANNEL_0` (GPIO1) with `atten = ADC_ATTEN_DB_12`,
  `bitwidth = ADC_BITWIDTH_12`. Seed EMA to first read.
- `read()`: `adc_oneshot_read` → raw 0..4095; normalize `raw / 4095.0f`; EMA
  smooth `ema_ = a*x + (1-a)*ema_` (a≈0.2); clamp `0.0..1.0`; return `ema_`.

### 3.4 Ws2812Led (`components/ui/`)

- `begin()`: `rmt_tx_channel_config_t` on `WS_DATA (48)`,
  `resolution_hz = 10 MHz` (0.1 µs tick), `mem_block_symbols = 64`,
  `trans_queue_depth = 4`; `rmt_new_tx_channel` + `rmt_enable`. Create a
  `rmt_bytes_encoder` with WS2812 T0H/T0L/T1H/T1L bit timings.
- `set_color(r,g,b)` / `set(Status)`: pack GRB into a 3-byte buffer,
  `rmt_transmit` through the bytes encoder, `rmt_tx_wait_all_done`. `set(Status)`
  maps Booting=blue, Running=green, Muted=amber, Fault=red.

> Fallback: if the RMT encoder API proves version-sensitive, `Ws2812Led` degrades
> to a compile-passing stub that `ESP_LOGI`s the requested color and returns —
> hardware bit-banging is deferred, the public surface is unchanged.

## 4. App wiring (concrete)

`App` gains four members (`SdConfigStore storage_`, `Encoder encoder_`,
`ThrottlePot pot_`, `Ws2812Led led_`) plus the in-RAM `config::RuntimeConfig cfg_`
and a `bool cfg_dirty_`.

- `begin()`: bring up `led_` first and `led_.set(Status::Booting)`. Init `storage_`;
  if mount ok call `storage_.load(cfg_)` (on `false`, keep `kDefaultRuntimeConfig`).
  Init `encoder_` and `pot_`. Then the existing CAN/audio/BLE bring-up. Return the
  AND of the required (non-optional) subsystems — storage/SD is treated as optional
  (a missing card must not fail boot), matching the "fallback to defaults" spec.
- `tick()`:
  1. `int steps = encoder_.poll();` — apply to `cfg_.audio_volume_pct` with clamp
     `[0,100]`; set `cfg_dirty_` if changed.
  2. `float thr = pot_.read();`
  3. `domain::VehicleState state{};` — `bool live = can_.poll(state);` when CAN is
     not valid, synthesize `state.throttle = thr` (local bench input).
  4. `state = engine_.update(state);`
  5. `audio_.setMuted(state.overspeed_mute); audio_.render(state);`
  6. LED status: `Fault` if no CAN and no SD, else `Muted` on overspeed, else `Running`.
  7. If `cfg_dirty_`, `storage_.save(cfg_); cfg_dirty_ = false;` (debounce left to a
     later polish pass — S4 persists on the tick the change is observed).

## 5. Data flow & wiring notes
- `RuntimeConfig` is the single persisted struct; `SdConfigStore` is its only
  disk backing. BLE writes and encoder deltas both mutate the in-RAM `cfg_`;
  a dirty flag drives `save()`.
- Throttle: when CAN provides live vehicle data, that wins; the pot is the local
  fallback / bench input feeding the engine model.
- LED status is derived, not stored — computed each tick from state/config.
- `RuntimeConfig` gains an additive `std::uint8_t profile_index = 0;` field for the
  persisted active engine profile; `kDefaultRuntimeConfig` keeps compiling unchanged.

## 6. Test strategy
- **Compile/link** is the primary S4 gate: `idf.py build` must exit 0 with the four
  new components and the rewired `App`. This is the automated acceptance for T9.
- **Host-testable logic** (deferred, no hardware): the encoder quadrature transition
  table and the pot EMA/clamp are pure functions and are the natural unit-test
  targets in a follow-up, mirroring `components/can/test/`.
- **On-target** validation (SD round-trip, real detents, LED color, ADC range) is a
  manual bench step outside the S4 build gate.

## 7. Non-goals (S4)
- No new BLE characteristics for the peripherals (BLE surface frozen at S3).
- No encoder push-button handling, no multi-LED strips, no SD file browser.
- No change to CAN/audio/domain logic beyond additive `RuntimeConfig` fields.
- Full RMT/ADC/SDMMC hardware validation is deferred; where an ESP-IDF v5.3 API
  proves version-sensitive at build time, the affected driver degrades to a
  compile-passing `ESP_LOGI` stub with an unchanged public surface (see §3.4).
