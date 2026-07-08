#pragma once

#include <cstdint>

namespace audio {

constexpr std::uint8_t clampVolumePercent(int volume_pct) {
    return static_cast<std::uint8_t>(
        volume_pct < 0 ? 0 : (volume_pct > 100 ? 100 : volume_pct));
}

constexpr float volumeGain(int volume_pct) {
    return static_cast<float>(clampVolumePercent(volume_pct)) / 100.0f;
}

}  // namespace audio
