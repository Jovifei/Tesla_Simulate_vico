#include "audio/AudioVolume.h"
#include "audio/StubAudioEngine.h"

#include <cstdint>

static_assert(audio::volumeGain(0) == 0.0f, "0 percent must mute audio");
static_assert(audio::volumeGain(100) == 1.0f, "100 percent must be unity gain");
static_assert(audio::volumeGain(150) == 1.0f, "volume above 100 must clamp");

void compile_audio_volume_contract() {
    audio::StubAudioEngine engine;
    audio::AudioEngine& base = engine;
    base.setVolumePercent(42);

    const std::uint8_t observed = engine.volumePercent();
    (void)observed;
}
