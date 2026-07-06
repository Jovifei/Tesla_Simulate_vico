#pragma once

#include "audio/StubAudioEngine.h"
#include "ble/BleService.h"
#include "can/TwaiCanSource.h"
#include "domain/EngineModel.h"

namespace tesla_speed::app {

class App {
 public:
  bool begin() {
    const bool can_ready = can_.begin();
    const bool audio_ready = audio_.begin();
    const bool ble_ready = ble_.begin();
    return can_ready && audio_ready && ble_ready;
  }

  void tick() {
    tesla_speed::domain::VehicleState state{};
    can_.poll(state);
    state = engine_.update(state);
    audio_.setMuted(state.overspeed_mute);
    audio_.render(state);
  }

 private:
  tesla_speed::can::TwaiCanSource can_;
  tesla_speed::audio::StubAudioEngine audio_;
  tesla_speed::ble::BleService ble_;
  tesla_speed::domain::EngineModel engine_;
};

}  // namespace tesla_speed::app
