# peripherals Specification

## ADDED Requirements

### Requirement: SD card configuration persistence

The system SHALL persist `config::RuntimeConfig` to the SD card so that runtime configuration survives a power cycle. `SdConfigStore` SHALL mount the SD card over SPI using the pins defined in `config/pin_map.h` (CS=GPIO45, CLK=GPIO39, MOSI=GPIO40, MISO=GPIO41) with a FATFS filesystem at `/sdcard`, load `RuntimeConfig` from `/sdcard/config.json` on boot, and save the current `RuntimeConfig` back to that file when the configuration changes. When the card or config file is absent or the JSON is invalid, the system SHALL fall back to `config::kDefaultRuntimeConfig` and continue operating.

#### Scenario: Config loaded from SD on boot

- WHEN `SdConfigStore::begin()` succeeds and `/sdcard/config.json` exists with valid JSON
- THEN `load()` parses the file into a `config::RuntimeConfig` and the loaded values (e.g. `audio_volume_pct`, active profile) are used instead of the compile-time defaults

#### Scenario: Fallback to defaults when card missing

- WHEN the SD card cannot be mounted or `/sdcard/config.json` is missing or invalid
- THEN `load()` returns `false`, the system uses `config::kDefaultRuntimeConfig`, and boot continues without fault

#### Scenario: Config saved on change

- WHEN the in-RAM `RuntimeConfig` is modified (via encoder or BLE) and marked dirty
- THEN `save()` serializes the current `RuntimeConfig` to JSON and writes it to `/sdcard/config.json`, and a subsequent boot loads the persisted values

### Requirement: Rotary encoder input

The system SHALL read a rotary encoder on CLK=GPIO4 and DT=GPIO5 and translate rotation into configuration adjustments. `Encoder` SHALL configure both pins as pulled-up inputs, decode quadrature transitions with debounce, and expose a `poll()` that returns the signed detent delta accumulated since the previous call. The application SHALL apply the detent delta to a configuration target (audio volume, or the active engine profile selection).

#### Scenario: Clockwise rotation increases target

- WHEN the encoder is rotated one detent clockwise and `poll()` is called
- THEN `poll()` returns a positive delta and the application increases the active target (e.g. `audio_volume_pct` up to its clamp)

#### Scenario: Counter-clockwise rotation decreases target

- WHEN the encoder is rotated one detent counter-clockwise and `poll()` is called
- THEN `poll()` returns a negative delta and the application decreases the active target (clamped at its lower bound)

#### Scenario: No rotation yields zero

- WHEN the encoder has not moved since the previous `poll()`
- THEN `poll()` returns `0` and no configuration change is applied

### Requirement: WS2812 status indication

The system SHALL drive the single WS2812 LED on GPIO48 via the ESP-IDF RMT driver to indicate device status. `Ws2812Led` SHALL expose a `set(Status)` operation mapping each status (Booting, Running, Muted, Fault) to a distinct color and transmitting one WS2812 frame. The application SHALL set the status LED to Booting during `begin()` and update it each tick from the current vehicle state and configuration.

#### Scenario: Booting color during init

- WHEN `App::begin()` initializes the peripherals
- THEN `Ws2812Led::set(Status::Booting)` is called and the LED shows the Booting color

#### Scenario: Status reflects running vehicle state

- WHEN the system is running normally and audio is not muted
- THEN the LED shows the Running color; and WHEN `overspeed_mute` is active the LED shows the Muted color

### Requirement: Throttle potentiometer ADC input

The system SHALL read the throttle potentiometer on GPIO1 via ADC1 (channel 0) and produce a normalized throttle value. `ThrottlePot` SHALL configure an ADC1 oneshot channel on `ADC_CHANNEL_0`, and expose a `read()` that returns a smoothed, clamped value in the range `0.0` to `1.0`. The application SHALL feed this throttle value into the engine model as a local input.

#### Scenario: Full-scale pot reads near 1.0

- WHEN the potentiometer is at its maximum position and `read()` is called
- THEN `read()` returns a value clamped at or near `1.0`

#### Scenario: Zero pot reads near 0.0

- WHEN the potentiometer is at its minimum position and `read()` is called
- THEN `read()` returns a value clamped at or near `0.0`

#### Scenario: Reading is smoothed

- WHEN consecutive `read()` calls are made while the pot position is steady
- THEN the returned values are stable (low-pass smoothed) rather than raw ADC jitter
