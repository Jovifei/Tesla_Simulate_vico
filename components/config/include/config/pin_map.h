#pragma once

#include <cstdint>

namespace config::pins {

constexpr std::uint8_t POT_IO1 = 1;

constexpr std::uint8_t I2S_BCK = 6;
constexpr std::uint8_t I2S_LCK = 7;
constexpr std::uint8_t I2S_DIN = 12;

constexpr std::uint8_t CAN_RX = 13;
constexpr std::uint8_t CAN_TX = 14;
constexpr std::uint8_t CAN_RS = 38;

constexpr std::uint8_t ENC_CLK = 4;
constexpr std::uint8_t ENC_DT = 5;

constexpr std::uint8_t LED_PWR = 21;
constexpr std::uint8_t WS_DATA = 48;

constexpr std::uint8_t SD_CS = 45;
constexpr std::uint8_t SD_CLK = 39;
constexpr std::uint8_t SD_MOSI = 40;
constexpr std::uint8_t SD_MISO = 41;

}  // namespace config::pins
