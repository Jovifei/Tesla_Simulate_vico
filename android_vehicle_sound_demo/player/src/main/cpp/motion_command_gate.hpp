#pragma once

#include "s12_core/engine.hpp"

#include <array>
#include <atomic>
#include <cstdint>

namespace app1::s12 {

constexpr std::uint32_t kMotionQueueCapacity = 256;
constexpr std::uint32_t kMaxCommandsPerCallback = 32;

struct PlaybackCommand {
    enum class Kind : std::uint8_t { kMotion, kProfile, kVolume };
    Kind kind{Kind::kMotion};
    MotionSample motion{};
    std::uint32_t profile_index{};
    float volume{};
};

class PlaybackCommandQueue final {
public:
    bool push(const PlaybackCommand& value) noexcept {
        const auto write = write_.load(std::memory_order_relaxed);
        const auto next = (write + 1U) % kMotionQueueCapacity;
        if (next == read_.load(std::memory_order_acquire)) {
            dropped_.fetch_add(1, std::memory_order_relaxed);
            return false;
        }
        commands_[write] = value;
        write_.store(next, std::memory_order_release);
        return true;
    }

    bool pop(PlaybackCommand& value) noexcept {
        const auto read = read_.load(std::memory_order_relaxed);
        if (read == write_.load(std::memory_order_acquire)) return false;
        value = commands_[read];
        read_.store((read + 1U) % kMotionQueueCapacity, std::memory_order_release);
        return true;
    }

    std::uint32_t dropped() const noexcept { return dropped_.load(std::memory_order_relaxed); }

private:
    std::array<PlaybackCommand, kMotionQueueCapacity> commands_{};
    alignas(64) std::atomic<std::uint32_t> write_{0};
    alignas(64) std::atomic<std::uint32_t> read_{0};
    std::atomic<std::uint32_t> dropped_{0};
};

class MotionCommandGate final {
public:
    bool submit_motion(const MotionSample& sample) noexcept {
        PlaybackCommand command{};
        command.kind = PlaybackCommand::Kind::kMotion;
        command.motion = sample;
        return queue_.push(command);
    }

    bool select_profile(std::uint32_t index) noexcept {
        PlaybackCommand command{};
        command.kind = PlaybackCommand::Kind::kProfile;
        command.profile_index = index;
        return queue_.push(command);
    }

    bool set_volume(float volume) noexcept {
        PlaybackCommand command{};
        command.kind = PlaybackCommand::Kind::kVolume;
        command.volume = volume;
        return queue_.push(command);
    }

    void invalidate_before(std::uint64_t next_sequence) noexcept {
        requested_boundary_.store(next_sequence, std::memory_order_release);
        invalidation_pending_.store(true, std::memory_order_release);
    }

    template<class ProfileHandler, class VolumeHandler>
    void consume(Engine& engine, std::uint64_t now_ns,
            ProfileHandler&& on_profile, VolumeHandler&& on_volume) noexcept {
        if (invalidation_pending_.exchange(false, std::memory_order_acq_rel)) {
            const auto boundary = requested_boundary_.load(std::memory_order_acquire);
            if (!has_invalidation_ || boundary > discarded_before_) discarded_before_ = boundary;
            has_invalidation_ = true;
            engine.update_motion(MotionSample{}, now_ns);
        }
        PlaybackCommand command{};
        for (std::uint32_t i = 0; i < kMaxCommandsPerCallback && queue_.pop(command); ++i) {
            if (command.kind == PlaybackCommand::Kind::kMotion) {
                if (!has_invalidation_ || command.motion.sequence >= discarded_before_)
                    engine.update_motion(command.motion, now_ns);
            } else if (command.kind == PlaybackCommand::Kind::kProfile)
                on_profile(command.profile_index);
            else
                on_volume(command.volume);
        }
    }

    std::uint32_t dropped() const noexcept { return queue_.dropped(); }

private:
    PlaybackCommandQueue queue_{};
    std::atomic<std::uint64_t> requested_boundary_{0};
    std::atomic<bool> invalidation_pending_{false};
    std::uint64_t discarded_before_{};
    bool has_invalidation_{};
};

}  // namespace app1::s12
