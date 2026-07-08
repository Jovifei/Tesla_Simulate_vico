# ble-config Specification

## Purpose

BLE runtime configuration and telemetry channel for Tesla Simulate Vico.

Current contract keeps backward compatibility with existing 0xffe0 clients while adding the
PRD-2 contract on `0xfff0`.

## Requirements

### Requirement: NimBLE GATT server initialization

The system SHALL run the ESP-IDF v5.3 built-in NimBLE host (`esp-nimble`) only.
`BleService::begin()` SHALL initialize NVS for BLE store usage, call
`nimble_port_init`, configure `ble_hs_cfg.sync_cb` and `ble_hs_cfg.reset_cb`, register GAP/GATT services,
register application GATT services, set the BLE device name, and start the host task with
`nimble_port_freertos_init`.

#### Scenario: host bring-up success

- WHEN `BleService::begin()` is called
- THEN `ble_gatts_count_cfg` and `ble_gatts_add_svcs` are called successfully, `started()` returns `true`, and `begin()` returns `true`.

### Requirement: BLE service UUID contract (PRD + compatibility)

The system SHALL register:
- A PRD service: primary service UUID `0xfff0` (`ble::kServiceUuid`).
- A legacy compatibility service: primary service UUID `0xffe0` (`ble::kLegacyServiceUuid`).

#### Scenario: service registration

- WHEN `BleService::begin()` returns `true`
- THEN the GATT table includes both service UUIDs.

### Requirement: PRD characteristic expansion on `0xfff0`

The `0xfff0` service SHALL expose at least the following 14 characteristics:

`ffe1` config, `ffe2` state, `ffe3` audio, `ffe4` can, `ffe5` diagnostics,
`ffe6` profile, `ffe7` control, `ffe8` ota, `ffe9` gear, `ffea` device status,
`ffeb` max speed, `ffec` profile count, `ffed` autotune mode, `ffee` tune data.

`ffe1`, `ffe3`, `ffe4`, `ffe6`, `ffe7`, `ffe8`, `ffeb`, `ffec`, `ffed`, and `ffee`
SHALL be writable as documented.
`ffe2` and `ffea` SHALL support read + notify.

#### Scenario: PRD characteristics present

- WHEN a GATT client enumerates the PRD table
- THEN all listed UUIDs are present under `0xfff0` with expected access behavior.

### Requirement: WiFi OTA IoT settings characteristic contract on `ffe8`

`ffe8` SHALL keep the existing UUID assignment and SHALL expose WiFi, OTA, and IoT settings as UTF-8 JSON
over BLE read/write. The JSON contract SHALL include `ssid`, `password`, `ota_url`, and `auto_check`, and
MAY include `iot_enable`, `mqtt_uri`, `client_id`, `mqtt_username`, `mqtt_password`, `topic_up`,
`topic_down`, `device_id`, and `product_id`. BLE writes to `ffe8` SHALL update runtime configuration only.
Writing `ffe8` SHALL NOT start OTA immediately; any automatic OTA check governed by `auto_check` SHALL
occur on a later boot.

#### Scenario: OTA settings read/write over BLE

- WHEN a BLE client reads `ffe8`
- THEN the response is UTF-8 JSON containing `ssid`, `password`, `ota_url`, `auto_check`, and any stored IoT fields
- AND WHEN a BLE client writes valid UTF-8 JSON with those fields to `ffe8`
- THEN the runtime WiFi, OTA, and IoT settings are updated without changing the characteristic UUID contract

#### Scenario: IoT settings remain optional and type-checked

- WHEN a BLE client writes the original short OTA JSON with only `ssid`, `password`, `ota_url`, and `auto_check`
- THEN the write remains valid
- AND WHEN a known IoT key is present with the wrong JSON type
- THEN the write is rejected with a BLE attribute error

#### Scenario: BLE OTA write does not start OTA in-place

- WHEN a BLE client writes `ffe8` with `auto_check=true`
- THEN the device stores the requested OTA settings for later use
- AND OTA execution remains deferred until a subsequent boot path evaluates that persisted configuration

### Requirement: Legacy compatibility on `0xffe0`

For backward-compatible clients, `0xffe0` SHALL expose `ffe1` through `ffe7`
with read/write semantics described in previous firmware behavior.

#### Scenario: legacy compatibility

- WHEN a `0xffe0` client reads/writes `ffe1..ffe7`
- THEN handlers for config/state/audio/can/diagnostics/profile/control execute and return correct BLE ATT status.

### Requirement: State snapshot read

`ffe2` SHALL return a serialized `domain::VehicleState` snapshot on read.

#### Scenario: state is live

- WHEN `app::App` advances state in the main loop
- THEN it calls `BleService::publishVehicleState()` to refresh the snapshot for subsequent BLE reads.

### Requirement: Diagnostics and live status characteristics

`ffe5` SHALL return UTF-8 JSON diagnostics on read from `status::RuntimeStatus` with at least `version`,
`partition`, `wifi_state`, `iot_state`, `ota_state`, `ota_progress`, `ota_last_result`, and `last_error`.
`ffea` SHALL remain the live status characteristic and SHALL continue to support read + notify for current
device status updates.

#### Scenario: diagnostics snapshot includes OTA and WiFi state

- WHEN a BLE client reads `ffe5`
- THEN the response is UTF-8 JSON containing `version`, `partition`, `wifi_state`, `iot_state`, `ota_state`, `ota_progress`, `ota_last_result`, and `last_error`

#### Scenario: live status bitfield includes network and OTA bits

- WHEN `app::App` publishes the live status bitfield on `ffea`
- THEN bit 0 represents BLE started, bit 1 SD mounted, bit 2 CAN valid, bit 3 overspeed mute, bit 4 OTA config ready, bit 5 WiFi connected, bit 6 IoT cloud connected, and bit 7 OTA in progress

#### Scenario: live status channel remains unchanged

- WHEN runtime device status changes while a client is subscribed to `ffea`
- THEN the system publishes the updated live status on `ffea` without repurposing the characteristic for OTA settings

### Requirement: Connectable advertising and reconnect

Advertising SHALL be connectable and general-discoverable with service UUIDs `0xfff0` and `0xffe0`.
Advertising SHALL restart on disconnect/adv complete events so the device remains discoverable.

#### Scenario: advertising lifecycle

- WHEN host sync completes
- THEN advertising starts in connectable/discoverable mode.
- WHEN disconnect or adv-complete occurs
- THEN advertising restarts automatically.

### Requirement: no NimBLE-Arduino dependency

BLE SHALL use only ESP-IDF native headers (`nimble/nimble_port.h`, `nimble/nimble_port_freertos.h`,
`host/ble_hs.h`, `services/gap/ble_svc_gap.h`, `services/gatt/ble_svc_gatt.h`) and not use
NimBLE-Arduino classes.

#### Scenario: dependency boundary

- WHEN `ble/BleService.cpp` is built under ESP-IDF v5.3
- THEN implementation includes only native headers and does not reference NimBLE-Arduino symbols.
