#pragma once

#include "audio/AudioEngine.h"
#include "driver/i2s_std.h"

#include <cstdint>

namespace audio {

constexpr uint32_t SAMPLE_RATE       = 44100;              // Hz
constexpr int      FRAMES_PER_RENDER = 1024;              // int16 samples per render()
constexpr float    AMPLITUDE         = 0.6f * 32767.0f;   // ~-4.4 dBFS headroom

// RPM -> frequency mapping
constexpr float    RPM_REF          = 8000.0f;  // reference (near redline)
constexpr float    RPM_FREQ_MIN     = 40.0f;    // Hz at idle-ish RPM
constexpr float    RPM_FREQ_MAX     = 220.0f;   // Hz at RPM_REF
constexpr uint32_t WRITE_TIMEOUT_MS = 100;

class I2sAudioEngine final : public AudioEngine {
public:
    I2sAudioEngine()           = default;
    ~I2sAudioEngine() override = default;

    bool begin() override;
    void render(const domain::VehicleState& state) override;
    void setMuted(bool muted) override;

private:
    static float rpmToFreq(float virtual_rpm);

    i2s_chan_handle_t tx_chan_ = nullptr;
    bool  started_ = false;
    bool  muted_   = false;
    float phase_   = 0.0f;  // radians, persists across render() calls
    int16_t samples_[FRAMES_PER_RENDER] = {};
};

}  // namespace audio
