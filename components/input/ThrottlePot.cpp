#include "input/ThrottlePot.h"

#include <algorithm>

#include "esp_log.h"
#include "esp_adc/adc_oneshot.h"

namespace input {

namespace {
constexpr char  kTag[]       = "ThrottlePot";
constexpr float kEmaAlpha    = 0.2f;
constexpr float kAdcFullScale = 4095.0f;   // 12-bit
constexpr adc_channel_t kChannel = ADC_CHANNEL_0;  // GPIO1 on ESP32-S3
}  // namespace

bool ThrottlePot::begin() {
    adc_oneshot_unit_handle_t unit = nullptr;
    adc_oneshot_unit_init_cfg_t unit_cfg = {};
    unit_cfg.unit_id = ADC_UNIT_1;

    esp_err_t err = adc_oneshot_new_unit(&unit_cfg, &unit);
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "adc_oneshot_new_unit failed: %s", esp_err_to_name(err));
        ready_ = false;
        return false;
    }

    adc_oneshot_chan_cfg_t chan_cfg = {};
    chan_cfg.atten    = ADC_ATTEN_DB_12;
    chan_cfg.bitwidth = ADC_BITWIDTH_12;

    err = adc_oneshot_config_channel(unit, kChannel, &chan_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "adc_oneshot_config_channel failed: %s",
                 esp_err_to_name(err));
        adc_oneshot_del_unit(unit);
        ready_ = false;
        return false;
    }

    handle_ = static_cast<void*>(unit);
    ready_  = true;
    seeded_ = false;
    ESP_LOGI(kTag, "throttle pot ready (ADC1 ch0)");
    return true;
}

float ThrottlePot::read() {
    if (!ready_ || handle_ == nullptr) {
        return 0.0f;
    }

    auto unit = static_cast<adc_oneshot_unit_handle_t>(handle_);
    int raw = 0;
    if (adc_oneshot_read(unit, kChannel, &raw) != ESP_OK) {
        return ema_;
    }

    float norm = static_cast<float>(raw) / kAdcFullScale;
    norm = std::max(0.0f, std::min(norm, 1.0f));

    if (!seeded_) {
        ema_    = norm;
        seeded_ = true;
    } else {
        ema_ = (kEmaAlpha * norm) + ((1.0f - kEmaAlpha) * ema_);
    }
    return std::max(0.0f, std::min(ema_, 1.0f));
}

}  // namespace input
