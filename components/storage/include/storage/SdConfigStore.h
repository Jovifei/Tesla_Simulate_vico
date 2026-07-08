#pragma once

#include "config/runtime_config.h"

namespace storage {

// Persists config::RuntimeConfig to an SD card (SPI + FATFS) as JSON.
// SD is optional at boot: a missing/unreadable card must not fail App::begin().
class SdConfigStore {
public:
    // Initialize the SPI bus and mount the SD card at /sdcard.
    // Returns true on successful mount, false (with ESP_LOGE) otherwise.
    bool begin();

    // Load /sdcard/config.json into cfg. Returns false (leaving cfg untouched)
    // when unmounted, file missing, or JSON invalid; true on a good parse.
    bool load(config::RuntimeConfig& cfg);

    // Serialize cfg to JSON and write atomically (temp + rename).
    // Returns false when unmounted or the write fails.
    bool save(const config::RuntimeConfig& cfg);

    bool mounted() const { return mounted_; }

private:
    bool mounted_ = false;
};

}  // namespace storage
