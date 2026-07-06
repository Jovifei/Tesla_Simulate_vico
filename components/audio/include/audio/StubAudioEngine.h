#pragma once

#include "audio/AudioEngine.h"

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

    bool  muted()   const { return muted_; }
    float lastRpm()  const { return last_rpm_; }
    bool  started()  const { return started_; }

private:
    bool  started_  = false;
    bool  muted_    = false;
    float last_rpm_ = 0.0f;
};

}  // namespace audio
