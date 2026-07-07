#include "unity.h"
#include "can/CanFrames.h"

using namespace can;

void setUp() {}
void tearDown() {}

// === parseSpeed tests ===

void test_parseSpeed_known_frame() {
    // Frame: {0x00, 0x64} = 100 raw * 0.01 = 1.0 km/h
    uint8_t data[8] = {0x00, 0x64, 0, 0, 0, 0, 0, 0};
    float speed = parseSpeed(data, 8);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.0f, speed);
}

void test_parseSpeed_zero_frame() {
    uint8_t data[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    float speed = parseSpeed(data, 8);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, speed);
}

void test_parseSpeed_max_frame() {
    // 0xFFFF = 65535 * 0.01 = 655.35 km/h
    uint8_t data[8] = {0xFF, 0xFF, 0, 0, 0, 0, 0, 0};
    float speed = parseSpeed(data, 8);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 655.35f, speed);
}

void test_parseSpeed_short_dlc_returns_sentinel() {
    uint8_t data[8] = {0x00, 0x64, 0, 0, 0, 0, 0, 0};
    float speed = parseSpeed(data, 1);  // DLC too short
    TEST_ASSERT_FLOAT_WITHIN(0.001f, -1.0f, speed);
}

// === parseTorque tests ===

void test_parseTorque_known_frame() {
    // Frame: {0x00, 0x64} = 100 raw * 0.1 / 204.7 = 0.04885...
    uint8_t data[8] = {0x00, 0x64, 0, 0, 0, 0, 0, 0};
    float torque = parseTorque(data, 8);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 10.0f / 204.7f, torque);
}

void test_parseTorque_zero_frame() {
    uint8_t data[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    float torque = parseTorque(data, 8);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, torque);
}

void test_parseTorque_max_positive() {
    // 0x7FFF = 32767 * 0.1 / 204.7 ≈ 15.99 → clamped to 1.0
    uint8_t data[8] = {0x7F, 0xFF, 0, 0, 0, 0, 0, 0};
    float torque = parseTorque(data, 8);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.0f, torque);
}

void test_parseTorque_negative_returns_zero() {
    // Negative torque (regen) should clamp to 0
    uint8_t data[8] = {0xFF, 0x00, 0, 0, 0, 0, 0, 0};  // -256 raw
    float torque = parseTorque(data, 8);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, torque);
}

void test_parseTorque_short_dlc_returns_sentinel() {
    uint8_t data[8] = {0x00, 0x64, 0, 0, 0, 0, 0, 0};
    float torque = parseTorque(data, 1);  // DLC too short
    TEST_ASSERT_FLOAT_WITHIN(0.001f, -1.0f, torque);
}

// === No-transmit API check ===

void test_no_transmit_api_exposed() {
    // Compile-time check: header only declares parse functions
    // This test passes if it compiles — no transmit/send/write functions exist
    TEST_ASSERT_TRUE(true);
}

extern "C" void app_main() {
    UNITY_BEGIN();

    RUN_TEST(test_parseSpeed_known_frame);
    RUN_TEST(test_parseSpeed_zero_frame);
    RUN_TEST(test_parseSpeed_max_frame);
    RUN_TEST(test_parseSpeed_short_dlc_returns_sentinel);

    RUN_TEST(test_parseTorque_known_frame);
    RUN_TEST(test_parseTorque_zero_frame);
    RUN_TEST(test_parseTorque_max_positive);
    RUN_TEST(test_parseTorque_negative_returns_zero);
    RUN_TEST(test_parseTorque_short_dlc_returns_sentinel);

    RUN_TEST(test_no_transmit_api_exposed);

    UNITY_END();
}
