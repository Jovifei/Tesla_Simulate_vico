#pragma once

#include "config/runtime_config.h"
#include "status/RuntimeStatus.h"
#include "ota/OtaStatus.h"

namespace ota {

enum class OtaTrigger : std::uint8_t {
    None = 0,
    BootConfig,
    BleConfig,
    CloudCommand,
};

struct OtaRequest {
    char url[192] = {};
    char version[32] = {};
    char md5[33] = {};
    std::uint32_t file_size = 0;
    OtaTrigger trigger = OtaTrigger::None;
};

class OtaManager {
public:
    bool begin();
    bool request(const OtaRequest& request);
    bool startIfConfigured(const config::RuntimeConfig& cfg);
    bool running() const;
    void copyStatus(status::RuntimeStatus& out) const;
    void copyStatus(OtaStatus& out) const;

private:
    bool requestOta_(const OtaRequest& request);
};

}  // namespace ota
