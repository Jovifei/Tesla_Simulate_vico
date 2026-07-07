## Context

Tesla CAN bus uses specific arbitration IDs for vehicle data. ID 0x256 carries vehicle speed, ID 0x116 carries drive torque. The firmware runs on ESP32-S3 with ESP-IDF v5.3, using a listen-only CAN driver (MCP2515 or TWAI). The `VehicleState` struct already exists in `components/domain/` and carries `speed_kph` (float) and `throttle_pct` (float 0-100).

This change adds the parsing layer that converts raw 8-byte CAN payloads into those VehicleState fields. The parser is intentionally decoupled from the CAN driver — it receives raw bytes and returns parsed values.

## Goals / Non-Goals

**Goals:**
- Pure C++17 parsing logic with zero ESP-IDF dependencies
- Parse 0x256 → speed_kph (float, km/h)
- Parse 0x116 → throttle_pct (float, 0-100%)
- Full Unity test coverage for known frames, edge cases, and invalid inputs
- Easy to extend with additional CAN IDs in future changes

**Non-Goals:**
- CAN bus driver initialization or configuration (handled elsewhere)
- CAN frame transmission — listen-only is a hard constraint
- Frame filtering or queuing — that's the driver layer's job
- Signal scaling calibration beyond Tesla's known DBC values (can be tuned later)

## Decisions

### D1: Standalone parser functions vs. class with state

**Choice:** Free functions (`parseSpeed`, `parseTorque`) operating on raw `uint8_t[8]` arrays.

**Rationale:** The parser has no internal state — each frame is independent. Free functions are simpler to test, composable, and avoid unnecessary OOP overhead. A `CanFrame` struct carries the ID + payload for dispatch.

**Alternative considered:** A `CanParser` class with `processFrame()` dispatch — rejected as over-engineered for 2 IDs; can be introduced later when the ID count grows.

### D2: Return parsed value vs. update VehicleState directly

**Choice:** Functions return the parsed scalar value (float). The caller updates VehicleState.

**Rationale:** Keeps parsing logic pure and testable without coupling to VehicleState. Callers can compose updates as needed.

**Alternative considered:** `void parseIntoVehicleState(frame, &state)` — couples parser to domain struct, harder to test in isolation.

### D3: Byte order and signal scaling

**Choice:** Big-endian (network byte order) for 16-bit signals, with Tesla DBC scaling factors: speed = raw * 0.01 km/h, torque = raw * 0.1 Nm (signed). Throttle derived as percentage of max torque.

**Rationale:** Tesla CAN frames follow standard big-endian encoding per their DBC files. Scaling factors are documented in public Tesla DBC references.

### D4: Test strategy

**Choice:** Unity framework, one test file per parser function, testing:
- Known-good frame bytes → expected output
- Zero payload → 0.0
- Max payload (0xFFFF) → max scaled value
- Wrong CAN ID → returns error/sentinel

**Rationale:** Unity is already integrated in the project. Focused test files make failures easy to locate.

## Risks / Trade-offs

- **[Risk] DBC scaling factors may differ across Tesla model years** → Mitigation: define scaling as named constants in the header; easy to adjust per vehicle profile later
- **[Risk] Byte order assumption wrong for some signals** → Mitigation: test with real captured frames when hardware is available; parser is easy to swap endianness
- **[Trade-off] No frame dispatch/router** → Acceptable for 2 IDs; revisit at ~5 IDs

## Open Questions

- Exact DBC scaling for torque → throttle_pct conversion (using 0-100% of 0x7FF raw range as placeholder)
- Whether to add a `CanFrame` struct now or defer to when frame routing is needed
