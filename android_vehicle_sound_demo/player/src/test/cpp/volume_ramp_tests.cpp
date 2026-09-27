#include "volume_ramp.hpp"
#include <cassert>
#include <cmath>
#include <limits>

int main() {
    VolumeRamp gain;
    assert(gain.next() == 1.0F);
    gain.set_target(0.0F);
    const float first = gain.next();
    assert(first > 0.0F && first < 1.0F);
    for (int i = 0; i < 10000; ++i) gain.next();
    assert(gain.next() < 0.001F);
    gain.set_target(std::numeric_limits<float>::quiet_NaN());
    assert(std::isfinite(gain.next()));
    gain.set_target(2.0F);
    for (int i = 0; i < 10000; ++i) gain.next();
    assert(gain.next() <= 1.0F);
}
