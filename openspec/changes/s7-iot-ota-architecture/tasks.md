# Tasks: s7-iot-ota-architecture

- [x] **T0: Change framing**
  - Add plan/docs entries and this change manifest under `openspec/changes/s7-iot-ota-architecture`
  - Run `openspec validate s7-iot-ota-architecture --strict` (or equivalent review equivalent command path used in this repo)

- [x] **T1: status component**
  - Add `components/status` and `status::RuntimeStatus` types and helpers.
  - `diagnosticsJson()` outputs JSON fields required by BLE `ffe5`.

- [x] **T2: RuntimeConfig extension**
  - Add helper methods `wifiConfigReady` / `otaConfigReady` / `iotConfigReady`.
  - Extend SD JSON load/save with new WiFi/OTA/IoT fields.

- [x] **T3: BLE ffe8 extension**
  - Accept optional IoT fields in known JSON.
  - Retain old `ssid/password/ota_url/auto_check` fields for compatibility.
  - Reject malformed/oversize payloads with BLE attribute error.

- [x] **T4: network component**
  - Add `components/network` with background network task and status bits.
  - Add begin/seed/start/request/reconnect/stop APIs.

- [x] **T5: ota component refactor**
  - Add `ota::OtaRequest` and `OtaTrigger`.
  - Replace direct one-shot OTA path with request-driven state machine.

- [x] **T6: iot component**
  - Add MQTT init/publish/subscribe and `ota_start` request parsing.
  - Add `takePendingOtaRequest()`.

- [x] **T7: app integration**
  - Compose `status/network/ota/iot` in `App`.
  - Merge status sources and publish `ffe5`/`ffea`.

- [x] **T8: docs + gates**
  - Update affected OpenSpec, `README`, `PLAN`, `docs/*` status docs.
  - Re-run `idf.py build` / `size` / `size-components` / `openspec validate --all --strict --json`.
