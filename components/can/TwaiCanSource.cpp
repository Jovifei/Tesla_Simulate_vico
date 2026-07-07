#include "can/TwaiCanSource.h"

#include "esp_log.h"

static constexpr const char* TAG = "twai-can";

namespace can {

bool TwaiCanSource::begin() {
    // Drive CAN_RS low → high-speed mode (listen-only filter on the transceiver)
    gpio_config_t rs_cfg = {};
    rs_cfg.pin_bit_mask = (1ULL << config::pins::CAN_RS);
    rs_cfg.mode = GPIO_MODE_OUTPUT;
    rs_cfg.pull_up_en = GPIO_PULLUP_DISABLE;
    rs_cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
    rs_cfg.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&rs_cfg);
    gpio_set_level(config::pins::CAN_RS, 0);

    // TWAI driver configuration — listen-only, 500 kbit/s
    g_config_ = TWAI_GENERAL_CONFIG_DEFAULT(config::pins::CAN_TX,
                                              config::pins::CAN_RX,
                                              TWAI_MODE_LISTEN_ONLY);
    t_config_ = TWAI_TIMING_CONFIG_500KBITS();
    f_config_ = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    esp_err_t err = twai_driver_install(&g_config_, &t_config_, &f_config_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "twai_driver_install failed: %s", esp_err_to_name(err));
        return false;
    }

    err = twai_start();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "twai_start failed: %s", esp_err_to_name(err));
        twai_driver_uninstall();
        return false;
    }

    installed_ = true;
    ESP_LOGI(TAG, "TWAI driver started (listen-only, 500 kbit/s)");
    return true;
}

bool TwaiCanSource::poll(domain::VehicleState& state) {
    if (!installed_) {
        return false;
    }

    twai_message_t frame;
    esp_err_t err = twai_receive(&frame, 0);  // non-blocking

    if (err != ESP_OK) {
        return false;
    }

    if (frame.identifier == 0x256) {
        state.speed_kph = parseSpeed(frame.data, frame.data_length_code);
    } else if (frame.identifier == 0x116) {
        state.throttle = parseTorque(frame.data, frame.data_length_code);
    }

    state.can_valid = true;
    return true;
}

}  // namespace can
