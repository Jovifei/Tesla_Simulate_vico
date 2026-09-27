#pragma once

#include <cmath>

class VolumeRamp final {
public:
    void set_target(float value, unsigned frames = 960) noexcept {
        if (!std::isfinite(value)) return;
        const float target = value < 0.0F ? 0.0F : value > 1.0F ? 1.0F : value;
        if (target == target_) return;
        target_ = target;
        if (frames == 0) {
            current_ = target_;
            remaining_ = 0;
        } else {
            remaining_ = frames;
            step_ = (target_ - current_) / static_cast<float>(frames);
        }
    }

    float next() noexcept {
        if (remaining_ > 0) {
            current_ += step_;
            if (--remaining_ == 0) current_ = target_;
        }
        return current_;
    }

    float value() const noexcept { return current_; }
    bool at_zero() const noexcept { return remaining_ == 0 && current_ == 0.0F; }

private:
    float current_{};
    float target_{};
    float step_{};
    unsigned remaining_{};
};
