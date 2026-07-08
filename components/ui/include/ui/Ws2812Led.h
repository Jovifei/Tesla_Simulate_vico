#pragma once

#include <cstdint>

namespace ui {

enum class Status {
    Booting,   // blue
    Running,   // green
    Muted,     // amber
    Fault,     // red
};

// Single WS2812 status LED on WS_DATA (GPIO48) driven over the RMT TX driver.
class Ws2812Led {
public:
    bool begin();

    // Send one WS2812 frame with the given 8-bit-per-channel color.
    void set_color(std::uint8_t r, std::uint8_t g, std::uint8_t b);

    // Map a device status to a color and transmit it.
    void set(Status status);

private:
    void* channel_ = nullptr;  // rmt_channel_handle_t (opaque here)
    void* encoder_ = nullptr;  // rmt_encoder_handle_t (opaque here)
    bool  ready_   = false;
};

}  // namespace ui
