#pragma once

namespace ble {

/// Stub BLE service — real GATT implementation arrives in S3.
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

}  // namespace ble
