#pragma once

#include <algorithm>

#include "audio/I2sAudioEngine.h"
#include "ble/BleService.h"
#include "can/TwaiCanSource.h"
#include "config/runtime_config.h"
#include "domain/EngineModel.h"
#include "input/Encoder.h"
#include "input/ThrottlePot.h"
#include "ota/OtaManager.h"
#include "storage/SdConfigStore.h"
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
        applyRuntimeConfig(cfg_);

        encoder_.begin();
        pot_.begin();

        const bool ota_ready = ota_.begin();
        ble_.seedRuntimeConfig(cfg_);

        const bool can_ready   = can_.begin();
        const bool audio_ready = audio_.begin();
        const bool ble_ready   = ble_.begin();

        if (cfg_.ota_auto_check) {
            ota_.startIfConfigured(cfg_);
            cfg_.ota_auto_check = false;
            persistConfig();
        }

        return can_ready && audio_ready && ble_ready && ota_ready;
    }

    void tick() {
        // Encoder -> volume (clamped), mark dirty on change.
        const int steps = encoder_.poll();
        if (steps != 0) {
            int vol = static_cast<int>(cfg_.audio_volume_pct) + steps;
            vol = std::max(0, std::min(vol, 100));
            if (vol != static_cast<int>(cfg_.audio_volume_pct)) {
                cfg_.audio_volume_pct = static_cast<std::uint8_t>(vol);
                audio_.setVolumePercent(cfg_.audio_volume_pct);
                cfg_dirty_ = true;
            }
        }

        applyBleConfigUpdates();

        const float thr = pot_.read();

        domain::VehicleState state{};
        can_.poll(state);
        if (!state.can_valid) {
            state.throttle = thr;  // local bench input when CAN is idle
        }

        state = engine_.update(state);
        ble_.publishVehicleState(state);
        publishStatus(state);
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
            persistConfig();
        }
    }

private:
    void applyRuntimeConfig(const config::RuntimeConfig& cfg) {
        audio_.setVolumePercent(cfg.audio_volume_pct);
        ble_.seedRuntimeConfig(cfg);
    }

    void applyBleConfigUpdates() {
        config::RuntimeConfig pending = cfg_;
        if (!ble_.takePendingRuntimeConfig(pending)) {
            return;
        }

        cfg_ = pending;
        applyRuntimeConfig(cfg_);
        cfg_dirty_ = true;
    }

    void publishStatus(const domain::VehicleState& state) {
        ota::OtaStatus ota_status{};
        ota_.copyStatus(ota_status);
        ble_.publishOtaStatus(ota_status);

        std::uint32_t device_status = 0;
        if (ble_.started()) {
            device_status |= (1u << 0);
        }
        if (storage_.mounted()) {
            device_status |= (1u << 1);
        }
        if (state.can_valid) {
            device_status |= (1u << 2);
        }
        if (state.overspeed_mute) {
            device_status |= (1u << 3);
        }
        if (config::otaConfigReady(cfg_)) {
            device_status |= (1u << 4);
        }
        ble_.publishDeviceStatus(device_status);
    }

    void persistConfig() {
        storage_.save(cfg_);
        ble_.seedRuntimeConfig(cfg_);
        cfg_dirty_ = false;
    }

    can::TwaiCanSource     can_;
    audio::I2sAudioEngine  audio_;
    ble::BleService        ble_;
    domain::EngineModel    engine_;
    ota::OtaManager        ota_;
    storage::SdConfigStore storage_;
    input::Encoder         encoder_;
    input::ThrottlePot     pot_;
    ui::Ws2812Led          led_;
    config::RuntimeConfig  cfg_{};
    bool                   cfg_dirty_ = false;
};

}  // namespace app
