#include "s12_core/c_api.hpp"

#include <new>

extern "C" {

app1::s12::Engine* app1_engine_create(const app1::s12::Profile* profile, std::uint32_t seed) {
    if (profile == nullptr || !app1::s12::profile_is_valid(*profile)) return nullptr;
    auto* engine = new (std::nothrow) app1::s12::Engine(*profile, seed);
    if (engine == nullptr) return nullptr;
    if (!engine->valid()) {
        delete engine;
        return nullptr;
    }
    return engine;
}

void app1_engine_destroy(app1::s12::Engine* engine) { delete engine; }

bool app1_engine_update_motion(
    app1::s12::Engine* engine,
    const app1::s12::MotionSample* sample,
    std::uint64_t now_monotonic_ns) {
    return engine != nullptr && sample != nullptr && engine->update_motion(*sample, now_monotonic_ns);
}

bool app1_engine_check_input_freshness(app1::s12::Engine* engine, std::uint64_t now_monotonic_ns) {
    return engine != nullptr && engine->check_input_freshness(now_monotonic_ns);
}

bool app1_engine_render(app1::s12::Engine* engine, float* output, std::size_t frames) {
    return engine != nullptr && engine->render(output, frames);
}

bool app1_engine_switch_profile(
    app1::s12::Engine* engine,
    const app1::s12::Profile* profile,
    std::uint32_t fade_frames) {
    return engine != nullptr && profile != nullptr && engine->switch_profile(*profile, fade_frames);
}

bool app1_engine_get_state(const app1::s12::Engine* engine, app1::s12::VirtualState* state) {
    if (engine == nullptr || state == nullptr) return false;
    *state = engine->state();
    return true;
}

bool app1_engine_snapshot(const app1::s12::Engine* engine, app1::s12::Snapshot* snapshot) {
    if (engine == nullptr || snapshot == nullptr) return false;
    *snapshot = engine->snapshot();
    return true;
}

bool app1_engine_restore(app1::s12::Engine* engine, const app1::s12::Snapshot* snapshot) {
    return engine != nullptr && snapshot != nullptr && engine->restore(*snapshot);
}

std::size_t app1_sizeof_profile() { return sizeof(app1::s12::Profile); }
std::size_t app1_sizeof_motion_sample() { return sizeof(app1::s12::MotionSample); }
std::size_t app1_sizeof_virtual_state() { return sizeof(app1::s12::VirtualState); }
bool app1_builtin_profile(std::uint32_t index, app1::s12::Profile* profile) {
    return app1::s12::builtin_profile(index, profile);
}

}
