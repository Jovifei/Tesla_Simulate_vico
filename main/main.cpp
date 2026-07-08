#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "config/pin_map.h"
#include "app/App.h"

static const char* TAG = "main";

static app::App app_instance;

extern "C" void app_main(void)
{
    gpio_config_t io_conf = {};
    io_conf.pin_bit_mask = (1ULL << config::pins::LED_PWR);
    io_conf.mode         = GPIO_MODE_OUTPUT;
    io_conf.pull_up_en   = GPIO_PULLUP_DISABLE;
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.intr_type    = GPIO_INTR_DISABLE;
    gpio_config(&io_conf);

    ESP_LOGI(TAG, "Tesla Simulate Vico boot - ESP-IDF v5.3");

    const bool app_ok = app_instance.begin();
    ESP_LOGI(TAG, "app.begin() = %s", app_ok ? "OK" : "FAIL");

    constexpr int kLoopDelayMs = 25;
    constexpr int kHeartbeatIntervalMs = 1000;

    int level = 1;
    int heartbeat_elapsed_ms = 0;
    while (true) {
        app_instance.tick();
        heartbeat_elapsed_ms += kLoopDelayMs;
        if (heartbeat_elapsed_ms >= kHeartbeatIntervalMs) {
            heartbeat_elapsed_ms -= kHeartbeatIntervalMs;
            gpio_set_level(config::pins::LED_PWR, level);
            ESP_LOGI(TAG, "heartbeat led=%d", level);
            level = !level;
        }
        vTaskDelay(pdMS_TO_TICKS(kLoopDelayMs));
    }
}
