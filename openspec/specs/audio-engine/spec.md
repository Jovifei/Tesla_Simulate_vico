# audio-engine Specification

## Purpose
I2S audio output and baseline engine-tone synthesis behavior for Tesla Simulate Vico.
## Requirements
### Requirement: I2S standard TX channel configuration

The system SHALL configure the ESP32-S3 I2S peripheral using the ESP-IDF v5.3 standard-mode API (`driver/i2s_std.h`) for a master transmit channel at 44100 Hz sample rate, 16-bit sample width, mono slot mode, with BCK on GPIO 6, LCK (word select) on GPIO 7, and DIN (data out) on GPIO 12. The channel SHALL be created with `i2s_new_channel`, initialized with `i2s_channel_init_std_mode`, and enabled with `i2s_channel_enable` inside `begin()`.

#### Scenario: Successful channel enable

- WHEN `I2sAudioEngine::begin()` is called
- THEN a master TX I2S standard channel is created, initialized at 44100 Hz / 16-bit / mono on GPIO 6/7/12, enabled, and `begin()` returns `true`

#### Scenario: Channel init failure

- WHEN `i2s_channel_init_std_mode()` or `i2s_channel_enable()` returns an error
- THEN `begin()` returns `false` and no audio is produced

### Requirement: RPM-based sine synthesis

The system SHALL synthesize a sine-wave engine tone whose frequency scales with `domain::VehicleState.virtual_rpm`. `render()` SHALL map `virtual_rpm` to a clamped synthesis frequency, generate 16-bit samples using a phase accumulator advanced by `2*pi*freq/44100` per sample, and write them to the I2S channel via `i2s_channel_write`. The phase accumulator SHALL persist across successive `render()` calls so that generated audio is phase-continuous.

#### Scenario: Higher RPM yields higher pitch

- WHEN `render()` is called with a larger `virtual_rpm` than the previous call (not muted)
- THEN the synthesized sine frequency is higher and non-zero samples are written to the I2S channel

#### Scenario: Phase continuity across renders

- WHEN two consecutive `render()` calls run at the same `virtual_rpm` (not muted)
- THEN the phase accumulator carries over from the first buffer to the second (no reset), producing a continuous waveform without discontinuity clicks

### Requirement: Mute on overspeed or explicit request

The system SHALL suppress audible output when muted. `setMuted(true)` SHALL set the muted state, and `render()` SHALL emit zero-valued (silent) samples whenever `muted_` is true OR `state.overspeed_mute` is true. When muting, the phase accumulator SHALL NOT be reset, so that un-muting resumes the tone cleanly.

#### Scenario: Explicit mute

- WHEN `setMuted(true)` has been called and `render()` runs
- THEN a zero-filled (silent) buffer is written to the I2S channel

#### Scenario: Overspeed mute

- WHEN `render()` is called with `state.overspeed_mute == true` (even if `setMuted(false)`)
- THEN a zero-filled (silent) buffer is written to the I2S channel

#### Scenario: Un-mute resumes cleanly

- WHEN mute is cleared after a muted period and `render()` runs with a non-zero `virtual_rpm`
- THEN synthesis resumes from the preserved phase accumulator without resetting it to zero

### Requirement: Runtime volume control

The system SHALL expose `AudioEngine::setVolumePercent()` so that persisted or locally adjusted runtime configuration can control output loudness. `I2sAudioEngine` SHALL clamp the volume percentage to the range 0..100 and scale generated PCM sample amplitude by `volume_pct / 100.0`. Volume 0 SHALL produce silence without resetting the phase accumulator; volume 100 SHALL preserve the nominal synthesis amplitude.

#### Scenario: Persisted volume scales I2S samples

- GIVEN `RuntimeConfig.audio_volume_pct` is 42
- WHEN the application applies runtime config to the audio engine and `render()` generates non-muted samples
- THEN the generated sample amplitude is scaled by 0.42 before being written to the I2S channel

#### Scenario: Volume clamp protects the output range

- WHEN a volume value below 0 or above 100 is applied through the audio volume helper
- THEN the effective volume is clamped to 0 or 100 respectively

### Requirement: No Arduino audio libraries

The `audio::` module SHALL NOT depend on any Arduino framework audio library or the deprecated legacy I2S driver (`driver/i2s.h`). Audio output SHALL use only the ESP-IDF v5.3 standard-mode I2S API (`driver/i2s_std.h`) with hand-rolled synthesis.

#### Scenario: No Arduino or legacy-I2S includes

- WHEN all source files under `components/audio/` are searched for `Arduino` and the legacy `driver/i2s.h` include
- THEN zero matches are found and only `driver/i2s_std.h` is used for I2S
