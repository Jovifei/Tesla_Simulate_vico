#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "config/pin_map.h"

static const char* TAG = "main";

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

    int level = 1;
    while (true) {
        gpio_set_level(config::pins::LED_PWR, level);
        ESP_LOGI(TAG, "heartbeat led=%d", level);
        level = !level;
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
