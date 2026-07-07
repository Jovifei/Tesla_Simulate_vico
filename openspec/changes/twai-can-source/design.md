# Design: twai-can-source

## Architecture

```
TWAI ISR (RX queue, depth=5)
    │
    ▼
TwaiCanSource::poll()
    │ twai_receive(&frame, timeout=0)  ── non-blocking dequeue
    ▼
  frame.identifier match?
    ├─ 0x256 → CanFrames::parseSpeed(frame.data, frame.dlc)  → state.speed_kph
    ├─ 0x116 → CanFrames::parseTorque(frame.data, frame.dlc) → state.throttle
    └─ else  → silently drop
    │
    ▼
  state.can_valid = true
  return true
```

## TWAI Configuration

- **Mode**: `TWAI_MODE_LISTEN_ONLY` — no ACK, no transmit, hardware-enforced
- **Bitrate**: 500 kbps (from `RuntimeConfig::can_bitrate`)
- **RX queue depth**: 5 frames
- **TX queue depth**: 0 (listen-only, no transmit)
- **Alerts**: none configured (polling via `twai_receive`, not alert-driven)
- **GPIO**: CAN_RX=GPIO_13, CAN_TX=GPIO_14 (from `config::pins`)
- **CAN_RS**: GPIO_38 driven LOW (normal slope mode for 500 kbps — TCAN330 transceiver: RS=LOW → normal, RS=HIGH → low-power/slope)
- **Timing**: ESP-IDF default 500 kbps timing table (`TWAI_TIMING_CONFIG_500KBITS()`)
- **Filter**: accept-all (no ID mask filtering — dispatch handled in software)

## Key Decisions

1. **Polling vs ISR callback**: Use `twai_receive()` with timeout=0 in `poll()`. Non-blocking, fits the existing `CanSource::poll()` interface. No FreeRTOS task or alert callback needed. One frame dequeued per `poll()` call.

2. **Listen-only enforcement**: `TWAI_MODE_LISTEN_ONLY` at driver level — hardware prevents ACK dominant bits. No `twai_transmit()` call anywhere in `components/can/`. The `CanSource` base class has no `transmit()` method (compile-time guard).

3. **Frame dispatch**: Switch on `frame.identifier` inside `poll()`. Only 0x256 (speed) and 0x116 (throttle) are handled. Unknown IDs silently dropped — no logging to avoid log spam at 500 kbps bus load.

4. **CAN_RS pin (GPIO 38)**: Configured as push-pull output, driven LOW in `begin()`. LOW = normal slope mode on TCAN330 transceiver, appropriate for 500 kbps. HIGH would select low-power/slope-control mode (reduced slew rate), not desired for normal operation.

5. **Error handling**: `twai_receive()` returning `ESP_ERR_TIMEOUT` → `poll()` returns `false`, state unchanged. Driver install failure → log error via `ESP_LOGE`, return `false`. Driver already installed (idempotent begin) → skip install, just start.

6. **API choice**: ESP-IDF v5.3 legacy TWAI API (`driver/twai.h`). The newer TWAI TWAI v2 API exists in v5.3 but is less documented and not needed for this simple use case. Legacy API is stable, well-tested, and sufficient for listen-only reception.

7. **Frame data access**: Use `frame.data[]` and `frame.data_length_code` directly — matches the `CanFrames::parseSpeed(data, dlc)` / `parseTorque(data, dlc)` signatures from S1.1.

## Data Flow

```
begin():
  gpio_set_direction(CAN_RS, GPIO_MODE_OUTPUT)
  gpio_set_level(CAN_RS, 0)                              // LOW = normal slope
  general_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX, CAN_RX, TWAI_MODE_LISTEN_ONLY)
  timing_config  = TWAI_TIMING_CONFIG_500KBITS()
  filter_config  = TWAI_FILTER_CONFIG_ACCEPT_ALL()
  twai_driver_install(&general_config, &timing_config, &filter_config)
  twai_start()
  configured_ = true

poll(VehicleState& state):
  twai_message_t frame
  esp_err_t rc = twai_receive(&frame, 0)                  // timeout=0, non-blocking
  if (rc == ESP_ERR_TIMEOUT) return false                  // nothing in queue
  if (rc != ESP_OK) return false                           // other error
  switch (frame.identifier):
    case 0x256: state.speed_kph = parseSpeed(frame.data, frame.data_length_code); break
    case 0x116: state.throttle  = parseTorque(frame.data, frame.data_length_code); break
    default: break                                           // silently drop
  state.can_valid = true
  return true
```

## Dependencies

- ESP-IDF v5.3 `driver/twai.h` (legacy API, stable)
- `driver/gpio.h` (for CAN_RS pin control)
- `config/pin_map.h` — CAN_RX (GPIO_13), CAN_TX (GPIO_14), CAN_RS (GPIO_38)
- `config/runtime_config.h` — can_bitrate (500000), can_listen_only (true)
- `can/CanFrames.h` — parseSpeed(), parseTorque() (S1.1 frozen, no changes)
- `domain/VehicleState.h` — speed_kph, throttle, can_valid fields

## Risks

1. **TWAI driver state machine**: If `begin()` is called twice without `twai_uninstall()`, second install fails. Mitigation: check `configured_` flag, or call `twai_uninstall()` before re-install.
2. **Bus-off condition**: In listen-only mode, bus-off cannot occur (no transmit). No recovery logic needed.
3. **GPIO 38 output capability**: GPIO 38 is an output-capable pin on ESP32-S3. Confirmed in pin map.
