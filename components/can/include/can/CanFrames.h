#pragma once

#include <cstdint>

namespace can {

/// Scaling constants from Tesla DBC definitions
constexpr float SPEED_SCALE = 0.01f;      // km/h per raw count
constexpr float TORQUE_SCALE = 0.1f;      // Nm per raw count
constexpr float TORQUE_MAX_RAW = 204.7f;  // Max torque for throttle normalization

// PRD-v4.2 canonical CAN IDs.
constexpr uint32_t SPEED_CAN_ID_PRIMARY = 0x257;
constexpr uint32_t THROTTLE_CAN_ID_PRIMARY = 0x118;

// Legacy compatibility CAN IDs preserved for existing boards and logs.
constexpr uint32_t SPEED_CAN_ID_LEGACY = 0x256;
constexpr uint32_t THROTTLE_CAN_ID_LEGACY = 0x116;

/// Raw CAN frame structure
struct CanFrame {
    uint32_t id;
    uint8_t dlc;
    uint8_t data[8];
};

/// Parse vehicle speed payload (Tesla speed frame, byte[2] big-endian raw count)
/// @param data Pointer to frame data bytes
/// @param dlc Data length code
/// @return Speed in km/h, or -1.0f if DLC < 2
float parseSpeed(const uint8_t* data, uint8_t dlc);

/// Parse throttle payload from CAN frame (TESLA-like signed value path)
/// @param data Pointer to frame data bytes
/// @param dlc Data length code
/// @return Throttle percentage 0.0-1.0, or -1.0f if DLC < 2
float parseTorque(const uint8_t* data, uint8_t dlc);

}  // namespace can
