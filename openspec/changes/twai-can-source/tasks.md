# Tasks: twai-can-source

## S1.2 — TWAI Real Reception

- [x] **T1: Configure TWAI driver in begin()** — Install TWAI driver with listen-only mode, 500 kbps timing, RX queue depth 5. Set CAN_RS HIGH. Call `twai_start()`. Return true on success.

- [x] **T2: Implement poll() frame reception** — Call `twai_receive()` with 0 timeout. On receive, dispatch by frame.identifier: 0x256 → parseSpeed, 0x116 → parseTorque. Update VehicleState fields. Set can_valid=true.

- [x] **T3: Include correct ESP-IDF headers** — Add `#include "driver/twai.h"` in TwaiCanSource.cpp. Ensure pin_map.h and CanFrames.h are included.

- [x] **T4: Build verification** — `idf.py build` succeeds with no errors. No transmit API referenced anywhere in can/ component.

- [x] **T5: No-transmit static verification** — Grep components/can/ for `twai_transmit`, `send`, `write` — zero matches. Confirms listen-only invariant.

- [x] **T6: Commit and verify** — Commit with comet-build message. Run unity tests if applicable. Verify build clean.
