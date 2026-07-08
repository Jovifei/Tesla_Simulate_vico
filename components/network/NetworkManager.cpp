#include "network/NetworkManager.h"

#include <cstddef>
#include <cstdint>
#include <cstring>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/portmacro.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"

namespace {

constexpr const char* kTag = "network";

constexpr EventBits_t kBitConfigured = BIT0;
constexpr EventBits_t kBitConnected = BIT1;
constexpr EventBits_t kBitFailed = BIT2;
constexpr EventBits_t kBitReconnect = BIT3;
constexpr EventBits_t kBitStop = BIT4;

constexpr int kNetworkTaskStackWords = 4096;
constexpr UBaseType_t kNetworkTaskPriority = 4;
constexpr int kWifiMaxRetries = 5;
constexpr int kConnectWaitMs = 30000;

config::RuntimeConfig g_cfg{};
status::RuntimeStatus g_status{};
EventGroupHandle_t g_events = nullptr;
esp_netif_t* g_wifi_netif = nullptr;
TaskHandle_t g_task_handle = nullptr;
portMUX_TYPE g_status_lock = portMUX_INITIALIZER_UNLOCKED;
portMUX_TYPE g_cfg_lock = portMUX_INITIALIZER_UNLOCKED;
bool g_handlers_registered = false;
bool g_stack_ready = false;
std::uint8_t g_retry_count = 0;

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

void updateStatus(status::WifiState state, const char* error = nullptr) {
    taskENTER_CRITICAL(&g_status_lock);
    g_status.wifi_state = state;
    if (error != nullptr) {
        copyString(g_status.last_error, sizeof(g_status.last_error), error);
    }
    taskEXIT_CRITICAL(&g_status_lock);
}

void setStatusBits(EventBits_t set_bits, EventBits_t clear_bits = 0) {
    if (g_events == nullptr) {
        return;
    }
    if (set_bits != 0) {
        xEventGroupSetBits(g_events, set_bits);
    }
    if (clear_bits != 0) {
        xEventGroupClearBits(g_events, clear_bits);
    }
}

bool ensureEvents() {
    if (g_events != nullptr) {
        return true;
    }
    g_events = xEventGroupCreate();
    if (g_events == nullptr) {
        updateStatus(status::WifiState::Failed, "network event group create failed");
        return false;
    }
    return true;
}

void ensureStackReady() {
    if (g_stack_ready) {
        return;
    }

    const esp_err_t netif_err = esp_netif_init();
    if (netif_err != ESP_OK && netif_err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(kTag, "esp_netif_init failed: %s", esp_err_to_name(netif_err));
        updateStatus(status::WifiState::Failed, "esp_netif_init failed");
        return;
    }

    const esp_err_t loop_err = esp_event_loop_create_default();
    if (loop_err != ESP_OK && loop_err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(kTag, "esp_event_loop_create_default failed: %s", esp_err_to_name(loop_err));
        updateStatus(status::WifiState::Failed, "event loop init failed");
        return;
    }

    if (g_wifi_netif == nullptr) {
        g_wifi_netif = esp_netif_create_default_wifi_sta();
        if (g_wifi_netif == nullptr) {
            updateStatus(status::WifiState::Failed, "create wifi netif failed");
            return;
        }
    }

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    const esp_err_t wifi_err = esp_wifi_init(&init_cfg);
    if (wifi_err != ESP_OK && wifi_err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(kTag, "esp_wifi_init failed: %s", esp_err_to_name(wifi_err));
        updateStatus(status::WifiState::Failed, "wifi init failed");
        return;
    }

    g_stack_ready = true;
}

void onNetworkEvent(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data) {
    (void)arg;
    (void)event_data;

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
        updateStatus(status::WifiState::Connecting);
        setStatusBits(0, kBitFailed);
        return;
    }

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if ((xEventGroupGetBits(g_events) & kBitStop) != 0) {
            return;
        }

        if (g_retry_count < kWifiMaxRetries) {
            ++g_retry_count;
            updateStatus(status::WifiState::Connecting, "reconnecting");
            esp_wifi_connect();
            return;
        }

        updateStatus(status::WifiState::Failed, "wifi connect failed");
        setStatusBits(kBitFailed, kBitConnected);
        return;
    }

    if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        g_retry_count = 0;
        updateStatus(status::WifiState::Connected);
        setStatusBits(kBitConnected, kBitFailed);
    }
}

void taskConnectOrWaitForConfig(config::RuntimeConfig snapshot_cfg) {
    if (!config::wifiConfigReady(snapshot_cfg)) {
        setStatusBits(0, kBitConnected | kBitFailed);
        updateStatus(status::WifiState::Unconfigured);
        setStatusBits(0, kBitConfigured);
        return;
    }

    setStatusBits(kBitConfigured, 0);
    setStatusBits(0, kBitConnected | kBitFailed);
    g_retry_count = 0;
    ensureStackReady();
    if (!g_stack_ready) {
        return;
    }

    wifi_config_t wifi_cfg{};
    const std::size_t ssid_len = boundedStrlen(snapshot_cfg.wifi_ssid, sizeof(wifi_cfg.sta.ssid));
    const std::size_t pwd_len = boundedStrlen(snapshot_cfg.wifi_password, sizeof(wifi_cfg.sta.password));
    if (ssid_len >= sizeof(wifi_cfg.sta.ssid) || pwd_len >= sizeof(wifi_cfg.sta.password)) {
        updateStatus(status::WifiState::Failed, "wifi credential too long");
        return;
    }

    std::memcpy(wifi_cfg.sta.ssid, snapshot_cfg.wifi_ssid, ssid_len + 1);
    std::memcpy(wifi_cfg.sta.password, snapshot_cfg.wifi_password, pwd_len + 1);
    wifi_cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    wifi_cfg.sta.pmf_cfg.capable = true;
    wifi_cfg.sta.pmf_cfg.required = false;

    esp_wifi_disconnect();
    esp_wifi_stop();

    if (esp_wifi_set_mode(WIFI_MODE_STA) != ESP_OK
        || esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg) != ESP_OK
        || esp_wifi_start() != ESP_OK) {
        updateStatus(status::WifiState::Failed, "wifi setup failed");
        return;
    }

    updateStatus(status::WifiState::Connecting);
    const EventBits_t bits = xEventGroupWaitBits(
        g_events,
        kBitConnected | kBitFailed,
        pdFALSE,
        pdFALSE,
        pdMS_TO_TICKS(kConnectWaitMs));

    if ((bits & kBitConnected) == 0) {
        updateStatus(status::WifiState::Failed, "wifi connect timeout");
        setStatusBits(kBitFailed, 0);
    }
}

void networkTask(void* /*param*/) {
    while (true) {
        const EventBits_t bits = xEventGroupWaitBits(
            g_events,
            kBitReconnect | kBitStop,
            pdTRUE,
            pdFALSE,
            pdMS_TO_TICKS(250));

        if ((bits & kBitStop) != 0) {
            esp_wifi_disconnect();
            esp_wifi_stop();
            setStatusBits(0, kBitConnected | kBitFailed);
            updateStatus(status::WifiState::Disabled, "");
            continue;
        }

        if ((bits & kBitReconnect) == 0) {
            continue;
        }

        config::RuntimeConfig snapshot{};
        taskENTER_CRITICAL(&g_cfg_lock);
        snapshot = g_cfg;
        taskEXIT_CRITICAL(&g_cfg_lock);
        if (!config::wifiConfigReady(snapshot)) {
            setStatusBits(0, kBitConfigured | kBitConnected | kBitFailed);
            updateStatus(status::WifiState::Unconfigured, "");
            continue;
        }

        taskConnectOrWaitForConfig(snapshot);
    }
}

}  // namespace

namespace network {

bool NetworkManager::begin() {
    if (!ensureEvents()) {
        return false;
    }

    ensureStackReady();
    if (!g_stack_ready) {
        return false;
    }

    if (!g_handlers_registered) {
        const esp_err_t wifi_rc = esp_event_handler_register(WIFI_EVENT,
                                                            ESP_EVENT_ANY_ID,
                                                            &onNetworkEvent,
                                                            nullptr);
        if (wifi_rc != ESP_OK && wifi_rc != ESP_ERR_INVALID_ARG) {
            ESP_LOGE(kTag, "register WIFI_EVENT handler failed: %s", esp_err_to_name(wifi_rc));
            return false;
        }
        const esp_err_t ip_rc = esp_event_handler_register(IP_EVENT,
                                                          IP_EVENT_STA_GOT_IP,
                                                          &onNetworkEvent,
                                                          nullptr);
        if (ip_rc != ESP_OK && ip_rc != ESP_ERR_INVALID_ARG) {
            ESP_LOGE(kTag, "register IP_EVENT handler failed: %s", esp_err_to_name(ip_rc));
            return false;
        }
        g_handlers_registered = true;
    }

    if (g_task_handle == nullptr) {
        if (xTaskCreate(&networkTask,
                        "network_mgr",
                        kNetworkTaskStackWords,
                        nullptr,
                        kNetworkTaskPriority,
                        &g_task_handle) != pdPASS) {
            updateStatus(status::WifiState::Failed, "network task create failed");
            return false;
        }
    }

    updateStatus(status::WifiState::Disabled, "");
    setStatusBits(0, kBitConfigured | kBitConnected | kBitFailed);
    return true;
}

void NetworkManager::seedConfig(const config::RuntimeConfig& cfg) {
    bool wifi_changed = false;
    taskENTER_CRITICAL(&g_cfg_lock);
    wifi_changed = std::strcmp(g_cfg.wifi_ssid, cfg.wifi_ssid) != 0
                   || std::strcmp(g_cfg.wifi_password, cfg.wifi_password) != 0;
    g_cfg = cfg;
    taskEXIT_CRITICAL(&g_cfg_lock);

    const bool configured = config::wifiConfigReady(cfg);
    EventBits_t clear_bits = configured ? 0 : (kBitConfigured | kBitConnected | kBitFailed | kBitReconnect);
    if (wifi_changed) {
        clear_bits |= kBitConnected | kBitFailed | kBitReconnect | kBitStop;
    }
    setStatusBits(configured ? kBitConfigured : 0, clear_bits);
    updateStatus(configured ? status::WifiState::Provisioned
                           : status::WifiState::Unconfigured);
}

void NetworkManager::startIfConfigured() {
    const EventBits_t current_bits = (g_events == nullptr) ? 0u : xEventGroupGetBits(g_events);
    if ((current_bits & kBitStop) != 0) {
        return;
    }
    if (current_bits & kBitConnected) {
        return;
    }
    if (current_bits & kBitReconnect) {
        return;
    }
    if (current_bits & kBitFailed) {
        return;
    }

    taskENTER_CRITICAL(&g_cfg_lock);
    const bool ready = config::wifiConfigReady(g_cfg);
    taskEXIT_CRITICAL(&g_cfg_lock);
    if (!ready) {
        return;
    }
    setStatusBits(kBitReconnect, 0);
}

void NetworkManager::requestReconnect() {
    taskENTER_CRITICAL(&g_cfg_lock);
    const bool ready = config::wifiConfigReady(g_cfg);
    taskEXIT_CRITICAL(&g_cfg_lock);
    if (!ready) {
        return;
    }
    setStatusBits(kBitReconnect, kBitConnected | kBitFailed | kBitStop);
}

void NetworkManager::requestStop() {
    setStatusBits(kBitStop, 0);
    setStatusBits(0, kBitReconnect);
}

void NetworkManager::copyStatus(status::RuntimeStatus& out) const {
    taskENTER_CRITICAL(&g_status_lock);
    out = g_status;
    taskEXIT_CRITICAL(&g_status_lock);
}

bool NetworkManager::connected() const {
    if (g_events == nullptr) {
        return false;
    }
    return (xEventGroupGetBits(g_events) & kBitConnected) != 0;
}

EventGroupHandle_t NetworkManager::eventGroup() const {
    return g_events;
}

}  // namespace network
