#include "motion_command_gate.hpp"

#include <cassert>
#include <cstdint>

using app1::s12::Direction;
using app1::s12::Engine;
using app1::s12::MotionCommandGate;
using app1::s12::MotionSample;
using app1::s12::Profile;

namespace {

Profile profile(std::uint32_t index) {
    Profile value{};
    assert(app1::s12::builtin_profile(index, &value));
    return value;
}

MotionSample motion(std::uint64_t sequence, std::uint64_t measured_ns, double speed) {
    return MotionSample{sequence, measured_ns, measured_ns + 5'000'000,
        speed, 0.0, Direction::kForward, true};
}

void old_queue_cannot_override_invalidation() {
    Engine engine(profile(0), 5);
    MotionCommandGate gate;
    for (std::uint64_t sequence = 0; sequence < 70; ++sequence) {
        assert(gate.submit_motion(motion(sequence, 1'000'000'000 + sequence * 1'000'000, 20.0)));
    }
    gate.invalidate_before(70);
    assert(gate.submit_motion(motion(70, 1'350'000'000, 15.0)));
    auto profile_command = [&](std::uint32_t index) {
        engine.switch_profile_prevalidated(profile(index), 4800);
    };
    auto volume_command = [](float) {};
    gate.consume(engine, 1'300'000'000, profile_command, volume_command);
    assert(engine.state().fallback);
    gate.consume(engine, 1'310'000'000, profile_command, volume_command);
    assert(engine.state().fallback);
    gate.consume(engine, 1'360'000'000, profile_command, volume_command);
    assert(!engine.state().fallback);
    assert(engine.state().virtual_rpm > profile(0).idle_rpm);
    assert(gate.submit_motion(motion(69, 1'050'000'000, 20.0)));
    gate.consume(engine, 1'370'000'000, profile_command, volume_command);
    assert(!engine.state().fallback);
    assert(gate.submit_motion(motion(71, 800'000'000, 20.0)));
    gate.consume(engine, 1'400'000'000, profile_command, volume_command);
    assert(engine.state().fallback);
}

void control_commands_do_not_reenable_old_motion() {
    Engine engine(profile(0), 7);
    assert(engine.update_motion(motion(0, 1'000'000'000, 20.0), 1'010'000'000));
    MotionCommandGate gate;
    assert(gate.submit_motion(motion(1, 1'010'000'000, 20.0)));
    assert(gate.select_profile(1));
    assert(gate.set_volume(0.5F));
    gate.invalidate_before(2);
    float selected_volume = -1.0F;
    gate.consume(engine, 1'300'000'000,
        [&](std::uint32_t index) { engine.switch_profile_prevalidated(profile(index), 4800); },
        [&](float value) { selected_volume = value; });
    assert(engine.state().fallback);
    assert(engine.state().virtual_rpm == profile(1).idle_rpm);
    assert(engine.state().load == 0.0);
    assert(selected_volume == 0.5F);
}

void invalidation_is_not_blocked_by_a_full_queue() {
    Engine engine(profile(0), 9);
    MotionCommandGate gate;
    for (std::uint64_t sequence = 0; sequence < 255; ++sequence)
        assert(gate.submit_motion(motion(sequence, 1'000'000'000 + sequence * 1'000'000, 20.0)));
    assert(!gate.submit_motion(motion(255, 1'255'000'000, 20.0)));
    gate.invalidate_before(255);
    gate.consume(engine, 1'300'000'000,
        [](std::uint32_t) {}, [](float) {});
    assert(engine.state().fallback);
    for (int callback = 0; callback < 8; ++callback) {
        gate.consume(engine, 1'310'000'000 + callback * 1'000'000,
            [](std::uint32_t) {}, [](float) {});
        assert(engine.state().fallback);
    }
}

void empty_queue_invalidation_does_not_block_first_new_sample() {
    Engine engine(profile(0), 10);
    MotionCommandGate gate;
    gate.invalidate_before(0);
    assert(gate.submit_motion(motion(0, 1'100'000'000, 12.0)));
    gate.consume(engine, 1'110'000'000,
        [](std::uint32_t) {}, [](float) {});
    assert(!engine.state().fallback);
}

void no_history_gate_profile_switch_stays_safe_until_fresh_motion() {
    Engine engine(profile(0), 11);
    MotionCommandGate gate;
    assert(gate.submit_motion(motion(0, 1'000'000'000, 20.0)));
    assert(gate.select_profile(1));
    assert(gate.set_volume(0.5F));
    gate.invalidate_before(1);
    float selected_volume = -1.0F;
    gate.consume(engine, 1'300'000'000,
        [&](std::uint32_t index) { engine.switch_profile_prevalidated(profile(index), 4800); },
        [&](float volume) { selected_volume = volume; });
    assert(engine.state().fallback);
    assert(!engine.snapshot().has_previous_sample);
    assert(engine.state().virtual_rpm == profile(1).idle_rpm);
    assert(engine.state().load == 0.0);
    assert(engine.state().shift_events == 0);
    assert(selected_volume == 0.5F);
    assert(gate.submit_motion(motion(1, 1'310'000'000, 12.0)));
    gate.consume(engine, 1'320'000'000,
        [](std::uint32_t) {}, [](float) {});
    assert(!engine.state().fallback);
}

}  // namespace

int main() {
    old_queue_cannot_override_invalidation();
    control_commands_do_not_reenable_old_motion();
    invalidation_is_not_blocked_by_a_full_queue();
    empty_queue_invalidation_does_not_block_first_new_sample();
    no_history_gate_profile_switch_stays_safe_until_fresh_motion();
}
