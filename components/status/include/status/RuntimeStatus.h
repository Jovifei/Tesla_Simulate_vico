#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace status {

enum class WifiState : std::uint8_t {
    Disabled = 0,
    Unconfigured,
    Provisioned,
    Connecting,
    Connected,
    Failed,
};

enum class IotState : std::uint8_t {
    Disabled = 0,
    Offline,
    Connecting,
    Local,
    Cloud,
    Failed,
};

enum class OtaState : std::uint8_t {
    Idle = 0,
    Pending,
    Checking,
    Downloading,
    Applying,
    Success,
    Failed,
};

inline constexpr std::size_t kStatusVersionMaxLen = 31;
inline constexpr std::size_t kStatusPartitionMaxLen = 15;
inline constexpr std::size_t kStatusResultMaxLen = 15;
inline constexpr std::size_t kStatusErrorMaxLen = 95;

struct RuntimeStatus {
    char version[kStatusVersionMaxLen + 1] = {};
    char partition[kStatusPartitionMaxLen + 1] = {};
    WifiState wifi_state = WifiState::Disabled;
    IotState iot_state = IotState::Disabled;
    OtaState ota_state = OtaState::Idle;
    std::uint8_t ota_progress_pct = 0;
    char ota_last_result[kStatusResultMaxLen + 1] = "idle";
    char last_error[kStatusErrorMaxLen + 1] = {};
    std::uint32_t device_status_bits = 0;
};

const char* toString(WifiState state);
const char* toString(IotState state);
const char* toString(OtaState state);

bool diagnosticsJson(const RuntimeStatus& status, char* dst, std::size_t dst_len);

}  // namespace status
