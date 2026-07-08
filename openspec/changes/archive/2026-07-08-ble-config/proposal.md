# Proposal: ble-config

## Why

Through S2.1 the firmware turns real Tesla CAN traffic into an RPM-tracked engine tone, but every tunable parameter (engine sound profile, audio synthesis limits, CAN signal mapping) is hard-coded at compile time, and the running vehicle state is only observable over a serial log. A companion phone/desktop app needs a wireless channel to (1) read live `domain::VehicleState`, (2) select and configure engine sound profiles, and (3) adjust audio and CAN parameters at runtime. `components/ble/` currently ships only a `BleService` stub whose `begin()` flips a flag and produces no radio activity — the ESP32-S3 BLE peripheral is idle. To make the simulator configurable and observable over the air, we need a real BLE GATT server exposing a structured configuration/telemetry service.

## What Changes

- Replace the `ble::BleService` stub with a real NimBLE GATT server (new implementation files under `components/ble/`) that keeps the existing `begin()`/`started()` surface but stands up an actual BLE peripheral.
- Initialize the ESP-IDF built-in NimBLE host (`nimble_port_init`, host/GAP config via `ble_hs_cfg`, `nimble_port_freertos_init` host task) inside `begin()`, and register the GATT service table with `ble_gatts_count_cfg` + `ble_gatts_add_svcs`.
- Register the primary configuration service on UUID `ffe0` (`ble::kServiceUuid`) with the seven characteristics already declared in `BleUuids.h`: `ffe1` config, `ffe2` state, `ffe3` audio, `ffe4` can, `ffe5` diagnostics, `ffe6` profile, `ffe7` control — each with appropriate read and/or write access callbacks.
- Start connectable, general-discoverable advertising (`ble_gap_adv_start`) that advertises the `ffe0` service UUID and the device name so the app can discover and connect.
- **Use the ESP-IDF built-in `esp-nimble` host only** — NOT `NimBLE-Arduino`. Namespace stays `ble::`. ESP-IDF v5.3.
- No changes to the CAN pipeline, audio engine, or `domain::VehicleState` (S1/S2 frozen). BLE reads consume `VehicleState` read-only.

## Capabilities

- ble-config (NEW)
