#pragma once

#include <algorithm>
#include <cstdio>
#include <cstdint>
#include <cstring>

#include "audio/I2sAudioEngine.h"
#include "ble/BleService.h"
#include "can/TwaiCanSource.h"
#include "config/runtime_config.h"
#include "domain/EngineModel.h"
#include "input/Encoder.h"
#include "input/ThrottlePot.h"
#include "ota/OtaManager.h"
#include "iot/IotManager.h"
#include "network/NetworkManager.h"
#include "storage/SdConfigStore.h"
#include "ui/Ws2812Led.h"
#include "status/RuntimeStatus.h"

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
        const bool network_ready = network_.begin();
        const bool iot_ready = iot_.begin();
        ble_.seedRuntimeConfig(cfg_);
        network_.seedConfig(cfg_);
        iot_.seedConfig(cfg_);

        const bool can_ready   = can_.begin();
        const bool audio_ready = audio_.begin();
        const bool ble_ready   = ble_.begin();
        network_.startIfConfigured();
        iot_.startIfConfigured();

        if (ota_.startIfConfigured(cfg_)) {
            cfg_.ota_auto_check = false;
            persistConfig();
        }

        return can_ready && audio_ready && ble_ready && ota_ready && network_ready && iot_ready;
    }

    void tick() {
        ++tick_counter_;

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
        network_.startIfConfigured();
        iot_.startIfConfigured();
        publishStatus(state);
        audio_.setMuted(state.overspeed_mute);
        audio_.render(state);
        maybeQueueCloudOta();

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
        network_.seedConfig(cfg);
        iot_.seedConfig(cfg);
    }

    void applyBleConfigUpdates() {
        config::RuntimeConfig pending = cfg_;
        if (!ble_.takePendingRuntimeConfig(pending)) {
            return;
        }

        cfg_ = pending;
        audio_.setVolumePercent(cfg_.audio_volume_pct);
        ble_.seedRuntimeConfig(cfg_);
        network_.seedConfig(cfg_);
        iot_.seedConfig(cfg_);
        cfg_dirty_ = true;
    }

    void publishStatus(const domain::VehicleState& state) {
        status::RuntimeStatus network_status{};
        status::RuntimeStatus ota_status{};
        status::RuntimeStatus iot_status{};
        network_.copyStatus(network_status);
        ota_.copyStatus(ota_status);
        iot_.copyStatus(iot_status);

        status::RuntimeStatus runtime_status{};
        std::snprintf(runtime_status.version,
                      sizeof(runtime_status.version),
                      "%s",
                      ota_status.version);
        std::snprintf(runtime_status.partition,
                      sizeof(runtime_status.partition),
                      "%s",
                      ota_status.partition);
        runtime_status.wifi_state = network_status.wifi_state;
        runtime_status.iot_state = iot_status.iot_state;
        runtime_status.ota_state = ota_status.ota_state;
        runtime_status.ota_progress_pct = ota_status.ota_progress_pct;
        std::snprintf(runtime_status.ota_last_result,
                      sizeof(runtime_status.ota_last_result),
                      "%s",
                      ota_status.ota_last_result);
        copyFirstError(runtime_status.last_error,
                       sizeof(runtime_status.last_error),
                       ota_status.last_error,
                       network_status.last_error,
                       iot_status.last_error);

        runtime_status.device_status_bits = computeDeviceStatus(state, runtime_status);
        ble_.publishRuntimeStatus(runtime_status);
        ble_.publishDeviceStatus(computeDeviceStatus(state, runtime_status));

        if ((tick_counter_ % kIotOtaPublishTicks) == 0) {
            iot_.publishOtaProgress(runtime_status);
        }
        if ((tick_counter_ % kIotDeviceInfoPublishTicks) == 0) {
            iot_.publishDeviceInfo(runtime_status);
        }
        if ((tick_counter_ % kIotVehiclePublishTicks) == 0) {
            iot_.publishVehicleState(state);
        }
    }

    std::uint32_t computeDeviceStatus(const domain::VehicleState& state,
                                     const status::RuntimeStatus& runtime_status = {}) const {
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
        if (network_.connected()) {
            device_status |= (1u << 5);
        }
        if (runtime_status.iot_state == status::IotState::Cloud) {
            device_status |= (1u << 6);
        }
        if (ota_.running()) {
            device_status |= (1u << 7);
        }
        return device_status;
    }

    void maybeQueueCloudOta() {
        ota::OtaRequest request{};
        if (!iot_.takePendingOtaRequest(request)) {
            return;
        }
        ota_.request(request);
    }

    bool persistConfig() {
        const bool ok = storage_.save(cfg_);
        if (ok) {
            ble_.seedRuntimeConfig(cfg_);
            network_.seedConfig(cfg_);
            iot_.seedConfig(cfg_);
            cfg_dirty_ = false;
        }
        return ok;
    }

    static void copyFirstError(char* dst,
                               std::size_t dst_len,
                               const char* first,
                               const char* second,
                               const char* third) {
        if (dst == nullptr || dst_len == 0) {
            return;
        }
        const char* chosen = "";
        if (first != nullptr && first[0] != '\0') {
            chosen = first;
        } else if (second != nullptr && second[0] != '\0') {
            chosen = second;
        } else if (third != nullptr && third[0] != '\0') {
            chosen = third;
        }
        std::snprintf(dst, dst_len, "%s", chosen);
    }

    can::TwaiCanSource     can_;
    audio::I2sAudioEngine  audio_;
    ble::BleService        ble_;
    domain::EngineModel    engine_;
    ota::OtaManager        ota_;
    network::NetworkManager network_;
    iot::IotManager        iot_;
    storage::SdConfigStore storage_;
    input::Encoder         encoder_;
    input::ThrottlePot     pot_;
    ui::Ws2812Led          led_;
    config::RuntimeConfig  cfg_{};
    std::uint32_t          tick_counter_ = 0;
    bool                   cfg_dirty_ = false;

    static constexpr std::uint32_t kIotVehiclePublishTicks = 4;      // 100 ms at 25 ms/tick
    static constexpr std::uint32_t kIotOtaPublishTicks = 10;         // 250 ms at 25 ms/tick
    static constexpr std::uint32_t kIotDeviceInfoPublishTicks = 200; // 5 s at 25 ms/tick
};

}  // namespace app
