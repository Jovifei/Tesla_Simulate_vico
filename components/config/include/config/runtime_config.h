#pragma once

#include <cstdint>

namespace config {

struct RuntimeConfig {
    std::uint32_t can_bitrate        = 500000;
    bool          can_listen_only    = true;
    std::uint16_t audio_sample_rate  = 44100;
    std::uint8_t  audio_volume_pct   = 70;
};

inline constexpr RuntimeConfig kDefaultRuntimeConfig{};

}  // namespace config
