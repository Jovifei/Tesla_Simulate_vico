#pragma once

#include <cstdint>

namespace can {

/// Scaling constants from Tesla DBC definitions
constexpr float SPEED_SCALE = 0.01f;      // km/h per raw count
constexpr float TORQUE_SCALE = 0.1f;      // Nm per raw count
constexpr float TORQUE_MAX_RAW = 204.7f;  // Max torque for throttle normalization

/// Raw CAN frame structure
struct CanFrame {
    uint32_t id;
    uint8_t dlc;
    uint8_t data[8];
};

/// Parse vehicle speed from CAN ID 0x256
/// @param data Pointer to frame data bytes
/// @param dlc Data length code
/// @return Speed in km/h, or -1.0f if DLC < 2
float parseSpeed(const uint8_t* data, uint8_t dlc);

/// Parse drive torque from CAN ID 0x116
/// @param data Pointer to frame data bytes
/// @param dlc Data length code
/// @return Throttle percentage 0.0-1.0, or -1.0f if DLC < 2
float parseTorque(const uint8_t* data, uint8_t dlc);

}  // namespace can
