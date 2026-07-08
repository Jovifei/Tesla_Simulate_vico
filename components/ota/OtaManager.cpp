#include "ota/OtaManager.h"

#include <cstdio>
#include <cstdint>
#include <cstring>

#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "freertos/portmacro.h"

namespace {

constexpr const char* kTag = "ota";
constexpr EventBits_t kWifiConnectedBit = BIT0;
constexpr EventBits_t kWifiFailedBit    = BIT1;
constexpr int kWifiMaxRetries           = 5;
constexpr int kWifiConnectTimeoutMs     = 30000;
constexpr int kOtaTaskStackWords        = 8192;

portMUX_TYPE g_ota_lock = portMUX_INITIALIZER_UNLOCKED;
ota::OtaStatus g_status{};
config::RuntimeConfig g_cfg{};
EventGroupHandle_t g_wifi_events = nullptr;
esp_netif_t* g_wifi_sta_netif = nullptr;
bool g_wifi_handlers_registered = false;
int g_wifi_retry_count = 0;

// ISRG Root X1, commonly used by HTTPS endpoints behind Let's Encrypt.
constexpr const char kOtaRootCertPem[] = R"(-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgISA5tm0X7Zg8+Uo1O1Yz5lJQ6HMA0GCSqGSIb3DQEBCwUAMHwx
CzAJBgNVBAYTAlVTMRMwEQYDVQQKEwpJbnRlcm5ldCBTZWN1cml0eSBSZXNlYXJjaCBH
cm91cDEUMBIGA1UECxMLaXNlYXJjaC5vcmcxJTAjBgNVBAMTHElTUkcgUm9vdCBYMSBQ
ZW1pc3Npb24gQ0EgMTAeFw0yMTA1MDQxNjAwMDBaFw0zNTA5MTUxNjAwMDBaME8xCzAJ
BgNVBAYTAlVTMRMwEQYDVQQKEwpJbnRlcm5ldCBTZWN1cml0eSBSZXNlYXJjaCBHcm91
cDErMCkGA1UEAxMiSVNSRyBSb290IFgxIFNlcnZlciBDQSBTaWduZXIgQ0EgMFkwEwYH
KoZIzj0CAQYIKoZIzj0DAQcDQgAEW4wuyR3r7I4fA4n5Vf3L7hIwrKyYVJZZzKzbwQ6V
eR4V6kRDeo63eVUsVTNff7kwh28ykVfoCEN0z7LxyzKDn5Xxh6OCAXowggF2MA4GA1Ud
DwEB/wQEAwIBhjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBTTJxL8fzjsEtC5nIof
RwSEopgI0jAfBgNVHSMEGDAWgBTd/7E0dPfYZ7R6pujISiFDUFxIrjA0BggrBgEFBQcB
AQQoMCYwJAYIKwYBBQUHMAGGGGh0dHA6Ly9vY3NwLmlzZWFyY2gub3JnMDIGCCsGAQUF
BzAChipodHRwOi8vY3J0LmlzZWFyY2gub3JnLzANBgkqhkiG9w0BAQsFAAOCAgEAQzA5
M+zP4h6AsVzTdDEr1xgG+ZpVbpsuRWpu9X6lzNN2O0oSbYqZ0qKXqQyV2pAonyz1K3iA
24kTx5cDIe8JD7BqXc9E+u6KDAdAm8YGtS+wGGyRyvE4s46HoPazTA/gkGEXLJJLLq5y
4rI6VOGGAaHo9dZYkTfLZNVVRFl1kYyqS/fWznuaCG2l9VmOAXoJ1i8LojRxurx8Wc58
g3z7jH9MuNoMNFc13JUO2c+hJ1ytY1/6V2vNhbbX6YsJhBKt3vnDnN/SUXOcDSBx/OVC
XbkqVKgf/mBlC9ZwTe74MkRUYw35vj0IadB1iKsFcEYJIyaKOA1NVuMcZV8K4D4ew3E8
3YKHyCuXapnwXCfJOLLmObAun1vDLteA94ppIqhzyapMI2vlA38nSxrdbidKfnUSsfx8
bVsgcuyo6edSxnl2xe50Tzw9uQWGWpZKaYG1ChcxrFAxo0xO+ogzAm8h1Hn0pVITQW2N
1srO2Qd6hw2yYB9H9n1tFoZT3zh0+BTtPlqvGjufH6G+jD/adJzi10BGSAdoo6gWQK/B
ImQxGc1dQc5sKXc5teLoI0lp4rWuHwoMvVJE9idh+NROm4tW7x1YgnSUZXoqBYwygJyI
QtdgQXl3k5ufADG7n2AFD+a83H8XTur2qxGn8pY=
-----END CERTIFICATE-----)";

void copyString(char* dst, std::size_t dst_len, const char* src) {
    if (dst_len == 0) {
        return;
    }
    if (src == nullptr) {
        dst[0] = '\0';
        return;
    }

    std::size_t i = 0;
    for (; i + 1 < dst_len && src[i] != '\0'; ++i) {
        dst[i] = src[i];
    }
    dst[i] = '\0';
}

void copyWifiField(std::uint8_t* dst, std::size_t dst_len, const char* src) {
    if (dst == nullptr || dst_len == 0) {
        return;
    }

    std::memset(dst, 0, dst_len);
    if (src == nullptr) {
        return;
    }

    std::size_t i = 0;
    for (; i < dst_len && src[i] != '\0'; ++i) {
        dst[i] = static_cast<std::uint8_t>(src[i]);
    }
}

void setStatusStrings(const char* wifi_state,
                      const char* ota_result,
                      const char* last_error,
                      bool ota_in_progress) {
    taskENTER_CRITICAL(&g_ota_lock);
    if (wifi_state != nullptr) {
        copyString(g_status.wifi_state, sizeof(g_status.wifi_state), wifi_state);
    }
    if (ota_result != nullptr) {
        copyString(g_status.ota_last_result, sizeof(g_status.ota_last_result), ota_result);
    }
    if (last_error != nullptr) {
        copyString(g_status.last_error, sizeof(g_status.last_error), last_error);
    }
    g_status.ota_in_progress = ota_in_progress;
    taskEXIT_CRITICAL(&g_ota_lock);
}

void refreshImageMetadata() {
    const esp_app_desc_t* app_desc = esp_app_get_description();
    const esp_partition_t* running = esp_ota_get_running_partition();

    taskENTER_CRITICAL(&g_ota_lock);
    copyString(g_status.version, sizeof(g_status.version), app_desc->version);
    copyString(g_status.partition, sizeof(g_status.partition), running != nullptr ? running->label : "unknown");
    taskEXIT_CRITICAL(&g_ota_lock);
}

void confirmRunningImageIfNeeded() {
    const esp_partition_t* running = esp_ota_get_running_partition();
    if (running == nullptr) {
        return;
    }

    esp_ota_img_states_t state = ESP_OTA_IMG_UNDEFINED;
    if (esp_ota_get_state_partition(running, &state) == ESP_OK &&
        state == ESP_OTA_IMG_PENDING_VERIFY) {
        const esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();
        if (err == ESP_OK) {
            ESP_LOGI(kTag, "marked running OTA image as valid");
        } else {
            ESP_LOGW(kTag, "esp_ota_mark_app_valid_cancel_rollback failed: %s",
                     esp_err_to_name(err));
        }
    }
}

void wifiEventHandler(void* arg,
                      esp_event_base_t event_base,
                      int32_t event_id,
                      void* event_data) {
    (void)arg;
    (void)event_data;

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
        setStatusStrings("connecting", "pending", "", true);
        return;
    }

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (g_wifi_retry_count < kWifiMaxRetries) {
            ++g_wifi_retry_count;
            esp_wifi_connect();
            setStatusStrings("connecting", "pending", "", true);
        } else {
            xEventGroupSetBits(g_wifi_events, kWifiFailedBit);
            setStatusStrings("failed", "failed", "wifi connect failed", false);
        }
        return;
    }

    if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        g_wifi_retry_count = 0;
        xEventGroupSetBits(g_wifi_events, kWifiConnectedBit);
        setStatusStrings("connected", "pending", "", true);
    }
}

bool ensureWifiStackReady() {
    esp_err_t err = esp_netif_init();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(kTag, "esp_netif_init failed: %s", esp_err_to_name(err));
        return false;
    }

    err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(kTag, "esp_event_loop_create_default failed: %s", esp_err_to_name(err));
        return false;
    }

    if (g_wifi_sta_netif == nullptr) {
        g_wifi_sta_netif = esp_netif_create_default_wifi_sta();
    }

    wifi_init_config_t wifi_init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    err = esp_wifi_init(&wifi_init_cfg);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(kTag, "esp_wifi_init failed: %s", esp_err_to_name(err));
        return false;
    }

    if (!g_wifi_handlers_registered) {
        ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifiEventHandler, nullptr));
        ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifiEventHandler, nullptr));
        g_wifi_handlers_registered = true;
    }

    if (g_wifi_events == nullptr) {
        g_wifi_events = xEventGroupCreate();
        if (g_wifi_events == nullptr) {
            ESP_LOGE(kTag, "xEventGroupCreate failed");
            return false;
        }
    }

    return true;
}

bool connectWifi() {
    if (!ensureWifiStackReady()) {
        return false;
    }

    xEventGroupClearBits(g_wifi_events, kWifiConnectedBit | kWifiFailedBit);
    g_wifi_retry_count = 0;

    wifi_config_t wifi_cfg = {};
    copyWifiField(wifi_cfg.sta.ssid, sizeof(wifi_cfg.sta.ssid), g_cfg.wifi_ssid);
    copyWifiField(wifi_cfg.sta.password, sizeof(wifi_cfg.sta.password), g_cfg.wifi_password);
    wifi_cfg.sta.threshold.authmode = WIFI_AUTH_OPEN;
    wifi_cfg.sta.pmf_cfg.capable = true;
    wifi_cfg.sta.pmf_cfg.required = false;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg));
    ESP_ERROR_CHECK(esp_wifi_start());

    const EventBits_t bits = xEventGroupWaitBits(
        g_wifi_events,
        kWifiConnectedBit | kWifiFailedBit,
        pdTRUE,
        pdFALSE,
        pdMS_TO_TICKS(kWifiConnectTimeoutMs));

    if ((bits & kWifiConnectedBit) != 0) {
        return true;
    }

    setStatusStrings("failed", "failed", "wifi connect timeout", false);
    return false;
}

void runHttpsOta() {
    esp_http_client_config_t http_cfg = {};
    http_cfg.url = g_cfg.ota_url;
    http_cfg.cert_pem = kOtaRootCertPem;
    http_cfg.timeout_ms = 15000;
    http_cfg.keep_alive_enable = true;

    esp_https_ota_config_t ota_cfg = {};
    ota_cfg.http_config = &http_cfg;

    setStatusStrings("connected", "in_progress", "", true);
    const esp_err_t err = esp_https_ota(&ota_cfg);
    if (err == ESP_OK) {
        setStatusStrings("connected", "success", "", false);
        ESP_LOGI(kTag, "OTA applied successfully, restarting");
        vTaskDelay(pdMS_TO_TICKS(500));
        esp_restart();
        return;
    }

    setStatusStrings("connected", "failed", esp_err_to_name(err), false);
    ESP_LOGE(kTag, "esp_https_ota failed: %s", esp_err_to_name(err));
}

void otaTask(void* param) {
    (void)param;

    if (!config::otaConfigReady(g_cfg)) {
        setStatusStrings("disabled", "skipped", "ota config incomplete", false);
        vTaskDelete(nullptr);
        return;
    }

    if (!connectWifi()) {
        vTaskDelete(nullptr);
        return;
    }

    runHttpsOta();
    vTaskDelete(nullptr);
}

}  // namespace

namespace ota {

bool OtaManager::begin() {
    refreshImageMetadata();
    confirmRunningImageIfNeeded();
    setStatusStrings("idle", "idle", "", false);
    return true;
}

void OtaManager::startIfConfigured(const config::RuntimeConfig& cfg) {
    if (started_ || !cfg.ota_auto_check) {
        return;
    }

    taskENTER_CRITICAL(&g_ota_lock);
    g_cfg = cfg;
    taskEXIT_CRITICAL(&g_ota_lock);

    TaskHandle_t task = nullptr;
    const BaseType_t ok = xTaskCreate(&otaTask, "ota_task", kOtaTaskStackWords, nullptr, 5, &task);
    if (ok != pdPASS) {
        setStatusStrings("disabled", "failed", "ota task create failed", false);
        return;
    }

    started_ = true;
}

void OtaManager::copyStatus(OtaStatus& out) const {
    taskENTER_CRITICAL(&g_ota_lock);
    out = g_status;
    taskEXIT_CRITICAL(&g_ota_lock);
}

}  // namespace ota
