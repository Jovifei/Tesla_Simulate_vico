#pragma once

#include <cmath>

class VolumeRamp final {
public:
    void set_target(float value) noexcept {
        if (std::isfinite(value)) target_ = value < 0.0F ? 0.0F : value > 1.0F ? 1.0F : value;
    }

    float next() noexcept {
        current_ += (target_ - current_) * 0.002F;
        return current_;
    }

private:
    float current_{1.0F};
    float target_{1.0F};
};
