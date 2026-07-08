# Tasks: ble-config

## S3 — BLE GATT Configuration Service (NimBLE)

- [x] **T1: Replace BleService stub with real class** — Rewrite `components/ble/include/ble/BleService.h` and add `components/ble/BleService.cpp` keeping the existing `begin()`/`started()` surface. Namespace `ble::`. Uses ESP-IDF built-in NimBLE (`esp-nimble`) — NOT `NimBLE-Arduino`.

- [x] **T2: Initialize NimBLE host in begin()** — Call `nimble_port_init()`, configure `ble_hs_cfg` (`sync_cb`, `reset_cb`), run `ble_svc_gap_init()` / `ble_svc_gatt_init()`, set device name via `ble_svc_gap_device_name_set`, and start the host task with `nimble_port_freertos_init`. Return `true` on success, `false` + `ESP_LOGE` on failure.

- [x] **T3: Build and register the GATT service table** — Define a static `ble_gatt_svc_def[]` for the `ffe0` primary service (`ble::kServiceUuid`) with the seven characteristics from `BleUuids.h`: `ffe1` config, `ffe2` state, `ffe3` audio, `ffe4` can, `ffe5` diagnostics, `ffe6` profile, `ffe7` control. Register with `ble_gatts_count_cfg` + `ble_gatts_add_svcs`.

- [x] **T4: Implement characteristic read/write access callbacks** — Dispatch on `ctxt->op`: reads append the current value to `ctxt->om` (state characteristic serializes a `domain::VehicleState` snapshot); writes parse `ctxt->om` and apply to the target config/control field. Return `0` on success, `BLE_ATT_ERR_*` on failure.

- [x] **T5: Start advertising** — In the host `sync_cb`, populate `ble_hs_adv_fields` (flags, `ffe0` service UUID, device name) and call `ble_gap_adv_start` with connectable / general-discoverable mode. Handle connect/disconnect in `gap_event_cb`; restart advertising on disconnect.

- [x] **T6: No NimBLE-Arduino static check** — Grep `components/ble/` for `NimBLE-Arduino`, `BLEDevice`, `BLEServer`, and `Arduino` — zero matches. Only esp-nimble headers (`host/ble_hs.h`, `nimble/nimble_port.h`, `services/gap`, `services/gatt`) are included.

- [x] **T7: Build integration** — Update `components/ble/CMakeLists.txt`: add `BleService.cpp` to `SRCS`, add `bt` and `domain` to `REQUIRES`. Ensure `sdkconfig.defaults` enables `CONFIG_BT_ENABLED` + `CONFIG_BT_NIMBLE_ENABLED`.

- [x] **T8: Build verification** — `idf.py build` succeeds with no errors from the ble component. Confirm `BleService` compiles against the NimBLE `bt` headers and the frozen `domain::VehicleState`.

- [x] **T9: Commit** — Commit with comet-build message. Verify build clean.
