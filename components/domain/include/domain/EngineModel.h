#pragma once

#include <algorithm>
#include "domain/VehicleState.h"

namespace domain {

struct EngineModelConfig {
    float idle_rpm         = 900.0f;
    float max_rpm          = 6200.0f;
    float speed_rpm_gain   = 42.0f;
    float throttle_rpm_gain = 2200.0f;
    float smoothing_alpha  = 0.35f;
    float overspeed_kph    = 180.0f;
};

class EngineModel {
public:
    explicit EngineModel(EngineModelConfig config = {})
        : config_(config), rpm_(config.idle_rpm) {}

    VehicleState update(VehicleState input) {
        const float speed    = std::max(0.0f, input.speed_kph);
        const float throttle = clamp(input.throttle, 0.0f, 1.0f);
        const float target   = targetRpm(speed, throttle);

        rpm_ = (rpm_ * (1.0f - config_.smoothing_alpha))
             + (target * config_.smoothing_alpha);

        input.throttle       = throttle;
        input.virtual_rpm    = std::max(config_.idle_rpm,
                                        std::min(rpm_, config_.max_rpm));
        input.overspeed_mute = speed >= config_.overspeed_kph;
        return input;
    }

    float targetRpm(float speed_kph, float throttle) const {
        const float speed = std::max(0.0f, speed_kph);
        const float load  = clamp(throttle, 0.0f, 1.0f);
        const float target = config_.idle_rpm
                           + (speed * config_.speed_rpm_gain)
                           + (load * config_.throttle_rpm_gain);
        return std::max(config_.idle_rpm,
                        std::min(target, config_.max_rpm));
    }

    float currentRpm() const { return rpm_; }

private:
    static float clamp(float v, float lo, float hi) {
        return std::max(lo, std::min(v, hi));
    }

    EngineModelConfig config_;
    float rpm_;
};

}  // namespace domain
