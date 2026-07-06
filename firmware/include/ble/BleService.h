#pragma once

#include "ble/BleUuids.h"

namespace tesla_speed::ble {

class BleService {
 public:
  bool begin() {
    started_ = true;
    return true;
  }

  bool started() const { return started_; }

 private:
  bool started_ = false;
};

}  // namespace tesla_speed::ble
