#pragma once

#include "domain/VehicleState.h"

#include <cstdint>

namespace audio {

class AudioEngine {
public:
    virtual ~AudioEngine() = default;
    virtual bool begin() = 0;
    virtual void render(const domain::VehicleState& state) = 0;
    virtual void setMuted(bool muted) = 0;
    virtual void setVolumePercent(std::uint8_t volume_pct) = 0;
};

}  // namespace audio
