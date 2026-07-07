## 1. Header & Data Structures

- [x] 1.1 Create `components/can/include/can/CanFrames.h` with `CanFrame` struct (id, dlc, data[8]) and function declarations for `parseSpeed()` and `parseTorque()`
- [x] 1.2 Define scaling constants (SPEED_SCALE, TORQUE_SCALE, TORQUE_MAX_RAW) in the header
- [x] 1.3 Declare `parseSpeed(const uint8_t* data, uint8_t dlc) -> float` and `parseTorque(const uint8_t* data, uint8_t dlc) -> float`

## 2. Parser Implementation

- [x] 2.1 Create `components/can/CanFrames.cpp`
- [x] 2.2 Implement `parseSpeed()` — extract big-endian uint16 from data[0:2], multiply by SPEED_SCALE, return km/h
- [x] 2.3 Implement `parseTorque()` — extract big-endian int16 from data[0:2], multiply by TORQUE_SCALE, return throttle_pct (0-100)
- [x] 2.4 Add DLC validation (return 0.0 or sentinel if dlc < expected)

## 3. Unit Tests

- [x] 3.1 Create `components/can/test/test_can_frames.cpp`
- [x] 3.2 Write tests for `parseSpeed()` — known frame {0x00, 0x64} → 1.0 km/h, zero frame, max frame
- [x] 3.3 Write tests for `parseTorque()` — known frame, zero, max, negative (signed)
- [x] 3.4 Write tests for DLC validation — short frame returns sentinel
- [x] 3.5 Add test runner registration (UNITY_BEGIN/END, RUN_TEST macros)

## 4. Build Integration

- [x] 4.1 Update `components/can/CMakeLists.txt` — add CanFrames.cpp to SRCS
- [ ] 4.2 Add test target for `test_can_frames` in CMakeLists (if test section exists)
- [ ] 4.3 Verify `idf.py build` passes with new files (no compile errors)

## 5. Verification

- [ ] 5.1 Run Unity tests on host or target — all pass
- [ ] 5.2 Confirm no transmit API exposed — header contains only parse/read functions
