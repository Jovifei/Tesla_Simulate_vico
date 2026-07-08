# Design: s7-iot-ota-architecture

## Module Split

```text
App
  |-- status   : shared runtime status model and diagnostics JSON
  |-- network  : WiFi STA init, connect, reconnect, stop, link state
  |-- iot      : MQTT connect, publish, subscribe, downlink command adapter
  |-- ota      : HTTPS OTA request queue, worker task, progress, rollback status
  |-- ble      : UUID-stable config entry and diagnostics/status readback
```

## BLE Contract

- Primary service remains `0xfff0`.
- Compatibility service remains `0xffe0`.
- `ffe8` remains the single BLE settings endpoint for WiFi / OTA / IoT JSON.
- BLE writes do not execute OTA directly.

## Runtime Status

`status::RuntimeStatus` carries:

- `version`
- `partition`
- `wifi_state`
- `iot_state`
- `ota_state`
- `ota_progress_pct`
- `ota_last_result`
- `last_error`
- `device_status_bits`

`ffe5` returns diagnostics JSON from the merged runtime status. `ffea` carries the live device bitfield.

## Network Layer

`network::NetworkManager` owns:

- ESP netif and event loop setup.
- WiFi STA configuration.
- EventGroup bits for configured, connected, failed, reconnect requested, and stop requested.
- Background network task.
- `connected()` and `copyStatus()` for App/BLE status reporting.

## IoT Layer

`iot::IotManager` owns:

- MQTT client start/stop.
- Uplink publish for device info, vehicle state, and OTA progress.
- Downlink JSON parsing.
- `ota_start` conversion into `ota::OtaRequest`.

## OTA Layer

`ota::OtaManager` owns:

- Boot validity confirmation.
- `ota::OtaRequest` queueing.
- Worker-task HTTPS OTA download/apply.
- Running flag, progress, result, version, partition, and last error.

## App Integration

`App` remains the coordinator:

- Load config from SD.
- Seed BLE/network/iot/ota with config.
- Poll encoder, throttle, CAN, and BLE pending config updates.
- Save accepted runtime config updates.
- Pull cloud OTA requests from IoT and pass them to OTA.
- Merge network/iot/ota status and publish BLE diagnostics/status.
- Keep WiFi/MQTT/OTA blocking work out of the 25 ms vehicle simulation path.
