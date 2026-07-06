#pragma once

#include "domain/VehicleState.h"

namespace can {

/// Abstract CAN source — listen-only by design.  No transmit() method.
class CanSource {
public:
    virtual ~CanSource() = default;
    virtual bool begin() = 0;
    virtual bool poll(domain::VehicleState& state) = 0;
    virtual bool isListenOnly() const = 0;
};

}  // namespace can
