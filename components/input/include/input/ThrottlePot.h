#pragma once

namespace input {

// Throttle potentiometer on ADC1 channel 0 (GPIO1). read() returns a smoothed,
// clamped value in [0.0, 1.0].
class ThrottlePot {
public:
    bool begin();

    // Returns the EMA-smoothed, clamped throttle value in [0.0, 1.0].
    float read();

private:
    void*  handle_ = nullptr;  // adc_oneshot_unit_handle_t (opaque here)
    float  ema_    = 0.0f;
    bool   ready_  = false;
    bool   seeded_ = false;
};

}  // namespace input
