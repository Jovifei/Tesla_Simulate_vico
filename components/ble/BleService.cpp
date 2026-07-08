#include "ble/BleService.h"

#include "ble/BleUuids.h"
#include "domain/VehicleState.h"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "cJSON.h"
#include "esp_log.h"
#include "nvs_flash.h"

#include "freertos/FreeRTOS.h"
#include "freertos/portmacro.h"

#include "host/ble_hs.h"
#include "host/ble_uuid.h"
#include "host/ble_store.h"
#include "host/util/util.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"

namespace {

constexpr const char* kTag = "ble";
constexpr const char* kDeviceName = "Tesla-Vico";

constexpr uint16_t kSvcUuid16 = 0xfff0;
constexpr uint16_t kLegacySvcUuid16 = 0xffe0;
constexpr uint16_t kConfigUuid16 = 0xffe1;
constexpr uint16_t kStateUuid16 = 0xffe2;
constexpr uint16_t kAudioUuid16 = 0xffe3;
constexpr uint16_t kCanUuid16 = 0xffe4;
constexpr uint16_t kDiagnosticsUuid16 = 0xffe5;
constexpr uint16_t kProfileUuid16 = 0xffe6;
constexpr uint16_t kControlUuid16 = 0xffe7;
constexpr uint16_t kOtaUuid16 = 0xffe8;
constexpr uint16_t kGearUuid16 = 0xffe9;
constexpr uint16_t kDeviceStatusUuid16 = 0xffea;
constexpr uint16_t kMaxSpeedUuid16 = 0xffeb;
constexpr uint16_t kProfileCountUuid16 = 0xffec;
constexpr uint16_t kAutoTuneModeUuid16 = 0xffed;
constexpr uint16_t kTuneDataUuid16 = 0xffee;

const ble_uuid16_t g_svc_uuid = BLE_UUID16_INIT(kSvcUuid16);
const ble_uuid16_t g_legacy_svc_uuid = BLE_UUID16_INIT(kLegacySvcUuid16);
const ble_uuid16_t g_config_uuid = BLE_UUID16_INIT(kConfigUuid16);
const ble_uuid16_t g_state_uuid = BLE_UUID16_INIT(kStateUuid16);
const ble_uuid16_t g_audio_uuid = BLE_UUID16_INIT(kAudioUuid16);
const ble_uuid16_t g_can_uuid = BLE_UUID16_INIT(kCanUuid16);
const ble_uuid16_t g_diagnostics_uuid = BLE_UUID16_INIT(kDiagnosticsUuid16);
const ble_uuid16_t g_profile_uuid = BLE_UUID16_INIT(kProfileUuid16);
const ble_uuid16_t g_control_uuid = BLE_UUID16_INIT(kControlUuid16);
const ble_uuid16_t g_ota_uuid = BLE_UUID16_INIT(kOtaUuid16);
const ble_uuid16_t g_gear_uuid = BLE_UUID16_INIT(kGearUuid16);
const ble_uuid16_t g_device_status_uuid = BLE_UUID16_INIT(kDeviceStatusUuid16);
const ble_uuid16_t g_max_speed_uuid = BLE_UUID16_INIT(kMaxSpeedUuid16);
const ble_uuid16_t g_profile_count_uuid = BLE_UUID16_INIT(kProfileCountUuid16);
const ble_uuid16_t g_auto_tune_mode_uuid = BLE_UUID16_INIT(kAutoTuneModeUuid16);
const ble_uuid16_t g_tune_data_uuid = BLE_UUID16_INIT(kTuneDataUuid16);

constexpr std::size_t kCfgBlobLen  = 64;
constexpr std::size_t kAudioBlobLen = 32;
constexpr std::size_t kCanBlobLen = 32;
constexpr std::size_t kDiagJsonLen = 384;
constexpr std::size_t kOtaJsonLen = 512;
constexpr std::size_t kTuneDataLen = 32;

uint8_t g_own_addr_type = 0;
portMUX_TYPE g_ble_state_lock = portMUX_INITIALIZER_UNLOCKED;
portMUX_TYPE g_ble_cfg_lock   = portMUX_INITIALIZER_UNLOCKED;

domain::VehicleState g_state_snapshot{};
config::RuntimeConfig g_runtime_cfg{};
config::RuntimeConfig g_pending_cfg{};

uint8_t g_config_blob[kCfgBlobLen] = {0};
uint8_t g_audio_blob[kAudioBlobLen] = {0};
uint8_t g_can_blob[kCanBlobLen] = {0};
char g_diagnostics_json[kDiagJsonLen] = "{}";
char g_ota_json[kOtaJsonLen] = "{}";
uint8_t g_profile_id = 0;
uint8_t g_control_reg = 0;
uint8_t g_gear = 0;
uint32_t g_device_status = 0;
uint16_t g_max_speed = 180;
uint8_t g_profile_count = 5;
uint8_t g_auto_tune_mode = 0;
uint8_t g_tune_data[kTuneDataLen] = {0};
bool g_has_pending_cfg = false;

void copyString(char* dst, std::size_t dst_len, const char* src) {
    if (dst_len == 0) {
        return;
    }
    if (src == nullptr) {
        dst[0] = '\0';
        return;
    }
    std::snprintf(dst, dst_len, "%s", src);
}

bool parseJsonBool(const cJSON* item, bool& out_value) {
    if (item == nullptr) {
        return true;
    }
    if (!cJSON_IsBool(item)) {
        return false;
    }
    out_value = cJSON_IsTrue(item);
    return true;
}

bool parseJsonString(const cJSON* item, char* dst, std::size_t dst_len, bool required) {
    if (item == nullptr) {
        return !required;
    }
    if (!cJSON_IsString(item) || item->valuestring == nullptr) {
        return false;
    }
    copyString(dst, dst_len, item->valuestring);
    return true;
}

bool parseJsonStringAlias(const cJSON* primary,
                          const cJSON* secondary,
                          char* dst,
                          std::size_t dst_len,
                          bool required) {
    if (primary != nullptr) {
        return parseJsonString(primary, dst, dst_len, required);
    }
    return parseJsonString(secondary, dst, dst_len, required);
}

bool serializeOtaJson(const config::RuntimeConfig& cfg, char* dst, std::size_t dst_len) {
    cJSON* root = cJSON_CreateObject();
    if (root == nullptr) {
        return false;
    }

    cJSON_AddStringToObject(root, "ssid", cfg.wifi_ssid);
    cJSON_AddStringToObject(root, "password", cfg.wifi_password);
    cJSON_AddStringToObject(root, "ota_url", cfg.ota_url);
    cJSON_AddBoolToObject(root, "auto_check", cfg.ota_auto_check);
    cJSON_AddBoolToObject(root, "iot_enable", cfg.iot_enable);
    cJSON_AddStringToObject(root, "mqtt_uri", cfg.mqtt_uri);
    cJSON_AddStringToObject(root, "client_id", cfg.mqtt_client_id);
    cJSON_AddStringToObject(root, "mqtt_username", cfg.mqtt_username);
    cJSON_AddStringToObject(root, "mqtt_password", cfg.mqtt_password);
    cJSON_AddStringToObject(root, "topic_up", cfg.mqtt_topic_up);
    cJSON_AddStringToObject(root, "topic_down", cfg.mqtt_topic_down);
    cJSON_AddStringToObject(root, "device_id", cfg.device_id);
    cJSON_AddStringToObject(root, "product_id", cfg.product_id);

    char* json = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (json == nullptr) {
        return false;
    }

    const bool fits = std::strlen(json) < dst_len;
    if (fits) {
        std::snprintf(dst, dst_len, "%s", json);
    }
    cJSON_free(json);
    return fits;
}

bool parseOtaJson(const void* src, std::size_t len, config::RuntimeConfig& cfg) {
    if (len == 0 || len >= kOtaJsonLen) {
        return false;
    }

    char json[kOtaJsonLen] = {};
    std::memcpy(json, src, len);
    json[len] = '\0';

    cJSON* root = cJSON_Parse(json);
    if (root == nullptr) {
        return false;
    }

    const cJSON* item = cJSON_GetObjectItemCaseSensitive(root, "ssid");
    if (!parseJsonString(item, cfg.wifi_ssid, sizeof(cfg.wifi_ssid), true)) {
        cJSON_Delete(root);
        return false;
    }
    item = cJSON_GetObjectItemCaseSensitive(root, "password");
    if (!parseJsonString(item, cfg.wifi_password, sizeof(cfg.wifi_password), true)) {
        cJSON_Delete(root);
        return false;
    }
    item = cJSON_GetObjectItemCaseSensitive(root, "ota_url");
    if (!parseJsonString(item, cfg.ota_url, sizeof(cfg.ota_url), true)) {
        cJSON_Delete(root);
        return false;
    }

    bool auto_check = cfg.ota_auto_check;
    item = cJSON_GetObjectItemCaseSensitive(root, "auto_check");
    if (!parseJsonBool(item, auto_check)) {
        cJSON_Delete(root);
        return false;
    }
    cfg.ota_auto_check = auto_check;

    const cJSON* iot_enable_item = cJSON_GetObjectItemCaseSensitive(root, "iot_enable");
    if (iot_enable_item != nullptr && !parseJsonBool(iot_enable_item, cfg.iot_enable)) {
        cJSON_Delete(root);
        return false;
    }

    if (!parseJsonString(cJSON_GetObjectItemCaseSensitive(root, "mqtt_uri"),
                        cfg.mqtt_uri,
                        sizeof(cfg.mqtt_uri),
                        false) ||
        !parseJsonStringAlias(cJSON_GetObjectItemCaseSensitive(root, "client_id"),
                              cJSON_GetObjectItemCaseSensitive(root, "mqtt_client_id"),
                              cfg.mqtt_client_id,
                              sizeof(cfg.mqtt_client_id),
                              false) ||
        !parseJsonString(cJSON_GetObjectItemCaseSensitive(root, "mqtt_username"),
                        cfg.mqtt_username,
                        sizeof(cfg.mqtt_username),
                        false) ||
        !parseJsonString(cJSON_GetObjectItemCaseSensitive(root, "mqtt_password"),
                        cfg.mqtt_password,
                        sizeof(cfg.mqtt_password),
                        false) ||
        !parseJsonString(cJSON_GetObjectItemCaseSensitive(root, "topic_up"),
                        cfg.mqtt_topic_up,
                        sizeof(cfg.mqtt_topic_up),
                        false) ||
        !parseJsonString(cJSON_GetObjectItemCaseSensitive(root, "topic_down"),
                        cfg.mqtt_topic_down,
                        sizeof(cfg.mqtt_topic_down),
                        false) ||
        !parseJsonString(cJSON_GetObjectItemCaseSensitive(root, "device_id"),
                        cfg.device_id,
                        sizeof(cfg.device_id),
                        false) ||
        !parseJsonString(cJSON_GetObjectItemCaseSensitive(root, "product_id"),
                        cfg.product_id,
                        sizeof(cfg.product_id),
                        false)) {
        cJSON_Delete(root);
        return false;
    }

    cJSON_Delete(root);
    return true;
}

status::WifiState parseWifiState(const char* wifi_state) {
    if (wifi_state == nullptr) {
        return status::WifiState::Disabled;
    }
    if (std::strcmp(wifi_state, "unconfigured") == 0) {
        return status::WifiState::Unconfigured;
    }
    if (std::strcmp(wifi_state, "provisioned") == 0) {
        return status::WifiState::Provisioned;
    }
    if (std::strcmp(wifi_state, "connecting") == 0) {
        return status::WifiState::Connecting;
    }
    if (std::strcmp(wifi_state, "connected") == 0) {
        return status::WifiState::Connected;
    }
    if (std::strcmp(wifi_state, "failed") == 0) {
        return status::WifiState::Failed;
    }
    return status::WifiState::Disabled;
}

status::OtaState parseOtaState(const char* ota_result, bool ota_in_progress) {
    if (ota_in_progress) {
        if (ota_result == nullptr || std::strcmp(ota_result, "downloading") == 0) {
            return status::OtaState::Downloading;
        }
        if (std::strcmp(ota_result, "applying") == 0) {
            return status::OtaState::Applying;
        }
        return status::OtaState::Checking;
    }
    if (ota_result == nullptr) {
        return status::OtaState::Idle;
    }
    if (std::strcmp(ota_result, "success") == 0) {
        return status::OtaState::Success;
    }
    if (std::strcmp(ota_result, "failed") == 0) {
        return status::OtaState::Failed;
    }
    if (std::strcmp(ota_result, "pending") == 0) {
        return status::OtaState::Pending;
    }
    return status::OtaState::Idle;
}

bool serializeDiagnosticsJson(const status::RuntimeStatus& status, char* dst, std::size_t dst_len) {
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

    const bool fits = std::strlen(json) < dst_len;
    if (fits) {
        std::snprintf(dst, dst_len, "%s", json);
    }
    cJSON_free(json);
    return fits;
}

void syncConfigViewLocked(const config::RuntimeConfig& cfg) {
    g_runtime_cfg = cfg;
    g_profile_id = cfg.profile_index;
    if (!serializeOtaJson(cfg, g_ota_json, sizeof(g_ota_json))) {
        std::snprintf(g_ota_json, sizeof(g_ota_json), "%s", "{}");
    }
}

int chrRead(struct ble_gatt_access_ctxt* ctxt, const void* src, uint16_t len) {
    const int rc = os_mbuf_append(ctxt->om, src, len);
    return rc == 0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
}

int chrWrite(struct os_mbuf* om, uint16_t max_len, void* dst, uint16_t* out_len) {
    const uint16_t om_len = OS_MBUF_PKTLEN(om);
    if (om_len > max_len) {
        return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    }
    uint16_t copied = 0;
    const int rc = ble_hs_mbuf_to_flat(om, dst, max_len, &copied);
    if (rc != 0) {
        return BLE_ATT_ERR_UNLIKELY;
    }
    if (out_len != nullptr) {
        *out_len = copied;
    }
    return 0;
}

int chrReadState(struct ble_gatt_access_ctxt* ctxt) {
    domain::VehicleState snapshot{};
    taskENTER_CRITICAL(&g_ble_state_lock);
    snapshot = g_state_snapshot;
    taskEXIT_CRITICAL(&g_ble_state_lock);
    return chrRead(ctxt, &snapshot, sizeof(snapshot));
}

int handleOtaWrite(struct os_mbuf* om) {
    const uint16_t len = OS_MBUF_PKTLEN(om);
    if (len == 0 || len >= kOtaJsonLen) {
        return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    }

    char payload[kOtaJsonLen] = {};
    uint16_t copied = 0;
    const int rc = ble_hs_mbuf_to_flat(om, payload, sizeof(payload) - 1, &copied);
    if (rc != 0) {
        return BLE_ATT_ERR_UNLIKELY;
    }

    config::RuntimeConfig next_cfg{};
    taskENTER_CRITICAL(&g_ble_cfg_lock);
    next_cfg = g_runtime_cfg;
    taskEXIT_CRITICAL(&g_ble_cfg_lock);

    if (!parseOtaJson(payload, copied, next_cfg)) {
        return BLE_ATT_ERR_UNLIKELY;
    }

    taskENTER_CRITICAL(&g_ble_cfg_lock);
    g_pending_cfg = next_cfg;
    g_has_pending_cfg = true;
    syncConfigViewLocked(next_cfg);
    taskEXIT_CRITICAL(&g_ble_cfg_lock);
    return 0;
}

int gattAccess(uint16_t conn_handle,
               uint16_t attr_handle,
               struct ble_gatt_access_ctxt* ctxt,
               void* arg) {
    (void)conn_handle;
    (void)attr_handle;
    (void)arg;

    const ble_uuid_t* uuid = ctxt->chr->uuid;

    switch (ctxt->op) {
    case BLE_GATT_ACCESS_OP_READ_CHR:
        if (ble_uuid_cmp(uuid, &g_state_uuid.u) == 0) {
            return chrReadState(ctxt);
        }
        if (ble_uuid_cmp(uuid, &g_config_uuid.u) == 0) {
            return chrRead(ctxt, g_config_blob, sizeof(g_config_blob));
        }
        if (ble_uuid_cmp(uuid, &g_audio_uuid.u) == 0) {
            return chrRead(ctxt, g_audio_blob, sizeof(g_audio_blob));
        }
        if (ble_uuid_cmp(uuid, &g_can_uuid.u) == 0) {
            return chrRead(ctxt, g_can_blob, sizeof(g_can_blob));
        }
        if (ble_uuid_cmp(uuid, &g_diagnostics_uuid.u) == 0) {
            return chrRead(ctxt, g_diagnostics_json,
                           static_cast<uint16_t>(std::strlen(g_diagnostics_json)));
        }
        if (ble_uuid_cmp(uuid, &g_profile_uuid.u) == 0) {
            return chrRead(ctxt, &g_profile_id, sizeof(g_profile_id));
        }
        if (ble_uuid_cmp(uuid, &g_ota_uuid.u) == 0) {
            return chrRead(ctxt, g_ota_json,
                           static_cast<uint16_t>(std::strlen(g_ota_json)));
        }
        if (ble_uuid_cmp(uuid, &g_gear_uuid.u) == 0) {
            return chrRead(ctxt, &g_gear, sizeof(g_gear));
        }
        if (ble_uuid_cmp(uuid, &g_device_status_uuid.u) == 0) {
            return chrRead(ctxt, &g_device_status, sizeof(g_device_status));
        }
        if (ble_uuid_cmp(uuid, &g_max_speed_uuid.u) == 0) {
            return chrRead(ctxt, &g_max_speed, sizeof(g_max_speed));
        }
        if (ble_uuid_cmp(uuid, &g_profile_count_uuid.u) == 0) {
            return chrRead(ctxt, &g_profile_count, sizeof(g_profile_count));
        }
        if (ble_uuid_cmp(uuid, &g_auto_tune_mode_uuid.u) == 0) {
            return chrRead(ctxt, &g_auto_tune_mode, sizeof(g_auto_tune_mode));
        }
        if (ble_uuid_cmp(uuid, &g_tune_data_uuid.u) == 0) {
            return chrRead(ctxt, g_tune_data, sizeof(g_tune_data));
        }
        return BLE_ATT_ERR_UNLIKELY;

    case BLE_GATT_ACCESS_OP_WRITE_CHR:
        if (ble_uuid_cmp(uuid, &g_config_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_config_blob), g_config_blob, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_audio_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_audio_blob), g_audio_blob, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_can_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_can_blob), g_can_blob, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_profile_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_profile_id), &g_profile_id, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_control_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_control_reg), &g_control_reg, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_ota_uuid.u) == 0) {
            return handleOtaWrite(ctxt->om);
        }
        if (ble_uuid_cmp(uuid, &g_max_speed_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_max_speed), &g_max_speed, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_profile_count_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_profile_count), &g_profile_count, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_auto_tune_mode_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_auto_tune_mode), &g_auto_tune_mode, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_tune_data_uuid.u) == 0) {
            return chrWrite(ctxt->om, sizeof(g_tune_data), g_tune_data, nullptr);
        }
        return BLE_ATT_ERR_UNLIKELY;

    default:
        return BLE_ATT_ERR_UNLIKELY;
    }
}

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
const struct ble_gatt_chr_def g_prd_chr_defs[] = {
    {.uuid = &g_config_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_state_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY},
    {.uuid = &g_audio_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_can_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_diagnostics_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ},
    {.uuid = &g_profile_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_control_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_ota_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_gear_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ},
    {.uuid = &g_device_status_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY},
    {.uuid = &g_max_speed_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_profile_count_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_auto_tune_mode_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_tune_data_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {0},
};

const struct ble_gatt_chr_def g_legacy_chr_defs[] = {
    {.uuid = &g_config_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_state_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ},
    {.uuid = &g_audio_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_can_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_diagnostics_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ},
    {.uuid = &g_profile_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE},
    {.uuid = &g_control_uuid.u, .access_cb = gattAccess, .flags = BLE_GATT_CHR_F_WRITE},
    {0},
};

const struct ble_gatt_svc_def g_ble_services[] = {
    {.type = BLE_GATT_SVC_TYPE_PRIMARY, .uuid = &g_svc_uuid.u, .includes = nullptr, .characteristics = g_prd_chr_defs},
    {.type = BLE_GATT_SVC_TYPE_PRIMARY, .uuid = &g_legacy_svc_uuid.u, .includes = nullptr, .characteristics = g_legacy_chr_defs},
    {0},
};
#pragma GCC diagnostic pop

int gattSvrInit() {
    ble_svc_gap_init();
    ble_svc_gatt_init();

    int rc = ble_gatts_count_cfg(g_ble_services);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_gatts_count_cfg failed; rc=%d", rc);
        return rc;
    }
    rc = ble_gatts_add_svcs(g_ble_services);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_gatts_add_svcs failed; rc=%d", rc);
        return rc;
    }
    return 0;
}

int gapEventCb(struct ble_gap_event* event, void* arg);

void startAdvertising() {
    struct ble_hs_adv_fields fields{};
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    fields.tx_pwr_lvl_is_present = 1;
    fields.tx_pwr_lvl = BLE_HS_ADV_TX_PWR_LVL_AUTO;

    const char* name = ble_svc_gap_device_name();
    fields.name = reinterpret_cast<uint8_t*>(const_cast<char*>(name));
    fields.name_len = static_cast<uint8_t>(std::strlen(name));
    fields.name_is_complete = 1;

    ble_uuid16_t uuids16[2] = {
        BLE_UUID16_INIT(kSvcUuid16),
        BLE_UUID16_INIT(kLegacySvcUuid16),
    };
    fields.uuids16 = uuids16;
    fields.num_uuids16 = 2;
    fields.uuids16_is_complete = 1;

    int rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_gap_adv_set_fields failed; rc=%d", rc);
        return;
    }

    struct ble_gap_adv_params adv_params{};
    adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;
    rc = ble_gap_adv_start(g_own_addr_type, nullptr, BLE_HS_FOREVER,
                           &adv_params, gapEventCb, nullptr);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_gap_adv_start failed; rc=%d", rc);
        return;
    }
    ESP_LOGI(kTag, "advertising as '%s' (services fff0 + ffe0)", name);
}

int gapEventCb(struct ble_gap_event* event, void* arg) {
    (void)arg;
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        ESP_LOGI(kTag, "GAP connect; status=%d", event->connect.status);
        if (event->connect.status != 0) {
            startAdvertising();
        }
        return 0;
    case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGI(kTag, "GAP disconnect; reason=%d", event->disconnect.reason);
        startAdvertising();
        return 0;
    case BLE_GAP_EVENT_ADV_COMPLETE:
        ESP_LOGI(kTag, "advertise complete; reason=%d", event->adv_complete.reason);
        startAdvertising();
        return 0;
    default:
        return 0;
    }
}

void onHostSync() {
    int rc = ble_hs_util_ensure_addr(0);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_hs_util_ensure_addr failed; rc=%d", rc);
        return;
    }
    rc = ble_hs_id_infer_auto(0, &g_own_addr_type);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_hs_id_infer_auto failed; rc=%d", rc);
        return;
    }
    startAdvertising();
}

void onHostReset(int reason) {
    ESP_LOGW(kTag, "NimBLE host reset; reason=%d", reason);
}

void nimbleHostTask(void* param) {
    (void)param;
    ESP_LOGI(kTag, "NimBLE host task started");
    nimble_port_run();
    nimble_port_freertos_deinit();
}

}  // namespace

namespace ble {

int BleService::gatt_svr_cb(uint16_t conn_handle,
                            uint16_t attr_handle,
                            struct ble_gatt_access_ctxt* ctxt,
                            void* arg) {
    return gattAccess(conn_handle, attr_handle, ctxt, arg);
}

bool BleService::begin() {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    if (ret != ESP_OK) {
        ESP_LOGE(kTag, "nvs_flash_init failed; err=0x%x", ret);
        return false;
    }

    ret = nimble_port_init();
    if (ret != ESP_OK) {
        ESP_LOGE(kTag, "nimble_port_init failed; err=0x%x", ret);
        return false;
    }

    ble_hs_cfg.sync_cb = onHostSync;
    ble_hs_cfg.reset_cb = onHostReset;
    ble_hs_cfg.store_status_cb = ble_store_util_status_rr;

    if (gattSvrInit() != 0) {
        ESP_LOGE(kTag, "gattSvrInit failed");
        return false;
    }

    const int rc = ble_svc_gap_device_name_set(kDeviceName);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_svc_gap_device_name_set failed; rc=%d", rc);
        return false;
    }

    nimble_port_freertos_init(nimbleHostTask);

    started_ = true;
    ESP_LOGI(kTag, "BleService started (NimBLE GATT fff0 + ffe0 compatibility)");
    return true;
}

void BleService::seedRuntimeConfig(const config::RuntimeConfig& cfg) {
    taskENTER_CRITICAL(&g_ble_cfg_lock);
    syncConfigViewLocked(cfg);
    taskEXIT_CRITICAL(&g_ble_cfg_lock);
}

bool BleService::takePendingRuntimeConfig(config::RuntimeConfig& cfg) {
    taskENTER_CRITICAL(&g_ble_cfg_lock);
    if (!g_has_pending_cfg) {
        taskEXIT_CRITICAL(&g_ble_cfg_lock);
        return false;
    }
    cfg = g_pending_cfg;
    g_has_pending_cfg = false;
    taskEXIT_CRITICAL(&g_ble_cfg_lock);
    return true;
}

void BleService::publishVehicleState(const domain::VehicleState& state) {
    taskENTER_CRITICAL(&g_ble_state_lock);
    g_state_snapshot = state;
    taskEXIT_CRITICAL(&g_ble_state_lock);
}

void BleService::publishRuntimeStatus(const status::RuntimeStatus& status) {
    taskENTER_CRITICAL(&g_ble_cfg_lock);
    if (!serializeDiagnosticsJson(status, g_diagnostics_json, sizeof(g_diagnostics_json))) {
        std::snprintf(g_diagnostics_json, sizeof(g_diagnostics_json), "%s", "{}");
    }
    taskEXIT_CRITICAL(&g_ble_cfg_lock);
}

void BleService::publishOtaStatus(const ota::OtaStatus& status) {
    status::RuntimeStatus normalized{};
    copyString(normalized.version, sizeof(normalized.version), status.version);
    copyString(normalized.partition, sizeof(normalized.partition), status.partition);
    normalized.wifi_state = parseWifiState(status.wifi_state);
    normalized.ota_state = parseOtaState(status.ota_last_result, status.ota_in_progress);
    if (std::strcmp(status.ota_last_result, "success") == 0) {
        copyString(normalized.ota_last_result, sizeof(normalized.ota_last_result), status.ota_last_result);
    } else if (std::strcmp(status.ota_last_result, "failed") == 0) {
        copyString(normalized.ota_last_result, sizeof(normalized.ota_last_result), status.ota_last_result);
    } else if (std::strlen(status.ota_last_result) != 0) {
        copyString(normalized.ota_last_result, sizeof(normalized.ota_last_result), status.ota_last_result);
    }
    copyString(normalized.last_error, sizeof(normalized.last_error), status.last_error);
    normalized.iot_state = status::IotState::Disabled;
    normalized.device_status_bits = 0;
    normalized.ota_progress_pct = status.ota_in_progress ? 50u : 0u;
    publishRuntimeStatus(normalized);
}

void BleService::publishDeviceStatus(std::uint32_t status) {
    taskENTER_CRITICAL(&g_ble_cfg_lock);
    g_device_status = status;
    taskEXIT_CRITICAL(&g_ble_cfg_lock);
}

}  // namespace ble
