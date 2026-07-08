#include "ui/Ws2812Led.h"

#include "esp_log.h"
#include "driver/rmt_tx.h"
#include "driver/rmt_encoder.h"

#include "config/pin_map.h"

namespace ui {

namespace {
constexpr char kTag[]         = "Ws2812Led";
constexpr std::uint32_t kResolutionHz = 10 * 1000 * 1000;  // 10 MHz, 0.1 us tick

// WS2812 bit timings expressed in 0.1 us ticks.
// T0H=0.3us T0L=0.9us  T1H=0.9us T1L=0.3us
const rmt_symbol_word_t kBit0 = {
    .duration0 = 3, .level0 = 1, .duration1 = 9, .level1 = 0,
};
const rmt_symbol_word_t kBit1 = {
    .duration0 = 9, .level0 = 1, .duration1 = 3, .level1 = 0,
};
}  // namespace

bool Ws2812Led::begin() {
    rmt_tx_channel_config_t tx_cfg = {};
    tx_cfg.gpio_num          = config::pins::WS_DATA;
    tx_cfg.clk_src           = RMT_CLK_SRC_DEFAULT;
    tx_cfg.resolution_hz     = kResolutionHz;
    tx_cfg.mem_block_symbols = 64;
    tx_cfg.trans_queue_depth = 4;

    rmt_channel_handle_t ch = nullptr;
    esp_err_t err = rmt_new_tx_channel(&tx_cfg, &ch);
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "rmt_new_tx_channel failed: %s", esp_err_to_name(err));
        ready_ = false;
        return false;
    }

    rmt_bytes_encoder_config_t enc_cfg = {};
    enc_cfg.bit0 = kBit0;
    enc_cfg.bit1 = kBit1;
    enc_cfg.flags.msb_first = 1;

    rmt_encoder_handle_t enc = nullptr;
    err = rmt_new_bytes_encoder(&enc_cfg, &enc);
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "rmt_new_bytes_encoder failed: %s", esp_err_to_name(err));
        rmt_del_channel(ch);
        ready_ = false;
        return false;
    }

    err = rmt_enable(ch);
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "rmt_enable failed: %s", esp_err_to_name(err));
        rmt_del_encoder(enc);
        rmt_del_channel(ch);
        ready_ = false;
        return false;
    }

    channel_ = static_cast<void*>(ch);
    encoder_ = static_cast<void*>(enc);
    ready_   = true;
    ESP_LOGI(kTag, "WS2812 ready (GPIO%d)", config::pins::WS_DATA);
    return true;
}

void Ws2812Led::set_color(std::uint8_t r, std::uint8_t g, std::uint8_t b) {
    if (!ready_ || channel_ == nullptr || encoder_ == nullptr) {
        ESP_LOGI(kTag, "set_color(%u,%u,%u) [not ready]", r, g, b);
        return;
    }

    // WS2812 wire order is GRB.
    const std::uint8_t grb[3] = {g, r, b};

    rmt_transmit_config_t tx = {};
    tx.loop_count = 0;

    auto ch  = static_cast<rmt_channel_handle_t>(channel_);
    auto enc = static_cast<rmt_encoder_handle_t>(encoder_);

    esp_err_t err = rmt_transmit(ch, enc, grb, sizeof(grb), &tx);
    if (err != ESP_OK) {
        ESP_LOGW(kTag, "rmt_transmit failed: %s", esp_err_to_name(err));
        return;
    }
    rmt_tx_wait_all_done(ch, 50);
}

void Ws2812Led::set(Status status) {
    switch (status) {
        case Status::Booting: set_color(0, 0, 64);   break;  // blue
        case Status::Running: set_color(0, 64, 0);   break;  // green
        case Status::Muted:   set_color(64, 40, 0);  break;  // amber
        case Status::Fault:   set_color(64, 0, 0);   break;  // red
    }
}

}  // namespace ui
