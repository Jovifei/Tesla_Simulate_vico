#pragma once

#include "can/CanSource.h"
#include "config/runtime_config.h"

namespace tesla_speed::can {

class TwaiCanSource final : public CanSource {
 public:
  explicit TwaiCanSource(tesla_speed::config::RuntimeConfig config =
                             tesla_speed::config::kDefaultRuntimeConfig)
      : config_(config) {}

  bool begin() override {
    configured_ = config_.can_listen_only;
    return configured_;
  }

  bool poll(tesla_speed::domain::VehicleState& state) override {
    state.can_valid = false;
    return false;
  }

  bool isListenOnly() const override { return config_.can_listen_only; }

 private:
  tesla_speed::config::RuntimeConfig config_;
  bool configured_ = false;
};

}  // namespace tesla_speed::can
