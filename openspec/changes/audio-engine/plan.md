# Plan: audio-engine (S2.1)

change: audio-engine
design-doc: docs/superpowers/specs/2026-07-07-audio-engine-design.md

## Build mode

- build_mode: subagent-driven-development
- isolation: branch (feature/audio-engine)
- tdd_mode: direct (direct_override: true — integration code, runtime needs PCM5102A hardware)
- review_mode: off

## Tasks

- [x] T1: Create `audio::I2sAudioEngine` (header + cpp) implementing `AudioEngine` interface.
- [x] T2: Configure I2S std TX channel in `begin()` — `i2s_new_channel` → `i2s_channel_init_std_mode` (44100 Hz, 16-bit Philips mono, BCK=6/WS=7/DOUT=12) → `i2s_channel_enable`.
- [x] T3: RPM → frequency sine synthesis with persistent phase accumulator, clamped [40,220] Hz.
- [x] T4: `render()` writes synthesized/silent buffer via `i2s_channel_write` with bounded timeout, phase-continuous.
- [x] T5: Mute behavior — `setMuted(bool)` + effective mute `muted_ || overspeed_mute`, silence without phase reset.
- [x] T6: No Arduino / legacy `driver/i2s.h` — only `driver/i2s_std.h`.
- [x] T7: Build verification — `idf.py build` clean.
- [x] T8: Commit with comet-build message.

## Wiring

- `components/audio/CMakeLists.txt`: add `I2sAudioEngine.cpp` to SRCS; REQUIRES `driver esp_driver_i2s domain config`.
- `components/app/include/app/App.h`: swap `StubAudioEngine` → `I2sAudioEngine`.

## Path boundary

components/audio/, components/app/include/app/App.h, openspec/changes/audio-engine/, feature/audio-engine branch.
