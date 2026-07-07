#include "can/CanFrames.h"

#include <algorithm>

namespace can {

float parseSpeed(const uint8_t* data, uint8_t dlc) {
    if (dlc < 2) {
        return -1.0f;  // Sentinel: insufficient data
    }

    // Big-endian uint16 extraction
    uint16_t raw = (static_cast<uint16_t>(data[0]) << 8) | data[1];
    return static_cast<float>(raw) * SPEED_SCALE;
}

float parseTorque(const uint8_t* data, uint8_t dlc) {
    if (dlc < 2) {
        return -1.0f;  // Sentinel: insufficient data
    }

    // Big-endian int16 extraction (signed)
    int16_t raw = static_cast<int16_t>((static_cast<uint16_t>(data[0]) << 8) | data[1]);

    // Convert to Nm, then normalize to 0-1 range
    float torque_nm = static_cast<float>(raw) * TORQUE_SCALE;
    float throttle = torque_nm / TORQUE_MAX_RAW;

    // Clamp to [0, 1] — negative torque (regen) maps to 0
    return std::max(0.0f, std::min(1.0f, throttle));
}

}  // namespace can
