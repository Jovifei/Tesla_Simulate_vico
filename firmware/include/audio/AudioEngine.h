#pragma once

#include "domain/VehicleState.h"

namespace tesla_speed::audio {

class AudioEngine {
 public:
  virtual ~AudioEngine() = default;
  virtual bool begin() = 0;
  virtual void render(const tesla_speed::domain::VehicleState& state) = 0;
  virtual void setMuted(bool muted) = 0;
};

}  // namespace tesla_speed::audio
