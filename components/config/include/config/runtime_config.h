#pragma once

#include <cstddef>
#include <cstdint>

namespace config {

inline constexpr std::size_t kWifiSsidMaxLen     = 32;
inline constexpr std::size_t kWifiPasswordMaxLen = 64;
inline constexpr std::size_t kOtaUrlMaxLen       = 191;

struct RuntimeConfig {
    std::uint32_t can_bitrate        = 500000;
    bool          can_listen_only    = true;
    bool          can_accept_legacy_can_ids = true;
    std::uint16_t audio_sample_rate  = 44100;
    std::uint8_t  audio_volume_pct   = 70;
    std::uint8_t  profile_index      = 0;
    char          wifi_ssid[kWifiSsidMaxLen + 1] = {};
    char          wifi_password[kWifiPasswordMaxLen + 1] = {};
    char          ota_url[kOtaUrlMaxLen + 1] = {};
    bool          ota_auto_check = false;
};

inline constexpr RuntimeConfig kDefaultRuntimeConfig{};

inline bool otaConfigReady(const RuntimeConfig& cfg) {
    return cfg.wifi_ssid[0] != '\0' && cfg.ota_url[0] != '\0';
}

}  // namespace config
