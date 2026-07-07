#pragma once

#include "can/CanSource.h"
#include "can/CanFrames.h"
#include "config/runtime_config.h"
#include "config/pin_map.h"
#include "driver/twai.h"

namespace can {

class TwaiCanSource final : public CanSource {
public:
    explicit TwaiCanSource(config::RuntimeConfig config = config::kDefaultRuntimeConfig)
        : config_(config) {}

    bool begin() override;
    bool poll(domain::VehicleState& state) override;
    bool isListenOnly() const override { return true; }

private:
    config::RuntimeConfig config_;
    twai_general_config_t g_config_ = {};
    twai_timing_config_t  t_config_ = {};
    twai_filter_config_t  f_config_ = {};
    bool installed_ = false;
};

}  // namespace can
