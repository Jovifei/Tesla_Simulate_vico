# Design: audio-engine

**Change:** audio-engine
**Date:** 2026-07-07
**Status:** Ready for build

## 1. Overview

S2.1 replaces the memory-only `StubAudioEngine` with a real `audio::I2sAudioEngine`
that streams I2S samples to the PCM5102A DAC. The engine synthesizes a sine-wave
engine tone whose pitch tracks `domain::VehicleState.virtual_rpm`, and emits silence
when muted (explicit `setMuted(true)` or `state.overspeed_mute`). It uses the
ESP-IDF v5.3 standard-mode I2S API (`driver/i2s_std.h`) only — no Arduino audio libs,
no legacy `driver/i2s.h`.

**Target files:**
- `components/audio/include/audio/I2sAudioEngine.h` — class declaration (namespace `audio::`)
- `components/audio/I2sAudioEngine.cpp` — implementation
- `components/audio/CMakeLists.txt` — add `.cpp` to SRCS, add `driver` to REQUIRES

`StubAudioEngine.h` is retired from production wiring (kept only if referenced by tests).
`AudioEngine.h` (interface) and `domain::VehicleState` are frozen — unchanged.

## 2. Architecture

```
domain::VehicleState.virtual_rpm
        │
        ▼
I2sAudioEngine::render(state)
        │  muted_ || state.overspeed_mute ?
        ├─ yes → fill buffer with 0 (silence), phase preserved
        └─ no  → freq = rpmToFreq(virtual_rpm)
                 for each sample:
                     phase_ += 2π·freq / SAMPLE_RATE
                     if (phase_ >= 2π) phase_ -= 2π
                     sample = int16( AMPLITUDE · sinf(phase_) )
        │
        ▼
i2s_channel_write(tx_chan_, samples_, bytes, &written, TIMEOUT_MS)
        │
        ▼
   PCM5102A DAC  (BCK=GPIO6, LCK=GPIO7, DIN=GPIO12)
```

## 3. API Design

### 3.1 Class declaration (`I2sAudioEngine.h`)

```cpp
#pragma once

#include "audio/AudioEngine.h"
#include "driver/i2s_std.h"

namespace audio {

class I2sAudioEngine : public AudioEngine {
public:
    I2sAudioEngine() = default;
    ~I2sAudioEngine() override = default;

    bool begin() override;
    void render(const domain::VehicleState& state) override;
    void setMuted(bool muted) override;

private:
    static float rpmToFreq(float virtual_rpm);

    i2s_chan_handle_t tx_chan_ = nullptr;
    bool  started_ = false;
    bool  muted_   = false;
    float phase_   = 0.0f;   // radians, persists across render() calls
    int16_t samples_[FRAMES_PER_RENDER] = {};
};

}  // namespace audio
```

### 3.2 Synthesis constants (in `I2sAudioEngine.h` or `.cpp`)

```cpp
namespace audio {

constexpr uint32_t SAMPLE_RATE        = 44100;  // Hz
constexpr int      FRAMES_PER_RENDER  = 1024;   // int16 samples per render()
constexpr float    AMPLITUDE          = 0.6f * 32767.0f;  // ~-4.4 dBFS headroom

// RPM → frequency mapping
constexpr float    RPM_REF            = 8000.0f;  // reference (near redline)
constexpr float    RPM_FREQ_MIN       = 40.0f;    // Hz at idle-ish RPM
constexpr float    RPM_FREQ_MAX       = 220.0f;   // Hz at RPM_REF
constexpr uint32_t WRITE_TIMEOUT_MS   = 100;

}  // namespace audio
```

**Rationale:**
- `FRAMES_PER_RENDER = 1024` @ 44100 Hz ≈ 23.2 ms per buffer — coarse enough to
  amortize call overhead, fine enough for responsive pitch tracking.
- `AMPLITUDE` at 0.6·full-scale leaves headroom, no clipping on a pure sine.
- Mapping band 40–220 Hz gives a plausible low engine rumble that rises with RPM.
  Single sine partial for S2.1; richer harmonic timbre is deferred.

## 4. I2S Standard Configuration (ESP-IDF v5.3)

`begin()` uses the new I2S driver exclusively:

```cpp
bool I2sAudioEngine::begin() {
    i2s_chan_config_t chan_cfg =
        I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    if (i2s_new_channel(&chan_cfg, &tx_chan_, nullptr) != ESP_OK) {
        ESP_LOGE(TAG, "i2s_new_channel failed");
        return false;
    }

    i2s_std_config_t std_cfg = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(
                        I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = GPIO_NUM_6,
            .ws   = GPIO_NUM_7,
            .dout = GPIO_NUM_12,
            .din  = I2S_GPIO_UNUSED,
            .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false },
        },
    };
    if (i2s_channel_init_std_mode(tx_chan_, &std_cfg) != ESP_OK) {
        ESP_LOGE(TAG, "i2s_channel_init_std_mode failed");
        return false;
    }
    if (i2s_channel_enable(tx_chan_) != ESP_OK) {
        ESP_LOGE(TAG, "i2s_channel_enable failed");
        return false;
    }
    started_ = true;
    return true;
}
```

- **API path**: `i2s_new_channel()` → `i2s_channel_init_std_mode()` → `i2s_channel_enable()`.
  No legacy `driver/i2s.h`, no Arduino `I2S` class.
- **Channel**: TX only, `I2S_ROLE_MASTER`, `I2S_NUM_AUTO` port selection.
- **Clock**: `I2S_STD_CLK_DEFAULT_CONFIG(44100)`.
- **Slot**: `I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(16BIT, MONO)`.
- **GPIO**: `bclk=GPIO_NUM_6`, `ws=GPIO_NUM_7`, `dout=GPIO_NUM_12`,
  `mclk=I2S_GPIO_UNUSED`, `din=I2S_GPIO_UNUSED` (PCM5102A needs no MCLK; SCK tied low).
- **DMA**: default `dma_desc_num` / `dma_frame_num` from `I2S_CHANNEL_DEFAULT_CONFIG`.
- **Failure**: any `!= ESP_OK` → `ESP_LOGE` + return `false`; no audio produced (spec scenario).

## 5. Sine Synthesis

### 5.1 RPM → frequency map

```cpp
float I2sAudioEngine::rpmToFreq(float virtual_rpm) {
    float r = virtual_rpm / RPM_REF;                 // normalize
    if (r < 0.0f) r = 0.0f;
    if (r > 1.0f) r = 1.0f;                           // clamp
    return RPM_FREQ_MIN + r * (RPM_FREQ_MAX - RPM_FREQ_MIN);
}
```

Idle-ish tone at low RPM, higher pitch as RPM climbs, clamped to
`[RPM_FREQ_MIN, RPM_FREQ_MAX]`.

### 5.2 Phase accumulator

- `float phase_` in radians, advanced per sample by `dphi = 2π·freq / SAMPLE_RATE`,
  wrapped modulo `2π` to avoid float precision drift.
- **Persists across `render()` calls** so successive buffers are phase-continuous
  (no discontinuity clicks when frequency changes between renders).
- Never reset on mute — un-muting resumes the tone smoothly.

### 5.3 Sample generation

```cpp
void I2sAudioEngine::render(const domain::VehicleState& state) {
    if (!started_) return;

    const bool mute = muted_ || state.overspeed_mute;
    if (mute) {
        memset(samples_, 0, sizeof(samples_));          // phase_ untouched
    } else {
        const float freq = rpmToFreq(state.virtual_rpm);
        const float dphi = 2.0f * static_cast<float>(M_PI) * freq / SAMPLE_RATE;
        for (int i = 0; i < FRAMES_PER_RENDER; ++i) {
            samples_[i] = static_cast<int16_t>(AMPLITUDE * sinf(phase_));
            phase_ += dphi;
            if (phase_ >= 2.0f * static_cast<float>(M_PI))
                phase_ -= 2.0f * static_cast<float>(M_PI);
        }
    }

    size_t written = 0;
    i2s_channel_write(tx_chan_, samples_, sizeof(samples_),
                      &written, WRITE_TIMEOUT_MS);
}

void I2sAudioEngine::setMuted(bool muted) { muted_ = muted; }
```

- Fixed `int16_t samples_[FRAMES_PER_RENDER]` (mono). One `render()` → one buffer,
  blocking on `i2s_channel_write` with a bounded timeout (natural pacing / backpressure).

## 6. Mute Semantics

- `setMuted(bool)` stores `muted_`.
- Effective mute = `muted_ || state.overspeed_mute`.
- When muted the buffer is zero-filled and **still written** to I2S (keeps the DAC
  clocked and glitch-free — silence, not `i2s_channel_disable`).
- The phase accumulator is NOT reset, so un-muting resumes the tone cleanly.

## 7. Key Decisions

1. **New I2S API only**: ESP-IDF v5.3 deprecates `driver/i2s.h`; use `driver/i2s_std.h`
   exclusively for forward-compat and to satisfy the hard "no legacy" rule.
2. **Mono 16-bit**: PCM5102A is stereo, but the tone is mono; `I2S_SLOT_MODE_MONO`
   duplicates one channel. 16-bit is ample for a synthetic tone and halves DMA bandwidth.
3. **Blocking write in render()**: `render()` runs in the app loop; `i2s_channel_write`
   with a small timeout provides pacing via DMA-ring backpressure. No separate audio task in S2.1.
4. **Phase-continuous synthesis**: keeping `phase_` across calls prevents clicks when
   frequency changes between renders.
5. **Silence-not-stop on mute**: writing zeros (not `i2s_channel_disable`) keeps clocks
   running and avoids pop / enable-latency on un-mute.
6. **No Arduino libs**: hand-rolled `sinf()` synthesis, ESP-IDF I2S only. Namespace `audio::`.

## 8. Data Flow (pseudocode)

```
begin():
  chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER)
  i2s_new_channel(&chan_cfg, &tx_chan_, nullptr)
  std_cfg = { clk=44100, slot=PHILIPS(16BIT,MONO),
              gpio={ bclk=6, ws=7, dout=12, mclk=UNUSED, din=UNUSED } }
  i2s_channel_init_std_mode(tx_chan_, &std_cfg)
  i2s_channel_enable(tx_chan_)
  started_ = true; return true   (false + ESP_LOGE on any error)

render(state):
  if !started_: return
  mute = muted_ || state.overspeed_mute
  if mute: memset(samples_, 0, sizeof(samples_))
  else:
    freq = rpmToFreq(state.virtual_rpm)      // clamped [40,220] Hz
    dphi = 2π * freq / SAMPLE_RATE
    for i in [0, FRAMES_PER_RENDER):
        samples_[i] = int16(AMPLITUDE * sinf(phase_))
        phase_ += dphi; if phase_ >= 2π: phase_ -= 2π
  i2s_channel_write(tx_chan_, samples_, sizeof(samples_), &written, WRITE_TIMEOUT_MS)

setMuted(muted): muted_ = muted
```

## 9. Test Strategy

S2.1 targets on-target build + behavioral verification (I2S is hardware; the DMA path
is not host-unit-testable without mocks). Verification layers:

| Layer | Method | Pass criterion |
|---|---|---|
| Compile | `idf.py build` | I2sAudioEngine compiles against frozen `AudioEngine` + `VehicleState`, no audio-component errors/warnings |
| Static (no Arduino/legacy) | grep `components/audio/` for `Arduino`, `driver/i2s.h` | zero matches; only `driver/i2s_std.h` used |
| RPM → pitch | Inspect `rpmToFreq`: monotonic increasing, clamped | higher `virtual_rpm` → higher freq; bounded [40,220] |
| Phase continuity | Code review: `phase_` is a member, never reset in `render()`/mute | continuous waveform across buffers |
| Mute | Code review: `muted_ || overspeed_mute` → memset, phase untouched | silent buffer, phase preserved |

Optionally, a host-side pure-function unit test for `rpmToFreq` (monotonicity + clamp
bounds) could be added later since it has no ESP-IDF dependency, but it is not required
for S2.1 exit.

## 10. Build Integration

**`components/audio/CMakeLists.txt`:**
- Add `I2sAudioEngine.cpp` to `SRCS`.
- Add `driver` to `REQUIRES` (I2S standard-mode API lives in the `driver` component).
- Keep `domain` in `REQUIRES` (for `VehicleState.h`).

No changes to the CAN pipeline (S1 frozen), `domain::VehicleState`, or hardware.

## 11. Dependencies

- ESP-IDF v5.3 `driver/i2s_std.h` (new I2S standard-mode API) + `esp_log.h`.
- `<math.h>` for `sinf`, `M_PI`; `<cstring>` for `memset`.
- `audio/AudioEngine.h` — existing interface (`begin`, `render`, `setMuted`), unchanged.
- `domain/VehicleState.h` — `virtual_rpm`, `overspeed_mute` fields (S1 frozen).
- Pins: I2S_BCK=GPIO6, I2S_LCK=GPIO7, I2S_DIN=GPIO12 (PCM5102A).

## 12. Risks

1. **DMA underrun / clicks**: if the app loop calls `render()` too slowly the DMA ring
   starves and audio glitches. Mitigation: `FRAMES_PER_RENDER=1024` (~23 ms) plus default
   DMA buffers cover several ms; blocking write paces the loop.
2. **Float `sinf()` cost per sample**: acceptable at 44100 Hz on the S3 FPU for a single
   partial; if CPU-bound later, switch to a wavetable. Not a concern for S2.1.
3. **GPIO conflict**: BCK/LCK/DIN (6/7/12) must not collide with CAN pins (13/14/38) or
   other peripherals — confirmed distinct.
4. **PCM5102A format lock**: board strapping (FMT/DEMP/XSMT) must match Philips-standard
   16-bit I2S; assumed correct per hardware design.
5. **RPM mapping is a placeholder**: 40–220 Hz band and single partial are a first cut;
   tuning the mapping and adding harmonics is deferred beyond S2.1.
