#include "input/Encoder.h"

#include "esp_log.h"
#include "esp_timer.h"

#include "config/pin_map.h"

namespace input {

namespace {
constexpr char kTag[] = "Encoder";
constexpr std::int64_t kDebounceUs = 20 * 1000;  // 20 ms

// Quadrature transition table indexed by (prev<<2 | cur): -1, 0, +1.
constexpr int kTable[16] = {
    0, -1, +1, 0,
    +1, 0, 0, -1,
    -1, 0, 0, +1,
    0, +1, -1, 0,
};
}  // namespace

int Encoder::readState() {
    const int clk = gpio_get_level(config::pins::ENC_CLK);
    const int dt  = gpio_get_level(config::pins::ENC_DT);
    return (clk << 1) | dt;
}

bool Encoder::begin() {
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << config::pins::ENC_CLK)
                    | (1ULL << config::pins::ENC_DT);
    io.mode         = GPIO_MODE_INPUT;
    io.pull_up_en   = GPIO_PULLUP_ENABLE;
    io.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io.intr_type    = GPIO_INTR_DISABLE;

    const esp_err_t err = gpio_config(&io);
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "gpio_config failed: %s", esp_err_to_name(err));
        ready_ = false;
        return false;
    }

    prev_state_   = static_cast<std::uint8_t>(readState());
    accum_        = 0;
    last_edge_us_ = esp_timer_get_time();
    ready_        = true;
    ESP_LOGI(kTag, "encoder ready (CLK=%d DT=%d)",
             config::pins::ENC_CLK, config::pins::ENC_DT);
    return true;
}

int Encoder::poll() {
    if (!ready_) {
        return 0;
    }

    const std::uint8_t cur = static_cast<std::uint8_t>(readState());
    if (cur == prev_state_) {
        return 0;
    }

    const std::int64_t now = esp_timer_get_time();
    if (now - last_edge_us_ < kDebounceUs) {
        prev_state_ = cur;
        return 0;
    }
    last_edge_us_ = now;

    accum_ += kTable[(prev_state_ << 2) | cur];
    prev_state_ = cur;

    int detents = 0;
    while (accum_ >= 4)  { detents += 1; accum_ -= 4; }
    while (accum_ <= -4) { detents -= 1; accum_ += 4; }
    return detents;
}

}  // namespace input
