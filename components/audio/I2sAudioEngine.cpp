#include "audio/I2sAudioEngine.h"

#include "audio/AudioVolume.h"
#include "esp_log.h"

#include <cmath>
#include <cstring>

namespace audio {

namespace {
constexpr const char* TAG = "I2sAudioEngine";
constexpr float TWO_PI = 2.0f * static_cast<float>(M_PI);
}  // namespace

bool I2sAudioEngine::begin() {
    i2s_chan_config_t chan_cfg =
        I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    if (i2s_new_channel(&chan_cfg, &tx_chan_, nullptr) != ESP_OK) {
        ESP_LOGE(TAG, "i2s_new_channel failed");
        return false;
    }

    i2s_std_config_t std_cfg = {};
    // I2S_STD_CLK_DEFAULT_CONFIG (ESP-IDF v5.3) omits the optional
    // ext_clk_freq_hz field; silence its -Wmissing-field-initializers.
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
    std_cfg.clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE);
#pragma GCC diagnostic pop
    std_cfg.slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(
                           I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
    std_cfg.gpio_cfg.mclk = I2S_GPIO_UNUSED;
    std_cfg.gpio_cfg.bclk = GPIO_NUM_6;
    std_cfg.gpio_cfg.ws   = GPIO_NUM_7;
    std_cfg.gpio_cfg.dout = GPIO_NUM_12;
    std_cfg.gpio_cfg.din  = I2S_GPIO_UNUSED;
    std_cfg.gpio_cfg.invert_flags.mclk_inv = false;
    std_cfg.gpio_cfg.invert_flags.bclk_inv = false;
    std_cfg.gpio_cfg.invert_flags.ws_inv   = false;
    if (i2s_channel_init_std_mode(tx_chan_, &std_cfg) != ESP_OK) {
        ESP_LOGE(TAG, "i2s_channel_init_std_mode failed");
        return false;
    }
    if (i2s_channel_enable(tx_chan_) != ESP_OK) {
        ESP_LOGE(TAG, "i2s_channel_enable failed");
        return false;
    }

    started_ = true;
    return true;
}

float I2sAudioEngine::rpmToFreq(float virtual_rpm) {
    float r = virtual_rpm / RPM_REF;  // normalize
    if (r < 0.0f) r = 0.0f;
    if (r > 1.0f) r = 1.0f;           // clamp
    return RPM_FREQ_MIN + r * (RPM_FREQ_MAX - RPM_FREQ_MIN);
}

void I2sAudioEngine::render(const domain::VehicleState& state) {
    if (!started_) return;

    const bool mute = muted_ || state.overspeed_mute;
    if (mute) {
        std::memset(samples_, 0, sizeof(samples_));  // phase_ untouched
    } else {
        const float freq = rpmToFreq(state.virtual_rpm);
        const float dphi = TWO_PI * freq / SAMPLE_RATE;
        const float amplitude = AMPLITUDE * volumeGain(volume_pct_);
        for (int i = 0; i < FRAMES_PER_RENDER; ++i) {
            samples_[i] = static_cast<int16_t>(amplitude * sinf(phase_));
            phase_ += dphi;
            if (phase_ >= TWO_PI) phase_ -= TWO_PI;
        }
    }

    size_t written = 0;
    i2s_channel_write(tx_chan_, samples_, sizeof(samples_),
                      &written, WRITE_TIMEOUT_MS);
}

void I2sAudioEngine::setMuted(bool muted) { muted_ = muted; }

void I2sAudioEngine::setVolumePercent(std::uint8_t volume_pct) {
    volume_pct_ = clampVolumePercent(volume_pct);
}

}  // namespace audio
