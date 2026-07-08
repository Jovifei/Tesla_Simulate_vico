#include "ota/OtaManager.h"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "esp_app_desc.h"
#include "esp_err.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/portmacro.h"
#include "freertos/task.h"

namespace {

constexpr const char* kTag = "ota";
constexpr int kTaskStackWords = 8192;
constexpr UBaseType_t kTaskPriority = 5;
constexpr int kOtaConnectTimeoutMs = 30000;
constexpr EventBits_t kBitRequest = BIT0;

// ESP-IDF component `json` embeds cJSON symbols.
constexpr const char kRootCertPem[] = R"(
-----BEGIN CERTIFICATE-----
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
BzAChipodHRwOi8vY3R0LmlzZWFyY2gub3JnLzANBgkqhkiG9w0BAQsFAAOCAgEAQzA5
M+zP4h6AsVzTdDEr1xgG+ZpVbpsuRWpu9X6lzNN2O0oSbYqZ0qKXqQyV2pAonyz1K3iA
24kTx5cDIe8JD7BqXc9E+u6KDAdAm8YGtS+wGGyRyvE4s46HoPazTA/gkGEXLJJLLq5y
4rI6VOGGAaHo9dZYkTfLZNVVRFl1kYyqS/fWznuaCG2l9VmOAXoJ1i8LojRxurx8Wc58
g3z7jH9MuNoMNFc13JUO2c+hJ1ytY1/6V2vNhbbX6YsJhBKt3vnDnN/SUXOcDSBx/OVC
XbkqVKgf/mBlC9ZwTe74MkRUYw35vj0IadB1iKsFcEYJIyaKOA1NVuMcZV8K4D4ew3E8
3YKHyCuXapnwXCfJOLLmObAun1vDLteA94ppIqhzyapMI2vlA38nSxrdbidKfnUSsfx8
bVsgcuyo6edSxnl2xe50Tzw9uQWGWpZKaYG1ChcxrFAxo0xO+ogzAm8h1Hn0pVITQW2N
1srO2Qd6hw2yB9H9n1tFoZT3zh0+BTtPlqvGjufH6G+jD/adJzi10BGSAdoo6gWQK/B
ImQxGc1dQc5sKXc5teLoI0lp4rWuHwoMvVJE9idh+NROm4tW7x1YgnSUZXoqBYwygJyI
QtdgQXl3k5ufADG7n2AFD+a83H8XTur2qxGn8pY=
-----END CERTIFICATE-----
)";

status::RuntimeStatus g_status{};
ota::OtaRequest g_request{};
bool g_has_request = false;
bool g_running = false;
bool g_task_started = false;
EventGroupHandle_t g_events = nullptr;
TaskHandle_t g_task_handle = nullptr;
portMUX_TYPE g_status_lock = portMUX_INITIALIZER_UNLOCKED;

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

void setRuntimeVersionFromRunningImage() {
    const esp_app_desc_t* app_desc = esp_app_get_description();
    const esp_partition_t* running = esp_ota_get_running_partition();
    if (app_desc == nullptr || running == nullptr) {
        return;
    }

    taskENTER_CRITICAL(&g_status_lock);
    copyString(g_status.version, sizeof(g_status.version), app_desc->version);
    copyString(g_status.partition, sizeof(g_status.partition), running->label);
    taskEXIT_CRITICAL(&g_status_lock);
}

void setOtaStatus(status::OtaState state,
                  const char* result,
                  const char* error,
                  std::uint8_t progress) {
    taskENTER_CRITICAL(&g_status_lock);
    g_status.ota_state = state;
    if (result != nullptr) {
        copyString(g_status.ota_last_result, sizeof(g_status.ota_last_result), result);
    }
    if (error != nullptr) {
        copyString(g_status.last_error, sizeof(g_status.last_error), error);
    }
    g_status.ota_progress_pct = progress;
    taskEXIT_CRITICAL(&g_status_lock);
}

bool awaitNetworkConnectivity(std::uint32_t timeout_ms) {
    const TickType_t start = xTaskGetTickCount();
    const TickType_t timeout_ticks = pdMS_TO_TICKS(timeout_ms);

    wifi_ap_record_t station_info{};
    while ((xTaskGetTickCount() - start) < timeout_ticks) {
        if (esp_wifi_sta_get_ap_info(&station_info) == ESP_OK) {
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }
    return false;
}

bool markOldImageValidIfNeeded() {
    const esp_partition_t* running = esp_ota_get_running_partition();
    if (running == nullptr) {
        return false;
    }
    esp_ota_img_states_t state = ESP_OTA_IMG_UNDEFINED;
    const esp_err_t err = esp_ota_get_state_partition(running, &state);
    if (err != ESP_OK || state != ESP_OTA_IMG_PENDING_VERIFY) {
        return false;
    }
    return esp_ota_mark_app_valid_cancel_rollback() == ESP_OK;
}

bool runHttpsOta(const ota::OtaRequest& request) {
    if (!awaitNetworkConnectivity(kOtaConnectTimeoutMs)) {
        setOtaStatus(status::OtaState::Failed, "failed", "wifi not connected", 0);
        return false;
    }

    esp_http_client_config_t http_config{};
    http_config.url = request.url;
    http_config.cert_pem = kRootCertPem;
    http_config.keep_alive_enable = true;
    http_config.timeout_ms = 15000;

    esp_https_ota_config_t ota_config{};
    ota_config.http_config = &http_config;

    setOtaStatus(status::OtaState::Checking, "checking", nullptr, 0);
    esp_https_ota_handle_t ota_handle = nullptr;
    const esp_err_t begin_err = esp_https_ota_begin(&ota_config, &ota_handle);
    if (begin_err != ESP_OK) {
        setOtaStatus(status::OtaState::Failed, "failed", "ota begin failed", 0);
        ESP_LOGE(kTag, "esp_https_ota_begin failed: %s", esp_err_to_name(begin_err));
        return false;
    }

    esp_app_desc_t img_desc{};
    if (esp_https_ota_get_img_desc(ota_handle, &img_desc) == ESP_OK) {
        taskENTER_CRITICAL(&g_status_lock);
        copyString(g_status.version, sizeof(g_status.version), img_desc.version);
        taskEXIT_CRITICAL(&g_status_lock);

        if (request.version[0] != '\0' && std::strcmp(request.version, img_desc.version) != 0) {
            setOtaStatus(status::OtaState::Failed, "failed", "ota version mismatch", 0);
            esp_https_ota_abort(ota_handle);
            return false;
        }
    }

    while (true) {
        const esp_err_t perform_err = esp_https_ota_perform(ota_handle);
        if (perform_err == ESP_ERR_HTTPS_OTA_IN_PROGRESS) {
            const int total = esp_https_ota_get_image_size(ota_handle);
            const int loaded = esp_https_ota_get_image_len_read(ota_handle);
            if (total > 0) {
                const std::uint8_t pct = static_cast<std::uint8_t>(
                    (static_cast<std::uint32_t>(loaded) * 100u) / static_cast<std::uint32_t>(total));
                setOtaStatus(status::OtaState::Downloading,
                             "downloading",
                             nullptr,
                             pct);
            }
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }

        if (perform_err != ESP_OK) {
            const int http_code = esp_https_ota_get_status_code(ota_handle);
            if (http_code > 0) {
                char err_msg[56]{};
                snprintf(err_msg, sizeof(err_msg), "ota download failed (%d)", http_code);
                setOtaStatus(status::OtaState::Failed, "failed", err_msg, 0);
            } else {
                setOtaStatus(status::OtaState::Failed,
                             "failed",
                             esp_err_to_name(perform_err),
                             0);
            }
            esp_https_ota_abort(ota_handle);
            return false;
        }

        setOtaStatus(status::OtaState::Applying, "applying", nullptr, 95);
        const int loaded = esp_https_ota_get_image_len_read(ota_handle);
        if (request.file_size != 0 && loaded != static_cast<int>(request.file_size)) {
            setOtaStatus(status::OtaState::Failed, "failed", "ota size mismatch", 0);
            esp_https_ota_abort(ota_handle);
            return false;
        }

        const esp_err_t finish_err = esp_https_ota_finish(ota_handle);
        if (finish_err == ESP_OK) {
            setOtaStatus(status::OtaState::Success, "success", nullptr, 100);
            vTaskDelay(pdMS_TO_TICKS(500));
            esp_restart();
            return true;
        }

        const char* finish_err_text = esp_err_to_name(finish_err);
        setOtaStatus(status::OtaState::Failed,
                     "failed",
                     finish_err_text != nullptr ? finish_err_text : "ota finish failed",
                     0);
        ESP_LOGE(kTag, "esp_https_ota_finish failed: %s", finish_err_text);
        break;
    }

    esp_https_ota_abort(ota_handle);
    return false;
}

void otaTask(void*) {
    while (true) {
        const EventBits_t bits = xEventGroupWaitBits(g_events,
                                                     kBitRequest,
                                                     pdTRUE,
                                                     pdFALSE,
                                                     portMAX_DELAY);
        if ((bits & kBitRequest) == 0) {
            continue;
        }

        ota::OtaRequest request{};
        bool has_request = false;

        taskENTER_CRITICAL(&g_status_lock);
        if (!g_running && g_has_request) {
            request = g_request;
            g_running = true;
            g_has_request = false;
            has_request = true;
        }
        taskEXIT_CRITICAL(&g_status_lock);

        if (!has_request) {
            taskENTER_CRITICAL(&g_status_lock);
            g_running = false;
            taskEXIT_CRITICAL(&g_status_lock);
            continue;
        }

        setRuntimeVersionFromRunningImage();
        setOtaStatus(status::OtaState::Pending, "pending", "", 0);
        (void)runHttpsOta(request);

        taskENTER_CRITICAL(&g_status_lock);
        g_running = false;
        taskEXIT_CRITICAL(&g_status_lock);
    }
}

void startOtaTask() {
    if (g_task_started) {
        return;
    }

    if (xTaskCreate(&otaTask,
                    "ota_task",
                    kTaskStackWords,
                    nullptr,
                    kTaskPriority,
                    &g_task_handle) != pdPASS) {
        ESP_LOGE(kTag, "failed to create ota task");
        setOtaStatus(status::OtaState::Failed, "failed", "ota task create failed", 0);
        return;
    }

    g_task_started = true;
}

}  // namespace

namespace ota {

bool OtaManager::begin() {
    setRuntimeVersionFromRunningImage();
    markOldImageValidIfNeeded();
    setOtaStatus(status::OtaState::Idle, "idle", nullptr, 0);

    if (g_events == nullptr) {
        g_events = xEventGroupCreate();
        if (g_events == nullptr) {
            setOtaStatus(status::OtaState::Failed, "failed", "ota event create failed", 0);
            return false;
        }
    }

    startOtaTask();
    return g_task_started;
}

bool OtaManager::startIfConfigured(const config::RuntimeConfig& cfg) {
    if (!cfg.ota_auto_check) {
        return false;
    }
    if (!config::otaConfigReady(cfg)) {
        return false;
    }

    ota::OtaRequest request{};
    copyString(request.url, sizeof(request.url), cfg.ota_url);
    request.trigger = OtaTrigger::BootConfig;
    request.version[0] = '\0';
    request.md5[0] = '\0';
    request.file_size = 0;
    return requestOta_(request);
}

bool OtaManager::request(const OtaRequest& request) {
    return requestOta_(request);
}

bool OtaManager::requestOta_(const OtaRequest& request) {
    if (request.url[0] == '\0') {
        setOtaStatus(status::OtaState::Failed, "failed", "request url empty", 0);
        return false;
    }

    bool accepted = false;
    taskENTER_CRITICAL(&g_status_lock);
    if (!g_running && !g_has_request) {
        g_request = request;
        g_has_request = true;
        accepted = true;
    }
    taskEXIT_CRITICAL(&g_status_lock);

    if (!accepted) {
        setOtaStatus(status::OtaState::Failed, "failed", "ota already running", 0);
        return false;
    }

    setOtaStatus(status::OtaState::Pending, "pending", "", 0);

    if (g_events != nullptr) {
        xEventGroupSetBits(g_events, kBitRequest);
        return true;
    }

    setOtaStatus(status::OtaState::Failed, "failed", "ota events missing", 0);
    return false;
}

bool OtaManager::running() const {
    taskENTER_CRITICAL(&g_status_lock);
    const bool running = g_running;
    taskEXIT_CRITICAL(&g_status_lock);
    return running;
}

void OtaManager::copyStatus(status::RuntimeStatus& out) const {
    taskENTER_CRITICAL(&g_status_lock);
    out = g_status;
    taskEXIT_CRITICAL(&g_status_lock);
}

void OtaManager::copyStatus(OtaStatus& out) const {
    status::RuntimeStatus status_snapshot{};
    copyStatus(status_snapshot);

    snprintf(out.version, sizeof(out.version), "%s", status_snapshot.version);
    snprintf(out.partition, sizeof(out.partition), "%s", status_snapshot.partition);
    snprintf(out.wifi_state,
                  sizeof(out.wifi_state),
                  "%s",
                  status::toString(status_snapshot.wifi_state));
    snprintf(out.ota_last_result,
                  sizeof(out.ota_last_result),
                  "%s",
                  status_snapshot.ota_last_result);
    snprintf(out.last_error,
                  sizeof(out.last_error),
                  "%s",
                  status_snapshot.last_error);
    out.ota_in_progress = status_snapshot.ota_state == status::OtaState::Pending
                           || status_snapshot.ota_state == status::OtaState::Checking
                           || status_snapshot.ota_state == status::OtaState::Downloading
                           || status_snapshot.ota_state == status::OtaState::Applying;
}

}  // namespace ota
