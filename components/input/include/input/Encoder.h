#pragma once

#include <cstdint>

#include "driver/gpio.h"

namespace input {

// Rotary encoder on CLK/DT (pins from config/pin_map.h). Polled quadrature
// decode with debounce. poll() returns signed detents since the last call.
class Encoder {
public:
    bool begin();

    // Returns accumulated signed detent delta since the previous call
    // (0 when idle).
    int poll();

private:
    static int readState();

    int           accum_       = 0;      // sub-step accumulator (4 per detent)
    std::uint8_t  prev_state_  = 0;      // last 2-bit CLK/DT sample
    std::int64_t  last_edge_us_ = 0;     // debounce timestamp
    bool          ready_       = false;
};

}  // namespace input
