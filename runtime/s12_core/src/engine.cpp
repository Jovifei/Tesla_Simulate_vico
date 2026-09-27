#include "s12_core/engine.hpp"

#include <cmath>
#include <cstdio>
#include <cstring>

namespace app1::s12 {
namespace {

constexpr double kTau = 6.283185307179586476925286766559;
constexpr std::uint64_t kMaxInputAgeNs = 500'000'000;

bool finite(double value) noexcept { return std::isfinite(value); }

double clamp(double value, double low, double high) noexcept {
    return value < low ? low : (value > high ? high : value);
}

std::uint32_t profile_crc32(const char* text) noexcept {
    std::uint32_t crc = 0xFFFFFFFFU;
    for (; *text != '\0'; ++text) {
        crc ^= static_cast<std::uint8_t>(*text);
        for (int bit = 0; bit < 8; ++bit) {
            const std::uint32_t mask = 0U - (crc & 1U);
            crc = (crc >> 1U) ^ (0xEDB88320U & mask);
        }
    }
    return ~crc;
}

bool finite_profile_state(const Snapshot& state) noexcept {
    return finite(state.phase) && finite(state.rpm) && finite(state.target_rpm)
        && finite(state.load) && finite(state.target_load)
        && finite(state.acceleration_mps2) && finite(state.shift_tail)
        && finite(state.envelope) && finite(state.last_speed_mps);
}

}  // namespace

bool profile_is_valid(const Profile& profile) noexcept {
    bool has_id_terminator = false;
    for (std::size_t i = 0; i < kProfileIdLength; ++i) {
        if (profile.profile_id[i] == '\0') {
            has_id_terminator = i > 0;
            break;
        }
    }
    if (!has_id_terminator || std::strncmp(profile.profile_id, "experimental-", 13) != 0) return false;
    if (profile.gear_count < 2 || profile.gear_count > kMaxGears
        || profile.order_count == 0 || profile.order_count > kMaxOrders
        || profile.sample_rate_hz != kOutputSampleRateHz) return false;
    if (!finite(profile.idle_rpm) || !finite(profile.max_rpm)
        || profile.idle_rpm < 500.0 || profile.max_rpm <= profile.idle_rpm
        || profile.max_rpm > 12000.0 || !finite(profile.acceleration_rpm_per_mps2)
        || !finite(profile.upshift_rpm) || !finite(profile.downshift_rpm)
        || !finite(profile.shift_rpm_drop) || !finite(profile.idle_load)
        || !finite(profile.positive_acceleration_load_per_mps2)
        || !finite(profile.negative_acceleration_load_per_mps2)) return false;
    if (profile.acceleration_rpm_per_mps2 < 0.0 || profile.upshift_rpm <= profile.downshift_rpm
        || profile.shift_rpm_drop <= 0.1 || profile.shift_rpm_drop > 1.0
        || profile.idle_load < 0.0 || profile.idle_load > 0.5
        || profile.positive_acceleration_load_per_mps2 < 0.0
        || profile.negative_acceleration_load_per_mps2 < 0.0) return false;
    for (std::uint32_t i = 0; i < profile.gear_count; ++i) {
        if (!finite(profile.rpm_per_mps_by_gear[i]) || profile.rpm_per_mps_by_gear[i] <= 0.0) return false;
    }
    for (std::uint32_t i = 0; i < profile.order_count; ++i) {
        const auto& order = profile.orders[i];
        if (!finite(order.order) || !finite(order.amplitude) || !finite(order.phase_rad)
            || order.order <= 0.0 || order.amplitude < 0.0 || order.amplitude > 1.0) return false;
    }
    return finite(profile.transient_gain) && finite(profile.acceleration_reference_mps2)
        && finite(profile.attack_s) && finite(profile.release_s)
        && finite(profile.shift_impulse) && finite(profile.carrier_order)
        && finite(profile.output_gain) && finite(profile.peak_limit)
        && profile.transient_gain >= 0.0 && profile.transient_gain <= 1.0
        && profile.acceleration_reference_mps2 > 0.0
        && profile.attack_s > 0.0 && profile.release_s > 0.0
        && profile.shift_impulse >= 0.0 && profile.shift_impulse <= 1.0
        && profile.carrier_order > 0.0
        && profile.output_gain >= 0.0 && profile.output_gain <= 1.0
        && profile.peak_limit > 0.0 && profile.peak_limit <= 1.0;
}

bool builtin_profile(std::uint32_t index, Profile* output) noexcept {
    if (output == nullptr || index > 1) return false;
    Profile profile{};
    profile.sample_rate_hz = kOutputSampleRateHz;
    profile.gear_count = 4;
    profile.order_count = 3;
    if (index == 0) {
        std::snprintf(profile.profile_id, sizeof(profile.profile_id), "%s", "experimental-v8-synth");
        profile.idle_rpm = 850.0;
        profile.max_rpm = 6500.0;
        profile.rpm_per_mps_by_gear[0] = 220.0;
        profile.rpm_per_mps_by_gear[1] = 135.0;
        profile.rpm_per_mps_by_gear[2] = 95.0;
        profile.rpm_per_mps_by_gear[3] = 72.0;
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
        profile.transient_gain = 0.12;
        profile.acceleration_reference_mps2 = 4.0;
        profile.attack_s = 0.035;
        profile.release_s = 0.14;
        profile.shift_impulse = 0.35;
        profile.carrier_order = 1.5;
        profile.output_gain = 0.42;
        profile.peak_limit = 0.92;
    } else {
        std::snprintf(profile.profile_id, sizeof(profile.profile_id), "%s", "experimental-rotary-synth");
        profile.idle_rpm = 950.0;
        profile.max_rpm = 9000.0;
        profile.rpm_per_mps_by_gear[0] = 300.0;
        profile.rpm_per_mps_by_gear[1] = 180.0;
        profile.rpm_per_mps_by_gear[2] = 125.0;
        profile.rpm_per_mps_by_gear[3] = 90.0;
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
        profile.transient_gain = 0.10;
        profile.acceleration_reference_mps2 = 4.0;
        profile.attack_s = 0.025;
        profile.release_s = 0.12;
        profile.shift_impulse = 0.30;
        profile.carrier_order = 1.8;
        profile.output_gain = 0.40;
        profile.peak_limit = 0.92;
    }
    if (!profile_is_valid(profile)) return false;
    *output = profile;
    return true;
}

Engine::Engine(const Profile& profile, std::uint32_t seed) noexcept
    : profile_(profile), valid_(profile_is_valid(profile)) {
    if (!valid_) return;
    std::memcpy(fade_from_.profile_id, profile_.profile_id, sizeof(profile_.profile_id));
    const auto seed_bits = profile_crc32(profile_.profile_id) ^ seed;
    phase_ = kTau * static_cast<double>(seed_bits & 0xFFFFU) / 65536.0;
    rpm_ = target_rpm_ = profile_.idle_rpm;
    load_ = target_load_ = profile_.idle_load;
}

bool Engine::update_motion(const MotionSample& sample, std::uint64_t now_ns) noexcept {
    const auto direction = static_cast<std::uint8_t>(sample.direction);
    bool accepted = valid_ && sample.valid && direction <= static_cast<std::uint8_t>(Direction::kUnknown)
        && sample.received_time_ns >= sample.measurement_time_ns
        && sample.received_time_ns <= now_ns
        && now_ns - sample.measurement_time_ns <= kMaxInputAgeNs
        && finite(sample.speed_mps) && finite(sample.acceleration_mps2)
        && sample.speed_mps >= 0.0 && sample.speed_mps <= 100.0
        && std::abs(sample.acceleration_mps2) <= 20.0;
    if (has_previous_sample_) {
        accepted = accepted && sample.sequence > last_sequence_
            && sample.measurement_time_ns > last_measurement_time_ns_;
    }
    if (!accepted) {
        set_safe_fallback();
        return false;
    }
    has_previous_sample_ = true;
    last_sequence_ = sample.sequence;
    last_measurement_time_ns_ = sample.measurement_time_ns;
    last_speed_mps_ = sample.speed_mps;
    last_direction_ = sample.direction;
    acceleration_mps2_ = sample.acceleration_mps2;
    fallback_ = false;
    map_targets();
    return true;
}

bool Engine::check_input_freshness(std::uint64_t now_ns) noexcept {
    if (!valid_ || !has_previous_sample_ || now_ns < last_measurement_time_ns_
        || now_ns - last_measurement_time_ns_ > kMaxInputAgeNs) {
        set_safe_fallback();
        return false;
    }
    return !fallback_;
}

void Engine::set_safe_fallback() noexcept {
    fallback_ = true;
    last_event_ = Event::kNone;
    if (valid_) {
        target_rpm_ = profile_.idle_rpm;
        target_load_ = 0.0;
    }
    acceleration_mps2_ = 0.0;
}

void Engine::map_targets() noexcept {
    const double speed = last_direction_ == Direction::kStationary ? 0.0 : last_speed_mps_;
    const double positive_accel = acceleration_mps2_ > 0.0 ? acceleration_mps2_ : 0.0;
    const double negative_accel = acceleration_mps2_ < 0.0 ? -acceleration_mps2_ : 0.0;
    const double predicted = profile_.idle_rpm + speed * profile_.rpm_per_mps_by_gear[gear_]
        + positive_accel * profile_.acceleration_rpm_per_mps2;
    last_event_ = Event::kNone;
    if (predicted > profile_.upshift_rpm && gear_ + 1 < profile_.gear_count) {
        ++gear_;
        last_event_ = Event::kShiftUp;
    } else if (predicted < profile_.downshift_rpm && gear_ > 0) {
        --gear_;
        last_event_ = Event::kShiftDown;
    }
    double target = profile_.idle_rpm + speed * profile_.rpm_per_mps_by_gear[gear_]
        + positive_accel * profile_.acceleration_rpm_per_mps2;
    if (last_event_ != Event::kNone) {
        target *= profile_.shift_rpm_drop;
        ++shift_events_;
        shift_tail_ = profile_.shift_impulse;
    }
    target_rpm_ = clamp(target, profile_.idle_rpm, profile_.max_rpm);
    target_load_ = clamp(
        profile_.idle_load
            + positive_accel * profile_.positive_acceleration_load_per_mps2
            - negative_accel * profile_.negative_acceleration_load_per_mps2,
        0.0, 1.0);
}

double Engine::render_profile(const Profile& profile) const noexcept {
    double harmonic = 0.0;
    for (std::uint32_t i = 0; i < profile.order_count; ++i) {
        const auto& partial = profile.orders[i];
        const double load_shape = 0.70 + load_ * 0.55 * (partial.order / 4.0 > 1.0 ? partial.order / 4.0 : 1.0);
        harmonic += partial.amplitude * load_shape * std::sin(partial.order * phase_ + partial.phase_rad);
    }
    const double transient = profile.transient_gain * envelope_
        * std::sin(profile.carrier_order * phase_);
    const double raw = profile.output_gain * (harmonic + transient);
    return profile.peak_limit * std::tanh(raw / profile.peak_limit);
}

bool Engine::render(float* output, std::size_t frames) noexcept {
    if (!valid_ || output == nullptr || frames == 0) return false;
    const double rpm_smoothing = 1.0 / (0.05 * kOutputSampleRateHz);
    const double load_smoothing = 1.0 / (0.04 * kOutputSampleRateHz);
    for (std::size_t frame = 0; frame < frames; ++frame) {
        rpm_ += (target_rpm_ - rpm_) * rpm_smoothing;
        load_ += (target_load_ - load_) * load_smoothing;
        phase_ = std::fmod(phase_ + kTau * rpm_ / 60.0 / kOutputSampleRateHz, kTau);
        const double envelope_target = std::fmin(
            1.0, std::abs(acceleration_mps2_) / profile_.acceleration_reference_mps2 + shift_tail_);
        const double envelope_time = envelope_target > envelope_ ? profile_.attack_s : profile_.release_s;
        envelope_ += (envelope_target - envelope_) / std::fmax(1.0, envelope_time * kOutputSampleRateHz);
        shift_tail_ *= std::exp(-1.0 / (0.08 * kOutputSampleRateHz));

        double sample = render_profile(profile_);
        if (fading_) {
            const double progress = static_cast<double>(fade_total_frames_ - fade_remaining_frames_)
                / static_cast<double>(fade_total_frames_);
            const double fade_angle = 0.25 * kTau * progress;
            const double old_gain = std::cos(fade_angle);
            const double new_gain = std::sin(fade_angle);
            sample = old_gain * render_profile(fade_from_) + new_gain * sample;
            if (--fade_remaining_frames_ == 0) fading_ = false;
        }
        const float output_sample = static_cast<float>(sample);
        output[frame * 2] = output_sample;
        output[frame * 2 + 1] = output_sample;
        ++sample_index_;
    }
    return true;
}

bool Engine::switch_profile(const Profile& profile, std::uint32_t fade_frames) noexcept {
    if (!profile_is_valid(profile)) return false;
    return switch_profile_prevalidated(profile, fade_frames);
}

bool Engine::switch_profile_prevalidated(const Profile& profile, std::uint32_t fade_frames) noexcept {
    if (!valid_) return false;
    fade_from_ = profile_;
    profile_ = profile;
    fading_ = fade_frames > 0;
    fade_total_frames_ = fade_frames;
    fade_remaining_frames_ = fade_frames;
    if (!has_previous_sample_) {
        target_rpm_ = profile_.idle_rpm;
        rpm_ = profile_.idle_rpm;
        target_load_ = profile_.idle_load;
        load_ = profile_.idle_load;
    } else {
        gear_ = 0;
        map_targets();
    }
    return true;
}

VirtualState Engine::state() const noexcept {
    return VirtualState{
        target_rpm_, target_load_, gear_ + 1, last_event_, shift_events_, sample_index_, fallback_
    };
}

Snapshot Engine::snapshot() const noexcept {
    Snapshot value{};
    value.version = 1;
    std::memcpy(value.profile_id, profile_.profile_id, sizeof(value.profile_id));
    value.fade_from = fade_from_;
    value.phase = phase_;
    value.rpm = rpm_;
    value.target_rpm = target_rpm_;
    value.load = load_;
    value.target_load = target_load_;
    value.acceleration_mps2 = acceleration_mps2_;
    value.shift_tail = shift_tail_;
    value.envelope = envelope_;
    value.last_speed_mps = last_speed_mps_;
    value.last_sequence = last_sequence_;
    value.last_measurement_time_ns = last_measurement_time_ns_;
    value.shift_events = shift_events_;
    value.sample_index = sample_index_;
    value.gear = gear_;
    value.fade_total_frames = fade_total_frames_;
    value.fade_remaining_frames = fade_remaining_frames_;
    value.last_direction = last_direction_;
    value.last_event = last_event_;
    value.has_previous_sample = has_previous_sample_;
    value.fallback = fallback_;
    value.fading = fading_;
    return value;
}

bool Engine::snapshot_is_valid(const Snapshot& value) const noexcept {
    return value.version == 1 && std::strncmp(value.profile_id, profile_.profile_id, kProfileIdLength) == 0
        && finite_profile_state(value) && value.gear < profile_.gear_count
        && value.target_rpm >= profile_.idle_rpm && value.target_rpm <= profile_.max_rpm
        && value.rpm >= profile_.idle_rpm && value.rpm <= profile_.max_rpm
        && value.load >= 0.0 && value.load <= 1.0 && value.target_load >= 0.0 && value.target_load <= 1.0
        && value.shift_tail >= 0.0 && value.shift_tail <= 1.0 && value.envelope >= 0.0 && value.envelope <= 1.0
        && value.fade_remaining_frames <= value.fade_total_frames
        && (!value.fading || (value.fade_total_frames > 0 && profile_is_valid(value.fade_from)));
}

bool Engine::restore(const Snapshot& value) noexcept {
    if (!valid_ || !snapshot_is_valid(value)) return false;
    fade_from_ = value.fade_from;
    phase_ = value.phase;
    rpm_ = value.rpm;
    target_rpm_ = value.target_rpm;
    load_ = value.load;
    target_load_ = value.target_load;
    acceleration_mps2_ = value.acceleration_mps2;
    shift_tail_ = value.shift_tail;
    envelope_ = value.envelope;
    last_speed_mps_ = value.last_speed_mps;
    last_sequence_ = value.last_sequence;
    last_measurement_time_ns_ = value.last_measurement_time_ns;
    shift_events_ = value.shift_events;
    sample_index_ = value.sample_index;
    gear_ = value.gear;
    fade_total_frames_ = value.fade_total_frames;
    fade_remaining_frames_ = value.fade_remaining_frames;
    last_direction_ = value.last_direction;
    last_event_ = value.last_event;
    has_previous_sample_ = value.has_previous_sample;
    fallback_ = value.fallback;
    fading_ = value.fading;
    return true;
}

}  // namespace app1::s12
