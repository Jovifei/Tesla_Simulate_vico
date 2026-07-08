# Tasks: audio-engine

## S2.1 — I2S Audio Engine + RPM Sine Synthesis

- [x] **T1: Create I2sAudioEngine class** — Add `components/audio/include/audio/I2sAudioEngine.h` and `components/audio/I2sAudioEngine.cpp` implementing the `audio::AudioEngine` interface (`begin`, `render`, `setMuted`). Namespace `audio::`. Retire `StubAudioEngine` from the production wiring (keep only if still used by tests).

- [x] **T2: Configure I2S standard TX channel in begin()** — Use ESP-IDF v5.3 `driver/i2s_std.h`: `i2s_new_channel` (master, TX), `i2s_channel_init_std_mode` with 44100 Hz clock, 16-bit Philips mono slot, GPIO bclk=6 / ws=7 / dout=12 / mclk=unused / din=unused, then `i2s_channel_enable`. Return true on success, false + `ESP_LOGE` on failure.

- [x] **T3: Implement RPM → frequency sine synthesis** — Map `state.virtual_rpm` to a clamped synthesis frequency, fill an `int16_t` sample buffer using a persistent phase accumulator (`phase_`) advanced by `2π·freq/44100` per sample, wrapped modulo `2π`. Fixed sub-full-scale amplitude to avoid clipping.

- [x] **T4: Implement render() I2S write** — Write the synthesized (or silent) buffer to the channel via `i2s_channel_write` with a bounded timeout. Preserve phase continuity across successive `render()` calls.

- [x] **T5: Implement mute behavior** — `setMuted(bool)` sets `muted_`. `render()` emits zero-filled silence when `muted_ || state.overspeed_mute`, without resetting `phase_`, so un-mute resumes cleanly.

- [x] **T6: No Arduino / legacy-I2S static check** — Grep `components/audio/` for `Arduino`, `driver/i2s.h` (legacy), and any Arduino audio class — zero matches. Only `driver/i2s_std.h` is included.

- [x] **T7: Build verification** — `idf.py build` succeeds with no errors or warnings from the audio component. Confirm `I2sAudioEngine` compiles against the frozen `AudioEngine` interface and `domain::VehicleState`.

- [x] **T8: Commit** — Commit with comet-build message. Verify build clean.
