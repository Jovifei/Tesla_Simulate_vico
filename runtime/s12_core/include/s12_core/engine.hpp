#pragma once

#include <cstddef>
#include <cstdint>

namespace app1::s12 {

constexpr std::size_t kMaxGears = 8;
constexpr std::size_t kMaxOrders = 8;
constexpr std::size_t kProfileIdLength = 48;
constexpr std::uint32_t kOutputSampleRateHz = 48000;

enum class Direction : std::uint8_t { kForward, kReverse, kStationary, kUnknown };
enum class Event : std::uint8_t { kNone, kShiftUp, kShiftDown };

struct Order {
    double order;
    double amplitude;
    double phase_rad;
};

struct Profile {
    char profile_id[kProfileIdLength]{};
    double idle_rpm{};
    double max_rpm{};
    double rpm_per_mps_by_gear[kMaxGears]{};
    std::uint32_t gear_count{};
    double acceleration_rpm_per_mps2{};
    double upshift_rpm{};
    double downshift_rpm{};
    double shift_rpm_drop{};
    double idle_load{};
    double positive_acceleration_load_per_mps2{};
    double negative_acceleration_load_per_mps2{};
    Order orders[kMaxOrders]{};
    std::uint32_t order_count{};
    double transient_gain{};
    double acceleration_reference_mps2{};
    double attack_s{};
    double release_s{};
    double shift_impulse{};
    double carrier_order{};
    std::uint32_t sample_rate_hz{kOutputSampleRateHz};
    double output_gain{};
    double peak_limit{};
};

struct MotionSample {
    std::uint64_t sequence{};
    std::uint64_t measurement_time_ns{};
    std::uint64_t received_time_ns{};
    double speed_mps{};
    double acceleration_mps2{};
    Direction direction{Direction::kUnknown};
    bool valid{};
};

struct VirtualState {
    double virtual_rpm{};
    double load{};
    std::uint32_t gear{};
    Event event{Event::kNone};
    std::uint64_t shift_events{};
    std::uint64_t sample_index{};
    bool fallback{};
};

struct Snapshot {
    std::uint32_t version{1};
    char profile_id[kProfileIdLength]{};
    Profile fade_from{};
    double phase{};
    double rpm{};
    double target_rpm{};
    double load{};
    double target_load{};
    double acceleration_mps2{};
    double shift_tail{};
    double envelope{};
    double last_speed_mps{};
    std::uint64_t last_sequence{};
    std::uint64_t last_measurement_time_ns{};
    std::uint64_t shift_events{};
    std::uint64_t sample_index{};
    std::uint32_t gear{};
    std::uint32_t fade_total_frames{};
    std::uint32_t fade_remaining_frames{};
    Direction last_direction{Direction::kStationary};
    Event last_event{Event::kNone};
    bool has_previous_sample{};
    bool fallback{};
    bool fading{};
};

bool profile_is_valid(const Profile& profile) noexcept;
bool builtin_profile(std::uint32_t index, Profile* output) noexcept;

class Engine final {
public:
    explicit Engine(const Profile& profile, std::uint32_t seed = 0) noexcept;

    bool valid() const noexcept { return valid_; }
    bool update_motion(const MotionSample& sample, std::uint64_t now_monotonic_ns) noexcept;
    bool check_input_freshness(std::uint64_t now_monotonic_ns) noexcept;
    bool render(float* interleaved_stereo, std::size_t frame_count) noexcept;
    bool switch_profile(const Profile& profile, std::uint32_t fade_frames) noexcept;
    // Audio-thread path: call only with a profile validated before publication.
    bool switch_profile_prevalidated(const Profile& profile, std::uint32_t fade_frames) noexcept;
    VirtualState state() const noexcept;
    Snapshot snapshot() const noexcept;
    bool restore(const Snapshot& snapshot) noexcept;

private:
    void set_safe_fallback() noexcept;
    void map_targets() noexcept;
    double render_profile(const Profile& profile) const noexcept;
    bool snapshot_is_valid(const Snapshot& snapshot) const noexcept;

    Profile profile_{};
    Profile fade_from_{};
    double phase_{};
    double rpm_{};
    double target_rpm_{};
    double load_{};
    double target_load_{};
    double acceleration_mps2_{};
    double shift_tail_{};
    double envelope_{};
    double last_speed_mps_{};
    std::uint64_t last_sequence_{};
    std::uint64_t last_measurement_time_ns_{};
    std::uint64_t shift_events_{};
    std::uint64_t sample_index_{};
    std::uint32_t gear_{};
    std::uint32_t fade_total_frames_{};
    std::uint32_t fade_remaining_frames_{};
    Direction last_direction_{Direction::kStationary};
    Event last_event_{Event::kNone};
    bool has_previous_sample_{};
    bool fallback_{};
    bool fading_{};
    bool valid_{};
};

}  // namespace app1::s12
