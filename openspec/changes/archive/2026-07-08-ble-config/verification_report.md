# Verification Report: ble-config (S3)

- **Change**: ble-config
- **Workflow**: full
- **Verify mode**: full
- **Branch**: feature/ble-config (build commit 9c6475a)
- **Base ref**: d456100
- **Date**: 2026-07-07
- **Verdict**: PASS (with deferred runtime verification)

## 1. Build

| Item | Result |
|------|--------|
| Command | `idf.py build` |
| Exit code | 0 |
| Output binary | `build/tesla_simulate_vico.bin` |
| Binary size | 601488 bytes (0x92D90) |
| App partition headroom | ~86% free |
| BLE component errors | none |

`BleService` compiles against the NimBLE `bt` component headers and the frozen
`domain::VehicleState` (S1/S2) with no errors or warnings from the ble component.

## 2. Spec Conformance

Delta spec `specs/ble-config/spec.md` validated with `openspec validate ble-config --strict`
→ `Change 'ble-config' is valid`. Structure: 1 `## ADDED Requirements` section,
5 requirements, all with `SHALL` normative language and WHEN/THEN scenarios.

| Requirement | Implementation evidence | Status |
|-------------|------------------------|--------|
| NimBLE GATT server init | `nimble_port_init`, `ble_hs_cfg` sync/reset cbs, `ble_svc_gap_init`/`ble_svc_gatt_init`, `ble_gatts_count_cfg` + `ble_gatts_add_svcs`, `nimble_port_freertos_init` | PASS |
| Primary service on UUID ffe0 | static `ble_gatt_svc_def[]`, `BLE_GATT_SVC_TYPE_PRIMARY`, `ble::kServiceUuid`, zeroed sentinel | PASS |
| Seven characteristics ffe1–ffe7 | config/state/audio/can/diagnostics/profile/control chars with read/write flags + access cb | PASS |
| Characteristic read/write callbacks | dispatch on `ctxt->op`; ffe2 read serializes `domain::VehicleState`; writes parse `ctxt->om` | PASS |
| Advertising | `sync_cb` populates `ble_hs_adv_fields` (flags, ffe0 UUID, name), `ble_gap_adv_start` connectable/general-discoverable; `gap_event_cb` restarts adv on disconnect | PASS |

## 3. Static Checks

- **No NimBLE-Arduino**: `grep -rniE "NimBLE-Arduino|BLEDevice|BLEServer|#include <Arduino"`
  over `components/ble/` → **zero matches** (exit 1). Only esp-nimble headers included
  (`host/ble_hs.h`, `nimble/nimble_port.h`, `services/gap`, `services/gatt`).
- **No hardcoded secrets / new unsafe operations** introduced.
- `sdkconfig.defaults` enables `CONFIG_BT_ENABLED` + `CONFIG_BT_NIMBLE_ENABLED`.

## 4. Tasks

All 9 tasks (T1–T9) in `tasks.md` marked complete `[x]`.

## 5. Tests

- **Compile-verified**: full `idf.py build` links the ble component into the app image.
- **Runtime BLE test deferred**: BLE discovery / connect / characteristic read-write
  requires physical ESP32-S3 hardware, which is unavailable in this environment.

## 6. Known Gaps / Accepted Deviations

All items below are WARNING/SUGGESTION severity — no CRITICAL/IMPORTANT failures.

1. **Runtime BLE verification pending** — advertising, connection, and GATT
   read/write exchanges are not exercised on hardware. Deferred to hardware
   bring-up. Compile + static conformance stand in until then.
2. **Config wire format placeholder** — write-characteristic buffer parsing uses a
   provisional layout; the companion app protocol is not yet frozen.
3. **ffe2 state serialization** — emits the raw `domain::VehicleState` struct rather
   than a versioned/portable encoding; acceptable for the current single-app pairing.

## 7. Branch Handling

Local merge to `main` (`--no-ff`), then archive. `branch_status: handled`.
