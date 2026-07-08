# ble-config Specification

## ADDED Requirements

### Requirement: NimBLE GATT server initialization

The system SHALL bring up a BLE GATT server using the ESP-IDF v5.3 built-in NimBLE host (`esp-nimble`). `BleService::begin()` SHALL initialize the NimBLE port with `nimble_port_init`, configure `ble_hs_cfg` synchronization and reset callbacks, register the standard GAP and GATT services, set the advertised device name, register the application GATT service table with `ble_gatts_count_cfg` + `ble_gatts_add_svcs`, and start the NimBLE host task via `nimble_port_freertos_init`. `begin()` SHALL return `true` only when host initialization succeeds.

#### Scenario: Successful host bring-up

- WHEN `BleService::begin()` is called
- THEN the NimBLE host is initialized, the GATT service table is registered, the host task is started, `started()` returns `true`, and `begin()` returns `true`

#### Scenario: Host init failure

- WHEN `nimble_port_init` (or GATT registration) returns a non-`ESP_OK` result
- THEN `begin()` logs the error via `ESP_LOGE` and returns `false`, and no BLE peripheral is advertised

### Requirement: Primary configuration service on UUID ffe0

The system SHALL register a primary GATT service using the 128-bit UUID defined by `ble::kServiceUuid` (`0000ffe0-0000-1000-8000-00805f9b34fb`). The service definition SHALL be a static `ble_gatt_svc_def` entry of type `BLE_GATT_SVC_TYPE_PRIMARY` terminated by a zeroed sentinel.

#### Scenario: ffe0 service registered

- WHEN the GATT service table is registered during `begin()`
- THEN a primary service with UUID `ffe0` is present in the table and accepted by `ble_gatts_add_svcs` without error

### Requirement: Seven configuration characteristics ffe1 through ffe7

The `ffe0` service SHALL expose the seven characteristics declared in `BleUuids.h`: `ffe1` (config, `kConfigUuid`), `ffe2` (state, `kStateUuid`), `ffe3` (audio, `kAudioUuid`), `ffe4` (can, `kCanUuid`), `ffe5` (diagnostics, `kDiagnosticsUuid`), `ffe6` (profile, `kProfileUuid`), and `ffe7` (control, `kControlUuid`). Each characteristic SHALL declare the appropriate access flags (read and/or write) and a GATT access callback. The state characteristic (`ffe2`) SHALL, on read, serialize the current `domain::VehicleState` snapshot; write-capable characteristics SHALL parse the written buffer and apply it to the corresponding configuration or control target.

#### Scenario: All seven characteristics present

- WHEN the GATT service table is inspected after registration
- THEN characteristics `ffe1`, `ffe2`, `ffe3`, `ffe4`, `ffe5`, `ffe6`, and `ffe7` are all registered under the `ffe0` service, each with a read and/or write flag and an access callback

#### Scenario: State characteristic read returns vehicle state

- WHEN a connected client reads the `ffe2` state characteristic
- THEN the access callback appends a serialized `domain::VehicleState` snapshot to the response mbuf and returns success

#### Scenario: Config characteristic write applies value

- WHEN a connected client writes to a write-capable characteristic (e.g. `ffe1` config, `ffe6` profile, or `ffe7` control)
- THEN the access callback reads the written buffer from `ctxt->om`, validates its length, applies it to the target field, and returns `0`

### Requirement: Connectable advertising of the ffe0 service

The system SHALL advertise as connectable and general-discoverable once the NimBLE host has synced. The host sync callback SHALL populate `ble_hs_adv_fields` with LE general-discoverable flags, the `ffe0` service UUID, and the complete device name, then call `ble_gap_adv_start` with `BLE_GAP_CONN_MODE_UND` and `BLE_GAP_DISC_MODE_GEN`. Advertising SHALL be restarted when a connection is dropped.

#### Scenario: Advertising starts on host sync

- WHEN the NimBLE host sync callback fires after `begin()`
- THEN `ble_gap_adv_start` is invoked in connectable, general-discoverable mode advertising the `ffe0` service UUID and device name

#### Scenario: Advertising restarts on disconnect

- WHEN a central disconnects (`BLE_GAP_EVENT_DISCONNECT`)
- THEN the GAP event callback restarts advertising so the device remains discoverable

### Requirement: No NimBLE-Arduino dependency

The `ble::` module SHALL NOT depend on the `NimBLE-Arduino` library or any Arduino BLE class (`BLEDevice`, `BLEServer`, etc.). BLE functionality SHALL use only the ESP-IDF v5.3 built-in NimBLE host headers (`nimble/nimble_port.h`, `nimble/nimble_port_freertos.h`, `host/ble_hs.h`, `services/gap/ble_svc_gap.h`, `services/gatt/ble_svc_gatt.h`) provided by the `bt` component.

#### Scenario: No Arduino BLE includes

- WHEN all source files under `components/ble/` are searched for `NimBLE-Arduino`, `BLEDevice`, `BLEServer`, and `Arduino`
- THEN zero matches are found and only ESP-IDF built-in NimBLE headers are used
