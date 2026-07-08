#pragma once

#include <algorithm>

#include "can/TwaiCanSource.h"
#include "audio/I2sAudioEngine.h"
#include "ble/BleService.h"
#include "domain/EngineModel.h"
#include "config/runtime_config.h"
#include "storage/SdConfigStore.h"
#include "input/Encoder.h"
#include "input/ThrottlePot.h"
#include "ui/Ws2812Led.h"

namespace app {

class App {
public:
    bool begin() {
        led_.begin();
        led_.set(ui::Status::Booting);

        // SD is optional: a missing card must not fail boot.
        if (storage_.begin()) {
            if (!storage_.load(cfg_)) {
                cfg_ = config::kDefaultRuntimeConfig;
            }
        } else {
            cfg_ = config::kDefaultRuntimeConfig;
        }

        encoder_.begin();
        pot_.begin();

        const bool can_ready   = can_.begin();
        const bool audio_ready = audio_.begin();
        const bool ble_ready   = ble_.begin();
        return can_ready && audio_ready && ble_ready;
    }

    void tick() {
        // Encoder → volume (clamped), mark dirty on change.
        const int steps = encoder_.poll();
        if (steps != 0) {
            int vol = static_cast<int>(cfg_.audio_volume_pct) + steps;
            vol = std::max(0, std::min(vol, 100));
            if (vol != static_cast<int>(cfg_.audio_volume_pct)) {
                cfg_.audio_volume_pct = static_cast<std::uint8_t>(vol);
                cfg_dirty_ = true;
            }
        }

        const float thr = pot_.read();

        domain::VehicleState state{};
        can_.poll(state);
        if (!state.can_valid) {
            state.throttle = thr;  // local bench input when CAN is idle
        }

        state = engine_.update(state);
        audio_.setMuted(state.overspeed_mute);
        audio_.render(state);

        // Derived status LED.
        if (!state.can_valid && !storage_.mounted()) {
            led_.set(ui::Status::Fault);
        } else if (state.overspeed_mute) {
            led_.set(ui::Status::Muted);
        } else {
            led_.set(ui::Status::Running);
        }

        if (cfg_dirty_) {
            storage_.save(cfg_);
            cfg_dirty_ = false;
        }
    }

private:
    can::TwaiCanSource     can_;
    audio::I2sAudioEngine  audio_;
    ble::BleService        ble_;
    domain::EngineModel    engine_;
    storage::SdConfigStore storage_;
    input::Encoder         encoder_;
    input::ThrottlePot     pot_;
    ui::Ws2812Led          led_;
    config::RuntimeConfig  cfg_{};
    bool                   cfg_dirty_ = false;
};

}  // namespace app
