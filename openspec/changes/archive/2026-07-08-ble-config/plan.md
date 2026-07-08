change: ble-config
design-doc: docs/superpowers/specs/2026-07-08-ble-config-design.md

# Build Plan: ble-config (S3 — NimBLE GATT Configuration Server)

Canonical spec: `openspec/changes/ble-config/`. Design: the linked Design Doc.

## Tasks

- [x] T1: Replace `BleService` stub with real class (header) keeping `begin()`/`started()`.
- [x] T2: Initialize NimBLE host in `begin()` (nvs, `nimble_port_init`, `ble_hs_cfg`, host task).
- [x] T3: Build + register the `ffe0` GATT service table with `ffe1`–`ffe7` characteristics.
- [x] T4: Implement characteristic read/write access callbacks (state → VehicleState snapshot).
- [x] T5: Start advertising from `sync_cb`; restart on disconnect via `gap_event_cb`.
- [x] T6: No NimBLE-Arduino — only esp-nimble headers; zero Arduino BLE matches.
- [x] T7: Build integration — CMake `SRCS`/`REQUIRES bt domain`, sdkconfig BT flags.
- [x] T8: Build verification — `idf.py build` exits 0, ble component compiles.
- [x] T9: Commit with comet-build message.

## Files

- `components/ble/include/ble/BleService.h` — class declaration.
- `components/ble/BleService.cpp` — NimBLE init, service table, callbacks, advertising.
- `components/ble/CMakeLists.txt` — SRCS + REQUIRES.
- `sdkconfig.defaults` — `CONFIG_BT_ENABLED` + `CONFIG_BT_NIMBLE_ENABLED`.
