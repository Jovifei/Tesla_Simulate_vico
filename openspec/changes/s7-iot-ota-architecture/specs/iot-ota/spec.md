# iot-ota Architecture Specification

## ADDED Requirements

### Requirement: Runtime status and diagnostics data model

The system SHALL expose a `status::RuntimeStatus` model with WiFi, IoT, OTA, version, partition, OTA progress, last result, last error, and live device status bits. BLE, IoT, Network, and OTA components SHALL use this model or compatible snapshots for diagnostics.

#### Scenario: App polls runtime status

- WHEN `app::App::tick()` runs
- THEN it SHALL read status snapshots from `status`, `network`, `iot`, and `ota` components and avoid blocking operations inside tick

#### Scenario: BLE diagnostics come from unified status

- WHEN a BLE client reads `ffe5`
- THEN the diagnostics JSON SHALL be derived from the merged runtime status instead of one module-specific temporary status object

### Requirement: Request-driven OTA execution

The system SHALL queue OTA intents through `ota::OtaRequest` and execute OTA only in the OTA worker task. OTA requests MAY come from boot-time persisted config or MQTT downlink commands.

#### Scenario: OTA request from BLE or boot config runs asynchronously

- WHEN BLE or boot config updates `ota::OtaRequest`
- THEN `ota::OtaManager` SHALL mark request state as pending and process it in a background task (not inline in `BleService`/`App::tick()`)

#### Scenario: Cloud OTA request runs asynchronously

- WHEN `iot::IotManager` accepts an MQTT `ota_start` command
- THEN App SHALL pass the pending request to `ota::OtaManager`
- AND OTA execution SHALL continue in the OTA worker task without blocking the 25 ms App loop

### Requirement: Network and IoT runtime split

The system SHALL keep WiFi and MQTT in separate components and use `ffe8` as the BLE runtime settings input path for WiFi, OTA, and IoT fields.

#### Scenario: Network and cloud remain decoupled

- WHEN WiFi is not configured or disconnected
- THEN `iot::IotManager` SHALL not crash and SHALL surface IoT state via `RuntimeStatus`

#### Scenario: BLE settings are applied by App coordinator

- WHEN `ffe8` setting payload updates are valid
- THEN App SHALL hand off parsed config to `network`/`iot`/`ota` components and persist via existing SD path without changing BLE UUIDs

### Requirement: MQTT cloud adapter

The system SHALL use an IoT/MQTT manager to publish device information, vehicle state, OTA progress, and command acknowledgements to configured topics, and to parse downlink JSON commands.

#### Scenario: OTA start command accepted

- WHEN the downlink JSON method is `ota_start` and contains a non-empty HTTPS URL
- THEN the IoT manager SHALL convert it to an `ota::OtaRequest`
- AND it SHALL publish an acknowledgement with code `0` when the request is accepted

#### Scenario: Downlink rejected

- WHEN a downlink JSON message is malformed, oversize, has an unknown method, or cannot be queued
- THEN the IoT manager SHALL publish a non-zero acknowledgement code and SHALL NOT crash or block the App tick
