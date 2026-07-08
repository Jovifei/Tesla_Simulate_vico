#pragma once

#include <cstdint>

#include "config/runtime_config.h"
// domain::VehicleState is intentionally included here so callers can stream
// a snapshot into BLE state for read/notify flows.
#include "domain/VehicleState.h"
#include "ota/OtaStatus.h"

struct ble_gatt_access_ctxt;

namespace ble {

/// Real BLE GATT configuration server built on the ESP-IDF v5.3 built-in
/// NimBLE host (esp-nimble, the ESP-IDF built-in stack, not any third-party
/// wrapper library). Stands up the primary service `fff0` with characteristics
/// `ffe1`..`ffeE` per PRD, while keeping `ffe0/ffe1..ffe7` compatibility.
class BleService {
public:
    /// Bring up the NimBLE host: nvs init, nimble_port_init, ble_hs_cfg
    /// callbacks, GATT service registration, device name, and the FreeRTOS
    /// host task. Returns true only on successful host initialization.
    bool begin();

    /// True once the NimBLE host task has been started.
    bool started() const { return started_; }

    /// Seeds the BLE-side runtime-config view from the current persisted config.
    void seedRuntimeConfig(const config::RuntimeConfig& cfg);

    /// Returns a pending config update written through BLE and clears the pending flag.
    bool takePendingRuntimeConfig(config::RuntimeConfig& cfg);

    /// Pushes a latest vehicle-state snapshot for BLE read/notify characteristics.
    void publishVehicleState(const domain::VehicleState& state);

    /// Pushes OTA / WiFi status for diagnostics and status characteristics.
    void publishOtaStatus(const ota::OtaStatus& status);

    /// Pushes a compact device-status bitfield for `ffea`.
    void publishDeviceStatus(std::uint32_t status);

private:
    /// Single GATT access dispatch callback shared by all characteristics.
    static int gatt_svr_cb(uint16_t conn_handle,
                           uint16_t attr_handle,
                           struct ble_gatt_access_ctxt* ctxt,
                           void* arg);

    bool started_ = false;
};

}  // namespace ble
