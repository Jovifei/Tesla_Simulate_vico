#include <unity.h>

#include "domain/EngineModel.h"

using tesla_speed::domain::EngineModel;
using tesla_speed::domain::VehicleState;

void test_idle_rpm_floor() {
  EngineModel model;
  VehicleState state{};
  state.speed_kph = 0.0f;
  state.throttle = 0.0f;

  const VehicleState out = model.update(state);

  TEST_ASSERT_FLOAT_WITHIN(0.01f, 900.0f, out.virtual_rpm);
}

void test_speed_to_rpm_is_monotonic() {
  EngineModel model;

  const float low = model.targetRpm(20.0f, 0.0f);
  const float high = model.targetRpm(80.0f, 0.0f);

  TEST_ASSERT_GREATER_THAN_FLOAT(low, high);
}

void test_throttle_load_increases_target_rpm() {
  EngineModel model;

  const float unloaded = model.targetRpm(50.0f, 0.0f);
  const float loaded = model.targetRpm(50.0f, 0.8f);

  TEST_ASSERT_GREATER_THAN_FLOAT(unloaded, loaded);
}

void test_overspeed_sets_mute_flag() {
  EngineModel model;
  VehicleState state{};
  state.speed_kph = 181.0f;

  const VehicleState out = model.update(state);

  TEST_ASSERT_TRUE(out.overspeed_mute);
}

int main(int argc, char** argv) {
  (void)argc;
  (void)argv;

  UNITY_BEGIN();
  RUN_TEST(test_idle_rpm_floor);
  RUN_TEST(test_speed_to_rpm_is_monotonic);
  RUN_TEST(test_throttle_load_increases_target_rpm);
  RUN_TEST(test_overspeed_sets_mute_flag);
  return UNITY_END();
}
