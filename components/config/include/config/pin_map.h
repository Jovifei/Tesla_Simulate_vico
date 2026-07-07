#pragma once

#include "driver/gpio.h"

namespace config::pins {

constexpr gpio_num_t POT_IO1 = GPIO_NUM_1;

constexpr gpio_num_t I2S_BCK = GPIO_NUM_6;
constexpr gpio_num_t I2S_LCK = GPIO_NUM_7;
constexpr gpio_num_t I2S_DIN = GPIO_NUM_12;

constexpr gpio_num_t CAN_RX = GPIO_NUM_13;
constexpr gpio_num_t CAN_TX = GPIO_NUM_14;
constexpr gpio_num_t CAN_RS = GPIO_NUM_38;

constexpr gpio_num_t ENC_CLK = GPIO_NUM_4;
constexpr gpio_num_t ENC_DT = GPIO_NUM_5;

constexpr gpio_num_t LED_PWR = GPIO_NUM_21;
constexpr gpio_num_t WS_DATA = GPIO_NUM_48;

constexpr gpio_num_t SD_CS = GPIO_NUM_45;
constexpr gpio_num_t SD_CLK = GPIO_NUM_39;
constexpr gpio_num_t SD_MOSI = GPIO_NUM_40;
constexpr gpio_num_t SD_MISO = GPIO_NUM_41;

}  // namespace config::pins
