# Capability: can-frame-parsing

**Status:** New capability
**Change:** can-frame-parser

## Purpose

Parse Tesla CAN bus frames (0x256 vehicle speed, 0x116 drive torque) into typed float values suitable for populating the `VehicleState` domain struct. Pure C++17, listen-only — no bus transmission.

## Signals

### 0x256 — Vehicle Speed

| Field | Value |
|---|---|
| CAN ID | `0x256` |
| Byte offset | `data[0:2]` |
| Byte order | Big-endian |
| Raw type | `uint16_t` |
| Scaling | `raw * 0.01` |
| Unit | km/h |
| Range | 0.0 – 655.35 km/h |

### 0x116 — Drive Torque (→ Throttle)

| Field | Value |
|---|---|
| CAN ID | `0x116` |
| Byte offset | `data[0:2]` |
| Byte order | Big-endian |
| Raw type | `int16_t` (signed) |
| Scaling | `raw * 0.1` → Nm |
| Normalization | `clamp(raw * 0.1 / 204.7, 0.0, 1.0)` |
| Output unit | Dimensionless [0.0, 1.0] |
| Max raw | `0x7FF` (2047) — PLACEHOLDER |

**PLACEHOLDER NOTICE:** Scaling constants are based on public Tesla DBC references. Calibrate with real captured frames for the specific Tesla model year before production use.

## API Contract

### CanFrame struct

```cpp
struct CanFrame {
    uint32_t id   = 0;
    uint8_t  dlc  = 0;
    uint8_t  data[8] = {};
};
```

### parseSpeed

```
Input:  CanFrame (expected id=0x256)
Output: float — speed in km/h
Error:  returns -1.0f if dlc < 2
```

### parseTorque

```
Input:  CanFrame (expected id=0x116)
Output: float — normalized throttle [0.0, 1.0]
Error:  returns -1.0f if dlc < 2
Clamp:  negative raw → 0.0, raw > 0x7FF → 1.0
```

## Constraints

- **Listen-only:** No transmit, send, or write-to-bus API in this module
- **Pure C++17:** Zero ESP-IDF dependencies; compilable on host for testing
- **Namespace:** All symbols in `can::`, scaling constants in `can::scaling::`
- **Error sentinel:** `-1.0f` (not NaN, not 0.0f)

## Acceptance Criteria

1. `parseSpeed({0x256, 8, {0x00, 0x64, ...}})` returns `1.0f` (±0.001)
2. `parseSpeed({0x256, 8, {0x00, 0x00, ...}})` returns `0.0f`
3. `parseSpeed({0x256, 8, {0xFF, 0xFF, ...}})` returns `655.35f` (±0.01)
4. `parseSpeed({0x256, 1, {0x00}})` returns `-1.0f` (short DLC)
5. `parseTorque({0x116, 8, {0x07, 0xFF, ...}})` returns `1.0f` (full torque)
6. `parseTorque({0x116, 8, {0x00, 0x00, ...}})` returns `0.0f`
7. `parseTorque({0x116, 8, {0xFF, 0xFF, ...}})` returns `0.0f` (negative clamped)
8. `parseTorque({0x116, 1, {0x00}})` returns `-1.0f` (short DLC)
9. Default-constructed `CanFrame` yields `0.0f` from both parsers
10. No function named `send`, `transmit`, `write`, or equivalent exists in `CanFrames.h`

## Test Strategy

Unity framework. Single test file `components/can/test/test_can_frames.cpp` with one test per acceptance criterion. Tests run on host (no ESP32 required).
