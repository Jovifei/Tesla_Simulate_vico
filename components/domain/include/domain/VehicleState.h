#pragma once

namespace domain {

struct VehicleState {
    float speed_kph      = 0.0f;
    float throttle       = 0.0f;
    float virtual_rpm    = 0.0f;
    bool  overspeed_mute = false;
    bool  can_valid      = false;
};

}  // namespace domain
