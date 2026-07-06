#pragma once

#include "domain/VehicleState.h"

namespace tesla_speed::can {

class CanSource {
 public:
  virtual ~CanSource() = default;
  virtual bool begin() = 0;
  virtual bool poll(tesla_speed::domain::VehicleState& state) = 0;
  virtual bool isListenOnly() const = 0;
};

}  // namespace tesla_speed::can
