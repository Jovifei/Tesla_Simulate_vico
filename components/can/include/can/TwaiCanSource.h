#pragma once

#include "can/CanSource.h"
#include "config/runtime_config.h"

namespace can {

class TwaiCanSource final : public CanSource {
public:
    explicit TwaiCanSource(config::RuntimeConfig config = config::kDefaultRuntimeConfig)
        : config_(config) {}

    bool begin() override;
    bool poll(domain::VehicleState& state) override;
    bool isListenOnly() const override { return config_.can_listen_only; }

private:
    config::RuntimeConfig config_;
    bool configured_ = false;
};

}  // namespace can
