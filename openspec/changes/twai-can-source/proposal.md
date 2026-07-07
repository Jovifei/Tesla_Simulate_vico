# Proposal: twai-can-source

## Problem

S1.1 delivered `CanFrames` pure-C++ parser (parseSpeed, parseTorque) but no real CAN bus reception. The `TwaiCanSource` is a stub that never receives frames from the ESP32-S3 TWAI peripheral. Without real reception, VehicleState never updates from live CAN data.

## Goal

Implement real TWAI CAN reception on ESP32-S3: configure the hardware TWAI driver in listen-only mode, receive CAN frames in a polling loop, dispatch matching frame IDs (0x256, 0x116) to the existing `CanFrames` parser, and update `VehicleState`.

## Scope

- TWAI driver configuration (500 kbps, listen-only, RX queue)
- `TwaiCanSource::begin()` — install driver, configure GPIO (CAN_RX=13, CAN_TX=14), start TWAI
- `TwaiCanSource::poll()` — receive frame from TWAI queue, dispatch by ID, update VehicleState
- CAN_RS pin (GPIO 38) HIGH for normal slope mode
- Integration with existing `CanFrames::parseSpeed()` / `CanFrames::parseTorque()`

## Non-Goals

- No CAN transmit API — listen-only is a hard constraint
- No bus-off recovery or error handling beyond logging
- No new CAN frame IDs beyond 0x256 and 0x116
- No changes to CanFrames parser (S1.1 frozen)
- No changes to hardware/ schematics or PCB
