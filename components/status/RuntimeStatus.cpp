#include "status/RuntimeStatus.h"

#include <cstdio>
#include <cstring>

#include "cJSON.h"

namespace status {

namespace {
constexpr const char* kWifiState[] = {"disabled", "unconfigured", "provisioned", "connecting", "connected", "failed"};
constexpr const char* kIotState[]  = {"disabled", "offline", "connecting", "local", "cloud", "failed"};
constexpr const char* kOtaState[]  = {"idle", "pending", "checking", "downloading", "applying", "success", "failed"};
}  // namespace

const char* toString(WifiState state) {
    const auto idx = static_cast<std::size_t>(state);
    if (idx >= (sizeof(kWifiState) / sizeof(kWifiState[0]))) {
        return "unknown";
    }
    return kWifiState[idx];
}

const char* toString(IotState state) {
    const auto idx = static_cast<std::size_t>(state);
    if (idx >= (sizeof(kIotState) / sizeof(kIotState[0]))) {
        return "unknown";
    }
    return kIotState[idx];
}

const char* toString(OtaState state) {
    const auto idx = static_cast<std::size_t>(state);
    if (idx >= (sizeof(kOtaState) / sizeof(kOtaState[0]))) {
        return "unknown";
    }
    return kOtaState[idx];
}

bool diagnosticsJson(const RuntimeStatus& status, char* dst, std::size_t dst_len) {
    if (dst == nullptr || dst_len == 0) {
        return false;
    }

    cJSON* root = cJSON_CreateObject();
    if (root == nullptr) {
        return false;
    }

    cJSON_AddStringToObject(root, "version", status.version);
    cJSON_AddStringToObject(root, "partition", status.partition);
    cJSON_AddStringToObject(root, "wifi_state", toString(status.wifi_state));
    cJSON_AddStringToObject(root, "iot_state", toString(status.iot_state));
    cJSON_AddStringToObject(root, "ota_state", toString(status.ota_state));
    cJSON_AddNumberToObject(root, "ota_progress", status.ota_progress_pct);
    cJSON_AddStringToObject(root, "ota_last_result", status.ota_last_result);
    cJSON_AddStringToObject(root, "last_error", status.last_error);

    char* json = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (json == nullptr) {
        return false;
    }

    const bool ok = std::snprintf(dst, dst_len, "%s", json) < static_cast<int>(dst_len);
    cJSON_free(json);
    return ok;
}

}  // namespace status
