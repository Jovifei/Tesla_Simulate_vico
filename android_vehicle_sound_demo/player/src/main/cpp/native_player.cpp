#include <jni.h>
#include <oboe/Oboe.h>
#include "s12_core/engine.hpp"
#include "volume_ramp.hpp"

#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <new>
#include <time.h>

namespace {

using app1::s12::Direction;
using app1::s12::Engine;
using app1::s12::MotionSample;
using app1::s12::Profile;

constexpr std::uint32_t kQueueCapacity = 256;
constexpr std::uint32_t kFadeFrames = 4800;

std::uint64_t elapsed_realtime_now_ns() noexcept {
    timespec value{};
    if (clock_gettime(CLOCK_BOOTTIME, &value) != 0) return 0;
    return static_cast<std::uint64_t>(value.tv_sec) * 1'000'000'000ULL
        + static_cast<std::uint64_t>(value.tv_nsec);
}

struct Command {
    enum class Kind : std::uint8_t { kMotion, kProfile, kVolume };
    Kind kind{Kind::kMotion};
    MotionSample motion{};
    std::uint32_t profile_index{};
    float volume{};
};

class CommandQueue final {
public:
    bool push(const Command& value) noexcept {
        const auto write = write_.load(std::memory_order_relaxed);
        const auto next = (write + 1U) % kQueueCapacity;
        if (next == read_.load(std::memory_order_acquire)) {
            dropped_.fetch_add(1, std::memory_order_relaxed);
            return false;
        }
        commands_[write] = value;
        write_.store(next, std::memory_order_release);
        return true;
    }

    bool pop(Command& value) noexcept {
        const auto read = read_.load(std::memory_order_relaxed);
        if (read == write_.load(std::memory_order_acquire)) return false;
        value = commands_[read];
        read_.store((read + 1U) % kQueueCapacity, std::memory_order_release);
        return true;
    }

    std::uint32_t dropped() const noexcept { return dropped_.load(std::memory_order_relaxed); }

private:
    std::array<Command, kQueueCapacity> commands_{};
    alignas(64) std::atomic<std::uint32_t> write_{0};
    alignas(64) std::atomic<std::uint32_t> read_{0};
    std::atomic<std::uint32_t> dropped_{0};
};

class PlayerAudio final : public oboe::AudioStreamDataCallback, public oboe::AudioStreamErrorCallback {
public:
    explicit PlayerAudio(std::uint32_t profile_index) noexcept
        : profile_(load_profile(profile_index)), profiles_{load_profile(0), load_profile(1)},
          engine_(profile_, 20260924U),
          valid_(engine_.valid() && app1::s12::profile_is_valid(profiles_[0])
              && app1::s12::profile_is_valid(profiles_[1])) {}

    bool valid() const noexcept { return valid_; }

    bool start() {
        if (!valid_) return false;
        oboe::AudioStreamBuilder builder;
        builder.setDirection(oboe::Direction::Output)
            ->setFormat(oboe::AudioFormat::Float)
            ->setChannelCount(2)
            ->setSampleRate(app1::s12::kOutputSampleRateHz)
            ->setPerformanceMode(oboe::PerformanceMode::LowLatency)
            ->setDataCallback(this)
            ->setErrorCallback(this);
        if (builder.openStream(stream_) != oboe::Result::OK || !stream_) return false;
        const auto burst = stream_->getFramesPerBurst();
        if (burst > 0) stream_->setBufferSizeInFrames(burst * 2);
        if (stream_->requestStart() != oboe::Result::OK) {
            stream_->close();
            stream_.reset();
            return false;
        }
        return true;
    }

    void stop() {
        if (!stream_) return;
        stream_->requestStop();
        stream_->close();
        stream_.reset();
    }

    bool submit_motion(const MotionSample& sample) noexcept {
        Command command{};
        command.kind = Command::Kind::kMotion;
        command.motion = sample;
        return queue_.push(command);
    }

    bool select_profile(std::uint32_t index) noexcept {
        if (index >= profiles_.size()) return false;
        Command command{};
        command.kind = Command::Kind::kProfile;
        command.profile_index = index;
        return queue_.push(command);
    }

    bool set_volume(float volume) noexcept {
        if (!std::isfinite(volume)) return false;
        Command command{};
        command.kind = Command::Kind::kVolume;
        command.volume = volume;
        return queue_.push(command);
    }

    void onErrorAfterClose(oboe::AudioStream*, oboe::Result) override {
        stream_error_.store(true, std::memory_order_release);
    }

    bool stream_error() const noexcept { return stream_error_.load(std::memory_order_acquire); }

    oboe::DataCallbackResult onAudioReady(oboe::AudioStream*, void* audio_data, std::int32_t frames) override {
        const auto callback_start_ns = elapsed_realtime_now_ns();
        Command command{};
        while (queue_.pop(command)) {
            if (command.kind == Command::Kind::kMotion) {
                engine_.update_motion(command.motion, command.motion.received_time_ns);
            } else if (command.kind == Command::Kind::kProfile) {
                if (command.profile_index < profiles_.size()) {
                    engine_.switch_profile_prevalidated(profiles_[command.profile_index], kFadeFrames);
                }
            } else {
                volume_.set_target(command.volume);
            }
        }
        engine_.check_input_freshness(elapsed_realtime_now_ns());
        if (audio_data != nullptr && frames > 0) {
            auto* output = static_cast<float*>(audio_data);
            if (!engine_.render(output, static_cast<std::size_t>(frames))) {
                for (std::int32_t i = 0; i < frames * 2; ++i) output[i] = 0.0F;
            }
            for (std::int32_t i = 0; i < frames; ++i) {
                const float gain = volume_.next();
                output[i * 2] *= gain;
                output[i * 2 + 1] *= gain;
            }
            const auto current = engine_.state();
            rpm_.store(static_cast<float>(current.virtual_rpm), std::memory_order_relaxed);
            load_.store(static_cast<float>(current.load), std::memory_order_relaxed);
            gear_.store(current.gear, std::memory_order_relaxed);
            fallback_.store(current.fallback, std::memory_order_relaxed);
            rendered_frames_.fetch_add(static_cast<std::uint64_t>(frames), std::memory_order_relaxed);
        }
        callbacks_.fetch_add(1, std::memory_order_relaxed);
        const auto callback_end_ns = elapsed_realtime_now_ns();
        const auto elapsed_us = callback_end_ns >= callback_start_ns
            ? static_cast<std::uint32_t>((callback_end_ns - callback_start_ns) / 1000U) : 0U;
        auto previous = max_callback_us_.load(std::memory_order_relaxed);
        while (elapsed_us > previous
            && !max_callback_us_.compare_exchange_weak(previous, elapsed_us, std::memory_order_relaxed)) {}
        return oboe::DataCallbackResult::Continue;
    }

    const char* diagnostics(char* buffer, std::size_t capacity) const noexcept {
        const auto xrun_count = stream_ && stream_->isXRunCountSupported()
            ? stream_->getXRunCount() : oboe::ResultWithValue<std::int32_t>(oboe::Result::ErrorUnimplemented);
        const int xruns = xrun_count ? xrun_count.value() : -1;
        const auto api = stream_ ? static_cast<int>(stream_->getAudioApi()) : -1;
        const auto rate = stream_ ? stream_->getSampleRate() : 0;
        const auto channels = stream_ ? stream_->getChannelCount() : 0;
        std::snprintf(buffer, capacity,
            "api=%d rate=%d channels=%d xruns=%d callbacks=%llu frames=%llu max_callback_us=%u dropped=%u rpm=%.0f gear=%u fallback=%u stream_error=%u",
            api, rate, channels, xruns,
            static_cast<unsigned long long>(callbacks_.load(std::memory_order_relaxed)),
            static_cast<unsigned long long>(rendered_frames_.load(std::memory_order_relaxed)),
            max_callback_us_.load(std::memory_order_relaxed), queue_.dropped(),
            rpm_.load(std::memory_order_relaxed), gear_.load(std::memory_order_relaxed),
            fallback_.load(std::memory_order_relaxed) ? 1U : 0U,
            stream_error() ? 1U : 0U);
        return buffer;
    }

private:
    static Profile load_profile(std::uint32_t index) noexcept {
        Profile result{};
        app1::s12::builtin_profile(index, &result);
        return result;
    }

    Profile profile_{};
    std::array<Profile, 2> profiles_{};
    Engine engine_;
    VolumeRamp volume_{};
    CommandQueue queue_{};
    std::shared_ptr<oboe::AudioStream> stream_{};
    std::atomic<std::uint64_t> callbacks_{0};
    std::atomic<std::uint64_t> rendered_frames_{0};
    std::atomic<std::uint32_t> max_callback_us_{0};
    std::atomic<float> rpm_{0.0F};
    std::atomic<float> load_{0.0F};
    std::atomic<std::uint32_t> gear_{0};
    std::atomic<bool> fallback_{true};
    std::atomic<bool> stream_error_{false};
    bool valid_{};
};

}  // namespace

extern "C" JNIEXPORT jlong JNICALL
Java_com_jovi_s12player_DriveAudioService_nativeStart(JNIEnv*, jclass, jint profile_index) {
    auto* player = new (std::nothrow) PlayerAudio(static_cast<std::uint32_t>(profile_index));
    if (player == nullptr || !player->valid() || !player->start()) {
        delete player;
        return 0;
    }
    return reinterpret_cast<jlong>(player);
}

extern "C" JNIEXPORT void JNICALL
Java_com_jovi_s12player_DriveAudioService_nativeStop(JNIEnv*, jclass, jlong handle) {
    auto* player = reinterpret_cast<PlayerAudio*>(handle);
    if (player == nullptr) return;
    player->stop();
    delete player;
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_jovi_s12player_DriveAudioService_nativeSubmitMotion(
    JNIEnv*, jclass, jlong handle, jlong sequence, jlong measurement_ns, jlong received_ns,
    jdouble speed_mps, jdouble acceleration_mps2, jint direction, jboolean valid) {
    auto* player = reinterpret_cast<PlayerAudio*>(handle);
    if (player == nullptr) return JNI_FALSE;
    const auto safe_direction = direction >= 0 && direction <= 3
        ? static_cast<Direction>(direction) : Direction::kUnknown;
    const MotionSample sample{
        static_cast<std::uint64_t>(sequence),
        static_cast<std::uint64_t>(measurement_ns),
        static_cast<std::uint64_t>(received_ns),
        speed_mps,
        acceleration_mps2,
        safe_direction,
        valid == JNI_TRUE,
    };
    return player->submit_motion(sample) ? JNI_TRUE : JNI_FALSE;
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_jovi_s12player_DriveAudioService_nativeSelectProfile(JNIEnv*, jclass, jlong handle, jint profile_index) {
    auto* player = reinterpret_cast<PlayerAudio*>(handle);
    if (player == nullptr || profile_index < 0) return JNI_FALSE;
    return player->select_profile(static_cast<std::uint32_t>(profile_index)) ? JNI_TRUE : JNI_FALSE;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_jovi_s12player_DriveAudioService_nativeGetDiagnostics(JNIEnv* env, jclass, jlong handle) {
    auto* player = reinterpret_cast<PlayerAudio*>(handle);
    if (player == nullptr) return env->NewStringUTF("audio=stopped");
    char buffer[256]{};
    return env->NewStringUTF(player->diagnostics(buffer, sizeof(buffer)));
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_jovi_s12player_DriveAudioService_nativeHasStreamError(JNIEnv*, jclass, jlong handle) {
    auto* player = reinterpret_cast<PlayerAudio*>(handle);
    return player != nullptr && player->stream_error() ? JNI_TRUE : JNI_FALSE;
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_jovi_s12player_DriveAudioService_nativeSetVolume(JNIEnv*, jclass, jlong handle, jfloat volume) {
    auto* player = reinterpret_cast<PlayerAudio*>(handle);
    return player != nullptr && player->set_volume(volume) ? JNI_TRUE : JNI_FALSE;
}
