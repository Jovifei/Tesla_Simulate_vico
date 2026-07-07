---
change: can-frame-parser
design-doc: openspec/changes/can-frame-parser/design.md
base-ref: 64211996944177337c533db3c2d86e03270b4894
---

# Implementation Plan: CAN Frame Parser

## Overview

Implement CAN frame parsing for Tesla vehicle speed (0x256) and torque (0x116) signals.
Pure C++17, no ESP-IDF dependencies, with full Unity test coverage.

## Tasks

### 1. Header & Data Structures
- 1.1 Create `components/can/include/can/CanFrames.h` with `CanFrame` struct and function declarations
- 1.2 Define scaling constants (SPEED_SCALE, TORQUE_SCALE, TORQUE_MAX_RAW)
- 1.3 Declare `parseSpeed(const uint8_t* data, uint8_t dlc) -> float` and `parseTorque(const uint8_t* data, uint8_t dlc) -> float`

### 2. Parser Implementation
- 2.1 Create `components/can/CanFrames.cpp`
- 2.2 Implement `parseSpeed()` — extract big-endian uint16, multiply by SPEED_SCALE
- 2.3 Implement `parseTorque()` — extract big-endian int16, multiply by TORQUE_SCALE, clamp [0,1]
- 2.4 Add DLC validation (return -1.0f sentinel if dlc < expected)

### 3. Unit Tests
- 3.1 Create `components/can/test/test_can_frames.cpp`
- 3.2 Write tests for `parseSpeed()` — known frame {0x00, 0x64} → 1.0 km/h, zero, max
- 3.3 Write tests for `parseTorque()` — known frame, zero, max, negative (signed)
- 3.4 Write tests for DLC validation — short frame returns sentinel
- 3.5 Add test runner registration (UNITY_BEGIN/END, RUN_TEST macros)

### 4. Build Integration
- 4.1 Update `components/can/CMakeLists.txt` — add CanFrames.cpp to SRCS
- 4.2 Add test target for `test_can_frames` in CMakeLists
- 4.3 Verify `idf.py build` passes

### 5. Verification
- 5.1 Run Unity tests — all pass
- 5.2 Confirm no transmit API exposed — header contains only parse/read functions
