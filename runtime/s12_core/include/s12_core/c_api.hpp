#pragma once

#include "s12_core/engine.hpp"

#if defined(_WIN32)
#define APP1_CORE_API __declspec(dllexport)
#else
#define APP1_CORE_API __attribute__((visibility("default")))
#endif

extern "C" {

APP1_CORE_API app1::s12::Engine* app1_engine_create(const app1::s12::Profile* profile, std::uint32_t seed);
APP1_CORE_API void app1_engine_destroy(app1::s12::Engine* engine);
APP1_CORE_API bool app1_engine_update_motion(
    app1::s12::Engine* engine,
    const app1::s12::MotionSample* sample,
    std::uint64_t now_monotonic_ns);
APP1_CORE_API bool app1_engine_check_input_freshness(app1::s12::Engine* engine, std::uint64_t now_monotonic_ns);
APP1_CORE_API bool app1_engine_render(app1::s12::Engine* engine, float* interleaved_stereo, std::size_t frames);
APP1_CORE_API bool app1_engine_switch_profile(
    app1::s12::Engine* engine,
    const app1::s12::Profile* profile,
    std::uint32_t fade_frames);
APP1_CORE_API bool app1_engine_get_state(const app1::s12::Engine* engine, app1::s12::VirtualState* state);
APP1_CORE_API bool app1_engine_snapshot(const app1::s12::Engine* engine, app1::s12::Snapshot* snapshot);
APP1_CORE_API bool app1_engine_restore(app1::s12::Engine* engine, const app1::s12::Snapshot* snapshot);
APP1_CORE_API std::size_t app1_sizeof_profile();
APP1_CORE_API std::size_t app1_sizeof_motion_sample();
APP1_CORE_API std::size_t app1_sizeof_virtual_state();
APP1_CORE_API bool app1_builtin_profile(std::uint32_t index, app1::s12::Profile* profile);

}
