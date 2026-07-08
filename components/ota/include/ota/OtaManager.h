#pragma once

#include "config/runtime_config.h"
#include "ota/OtaStatus.h"

namespace ota {

class OtaManager {
public:
    bool begin();
    void startIfConfigured(const config::RuntimeConfig& cfg);
    void copyStatus(OtaStatus& out) const;

private:
    bool started_ = false;
};

}  // namespace ota
