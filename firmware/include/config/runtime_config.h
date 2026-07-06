#pragma once

#include <cstdint>

namespace tesla_speed::config {

struct RuntimeConfig {
  std::uint32_t can_bitrate = 500000;
  bool can_listen_only = true;
  std::uint16_t audio_sample_rate_hz = 44100;
  std::uint8_t audio_volume_percent = 70;
};

inline constexpr RuntimeConfig kDefaultRuntimeConfig{};

}  // namespace tesla_speed::config
