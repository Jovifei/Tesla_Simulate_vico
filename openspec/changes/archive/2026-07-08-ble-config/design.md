# Design: ble-config

**Change:** ble-config
**Date:** 2026-07-08
**Status:** Initial sketch (open phase)

## 1. Overview

S3 replaces the memory-only `ble::BleService` stub with a real BLE GATT
configuration server built on the ESP-IDF v5.3 built-in NimBLE host
(`esp-nimble`, **not** `NimBLE-Arduino`). The server stands up the primary
service on UUID `ffe0` with seven characteristics (`ffe1`–`ffe7`) covering
config, state, audio, can, diagnostics, profile, and control, and advertises
connectably so a companion app can discover, connect, read live vehicle state,
and write configuration/control parameters. Namespace stays `ble::`.

**Target files:**
- `components/ble/include/ble/BleService.h` — real class declaration (replaces stub, namespace `ble::`)
- `components/ble/BleService.cpp` — NimBLE init, GATT service table, advertising, characteristic access callbacks
- `components/ble/CMakeLists.txt` — add `.cpp` to SRCS, add `bt` (and `domain`) to REQUIRES

`BleUuids.h` (UUID constants) is reused unchanged. `domain::VehicleState` is
frozen — consumed read-only by the state characteristic.

## 2. Architecture

```
begin()
  ├─ nvs_flash_init()                            // PHY cal data (idempotent, erase+retry)
  ├─ nimble_port_init()                          // init controller + host (esp_err_t)
  ├─ ble_hs_cfg.sync_cb          = bleprph_on_sync   // → advertise once synced
  │  ble_hs_cfg.reset_cb         = bleprph_on_reset
  │  ble_hs_cfg.gatts_register_cb= gatt_svr_register_cb (optional, log-only)
  │  ble_hs_cfg.store_status_cb  = ble_store_util_status_rr
  ├─ gatt_svr_init():
  │     ble_svc_gap_init()
  │     ble_svc_gatt_init()
  │     ble_gatts_count_cfg(svc_table)           // rc==0 else return false
  │     ble_gatts_add_svcs(svc_table)            // ffe0 + ffe1..ffe7
  ├─ ble_svc_gap_device_name_set("Tesla-Vico")   // advertised name
  └─ nimble_port_freertos_init(nimble_host_task) // spawn host event loop task

nimble_host_task(param) → nimble_port_run(); nimble_port_freertos_deinit();

bleprph_on_sync() →
   ble_hs_util_ensure_addr(0)                    // ensure a valid identity addr
   ble_hs_id_infer_auto(0, &own_addr_type)       // pick own address type
   ble_gap_adv_start(own_addr_type, NULL, BLE_HS_FOREVER,
                     &adv_params, gap_event_cb, NULL)   // connectable, general disc.

GATT access callback (single dispatch cb, keyed on attr_handle / ctxt->chr->uuid):
   read  → os_mbuf_append(ctxt->om, &value, len)  (ffe2 → VehicleState snapshot)
   write → ble_hs_mbuf_to_flat(ctxt->om, dst, max, &len) → apply to config/control
```

## 3. Service / Characteristic Table

Primary service UUID `ffe0` (`ble::kServiceUuid`), 7 characteristics from `BleUuids.h`:

| UUID | Constant | Purpose | Access |
|------|----------|---------|--------|
| ffe1 | kConfigUuid | General config blob | read + write |
| ffe2 | kStateUuid | Live `domain::VehicleState` snapshot | read (+ notify later) |
| ffe3 | kAudioUuid | Audio synth params (limits, amplitude) | read + write |
| ffe4 | kCanUuid | CAN signal mapping params | read + write |
| ffe5 | kDiagnosticsUuid | Diagnostics / counters | read |
| ffe6 | kProfileUuid | Selected engine sound profile | read + write |
| ffe7 | kControlUuid | Runtime control (mute, restart) | write |

Each characteristic UUID is a 16-bit SIG-form UUID (`0xffe0`..`0xffe7`) — the
`BleUuids.h` strings are the canonical `0000ffeX-0000-1000-8000-00805f9b34fb`
Bluetooth base, so the runtime table uses `BLE_UUID16_INIT(0xffe0)` …
`BLE_UUID16_INIT(0xffe7)` (`static const ble_uuid16_t`). This keeps the wire
UUIDs identical to `BleUuids.h` while avoiding hand-parsing 128-bit strings.
The service table is a static `struct ble_gatt_svc_def[]` terminated by a
`{0}` sentinel, with a `struct ble_gatt_chr_def[]` (also `{0}`-terminated) for
the seven characteristics. `BleUuids.h` remains the documented source of truth
for the UUID values; a `static_assert`-style comment ties the two together.

## 4. NimBLE Initialization (ESP-IDF v5.3)

`begin()` uses the built-in NimBLE host exclusively:

- `nvs_flash_init()` — NimBLE stores PHY calibration in NVS; erase+retry on
  `ESP_ERR_NVS_NO_FREE_PAGES` / `ESP_ERR_NVS_NEW_VERSION_FOUND`.
- `nimble_port_init()` — brings up the BLE controller and NimBLE host stack
  (returns `esp_err_t`; non-`ESP_OK` → `ESP_LOGE` + return `false`).
- Configure `ble_hs_cfg`: `sync_cb = bleprph_on_sync`, `reset_cb = bleprph_on_reset`,
  and `store_status_cb = ble_store_util_status_rr` (no bonding/SM for first cut).
- `gatt_svr_init()`: `ble_svc_gap_init()`, `ble_svc_gatt_init()`, then
  `ble_gatts_count_cfg(svc_table)` and `ble_gatts_add_svcs(svc_table)`
  (each `rc != 0` → `ESP_LOGE` + return `false`).
- `ble_svc_gap_device_name_set("Tesla-Vico")` — advertised device name.
- `nimble_port_freertos_init(nimble_host_task)` — spawn the host task that runs
  `nimble_port_run()`; `started_ = true; return true`.

The C-linkage callbacks (`bleprph_on_sync`, `bleprph_on_reset`,
`nimble_host_task`, `gap_event_cb`, `gatt_svr_cb`) are file-static functions in
`BleService.cpp` (declared `extern "C"` where NimBLE takes a function pointer);
`gatt_svr_cb` is exposed as a `static` member per the class contract and wraps
the free dispatch function.

**No `NimBLE-Arduino`, no Arduino `BLEDevice`/`BLEServer` classes** — only the
ESP-IDF component `bt` (`host/ble_hs.h`, `services/gap/ble_svc_gap.h`,
`services/gatt/ble_svc_gatt.h`, `nimble/nimble_port.h`, `nimble/nimble_port_freertos.h`).

## 5. Advertising

`bleprph_on_sync()` (fired when the host is ready) starts advertising:
- `ble_hs_util_ensure_addr(0)` then `ble_hs_id_infer_auto(0, &own_addr_type)`
  to obtain a valid identity address and own-address type before any GAP call.
- `struct ble_hs_adv_fields`: flags (`BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP`),
  auto TX power, the `ffe0` service UUID (`uuids16` = `BLE_UUID16_INIT(0xffe0)`,
  `num_uuids16 = 1`, `uuids16_is_complete = 1`), and the complete device name
  from `ble_svc_gap_device_name()`. Set via `ble_gap_adv_set_fields(&fields)`.
- `struct ble_gap_adv_params` with `conn_mode = BLE_GAP_CONN_MODE_UND`
  (connectable) and `disc_mode = BLE_GAP_DISC_MODE_GEN` (general discoverable),
  then `ble_gap_adv_start(own_addr_type, NULL, BLE_HS_FOREVER, &adv_params,
  gap_event_cb, NULL)`.
- `gap_event_cb` handles `BLE_GAP_EVENT_CONNECT` /
  `BLE_GAP_EVENT_DISCONNECT` / `BLE_GAP_EVENT_ADV_COMPLETE` — re-invoking the
  advertise routine on disconnect / adv-complete so the device stays discoverable.
  (`BLE_GAP_EVENT_LINK_ESTAB` is also handled where the v5.3 host emits it on
  connection establishment; a failed connect resumes advertising.)

## 6. Characteristic Access Callbacks

One `gatt_access_cb(conn_handle, attr_handle, ctxt, arg)` (or per-char callbacks)
dispatches on `ctxt->op`:
- `BLE_GATT_ACCESS_OP_READ_CHR` → `os_mbuf_append(ctxt->om, &value, len)`.
  For `ffe2` state, serialize the current `domain::VehicleState` snapshot.
- `BLE_GATT_ACCESS_OP_WRITE_CHR` → read `ctxt->om` (`ble_hs_mbuf_to_flat`),
  validate length, apply to the target config/control field.
- Return `0` on success, a `BLE_ATT_ERR_*` code on failure.

## 7. Key Decisions

1. **esp-nimble, not NimBLE-Arduino**: ESP-IDF v5.3 bundles NimBLE as the `bt`
   component; the Arduino wrapper is out of scope and violates the hard rule.
2. **Keep `begin()`/`started()` surface**: minimizes churn at the call site;
   the app wiring that calls `BleService::begin()` stays unchanged.
3. **Advertise on sync, not in begin()**: NimBLE requires the host to be synced
   before GAP calls; advertising is kicked off from `sync_cb`.
4. **Static service table**: `ble_gatt_svc_def[]` built at compile time from the
   `BleUuids.h` constants — simple, no dynamic allocation.
5. **Read-only VehicleState coupling**: the state characteristic reads a snapshot;
   S1/S2 pipelines are frozen and untouched.

## 8. Build Integration

**`components/ble/CMakeLists.txt`:**
- Add `BleService.cpp` to `SRCS`.
- Add `bt` to `REQUIRES` (NimBLE host lives in the ESP-IDF `bt` component).
- Add `domain` to `REQUIRES` (for `VehicleState.h`).
- Keep `INCLUDE_DIRS include`.

`sdkconfig.defaults` must enable Bluetooth + NimBLE host
(`CONFIG_BT_ENABLED`, `CONFIG_BT_NIMBLE_ENABLED`) if not already set.

## 9. Test Strategy

S3 targets on-target build + behavioral verification (BLE is hardware/RF; the
host stack is not host-unit-testable without mocks):

| Layer | Method | Pass criterion |
|---|---|---|
| Compile | `idf.py build` | BleService compiles against the `bt` NimBLE headers, no ble-component errors |
| Static (no Arduino) | grep `components/ble/` for `NimBLE-Arduino`, `BLEDevice`, `Arduino` | zero matches; only esp-nimble headers |
| Service table | Code review: `ffe0` + `ffe1`..`ffe7` present, `{0}`-terminated | all 7 chars registered |
| Advertising | Code review: `ble_gap_adv_start` from `sync_cb`, restart on disconnect | connectable + discoverable |

## 10. Risks

1. **NimBLE async init**: GAP calls before `sync_cb` fail; advertising must be
   deferred to the sync callback. Mitigation: kick advertising only from `sync_cb`.
2. **sdkconfig BT flags**: build fails if `CONFIG_BT_NIMBLE_ENABLED` is off.
   Mitigation: ensure `sdkconfig.defaults` enables NimBLE.
3. **Characteristic payload formats**: config/audio/can blobs need a stable
   binary layout agreed with the app; first cut is a placeholder struct.
4. **Flash/RAM budget**: NimBLE adds significant footprint; monitor build size.
5. **VehicleState serialization**: exposing a raw struct couples the wire format
   to internal layout; a versioned packed format is deferred.
