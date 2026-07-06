#include <Arduino.h>

#include "app/App.h"
#include "config/pin_map.h"

namespace {
tesla_speed::app::App app;
}

void setup() {
  pinMode(tesla_speed::config::pins::LED_PWR, OUTPUT);
  digitalWrite(tesla_speed::config::pins::LED_PWR, HIGH);
  app.begin();
}

void loop() {
  app.tick();
  delay(10);
}
