#include "volume_ramp.hpp"
#include <cassert>
#include <cmath>
#include <limits>

int main() {
    VolumeRamp gain;
    assert(gain.next() == 0.0F);
    gain.set_target(0.0F, 960);
    assert(gain.next() == 0.0F);
    gain.set_target(1.0F, 960);
    float previous = gain.next();
    for (int i = 1; i < 960; ++i) {
        const float value = gain.next();
        assert(value >= previous && value <= 1.0F);
        previous = value;
    }
    assert(gain.value() == 1.0F);
    gain.set_target(0.0F, 960);
    for (int i = 0; i < 959; ++i) assert(gain.next() > 0.0F);
    assert(gain.next() == 0.0F);
    assert(gain.at_zero());
    gain.set_target(std::numeric_limits<float>::quiet_NaN());
    assert(std::isfinite(gain.next()));
    gain.set_target(2.0F, 960);
    for (int i = 0; i < 960; ++i) assert(gain.next() <= 1.0F);
    assert(gain.value() == 1.0F);
    gain.set_target(0.0F, 960);
    for (int i = 0; i < 480; ++i) gain.next();
    const float halfway = gain.value();
    gain.set_target(0.8F, 960);
    const float following = gain.next();
    assert(following >= halfway && following <= 0.8F);
}
