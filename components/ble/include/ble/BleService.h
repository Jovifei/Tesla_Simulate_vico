#pragma once

#include <cstdint>

struct ble_gatt_access_ctxt;

namespace ble {

/// Real BLE GATT configuration server built on the ESP-IDF v5.3 built-in
/// NimBLE host (esp-nimble, the ESP-IDF built-in stack, not any third-party
/// wrapper library). Stands up the primary service
/// `ffe0` with characteristics `ffe1`..`ffe7` and advertises connectably as
/// "Tesla-Vico". Keeps the stub's `begin()` / `started()` surface so the
/// `app::App` wiring is unchanged.
class BleService {
public:
    /// Bring up the NimBLE host: nvs init, nimble_port_init, ble_hs_cfg
    /// callbacks, GATT service registration, device name, and the FreeRTOS
    /// host task. Returns true only on successful host initialization.
    bool begin();

    /// True once the NimBLE host task has been started.
    bool started() const { return started_; }

private:
    /// Single GATT access dispatch callback shared by all characteristics.
    static int gatt_svr_cb(uint16_t conn_handle,
                           uint16_t attr_handle,
                           struct ble_gatt_access_ctxt* ctxt,
                           void* arg);

    bool started_ = false;
};

}  // namespace ble
