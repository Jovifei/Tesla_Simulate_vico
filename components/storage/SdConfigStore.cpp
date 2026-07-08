#include "storage/SdConfigStore.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdspi_host.h"
#include "driver/spi_common.h"
#include "cJSON.h"

#include "config/pin_map.h"

namespace storage {

namespace {
constexpr char kTag[]      = "SdConfigStore";
constexpr char kMount[]    = "/sdcard";
constexpr char kPath[]     = "/sdcard/config.json";
constexpr char kTmpPath[]  = "/sdcard/config.tmp";

sdmmc_card_t* g_card = nullptr;
}  // namespace

bool SdConfigStore::begin() {
    spi_bus_config_t bus_cfg = {};
    bus_cfg.mosi_io_num     = config::pins::SD_MOSI;
    bus_cfg.miso_io_num     = config::pins::SD_MISO;
    bus_cfg.sclk_io_num     = config::pins::SD_CLK;
    bus_cfg.quadwp_io_num   = -1;
    bus_cfg.quadhd_io_num   = -1;
    bus_cfg.max_transfer_sz = 4000;

    esp_err_t err = spi_bus_initialize(SPI2_HOST, &bus_cfg, SDSPI_DEFAULT_DMA);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(kTag, "spi_bus_initialize failed: %s", esp_err_to_name(err));
        mounted_ = false;
        return false;
    }

    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.slot = SPI2_HOST;

    sdspi_device_config_t slot = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot.gpio_cs   = config::pins::SD_CS;
    slot.host_id   = SPI2_HOST;

    esp_vfs_fat_sdmmc_mount_config_t mount_cfg = {};
    mount_cfg.format_if_mount_failed = false;
    mount_cfg.max_files              = 4;
    mount_cfg.allocation_unit_size   = 16 * 1024;

    err = esp_vfs_fat_sdspi_mount(kMount, &host, &slot, &mount_cfg, &g_card);
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "mount failed: %s (SD optional, using defaults)",
                 esp_err_to_name(err));
        mounted_ = false;
        return false;
    }

    if (g_card != nullptr) {
        sdmmc_card_print_info(stdout, g_card);
    }
    mounted_ = true;
    ESP_LOGI(kTag, "SD mounted at %s", kMount);
    return true;
}

bool SdConfigStore::load(config::RuntimeConfig& cfg) {
    if (!mounted_) {
        return false;
    }

    FILE* f = std::fopen(kPath, "r");
    if (f == nullptr) {
        ESP_LOGW(kTag, "%s not found, keeping defaults", kPath);
        return false;
    }

    std::fseek(f, 0, SEEK_END);
    long len = std::ftell(f);
    std::fseek(f, 0, SEEK_SET);
    if (len <= 0 || len > 8192) {
        std::fclose(f);
        return false;
    }

    char* buf = static_cast<char*>(std::malloc(static_cast<size_t>(len) + 1));
    if (buf == nullptr) {
        std::fclose(f);
        return false;
    }
    size_t read = std::fread(buf, 1, static_cast<size_t>(len), f);
    buf[read] = '\0';
    std::fclose(f);

    cJSON* root = cJSON_Parse(buf);
    std::free(buf);
    if (root == nullptr) {
        ESP_LOGW(kTag, "config.json parse failed, keeping defaults");
        return false;
    }

    const cJSON* item = nullptr;
    if ((item = cJSON_GetObjectItemCaseSensitive(root, "can_bitrate")) != nullptr
        && cJSON_IsNumber(item)) {
        cfg.can_bitrate = static_cast<std::uint32_t>(item->valuedouble);
    }
    if ((item = cJSON_GetObjectItemCaseSensitive(root, "can_listen_only")) != nullptr
        && cJSON_IsBool(item)) {
        cfg.can_listen_only = cJSON_IsTrue(item);
    }
    if ((item = cJSON_GetObjectItemCaseSensitive(root, "audio_sample_rate")) != nullptr
        && cJSON_IsNumber(item)) {
        cfg.audio_sample_rate = static_cast<std::uint16_t>(item->valuedouble);
    }
    if ((item = cJSON_GetObjectItemCaseSensitive(root, "audio_volume_pct")) != nullptr
        && cJSON_IsNumber(item)) {
        cfg.audio_volume_pct = static_cast<std::uint8_t>(item->valuedouble);
    }
    if ((item = cJSON_GetObjectItemCaseSensitive(root, "profile_index")) != nullptr
        && cJSON_IsNumber(item)) {
        cfg.profile_index = static_cast<std::uint8_t>(item->valuedouble);
    }

    cJSON_Delete(root);
    ESP_LOGI(kTag, "config loaded from %s", kPath);
    return true;
}

bool SdConfigStore::save(const config::RuntimeConfig& cfg) {
    if (!mounted_) {
        return false;
    }

    cJSON* root = cJSON_CreateObject();
    if (root == nullptr) {
        return false;
    }
    cJSON_AddNumberToObject(root, "can_bitrate", cfg.can_bitrate);
    cJSON_AddBoolToObject(root, "can_listen_only", cfg.can_listen_only);
    cJSON_AddNumberToObject(root, "audio_sample_rate", cfg.audio_sample_rate);
    cJSON_AddNumberToObject(root, "audio_volume_pct", cfg.audio_volume_pct);
    cJSON_AddNumberToObject(root, "profile_index", cfg.profile_index);

    char* json = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (json == nullptr) {
        return false;
    }

    FILE* f = std::fopen(kTmpPath, "w");
    if (f == nullptr) {
        cJSON_free(json);
        return false;
    }
    std::fwrite(json, 1, std::strlen(json), f);
    std::fflush(f);
    std::fclose(f);
    cJSON_free(json);

    if (std::rename(kTmpPath, kPath) != 0) {
        ESP_LOGE(kTag, "rename %s -> %s failed", kTmpPath, kPath);
        return false;
    }
    ESP_LOGI(kTag, "config saved to %s", kPath);
    return true;
}

}  // namespace storage
