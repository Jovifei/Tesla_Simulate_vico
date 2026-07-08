#pragma once

#include <cstdint>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "config/runtime_config.h"
#include "status/RuntimeStatus.h"

namespace network {

class NetworkManager {
public:
    bool begin();

    void seedConfig(const config::RuntimeConfig& cfg);

    void startIfConfigured();

    void requestReconnect();

    void requestStop();

    void copyStatus(status::RuntimeStatus& out) const;

    bool connected() const;

    EventGroupHandle_t eventGroup() const;
};

}  // namespace network
