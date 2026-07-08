#pragma once

#include "audio/AudioEngine.h"
#include "audio/AudioVolume.h"

namespace audio {

class StubAudioEngine final : public AudioEngine {
public:
    bool begin() override {
        started_ = true;
        return true;
    }

    void render(const domain::VehicleState& state) override {
        last_rpm_ = state.virtual_rpm;
        muted_ = muted_ || state.overspeed_mute;
    }

    void setMuted(bool muted) override { muted_ = muted; }
    void setVolumePercent(std::uint8_t volume_pct) override {
        volume_pct_ = clampVolumePercent(volume_pct);
    }

    bool  muted()   const { return muted_; }
    float lastRpm()  const { return last_rpm_; }
    bool  started()  const { return started_; }
    std::uint8_t volumePercent() const { return volume_pct_; }

private:
    bool  started_  = false;
    bool  muted_    = false;
    float last_rpm_ = 0.0f;
    std::uint8_t volume_pct_ = 100;
};

}  // namespace audio
