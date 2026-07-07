## Why

The firmware needs to read vehicle speed and throttle data from the Tesla's CAN bus to drive the engine sound simulation. Without a CAN frame parser, there is no way to extract speed (0x256) or torque (0x116) signals from raw CAN frames. This is the foundational data-input layer for S1.

## What Changes

- Add `components/can/CanFrames.h` — pure C++ header declaring frame parsing functions and the `VehicleState` output struct
- Add `components/can/CanFrames.cpp` — implementation of `parseSpeed()` and `parseTorque()` extracting signal values from raw 8-byte CAN payloads
- Add `components/can/test/test_can_frames.cpp` — Unity unit tests covering known-good frames, boundary values, and null/zero inputs
- Update `components/can/CMakeLists.txt` to compile the new source files (both production and test targets)
- **No HAL, no ESP-IDF dependencies** — parsing logic is pure C++17, testable on host
- **Listen-only only** — no CAN transmit API is introduced; the parser is a pure data-extraction layer

## Capabilities

### New Capabilities
- `can-frame-parsing`: Parse Tesla CAN frames 0x256 (vehicle speed) and 0x116 (torque) into structured VehicleState fields (speed_kph, throttle_pct)

### Modified Capabilities
(none — this is new functionality)

## Impact

- `components/can/` — new files added; existing `CanSource.h/cpp` unchanged in this change
- `components/domain/` — `VehicleState` struct is referenced but not modified (already exists)
- Build system: `components/can/CMakeLists.txt` updated to include new sources
- Tests: new Unity test binary `test_can_frames` added to the test suite
- Dependencies: no new external packages; uses existing Unity test framework
