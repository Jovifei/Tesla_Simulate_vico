# Proposal: twai-can-source

## Why

S1.1 delivered `CanFrames` pure-C++ parser (parseSpeed, parseTorque) but no real CAN bus reception. The `TwaiCanSource` is a stub that never receives frames from the ESP32-S3 TWAI peripheral. Without real reception, VehicleState never updates from live CAN data.

## What Changes

- Update `components/can/include/can/TwaiCanSource.h` — add TWAI driver config members (g_config_, t_config_, f_config_), include driver/twai.h, driver/gpio.h, config/pin_map.h
- Update `components/can/TwaiCanSource.cpp` — implement real begin() (CAN_RS gpio + twai_driver_install + twai_start) and poll() (twai_receive + dispatch by ID to CanFrames parser + update VehicleState)
- TWAI config: 500 kbps, TWAI_MODE_LISTEN_ONLY, CAN_RX=GPIO13, CAN_TX=GPIO14, CAN_RS=GPIO38 (driven low for normal slope)
- Dispatch: 0x256→parseSpeed→speed_kph, 0x116→parseTorque→throttle
- **No transmit API** — listen-only is a hard constraint
- No changes to CanFrames parser (S1.1 frozen) or hardware

## Capabilities

- twai-can-source (NEW)
