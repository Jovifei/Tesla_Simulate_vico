// BleService.cpp — S3 NimBLE GATT configuration server.
//
// Uses the ESP-IDF v5.3 built-in NimBLE host (esp-nimble) exclusively.
// Deliberately avoids any BLE wrapper library and its wrapper classes:
// only the esp-nimble headers below are included.
//
// Primary service ffe0 with characteristics ffe1..ffe7 (see BleUuids.h),
// advertised connectably as "Tesla-Vico". The ffe2 (state) characteristic
// serializes a domain::VehicleState snapshot on read; write-capable
// characteristics parse the written buffer into placeholder config storage.

#include "ble/BleService.h"
#include "ble/BleUuids.h"
#include "domain/VehicleState.h"

#include <cstring>

#include "esp_log.h"
#include "nvs_flash.h"

#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_uuid.h"
#include "host/util/util.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"

namespace {

constexpr const char* kTag        = "ble";
constexpr const char* kDeviceName = "Tesla-Vico";

// Own address type resolved on host sync, used for advertising.
uint8_t g_own_addr_type = 0;

// ---------------------------------------------------------------------------
// Characteristic UUIDs — 16-bit SIG form (0xffe0..0xffe7). Identical on the
// wire to the BleUuids.h 0000ffeX-0000-1000-8000-00805f9b34fb base strings.
// ---------------------------------------------------------------------------
constexpr uint16_t kSvcUuid16         = 0xffe0;  // ble::kServiceUuid
constexpr uint16_t kConfigUuid16      = 0xffe1;  // ble::kConfigUuid
constexpr uint16_t kStateUuid16       = 0xffe2;  // ble::kStateUuid
constexpr uint16_t kAudioUuid16       = 0xffe3;  // ble::kAudioUuid
constexpr uint16_t kCanUuid16         = 0xffe4;  // ble::kCanUuid
constexpr uint16_t kDiagnosticsUuid16 = 0xffe5;  // ble::kDiagnosticsUuid
constexpr uint16_t kProfileUuid16     = 0xffe6;  // ble::kProfileUuid
constexpr uint16_t kControlUuid16     = 0xffe7;  // ble::kControlUuid

const ble_uuid16_t g_svc_uuid         = BLE_UUID16_INIT(kSvcUuid16);
const ble_uuid16_t g_config_uuid      = BLE_UUID16_INIT(kConfigUuid16);
const ble_uuid16_t g_state_uuid       = BLE_UUID16_INIT(kStateUuid16);
const ble_uuid16_t g_audio_uuid       = BLE_UUID16_INIT(kAudioUuid16);
const ble_uuid16_t g_can_uuid         = BLE_UUID16_INIT(kCanUuid16);
const ble_uuid16_t g_diagnostics_uuid = BLE_UUID16_INIT(kDiagnosticsUuid16);
const ble_uuid16_t g_profile_uuid     = BLE_UUID16_INIT(kProfileUuid16);
const ble_uuid16_t g_control_uuid     = BLE_UUID16_INIT(kControlUuid16);

// ---------------------------------------------------------------------------
// Placeholder in-memory storage. The wire layout for config/audio/can/profile
// blobs is a documented follow-up (design.md §10). First cut is raw buffers.
// ---------------------------------------------------------------------------
domain::VehicleState g_state_snapshot{};       // ffe2: live vehicle state (read)
uint8_t              g_config_blob[64]  = {0};  // ffe1
uint8_t              g_audio_blob[32]   = {0};  // ffe3
uint8_t              g_can_blob[32]     = {0};  // ffe4
uint8_t              g_diagnostics[32]  = {0};  // ffe5 (read-only counters)
uint8_t              g_profile_id       = 0;    // ffe6
uint8_t              g_control_reg      = 0;    // ffe7 (write: mute/restart)

// Forward declaration; the class member wraps this dispatch table.
int gatt_access(uint16_t conn_handle, uint16_t attr_handle,
                struct ble_gatt_access_ctxt* ctxt, void* arg);

// ---------------------------------------------------------------------------
// GATT service table: ffe0 primary service + ffe1..ffe7 characteristics.
// ---------------------------------------------------------------------------
const struct ble_gatt_svc_def g_gatt_svcs[] = {
    {
        .type            = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid            = &g_svc_uuid.u,
        .includes        = nullptr,
        .characteristics = (struct ble_gatt_chr_def[]){
            {
                .uuid       = &g_config_uuid.u,
                .access_cb  = gatt_access,
                .arg        = nullptr,
                .descriptors = nullptr,
                .flags      = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE,
                .min_key_size = 0,
                .val_handle = nullptr,
            },
            {
                .uuid       = &g_state_uuid.u,
                .access_cb  = gatt_access,
                .arg        = nullptr,
                .descriptors = nullptr,
                .flags      = BLE_GATT_CHR_F_READ,
                .min_key_size = 0,
                .val_handle = nullptr,
            },
            {
                .uuid       = &g_audio_uuid.u,
                .access_cb  = gatt_access,
                .arg        = nullptr,
                .descriptors = nullptr,
                .flags      = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE,
                .min_key_size = 0,
                .val_handle = nullptr,
            },
            {
                .uuid       = &g_can_uuid.u,
                .access_cb  = gatt_access,
                .arg        = nullptr,
                .descriptors = nullptr,
                .flags      = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE,
                .min_key_size = 0,
                .val_handle = nullptr,
            },
            {
                .uuid       = &g_diagnostics_uuid.u,
                .access_cb  = gatt_access,
                .arg        = nullptr,
                .descriptors = nullptr,
                .flags      = BLE_GATT_CHR_F_READ,
                .min_key_size = 0,
                .val_handle = nullptr,
            },
            {
                .uuid       = &g_profile_uuid.u,
                .access_cb  = gatt_access,
                .arg        = nullptr,
                .descriptors = nullptr,
                .flags      = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_WRITE,
                .min_key_size = 0,
                .val_handle = nullptr,
            },
            {
                .uuid       = &g_control_uuid.u,
                .access_cb  = gatt_access,
                .arg        = nullptr,
                .descriptors = nullptr,
                .flags      = BLE_GATT_CHR_F_WRITE,
                .min_key_size = 0,
                .val_handle = nullptr,
            },
            {
                0,  // No more characteristics in this service.
            },
        },
    },
    {
        0,  // No more services.
    },
};

// Read helper: append a flat buffer to the response mbuf.
int chr_read(struct ble_gatt_access_ctxt* ctxt, const void* src, uint16_t len) {
    const int rc = os_mbuf_append(ctxt->om, src, len);
    return rc == 0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
}

// Write helper: flatten the incoming mbuf into a destination buffer with length
// validation.
int chr_write(struct os_mbuf* om, uint16_t max_len, void* dst, uint16_t* out_len) {
    const uint16_t om_len = OS_MBUF_PKTLEN(om);
    if (om_len > max_len) {
        return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    }
    const int rc = ble_hs_mbuf_to_flat(om, dst, max_len, out_len);
    return rc == 0 ? 0 : BLE_ATT_ERR_UNLIKELY;
}

int gatt_access(uint16_t conn_handle, uint16_t attr_handle,
                struct ble_gatt_access_ctxt* ctxt, void* arg) {
    (void)conn_handle;
    (void)attr_handle;
    (void)arg;

    const ble_uuid_t* uuid = ctxt->chr->uuid;

    switch (ctxt->op) {
    case BLE_GATT_ACCESS_OP_READ_CHR:
        if (ble_uuid_cmp(uuid, &g_state_uuid.u) == 0) {
            // ffe2: serialize the current VehicleState snapshot.
            return chr_read(ctxt, &g_state_snapshot, sizeof(g_state_snapshot));
        }
        if (ble_uuid_cmp(uuid, &g_config_uuid.u) == 0) {
            return chr_read(ctxt, g_config_blob, sizeof(g_config_blob));
        }
        if (ble_uuid_cmp(uuid, &g_audio_uuid.u) == 0) {
            return chr_read(ctxt, g_audio_blob, sizeof(g_audio_blob));
        }
        if (ble_uuid_cmp(uuid, &g_can_uuid.u) == 0) {
            return chr_read(ctxt, g_can_blob, sizeof(g_can_blob));
        }
        if (ble_uuid_cmp(uuid, &g_diagnostics_uuid.u) == 0) {
            return chr_read(ctxt, g_diagnostics, sizeof(g_diagnostics));
        }
        if (ble_uuid_cmp(uuid, &g_profile_uuid.u) == 0) {
            return chr_read(ctxt, &g_profile_id, sizeof(g_profile_id));
        }
        return BLE_ATT_ERR_UNLIKELY;

    case BLE_GATT_ACCESS_OP_WRITE_CHR:
        if (ble_uuid_cmp(uuid, &g_config_uuid.u) == 0) {
            return chr_write(ctxt->om, sizeof(g_config_blob), g_config_blob, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_audio_uuid.u) == 0) {
            return chr_write(ctxt->om, sizeof(g_audio_blob), g_audio_blob, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_can_uuid.u) == 0) {
            return chr_write(ctxt->om, sizeof(g_can_blob), g_can_blob, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_profile_uuid.u) == 0) {
            return chr_write(ctxt->om, sizeof(g_profile_id), &g_profile_id, nullptr);
        }
        if (ble_uuid_cmp(uuid, &g_control_uuid.u) == 0) {
            return chr_write(ctxt->om, sizeof(g_control_reg), &g_control_reg, nullptr);
        }
        return BLE_ATT_ERR_UNLIKELY;

    default:
        return BLE_ATT_ERR_UNLIKELY;
    }
}

int gatt_svr_init() {
    ble_svc_gap_init();
    ble_svc_gatt_init();

    int rc = ble_gatts_count_cfg(g_gatt_svcs);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_gatts_count_cfg failed; rc=%d", rc);
        return rc;
    }
    rc = ble_gatts_add_svcs(g_gatt_svcs);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_gatts_add_svcs failed; rc=%d", rc);
        return rc;
    }
    return 0;
}

int gap_event_cb(struct ble_gap_event* event, void* arg);

// Populate advertising fields and start connectable, general-discoverable
// advertising of the ffe0 service.
void start_advertising() {
    struct ble_hs_adv_fields fields;
    std::memset(&fields, 0, sizeof(fields));

    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;

    fields.tx_pwr_lvl_is_present = 1;
    fields.tx_pwr_lvl            = BLE_HS_ADV_TX_PWR_LVL_AUTO;

    const char* name = ble_svc_gap_device_name();
    fields.name             = reinterpret_cast<uint8_t*>(const_cast<char*>(name));
    fields.name_len         = static_cast<uint8_t>(std::strlen(name));
    fields.name_is_complete = 1;

    ble_uuid16_t adv_svc_uuid = BLE_UUID16_INIT(kSvcUuid16);
    fields.uuids16             = &adv_svc_uuid;
    fields.num_uuids16         = 1;
    fields.uuids16_is_complete = 1;

    int rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_gap_adv_set_fields failed; rc=%d", rc);
        return;
    }

    struct ble_gap_adv_params adv_params;
    std::memset(&adv_params, 0, sizeof(adv_params));
    adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;  // connectable
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;  // general discoverable

    rc = ble_gap_adv_start(g_own_addr_type, nullptr, BLE_HS_FOREVER,
                           &adv_params, gap_event_cb, nullptr);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_gap_adv_start failed; rc=%d", rc);
        return;
    }
    ESP_LOGI(kTag, "advertising as '%s' (service ffe0)", name);
}

int gap_event_cb(struct ble_gap_event* event, void* arg) {
    (void)arg;
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        ESP_LOGI(kTag, "GAP connect; status=%d", event->connect.status);
        if (event->connect.status != 0) {
            // Connection failed; resume advertising.
            start_advertising();
        }
        return 0;

#ifdef BLE_GAP_EVENT_LINK_ESTAB
    case BLE_GAP_EVENT_LINK_ESTAB:
        ESP_LOGI(kTag, "GAP link established; status=%d", event->link_estab.status);
        if (event->link_estab.status != 0) {
            start_advertising();
        }
        return 0;
#endif

    case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGI(kTag, "GAP disconnect; reason=%d", event->disconnect.reason);
        start_advertising();  // stay discoverable
        return 0;

    case BLE_GAP_EVENT_ADV_COMPLETE:
        ESP_LOGI(kTag, "advertise complete; reason=%d", event->adv_complete.reason);
        start_advertising();
        return 0;

    default:
        return 0;
    }
}

void on_host_sync() {
    // Ensure a valid identity address, then infer the own-address type.
    int rc = ble_hs_util_ensure_addr(0);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_hs_util_ensure_addr failed; rc=%d", rc);
        return;
    }
    rc = ble_hs_id_infer_auto(0, &g_own_addr_type);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_hs_id_infer_auto failed; rc=%d", rc);
        return;
    }
    start_advertising();
}

void on_host_reset(int reason) {
    ESP_LOGW(kTag, "NimBLE host reset; reason=%d", reason);
}

void nimble_host_task(void* param) {
    (void)param;
    ESP_LOGI(kTag, "NimBLE host task started");
    // Returns only when nimble_port_stop() is called.
    nimble_port_run();
    nimble_port_freertos_deinit();
}

}  // namespace

namespace ble {

int BleService::gatt_svr_cb(uint16_t conn_handle, uint16_t attr_handle,
                            struct ble_gatt_access_ctxt* ctxt, void* arg) {
    return gatt_access(conn_handle, attr_handle, ctxt, arg);
}

bool BleService::begin() {
    // NimBLE stores PHY calibration data in NVS.
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    if (ret != ESP_OK) {
        ESP_LOGE(kTag, "nvs_flash_init failed; err=0x%x", ret);
        return false;
    }

    ret = nimble_port_init();
    if (ret != ESP_OK) {
        ESP_LOGE(kTag, "nimble_port_init failed; err=0x%x", ret);
        return false;
    }

    // Host configuration callbacks.
    ble_hs_cfg.sync_cb         = on_host_sync;
    ble_hs_cfg.reset_cb        = on_host_reset;
    ble_hs_cfg.store_status_cb = ble_store_util_status_rr;

    if (gatt_svr_init() != 0) {
        ESP_LOGE(kTag, "gatt_svr_init failed");
        return false;
    }

    int rc = ble_svc_gap_device_name_set(kDeviceName);
    if (rc != 0) {
        ESP_LOGE(kTag, "ble_svc_gap_device_name_set failed; rc=%d", rc);
        return false;
    }

    nimble_port_freertos_init(nimble_host_task);

    started_ = true;
    ESP_LOGI(kTag, "BleService started (NimBLE GATT ffe0)");
    return true;
}

}  // namespace ble
