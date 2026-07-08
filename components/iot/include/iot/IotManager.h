#pragma once

#include <cstdint>

#include "config/runtime_config.h"
#include "domain/VehicleState.h"
#include "ota/OtaManager.h"
#include "status/RuntimeStatus.h"

namespace iot {

class IotManager {
public:
    bool begin();

    void seedConfig(const config::RuntimeConfig& cfg);

    void startIfConfigured();

    void stop();

    void publishDeviceInfo(const status::RuntimeStatus& status);

    void publishVehicleState(const domain::VehicleState& state);

    void publishOtaProgress(const status::RuntimeStatus& status);

    bool takePendingOtaRequest(ota::OtaRequest& out);

    void copyStatus(status::RuntimeStatus& out) const;

private:
    void publishJsonToUp(const char* payload, std::size_t len);
    void publishPayload(const status::RuntimeStatus& status);
};

}  // namespace iot
