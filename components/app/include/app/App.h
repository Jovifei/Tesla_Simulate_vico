#pragma once

#include "can/TwaiCanSource.h"
#include "audio/I2sAudioEngine.h"
#include "ble/BleService.h"
#include "domain/EngineModel.h"

namespace app {

class App {
public:
    bool begin() {
        const bool can_ready   = can_.begin();
        const bool audio_ready = audio_.begin();
        const bool ble_ready   = ble_.begin();
        return can_ready && audio_ready && ble_ready;
    }

    void tick() {
        domain::VehicleState state{};
        can_.poll(state);
        state = engine_.update(state);
        audio_.setMuted(state.overspeed_mute);
        audio_.render(state);
    }

private:
    can::TwaiCanSource     can_;
    audio::I2sAudioEngine  audio_;
    ble::BleService        ble_;
    domain::EngineModel    engine_;
};

}  // namespace app
