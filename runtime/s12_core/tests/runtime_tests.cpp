#include "s12_core/engine.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <new>

namespace {

using app1::s12::Direction;
using app1::s12::Engine;
using app1::s12::Event;
using app1::s12::MotionSample;
using app1::s12::Order;
using app1::s12::Profile;

bool track_allocations = false;
std::size_t tracked_allocations = 0;
int failures = 0;

#define CHECK(condition) \
    do { \
        if (!(condition)) { \
            std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #condition); \
            ++failures; \
        } \
    } while (false)

Profile make_v8_profile() {
    Profile profile{};
    std::snprintf(profile.profile_id, sizeof(profile.profile_id), "%s", "experimental-v8-synth");
    profile.idle_rpm = 850.0;
    profile.max_rpm = 6500.0;
    profile.rpm_per_mps_by_gear[0] = 220.0;
    profile.rpm_per_mps_by_gear[1] = 135.0;
    profile.rpm_per_mps_by_gear[2] = 95.0;
    profile.rpm_per_mps_by_gear[3] = 72.0;
    profile.gear_count = 4;
    profile.acceleration_rpm_per_mps2 = 60.0;
    profile.upshift_rpm = 5600.0;
    profile.downshift_rpm = 1700.0;
    profile.shift_rpm_drop = 0.70;
    profile.idle_load = 0.12;
    profile.positive_acceleration_load_per_mps2 = 0.14;
    profile.negative_acceleration_load_per_mps2 = 0.04;
    profile.orders[0] = Order{4.0, 0.68, 0.0};
    profile.orders[1] = Order{8.0, 0.24, 0.15};
    profile.orders[2] = Order{12.0, 0.08, -0.2};
    profile.order_count = 3;
    profile.transient_gain = 0.12;
    profile.acceleration_reference_mps2 = 4.0;
    profile.attack_s = 0.035;
    profile.release_s = 0.14;
    profile.shift_impulse = 0.35;
    profile.carrier_order = 1.5;
    profile.sample_rate_hz = 48000;
    profile.output_gain = 0.42;
    profile.peak_limit = 0.92;
    return profile;
}

Profile make_rotary_profile() {
    Profile profile{};
    std::snprintf(profile.profile_id, sizeof(profile.profile_id), "%s", "experimental-rotary-synth");
    profile.idle_rpm = 950.0;
    profile.max_rpm = 9000.0;
    profile.rpm_per_mps_by_gear[0] = 300.0;
    profile.rpm_per_mps_by_gear[1] = 180.0;
    profile.rpm_per_mps_by_gear[2] = 125.0;
    profile.rpm_per_mps_by_gear[3] = 90.0;
    profile.gear_count = 4;
    profile.acceleration_rpm_per_mps2 = 75.0;
    profile.upshift_rpm = 8200.0;
    profile.downshift_rpm = 2400.0;
    profile.shift_rpm_drop = 0.76;
    profile.idle_load = 0.10;
    profile.positive_acceleration_load_per_mps2 = 0.13;
    profile.negative_acceleration_load_per_mps2 = 0.035;
    profile.orders[0] = Order{6.0, 0.66, 0.0};
    profile.orders[1] = Order{12.0, 0.25, -0.12};
    profile.orders[2] = Order{18.0, 0.09, 0.22};
    profile.order_count = 3;
    profile.transient_gain = 0.10;
    profile.acceleration_reference_mps2 = 4.0;
    profile.attack_s = 0.025;
    profile.release_s = 0.12;
    profile.shift_impulse = 0.30;
    profile.carrier_order = 1.8;
    profile.sample_rate_hz = 48000;
    profile.output_gain = 0.40;
    profile.peak_limit = 0.92;
    return profile;
}

MotionSample motion(
    std::uint64_t sequence,
    std::uint64_t measured_ns,
    double speed_mps,
    double acceleration_mps2,
    Direction direction = Direction::kForward
) {
    return MotionSample{
        sequence,
        measured_ns,
        measured_ns + 2'000'000,
        speed_mps,
        acceleration_mps2,
        direction,
        true,
    };
}

void test_state_mapping_and_input_validation() {
    Engine engine(make_v8_profile(), 20260924);
    CHECK(engine.valid());
    CHECK(engine.update_motion(motion(0, 1'000'000'000, 0.0, 0.0, Direction::kStationary), 1'003'000'000));
    auto idle = engine.state();
    CHECK(idle.gear == 1);
    CHECK(std::abs(idle.virtual_rpm - 850.0) < 1.0e-6);

    CHECK(engine.update_motion(motion(1, 1'010'000'000, 20.0, 2.0), 1'013'000'000));
    auto accelerating = engine.state();
    CHECK(accelerating.virtual_rpm > idle.virtual_rpm);
    CHECK(accelerating.load > idle.load);
    CHECK(!accelerating.fallback);
}

void test_stale_and_out_of_order_input_falls_back_safely() {
    Engine engine(make_v8_profile(), 9);
    CHECK(engine.update_motion(motion(0, 1'000'000'000, 10.0, 1.0), 1'003'000'000));
    CHECK(!engine.update_motion(motion(1, 1'010'000'000, 15.0, 2.0), 1'700'000'000));
    auto stale = engine.state();
    CHECK(stale.fallback);
    CHECK(stale.virtual_rpm == 850.0);
    CHECK(stale.load == 0.0);

    CHECK(engine.update_motion(motion(2, 1'020'000'000, 8.0, 0.5), 1'023'000'000));
    CHECK(!engine.state().fallback);
    CHECK(!engine.update_motion(motion(2, 1'030'000'000, 8.0, 0.5), 1'033'000'000));
    CHECK(engine.state().fallback);
}

void test_missing_updates_become_stale_without_replaying_packets() {
    Engine engine(make_v8_profile(), 8);
    CHECK(engine.update_motion(motion(0, 1'000'000'000, 25.0, 1.0), 1'003'000'000));
    engine.check_input_freshness(1'499'999'999);
    CHECK(!engine.state().fallback);
    engine.check_input_freshness(1'500'000'001);
    CHECK(engine.state().fallback);
    CHECK(engine.state().virtual_rpm == 850.0);
    CHECK(engine.state().load == 0.0);
}

void test_shift_event_and_gear_state_persist() {
    Engine engine(make_v8_profile(), 2);
    CHECK(engine.update_motion(motion(0, 1'000'000'000, 32.0, 4.0), 1'003'000'000));
    auto shifted = engine.state();
    CHECK(shifted.gear == 2);
    CHECK(shifted.event == Event::kShiftUp);
    CHECK(shifted.shift_events == 1);

    CHECK(engine.update_motion(motion(1, 1'010'000'000, 33.0, 1.0), 1'013'000'000));
    CHECK(engine.state().shift_events == 1);
}

void test_render_is_allocation_free_and_partition_invariant() {
    auto profile = make_v8_profile();
    Engine whole(profile, 11);
    Engine split(profile, 11);
    const auto sample = motion(0, 1'000'000'000, 18.0, 1.5);
    CHECK(whole.update_motion(sample, 1'003'000'000));
    CHECK(split.update_motion(sample, 1'003'000'000));

    std::array<float, 960 * 2> whole_output{};
    std::array<float, 960 * 2> split_output{};
    const auto allocations_before = tracked_allocations;
    track_allocations = true;
    CHECK(whole.render(whole_output.data(), 960));
    CHECK(split.render(split_output.data(), 96));
    CHECK(split.render(split_output.data() + 96 * 2, 192));
    CHECK(split.render(split_output.data() + (96 + 192) * 2, 192));
    CHECK(split.render(split_output.data() + 480 * 2, 240));
    CHECK(split.render(split_output.data() + 720 * 2, 240));
    track_allocations = false;

    CHECK(tracked_allocations == allocations_before);
    for (std::size_t i = 0; i < whole_output.size(); ++i) {
        CHECK(std::abs(whole_output[i] - split_output[i]) < 1.0e-7F);
    }
    const std::array<std::size_t, 6> block_sizes{96U, 192U, 240U, 256U, 480U, 960U};
    for (const std::size_t frames : block_sizes) {
        Engine block_engine(profile, 3);
        CHECK(block_engine.update_motion(sample, 1'003'000'000));
        std::array<float, 960 * 2> block{};
        CHECK(block_engine.render(block.data(), frames));
    }
}

void test_profile_switch_crossfades_without_resetting_engine_state() {
    double worst_new_profile_error = 0.0;
    for (std::uint32_t seed = 1; seed <= 32; ++seed) {
        Engine engine(make_v8_profile(), seed);
        CHECK(engine.update_motion(motion(0, 1'000'000'000, 20.0, 0.5), 1'003'000'000));
        std::array<float, 480 * 2> before{};
        CHECK(engine.render(before.data(), 480));
        const auto sample_index = engine.state().sample_index;
        CHECK(engine.switch_profile(make_rotary_profile(), 4800));
        CHECK(engine.state().sample_index == sample_index);

        std::array<float, 480 * 2> after{};
        CHECK(engine.render(after.data(), 480));
        CHECK(std::abs(after[0] - before.back()) < 0.25F);
        CHECK(engine.state().gear >= 1);

        std::array<float, 4319 * 2> fade_tail{};
        std::array<float, 2> final_fade_sample{};
        std::array<float, 2> post_fade_sample{};
        std::array<float, 2> expected_final_sample{};
        std::array<float, 2> expected_post_sample{};
        CHECK(engine.render(fade_tail.data(), 4319));
        auto before_final_fade = engine.snapshot();
        before_final_fade.fading = false;
        before_final_fade.fade_total_frames = 0;
        before_final_fade.fade_remaining_frames = 0;
        Engine new_profile_only(make_rotary_profile(), seed);
        CHECK(new_profile_only.restore(before_final_fade));
        CHECK(engine.render(final_fade_sample.data(), 1));
        CHECK(new_profile_only.render(expected_final_sample.data(), 1));
        CHECK(engine.render(post_fade_sample.data(), 1));
        CHECK(new_profile_only.render(expected_post_sample.data(), 1));
        const double error = std::abs(expected_final_sample[0] - final_fade_sample[0]);
        if (error > worst_new_profile_error) worst_new_profile_error = error;
        CHECK(std::abs(post_fade_sample[0] - expected_post_sample[0]) < 1.0e-7F);
    }
    CHECK(worst_new_profile_error < 0.01);
}

void test_profile_switch_before_input_keeps_phase_and_rejects_bad_profiles() {
    Engine engine(make_v8_profile(), 41);
    std::array<float, 240 * 2> warmup{};
    CHECK(engine.render(warmup.data(), 240));
    const double phase_before = engine.snapshot().phase;

    CHECK(engine.switch_profile(make_rotary_profile(), 0));
    CHECK(engine.snapshot().phase == phase_before);

    auto invalid = make_v8_profile();
    invalid.sample_rate_hz = 44100;
    CHECK(!engine.switch_profile(invalid, 480));
    CHECK(std::strncmp(engine.snapshot().profile_id, "experimental-rotary-synth", 25) == 0);
}

void test_reselecting_current_profile_is_exact_noop() {
    Engine reference(make_v8_profile(), 77);
    Engine actual(make_v8_profile(), 77);
    const auto input = motion(0, 1'000'000'000, 30.0, 1.0);
    CHECK(reference.update_motion(input, 1'003'000'000));
    CHECK(actual.update_motion(input, 1'003'000'000));
    std::array<float, 240 * 2> warmup{};
    CHECK(reference.render(warmup.data(), 240));
    CHECK(actual.render(warmup.data(), 240));
    const auto before = actual.state();
    CHECK(actual.switch_profile(make_v8_profile(), 4800));
    CHECK(!actual.snapshot().fading);
    CHECK(actual.state().gear == before.gear);
    CHECK(actual.state().shift_events == before.shift_events);
    std::array<float, 960 * 2> expected{};
    std::array<float, 960 * 2> observed{};
    CHECK(reference.render(expected.data(), 960));
    CHECK(actual.render(observed.data(), 960));
    CHECK(expected == observed);
}

void test_interrupted_switch_queues_latest_without_changing_current_fade() {
    Engine reference(make_v8_profile(), 81);
    Engine actual(make_v8_profile(), 81);
    const auto input = motion(0, 1'000'000'000, 20.0, 0.5);
    CHECK(reference.update_motion(input, 1'003'000'000));
    CHECK(actual.update_motion(input, 1'003'000'000));
    CHECK(reference.switch_profile(make_rotary_profile(), 4800));
    CHECK(actual.switch_profile(make_rotary_profile(), 4800));
    std::array<float, 1000 * 2> prefix{};
    CHECK(reference.render(prefix.data(), 1000));
    CHECK(actual.render(prefix.data(), 1000));
    CHECK(actual.switch_profile(make_v8_profile(), 4800));
    CHECK(actual.switch_profile(make_rotary_profile(), 4800));
    CHECK(actual.switch_profile(make_v8_profile(), 4800));
    Engine restored(make_rotary_profile(), 0);
    CHECK(restored.restore(actual.snapshot()));
    std::array<float, 3800 * 2> expected_tail{};
    std::array<float, 3800 * 2> actual_tail{};
    std::array<float, 3800 * 2> restored_tail{};
    CHECK(reference.render(expected_tail.data(), 3800));
    CHECK(actual.render(actual_tail.data(), 3800));
    CHECK(restored.render(restored_tail.data(), 3800));
    CHECK(expected_tail == actual_tail);
    CHECK(restored_tail == actual_tail);
    CHECK(reference.switch_profile(make_v8_profile(), 4800));
    std::array<float, 4800 * 2> expected_return{};
    std::array<float, 4800 * 2> actual_return{};
    CHECK(reference.render(expected_return.data(), 4800));
    CHECK(actual.render(actual_return.data(), 4800));
    std::array<float, 4800 * 2> restored_return{};
    CHECK(restored.render(restored_return.data(), 4800));
    CHECK(expected_return == actual_return);
    CHECK(restored_return == actual_return);
}

void test_crossfade_obeys_profile_peak_limit() {
    auto first = make_v8_profile();
    first.output_gain = 1.0;
    first.order_count = 8;
    for (auto& order : first.orders) order = Order{4.0, 1.0, 0.0};
    auto second = first;
    std::snprintf(second.profile_id, sizeof(second.profile_id), "%s", "experimental-loud-b");
    CHECK(app1::s12::profile_is_valid(first));
    CHECK(app1::s12::profile_is_valid(second));
    Engine engine(first, 13);
    CHECK(engine.update_motion(motion(0, 1'000'000'000, 20.0, 0.5), 1'003'000'000));
    CHECK(engine.switch_profile(second, 4800));
    std::array<float, 4800 * 2> output{};
    CHECK(engine.render(output.data(), 4800));
    float peak = 0.0F;
    for (float sample : output) peak = std::max(peak, std::abs(sample));
    CHECK(peak <= first.peak_limit + 1.0e-6);
}

void test_queued_switch_is_partition_independent() {
    Engine full(make_v8_profile(), 39);
    Engine partitioned(make_v8_profile(), 39);
    const auto input = motion(0, 1'000'000'000, 18.0, 1.0);
    CHECK(full.update_motion(input, 1'003'000'000));
    CHECK(partitioned.update_motion(input, 1'003'000'000));
    CHECK(full.switch_profile(make_rotary_profile(), 4800));
    CHECK(partitioned.switch_profile(make_rotary_profile(), 4800));
    std::array<float, 1000 * 2> warmup{};
    CHECK(full.render(warmup.data(), 1000));
    CHECK(partitioned.render(warmup.data(), 1000));
    CHECK(full.switch_profile(make_v8_profile(), 4800));
    CHECK(partitioned.switch_profile(make_v8_profile(), 4800));
    std::array<float, 8600 * 2> expected{};
    std::array<float, 8600 * 2> observed{};
    CHECK(full.render(expected.data(), 8600));
    constexpr std::size_t blocks[]{96, 192, 240, 256, 480, 960};
    for (std::size_t offset = 0, index = 0; offset < 8600; ++index) {
        const auto frames = std::min(blocks[index % 6], 8600 - offset);
        CHECK(partitioned.render(observed.data() + offset * 2, frames));
        offset += frames;
    }
    CHECK(expected == observed);
}

void test_profile_switch_during_fallback_keeps_safe_targets() {
    Engine engine(make_v8_profile(), 61);
    CHECK(engine.update_motion(motion(0, 1'000'000'000, 20.0, 0.0), 1'003'000'000));
    MotionSample invalid{};
    CHECK(!engine.update_motion(invalid, 1'300'000'000));
    const auto shifts = engine.state().shift_events;
    CHECK(engine.switch_profile(make_rotary_profile(), 4800));
    const auto state = engine.state();
    CHECK(state.fallback);
    CHECK(state.virtual_rpm == make_rotary_profile().idle_rpm);
    CHECK(state.load == 0.0);
    CHECK(state.shift_events == shifts);
    CHECK(state.event == Event::kNone);
    Engine restored(make_rotary_profile(), 0);
    CHECK(restored.restore(engine.snapshot()));
}

void test_pending_profile_switch_during_fallback_is_safe_and_partition_independent() {
    Engine full(make_v8_profile(), 67);
    Engine split(make_v8_profile(), 67);
    const auto input = motion(0, 1'000'000'000, 20.0, 0.0);
    CHECK(full.update_motion(input, 1'003'000'000));
    CHECK(split.update_motion(input, 1'003'000'000));
    CHECK(full.switch_profile(make_rotary_profile(), 4800));
    CHECK(split.switch_profile(make_rotary_profile(), 4800));
    std::array<float, 1000 * 2> warmup{};
    CHECK(full.render(warmup.data(), 1000));
    CHECK(split.render(warmup.data(), 1000));
    CHECK(full.switch_profile(make_v8_profile(), 4800));
    CHECK(split.switch_profile(make_v8_profile(), 4800));
    MotionSample invalid{};
    CHECK(!full.update_motion(invalid, 1'300'000'000));
    CHECK(!split.update_motion(invalid, 1'300'000'000));
    const auto shifts = full.state().shift_events;
    Engine restored(make_rotary_profile(), 0);
    CHECK(restored.restore(split.snapshot()));
    std::array<float, 3800 * 2> expected{};
    std::array<float, 3800 * 2> observed{};
    CHECK(full.render(expected.data(), 3800));
    constexpr std::size_t blocks[]{96, 192, 240, 256, 480, 960};
    for (std::size_t offset = 0, index = 0; offset < 3800; ++index) {
        const auto frames = std::min(blocks[index % 6], 3800 - offset);
        CHECK(split.render(observed.data() + offset * 2, frames));
        offset += frames;
    }
    CHECK(expected == observed);
    CHECK(full.state().fallback);
    CHECK(full.state().virtual_rpm == make_v8_profile().idle_rpm);
    CHECK(full.state().load == 0.0);
    CHECK(full.state().shift_events == shifts);
    std::array<float, 3800 * 2> restored_output{};
    CHECK(restored.render(restored_output.data(), 3800));
    CHECK(restored_output == observed);
}

void test_snapshot_restore_continues_identically() {
    auto profile = make_rotary_profile();
    Engine original(profile, 31);
    CHECK(original.update_motion(motion(0, 1'000'000'000, 16.0, 2.0), 1'003'000'000));
    std::array<float, 240 * 2> warmup{};
    CHECK(original.render(warmup.data(), 240));

    const auto snapshot = original.snapshot();
    Engine restored(profile, 0);
    CHECK(restored.restore(snapshot));
    std::array<float, 256 * 2> expected{};
    std::array<float, 256 * 2> actual{};
    CHECK(original.render(expected.data(), 256));
    CHECK(restored.render(actual.data(), 256));
    for (std::size_t i = 0; i < expected.size(); ++i) {
        CHECK(std::abs(expected[i] - actual[i]) < 1.0e-7F);
    }
}

}  // namespace

void* operator new(std::size_t size) {
    if (track_allocations) ++tracked_allocations;
    if (void* value = std::malloc(size)) return value;
    std::abort();
}

void* operator new[](std::size_t size) {
    if (track_allocations) ++tracked_allocations;
    if (void* value = std::malloc(size)) return value;
    std::abort();
}

void operator delete(void* value) noexcept { std::free(value); }
void operator delete[](void* value) noexcept { std::free(value); }
void operator delete(void* value, std::size_t) noexcept { std::free(value); }
void operator delete[](void* value, std::size_t) noexcept { std::free(value); }

int main() {
    test_state_mapping_and_input_validation();
    test_stale_and_out_of_order_input_falls_back_safely();
    test_missing_updates_become_stale_without_replaying_packets();
    test_shift_event_and_gear_state_persist();
    test_render_is_allocation_free_and_partition_invariant();
    test_profile_switch_crossfades_without_resetting_engine_state();
    test_profile_switch_before_input_keeps_phase_and_rejects_bad_profiles();
    test_reselecting_current_profile_is_exact_noop();
    test_interrupted_switch_queues_latest_without_changing_current_fade();
    test_crossfade_obeys_profile_peak_limit();
    test_queued_switch_is_partition_independent();
    test_profile_switch_during_fallback_keeps_safe_targets();
    test_pending_profile_switch_during_fallback_is_safe_and_partition_independent();
    test_snapshot_restore_continues_identically();
    if (failures != 0) {
        std::fprintf(stderr, "%d assertion(s) failed\n", failures);
        return 1;
    }
    std::puts("APP-1 native runtime tests PASS");
    return 0;
}
