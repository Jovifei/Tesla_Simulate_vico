#pragma once

#include <cstddef>
#include <cstdint>

namespace config {

inline constexpr std::size_t kWifiSsidMaxLen     = 32;
inline constexpr std::size_t kWifiPasswordMaxLen = 64;
inline constexpr std::size_t kOtaUrlMaxLen       = 191;
inline constexpr std::size_t kMqttUriMaxLen      = 127;
inline constexpr std::size_t kMqttClientIdMaxLen  = 47;
inline constexpr std::size_t kMqttUsernameMaxLen  = 63;
inline constexpr std::size_t kMqttPasswordMaxLen  = 63;
inline constexpr std::size_t kMqttTopicMaxLen     = 95;
inline constexpr std::size_t kDeviceIdMaxLen      = 47;
inline constexpr std::size_t kProductIdMaxLen     = 31;

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
    bool          iot_enable = false;
    char          mqtt_uri[kMqttUriMaxLen + 1] = {};
    char          mqtt_client_id[kMqttClientIdMaxLen + 1] = {};
    char          mqtt_username[kMqttUsernameMaxLen + 1] = {};
    char          mqtt_password[kMqttPasswordMaxLen + 1] = {};
    char          mqtt_topic_up[kMqttTopicMaxLen + 1] = {};
    char          mqtt_topic_down[kMqttTopicMaxLen + 1] = {};
    char          device_id[kDeviceIdMaxLen + 1] = {};
    char          product_id[kProductIdMaxLen + 1] = {};
};

inline constexpr RuntimeConfig kDefaultRuntimeConfig{};

inline bool otaConfigReady(const RuntimeConfig& cfg) {
    return cfg.wifi_ssid[0] != '\0' && cfg.ota_url[0] != '\0';
}

inline bool wifiConfigReady(const RuntimeConfig& cfg) {
    return cfg.wifi_ssid[0] != '\0' && cfg.wifi_password[0] != '\0';
}

inline bool iotConfigReady(const RuntimeConfig& cfg) {
    return cfg.iot_enable && cfg.mqtt_uri[0] != '\0' && cfg.mqtt_client_id[0] != '\0' &&
           cfg.mqtt_topic_up[0] != '\0' && cfg.mqtt_topic_down[0] != '\0';
}

}  // namespace config
