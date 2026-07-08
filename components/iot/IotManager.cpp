#include "iot/IotManager.h"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "cJSON.h"
#include "esp_log.h"
#include "mqtt_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/portmacro.h"
#include "freertos/task.h"

namespace {

constexpr const char* kTag = "iot";
constexpr int kIotDownPayloadMax = 512;

struct DownState {
    char topic[kIotDownPayloadMax + 1]{};
    char payload[kIotDownPayloadMax + 1]{};
    std::uint32_t payload_len = 0;
    bool overflow = false;
    bool in_progress = false;
};

config::RuntimeConfig g_cfg{};
status::RuntimeStatus g_status{};
esp_mqtt_client_handle_t g_client = nullptr;
ota::OtaRequest g_pending_request{};
bool g_has_pending_request = false;
DownState g_down_state{};
portMUX_TYPE g_status_lock = portMUX_INITIALIZER_UNLOCKED;
portMUX_TYPE g_cfg_lock = portMUX_INITIALIZER_UNLOCKED;
portMUX_TYPE g_req_lock = portMUX_INITIALIZER_UNLOCKED;
bool g_started = false;

void copyString(char* dst, std::size_t dst_len, const char* src) {
    if (dst_len == 0) {
        return;
    }
    if (src == nullptr) {
        dst[0] = '\0';
        return;
    }
    snprintf(dst, dst_len, "%s", src);
}

std::size_t boundedStrlen(const char* s, std::size_t max_len) {
    if (s == nullptr || max_len == 0) {
        return 0;
    }
    std::size_t len = 0;
    while (len < max_len && s[len] != '\0') {
        ++len;
    }
    return len;
}

void setIotState(status::IotState state, const char* last_error = nullptr) {
    taskENTER_CRITICAL(&g_status_lock);
    g_status.iot_state = state;
    if (last_error != nullptr) {
        copyString(g_status.last_error, sizeof(g_status.last_error), last_error);
    }
    taskEXIT_CRITICAL(&g_status_lock);
}

bool publishStatusPayload(const char* topic, const char* payload, std::size_t payload_len = 0) {
    if (g_client == nullptr) {
        return false;
    }
    if (topic == nullptr || topic[0] == '\0') {
        return false;
    }

    int result = 0;
    if (payload_len != 0) {
        result = esp_mqtt_client_publish(g_client, topic, payload, payload_len, 1, 0);
    } else {
        result = esp_mqtt_client_publish(g_client, topic, payload, 0, 1, 0);
    }
    return result >= 0;
}

bool mqttCloudReady() {
    taskENTER_CRITICAL(&g_status_lock);
    const bool ready = g_status.iot_state == status::IotState::Cloud;
    taskEXIT_CRITICAL(&g_status_lock);
    return ready;
}

bool iotConnectionConfigChanged(const config::RuntimeConfig& old_cfg,
                                const config::RuntimeConfig& new_cfg) {
    return old_cfg.iot_enable != new_cfg.iot_enable
           || std::strcmp(old_cfg.mqtt_uri, new_cfg.mqtt_uri) != 0
           || std::strcmp(old_cfg.mqtt_client_id, new_cfg.mqtt_client_id) != 0
           || std::strcmp(old_cfg.mqtt_username, new_cfg.mqtt_username) != 0
           || std::strcmp(old_cfg.mqtt_password, new_cfg.mqtt_password) != 0
           || std::strcmp(old_cfg.mqtt_topic_up, new_cfg.mqtt_topic_up) != 0
           || std::strcmp(old_cfg.mqtt_topic_down, new_cfg.mqtt_topic_down) != 0;
}

bool parseInteger(cJSON* value, int& out) {
    if (value == nullptr || !cJSON_IsNumber(value)) {
        return false;
    }
    out = static_cast<int>(value->valuedouble);
    return true;
}

bool publishAck(int command_id, const char* method, int code) {
    cJSON* root = cJSON_CreateObject();
    if (root == nullptr) {
        return false;
    }

    cJSON_AddNumberToObject(root, "id", command_id);
    cJSON_AddStringToObject(root, "method", method == nullptr ? "" : method);
    cJSON_AddNumberToObject(root, "code", code);

    char* text = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (text == nullptr) {
        return false;
    }

    const bool ok = publishStatusPayload(g_cfg.mqtt_topic_up, text, std::strlen(text));
    cJSON_free(text);
    return ok;
}

bool parseOtaStartCommand(const char* payload,
                          std::size_t len,
                          int& command_id,
                          ota::OtaRequest& request,
                          char* ack_method,
                          std::size_t ack_method_len) {
    cJSON* root = cJSON_ParseWithLength(payload, len);
    if (root == nullptr) {
        publishAck(command_id, "ota_start", -4001);
        return false;
    }

    cJSON* id_item = cJSON_GetObjectItemCaseSensitive(root, "id");
    if (!parseInteger(id_item, command_id)) {
        cJSON_Delete(root);
        publishAck(-1, "ota_start", -4004);
        return false;
    }

    const cJSON* method = cJSON_GetObjectItemCaseSensitive(root, "method");
    if (!cJSON_IsString(method) || method->valuestring == nullptr) {
        cJSON_Delete(root);
        publishAck(command_id, "ota_start", -4004);
        return false;
    }
    copyString(ack_method, ack_method_len, method->valuestring);

    if (std::strcmp(method->valuestring, "ota_start") != 0) {
        cJSON_Delete(root);
        publishAck(command_id, method->valuestring, -4004);
        return false;
    }

    const cJSON* params = cJSON_GetObjectItemCaseSensitive(root, "params");
    if (!cJSON_IsObject(params)) {
        cJSON_Delete(root);
        publishAck(command_id, "ota_start", -4001);
        return false;
    }

    const cJSON* url = cJSON_GetObjectItemCaseSensitive(params, "url");
    const cJSON* version = cJSON_GetObjectItemCaseSensitive(params, "firmware_version");
    const cJSON* length = cJSON_GetObjectItemCaseSensitive(params, "file_length");
    const cJSON* md5 = cJSON_GetObjectItemCaseSensitive(params, "md5");

    if (!cJSON_IsString(url) || url->valuestring == nullptr || url->valuestring[0] == '\0') {
        cJSON_Delete(root);
        publishAck(command_id, "ota_start", -4001);
        return false;
    }

    std::size_t url_len = boundedStrlen(url->valuestring, sizeof(request.url));
    if (url_len == 0 || url_len >= sizeof(request.url)) {
        cJSON_Delete(root);
        publishAck(command_id, "ota_start", -4001);
        return false;
    }
    std::memcpy(request.url, url->valuestring, url_len + 1);

    if (cJSON_IsString(version) && version->valuestring != nullptr) {
        std::size_t version_len = boundedStrlen(version->valuestring, sizeof(request.version));
        if (version_len >= sizeof(request.version)) {
            cJSON_Delete(root);
            publishAck(command_id, "ota_start", -4001);
            return false;
        }
        std::memcpy(request.version, version->valuestring, version_len + 1);
    } else {
        request.version[0] = '\0';
    }

    if (cJSON_IsNumber(length)) {
        request.file_size = static_cast<std::uint32_t>(length->valuedouble);
    } else {
        request.file_size = 0;
    }

    if (cJSON_IsString(md5) && md5->valuestring != nullptr) {
        std::size_t md5_len = boundedStrlen(md5->valuestring, sizeof(request.md5));
        if (md5_len >= sizeof(request.md5)) {
            cJSON_Delete(root);
            publishAck(command_id, "ota_start", -4001);
            return false;
        }
        std::memcpy(request.md5, md5->valuestring, md5_len + 1);
    } else {
        request.md5[0] = '\0';
    }

    request.trigger = ota::OtaTrigger::CloudCommand;
    cJSON_Delete(root);
    return true;
}

void mqttEventHandler(void* handler_args, esp_event_base_t base, int32_t event_id, void* event_data) {
    (void)handler_args;

    (void)base;
    if (event_data == nullptr) {
        return;
    }

    esp_mqtt_event_handle_t event = static_cast<esp_mqtt_event_handle_t>(event_data);
    if (event == nullptr) {
        return;
    }

    switch (event->event_id) {
    case MQTT_EVENT_CONNECTED:
        setIotState(status::IotState::Cloud, "");
        if (g_cfg.mqtt_topic_down[0] != '\0') {
            esp_mqtt_client_subscribe(g_client, g_cfg.mqtt_topic_down, 1);
        }
        return;

    case MQTT_EVENT_DISCONNECTED:
        setIotState(status::IotState::Offline, "mqtt disconnected");
        return;

    case MQTT_EVENT_DATA: {
        if (g_cfg.mqtt_topic_down[0] == '\0' || event->topic == nullptr) {
            return;
        }

        if (event->topic_len != std::strlen(g_cfg.mqtt_topic_down)
            || std::strncmp(event->topic, g_cfg.mqtt_topic_down, event->topic_len) != 0) {
            return;
        }

        if (event->total_data_len > kIotDownPayloadMax) {
            setIotState(status::IotState::Failed, "down payload too large");
            return;
        }

        const bool is_single = event->current_data_offset + event->data_len >= event->total_data_len;

        if (!g_down_state.in_progress) {
            std::memset(&g_down_state, 0, sizeof(g_down_state));
            g_down_state.in_progress = true;
            g_down_state.payload_len = 0;
            g_down_state.overflow = false;
        }

        if (event->current_data_offset + event->data_len <= kIotDownPayloadMax) {
            std::memcpy(g_down_state.payload + g_down_state.payload_len,
                        event->data,
                        static_cast<std::size_t>(event->data_len));
            g_down_state.payload_len += static_cast<std::uint32_t>(event->data_len);
        } else {
            g_down_state.overflow = true;
        }

        if (!is_single) {
            return;
        }

        g_down_state.in_progress = false;

        if (g_down_state.overflow) {
            setIotState(status::IotState::Failed, "down payload overflow");
            return;
        }

        g_down_state.payload[g_down_state.payload_len] = '\0';

        int command_id = 0;
        char method[32] = {};
        ota::OtaRequest request{};
        if (!parseOtaStartCommand(g_down_state.payload,
                                  g_down_state.payload_len,
                                  command_id,
                                  request,
                                  method,
                                  sizeof(method))) {
            return;
        }

        request.trigger = ota::OtaTrigger::CloudCommand;
        bool accepted = false;
        taskENTER_CRITICAL(&g_req_lock);
        if (!g_has_pending_request) {
            g_pending_request = request;
            g_has_pending_request = true;
            accepted = true;
        }
        taskEXIT_CRITICAL(&g_req_lock);

        publishAck(command_id, method, accepted ? 0 : -4000);
        return;
    }

    default:
        return;
    }
}

}  // namespace

namespace iot {

bool IotManager::begin() {
    setIotState(status::IotState::Disabled, "");
    g_status.iot_state = status::IotState::Disabled;
    return true;
}

void IotManager::seedConfig(const config::RuntimeConfig& cfg) {
    bool connection_changed = false;
    taskENTER_CRITICAL(&g_cfg_lock);
    connection_changed = iotConnectionConfigChanged(g_cfg, cfg);
    g_cfg = cfg;
    taskEXIT_CRITICAL(&g_cfg_lock);

    if (connection_changed && g_started) {
        stop();
    }

    const bool ready = config::iotConfigReady(cfg);
    setIotState(ready ? status::IotState::Offline : status::IotState::Disabled);
}

void IotManager::startIfConfigured() {
    if (g_started) {
        if (!config::iotConfigReady(g_cfg) && g_client != nullptr) {
            stop();
        }
        return;
    }

    if (!config::iotConfigReady(g_cfg)) {
        return;
    }

    esp_mqtt_client_config_t mqtt_cfg{};
    mqtt_cfg.broker.address.uri = g_cfg.mqtt_uri;
    mqtt_cfg.credentials.client_id = g_cfg.mqtt_client_id;
    mqtt_cfg.credentials.username = g_cfg.mqtt_username;
    mqtt_cfg.credentials.authentication.password = g_cfg.mqtt_password;
    mqtt_cfg.session.disable_clean_session = false;
    mqtt_cfg.network.disable_auto_reconnect = false;
    mqtt_cfg.network.reconnect_timeout_ms = 3000;

    g_client = esp_mqtt_client_init(&mqtt_cfg);
    if (g_client == nullptr) {
        setIotState(status::IotState::Failed, "mqtt init failed");
        return;
    }

    if (esp_mqtt_client_register_event(g_client,
                                      MQTT_EVENT_ANY,
                                      mqttEventHandler,
                                      this) != ESP_OK) {
        esp_mqtt_client_destroy(g_client);
        g_client = nullptr;
        setIotState(status::IotState::Failed, "mqtt register event failed");
        return;
    }

    if (esp_mqtt_client_start(g_client) != ESP_OK) {
        esp_mqtt_client_destroy(g_client);
        g_client = nullptr;
        setIotState(status::IotState::Failed, "mqtt start failed");
        return;
    }

    g_started = true;
    setIotState(status::IotState::Connecting, "");
}

void IotManager::stop() {
    if (g_client != nullptr) {
        esp_mqtt_client_stop(g_client);
        esp_mqtt_client_destroy(g_client);
        g_client = nullptr;
    }
    g_started = false;
    setIotState(status::IotState::Offline, "");
}

void IotManager::publishJsonToUp(const char* payload, std::size_t len) {
    if (payload == nullptr) {
        return;
    }
    if (!config::iotConfigReady(g_cfg) || !mqttCloudReady()) {
        return;
    }

    if (!publishStatusPayload(g_cfg.mqtt_topic_up,
                             payload,
                             len == 0 ? std::strlen(payload) : len)) {
        setIotState(status::IotState::Failed, "publish to cloud failed");
    }
}

void IotManager::publishPayload(const status::RuntimeStatus& status) {
    cJSON* root = cJSON_CreateObject();
    if (root == nullptr) {
        return;
    }

    cJSON_AddStringToObject(root, "type", "ota_progress");
    cJSON_AddStringToObject(root, "wifi_state", status::toString(status.wifi_state));
    cJSON_AddStringToObject(root, "iot_state", status::toString(status.iot_state));
    cJSON_AddStringToObject(root, "ota_state", status::toString(status.ota_state));
    cJSON_AddNumberToObject(root, "ota_progress", status.ota_progress_pct);
    cJSON_AddStringToObject(root, "ota_last_result", status.ota_last_result);

    char* text = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (text == nullptr) {
        return;
    }

    publishJsonToUp(text, 0);
    cJSON_free(text);
}

void IotManager::publishDeviceInfo(const status::RuntimeStatus& status) {
    cJSON* root = cJSON_CreateObject();
    if (root == nullptr) {
        return;
    }

    cJSON_AddStringToObject(root, "type", "device_info");
    cJSON_AddStringToObject(root, "version", status.version);
    cJSON_AddStringToObject(root, "partition", status.partition);
    cJSON_AddStringToObject(root, "wifi_state", status::toString(status.wifi_state));
    cJSON_AddStringToObject(root, "iot_state", status::toString(status.iot_state));
    cJSON_AddStringToObject(root, "ota_state", status::toString(status.ota_state));

    const char* device_id = (g_cfg.device_id[0] != '\0') ? g_cfg.device_id : "tesla-vico";
    const char* product_id = (g_cfg.product_id[0] != '\0') ? g_cfg.product_id : "tesla-vico";
    cJSON_AddStringToObject(root, "device_id", device_id);
    cJSON_AddStringToObject(root, "product_id", product_id);

    char* text = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (text == nullptr) {
        return;
    }

    publishJsonToUp(text, 0);
    cJSON_free(text);
}

void IotManager::publishVehicleState(const domain::VehicleState& state) {
    cJSON* root = cJSON_CreateObject();
    if (root == nullptr) {
        return;
    }

    cJSON_AddStringToObject(root, "type", "vehicle_state");
    cJSON_AddNumberToObject(root, "speed_kph", state.speed_kph);
    cJSON_AddNumberToObject(root, "throttle", state.throttle);
    cJSON_AddNumberToObject(root, "rpm", state.virtual_rpm);
    cJSON_AddBoolToObject(root, "can_valid", state.can_valid);
    cJSON_AddBoolToObject(root, "overspeed_mute", state.overspeed_mute);

    char* text = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (text == nullptr) {
        return;
    }

    publishJsonToUp(text, 0);
    cJSON_free(text);
}

void IotManager::publishOtaProgress(const status::RuntimeStatus& status) {
    publishPayload(status);
}

bool IotManager::takePendingOtaRequest(ota::OtaRequest& out) {
    taskENTER_CRITICAL(&g_req_lock);
    if (!g_has_pending_request) {
        taskEXIT_CRITICAL(&g_req_lock);
        return false;
    }
    out = g_pending_request;
    g_has_pending_request = false;
    taskEXIT_CRITICAL(&g_req_lock);
    return true;
}

void IotManager::copyStatus(status::RuntimeStatus& out) const {
    taskENTER_CRITICAL(&g_status_lock);
    out = g_status;
    taskEXIT_CRITICAL(&g_status_lock);
}

}  // namespace iot
