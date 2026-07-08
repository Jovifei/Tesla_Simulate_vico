# Proposal: s7-iot-ota-architecture

## Why

S7 moves Tesla Simulate Vico from an App-centered BLE/OTA/config shape into the layered runtime architecture used in Jovi's earlier firmware projects. The new baseline keeps Tesla-specific behavior and BLE UUIDs, but separates WiFi link management, MQTT cloud interaction, request-driven OTA, and runtime diagnostics.

Reference mapping:

- `wifi_esp32_ct`: ESP-IDF tasks, EventGroup link bits, BLE provisioning, MQTT, HTTPS OTA worker.
- `smart-controller-esp32s3`: IoT state mirror and UI/status register style runtime snapshot.
- `smart-controller-gd32f4`: explicit reconnect/state-machine style and MQTT uplink/downlink behavior.

## What Changes

- Add `components/status` with `status::RuntimeStatus` and diagnostics JSON helper.
- Extend `config::RuntimeConfig` and SD persistence for WiFi, OTA, MQTT, device ID, and product ID fields.
- Extend BLE `ffe8` to carry WiFi / OTA / IoT JSON while keeping the existing UUID contract.
- Add `components/network` for WiFi STA lifecycle, EventGroup state bits, reconnect, and stop handling.
- Add `components/iot` for MQTT connect, uplink publish, downlink parsing, and `ota_start` request handoff.
- Refactor `components/ota` into a request-driven HTTPS OTA worker with progress and failure status.
- Update `app::App` so the 25 ms tick loop polls and publishes state while network/MQTT/OTA work stays in component-owned background flows.

## Scope

- Preserve BLE primary service `0xfff0` and compatibility service `0xffe0`.
- Preserve CAN listen-only behavior; no CAN transmit work is added.
- Keep OTA HTTPS-only for S7.
- Do not implement USB CDC, advanced tuning UI, or MATLAB sound-modeling work in this change.
- Do not hardcode old-project cloud credentials, product IDs, or production topics; Tesla_speed owns an adapter layer through runtime config.

## Acceptance

- Build, size, size-components, and OpenSpec gates pass.
- BLE diagnostics reflect unified runtime status.
- S7 hardware acceptance remains explicitly blocked until BLE, WiFi, MQTT, and OTA are tested on device.
