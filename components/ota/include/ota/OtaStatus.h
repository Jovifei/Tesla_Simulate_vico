#pragma once

#include <cstddef>

namespace ota {

inline constexpr std::size_t kVersionMaxLen       = 31;
inline constexpr std::size_t kPartitionMaxLen     = 15;
inline constexpr std::size_t kWifiStateMaxLen     = 15;
inline constexpr std::size_t kOtaResultMaxLen     = 15;
inline constexpr std::size_t kLastErrorMaxLen     = 95;

struct OtaStatus {
    char version[kVersionMaxLen + 1] = {};
    char partition[kPartitionMaxLen + 1] = {};
    char wifi_state[kWifiStateMaxLen + 1] = "idle";
    char ota_last_result[kOtaResultMaxLen + 1] = "idle";
    char last_error[kLastErrorMaxLen + 1] = {};
    bool ota_in_progress = false;
};

}  // namespace ota
