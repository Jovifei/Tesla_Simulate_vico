#include "can/TwaiCanSource.h"

namespace can {

bool TwaiCanSource::begin() {
    // Stub: accept listen-only config, mark as configured.
    // Real TWAI driver init arrives in S1.
    configured_ = config_.can_listen_only;
    return configured_;
}

bool TwaiCanSource::poll(domain::VehicleState& state) {
    // Stub: no CAN frames received yet.
    // Real TWAI receive arrives in S1.
    state.can_valid = false;
    return false;
}

}  // namespace can
