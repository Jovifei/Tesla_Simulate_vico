# Proposal: audio-engine

## Why

S1 (can-frame-parser + twai-can-source) now delivers a live `domain::VehicleState` whose `virtual_rpm` field is derived from real Tesla CAN traffic. Nothing yet turns that RPM into sound: `components/audio/` ships only `StubAudioEngine`, which records `last_rpm_`/`muted_` in memory and produces no audio. The ESP32-S3 drives a PCM5102A I2S DAC (BCK=GPIO6, LCK=GPIO7, DIN=GPIO12) that is currently idle. To make the Tesla Sound Simulator actually simulate an engine, we need a real `AudioEngine` that streams I2S samples whose pitch tracks `virtual_rpm`.

## What Changes

- Replace `StubAudioEngine` with a real `audio::I2sAudioEngine` (new files under `components/audio/`) implementing the existing `AudioEngine` interface (`begin`, `render`, `setMuted`).
- `begin()` configures the ESP-IDF v5.3 I2S standard TX channel (`driver/i2s_std.h`): 44100 Hz, 16-bit, mono, on BCK=GPIO6, LCK=GPIO7, DIN=GPIO12 (PCM5102A). Uses the new API only: `i2s_new_channel` → `i2s_channel_init_std_mode` → `i2s_channel_enable`.
- `render(state)` maps `state.virtual_rpm` to a synthesis frequency, generates a simplified sine-wave engine tone into a sample buffer with a continuous phase accumulator, and writes it to the I2S channel via `i2s_channel_write`.
- Mute behavior: when muted (`setMuted(true)`) or when `state.overspeed_mute` is set, `render()` emits silence (zero samples) instead of the tone; the phase accumulator is preserved so audio resumes cleanly on un-mute.
- **No Arduino audio libraries** — pure ESP-IDF I2S + hand-rolled sine synthesis. Namespace stays `audio::`.
- No changes to the CAN pipeline (S1 frozen), `domain::VehicleState`, or hardware.

## Capabilities

- audio-engine (NEW)
