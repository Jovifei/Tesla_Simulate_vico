# twai-can-source Specification

## Purpose
TBD - created by archiving change twai-can-source. Update Purpose after archive.
## Requirements
### Requirement: TWAI listen-only driver configuration

The system SHALL configure the ESP32-S3 TWAI peripheral in `TWAI_MODE_LISTEN_ONLY` mode at 500 kbps with CAN_RX on GPIO 13, CAN_TX on GPIO 14, and CAN_RS driven LOW on GPIO 38 (normal slope mode). The driver SHALL install with an RX queue depth of 5 and TX queue depth of 0. `twai_start()` SHALL be called after successful installation.

#### Scenario: Successful driver install

- WHEN `TwaiCanSource::begin()` is called with default RuntimeConfig
- THEN the TWAI driver is installed in listen-only mode and `begin()` returns `true`

#### Scenario: CAN_RS pin driven high

- WHEN `begin()` completes successfully
- THEN GPIO 38 is set to logical LOW (normal slope mode for 500 kbps)

#### Scenario: Driver install failure

- WHEN `twai_driver_install()` returns an error
- THEN `begin()` returns `false` and no frames are received

### Requirement: CAN frame reception via twai_receive

The system SHALL call `twai_receive()` with zero timeout inside `poll()` to non-blockingly dequeue one CAN frame per call. If no frame is available (`ESP_ERR_TIMEOUT`), `poll()` SHALL return `false` without modifying VehicleState.

#### Scenario: Frame available in RX queue

- WHEN a CAN frame is available and `poll()` is called
- THEN the frame is dequeued and dispatched by identifier

#### Scenario: No frame available

- WHEN the RX queue is empty and `poll()` is called
- THEN `poll()` returns `false` and `state` is unchanged

### Requirement: Dispatch frames to CanFrames parser

The system SHALL dispatch received CAN frames by identifier: primary frame ID 0x257 SHALL be parsed by `CanFrames::parseSpeed()` and written to `state.speed_kph`; primary frame ID 0x118 SHALL be parsed by `CanFrames::parseTorque()` and written to `state.throttle`. Unknown frame IDs SHALL be silently dropped. After a valid dispatch, `state.can_valid` SHALL be set to `true`.

#### Scenario: Speed frame dispatched

- WHEN a frame with id=0x257, dlc=8, data={0x00, 0x64, ...} is received
- THEN `state.speed_kph` is set to 1.0f and `state.can_valid` is `true`

#### Scenario: Torque frame dispatched

- WHEN a frame with id=0x118, dlc=8, data={0x07, 0xFF, ...} is received
- THEN `state.throttle` is set to 1.0f and `state.can_valid` is `true`

### Requirement: Backward-compatible legacy frame dispatch

The system SHALL accept legacy IDs 0x256 and 0x116 with the same dispatch behavior when runtime config enables compatibility mode.

#### Scenario: Legacy speed frame dispatched

- WHEN config flag enables legacy and a frame with id=0x256, dlc=8, data={0x00, 0x64, ...} is received
- THEN `state.speed_kph` is set to 1.0f and `state.can_valid` is `true`

#### Scenario: Legacy torque frame dispatched

- WHEN config flag enables legacy and a frame with id=0x116, dlc=8, data={0x07, 0xFF, ...} is received
- THEN `state.throttle` is set to 1.0f and `state.can_valid` is `true`

#### Scenario: Unknown frame ignored

- WHEN a frame with id=0x300 is received
- THEN `state` is not modified and `poll()` returns `true`

### Requirement: No transmit API exposed

The `can::` module SHALL NOT expose any transmit, send, or write-to-bus function. No call to `twai_transmit()` SHALL exist in any source file under `components/can/`. The listen-only invariant SHALL be enforced at both the TWAI driver configuration level and the source code level.

#### Scenario: No transmit function in codebase

- WHEN all source files under `components/can/` are searched for `twai_transmit`, `send`, or `write`
- THEN zero matches are found

#### Scenario: Listen-only mode enforced

- WHEN `twai_driver_install()` is called
- THEN `general_config.mode` is `TWAI_MODE_LISTEN_ONLY`
