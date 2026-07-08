# can-frame-parser Specification

## Purpose
CAN frame parsing rules that convert Tesla speed and torque frames into normalized vehicle-state fields.

## Requirements
### Requirement: Parse vehicle speed from CAN frame 0x257

The system SHALL parse vehicle speed from CAN frame ID 0x257 by extracting a big-endian uint16 from data[0:2] and multiplying by 0.01 to produce speed in km/h. Returns -1.0f if DLC < 2. Placeholder scaling must be calibrated with real Tesla DBC before production.

#### Scenario: Valid speed frame

- WHEN a CAN frame with id=0x257, dlc=8, data={0x00, 0x64, 0,0,0,0,0,0} is parsed
- THEN parseSpeed returns 1.0f (±0.001)

#### Scenario: Zero speed

- WHEN a CAN frame with id=0x257, dlc=8, data={0x00, 0x00, ...} is parsed
- THEN parseSpeed returns 0.0f

#### Scenario: Short DLC rejected

- WHEN a CAN frame with dlc=1 is parsed
- THEN parseSpeed returns -1.0f

### Requirement: Backward-compatible Tesla speed parsing for legacy frame 0x256

The system SHALL also support legacy frame ID 0x256 with the same `parseSpeed` payload semantics as a compatibility path when runtime config enables it.

#### Scenario: Legacy speed frame parsed

- WHEN a CAN frame with id=0x256, dlc=8, data={0x00, 0x64, ...} is parsed
- THEN parseSpeed returns 1.0f (±0.001)

### Requirement: Parse drive torque from CAN frame 0x118

The system SHALL parse drive torque from CAN frame ID 0x118 by extracting a big-endian int16 from data[0:2], multiplying by 0.1, and normalizing to [0,1] using max raw 0x7FF (placeholder). Returns -1.0f if DLC < 2. Negative raw values clamp to 0.0f.

#### Scenario: Full torque

- WHEN a CAN frame with id=0x118, dlc=8, data={0x07, 0xFF, ...} is parsed
- THEN parseTorque returns 1.0f

#### Scenario: Negative torque clamped

- WHEN a CAN frame with id=0x118, dlc=8, data={0xFF, 0xFF, ...} is parsed
- THEN parseTorque returns 0.0f (negative clamped)

#### Scenario: Short DLC rejected

- WHEN a CAN frame with dlc=1 is parsed
- THEN parseTorque returns -1.0f

### Requirement: Backward-compatible Tesla torque parsing for legacy frame 0x116

The system SHALL also support legacy frame ID 0x116 with the same `parseTorque` payload semantics as a compatibility path when runtime config enables it.

#### Scenario: Legacy torque frame parsed

- WHEN a CAN frame with id=0x116, dlc=8, data={0x07, 0xFF, ...} is parsed
- THEN parseTorque returns 1.0f

### Requirement: Listen-only (no transmit API)

The `can::` module SHALL expose only parse functions (`parseSpeed`, `parseTorque`). No transmit, send, or write-to-bus API SHALL exist in any header or source file under `components/can/`.

#### Scenario: No transmit function exposed

- WHEN `components/can/include/can/CanFrames.h` is inspected
- THEN no function named `send`, `transmit`, `write`, or equivalent exists

### Requirement: Pure C++17 with no HAL dependency

The parser SHALL be pure C++17 with zero ESP-IDF dependencies, compilable on host for unit testing. Scaling constants SHALL be `constexpr` in namespace `can::`.

#### Scenario: Host-compilable

- WHEN CanFrames.cpp is compiled without ESP-IDF includes
- THEN it compiles successfully
