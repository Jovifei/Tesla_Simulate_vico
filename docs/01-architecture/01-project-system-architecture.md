# Tesla Simulate Vico / S12 当前系统架构

> 当前产品 = 车内 Android App；ESP32 = `DEFERRED_FUTURE_OPTION`。
>
> 详见长期记忆：`docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`。

## Product flow

```text
speed + acceleration
→ VehicleState Normalizer
→ VirtualEngineState
   ├─ virtual RPM
   ├─ load/throttle proxy
   ├─ virtual gear/shift
   ├─ tip-in/lift/overrun
   └─ transient state
→ Vehicle Profile Selector
→ Persistent Event-Domain Engine
→ Pressure Audio Chain
→ Frozen PTR/Radiation
→ Realtime PCM
→ Android Audio Output
```

## Current input contract

Minimum: `speed + acceleration`。

App derives virtual RPM/load/gear/shift；CAN/OBD is future richer adapter, not current prerequisite。

## S12 authority

Persistent crank/rotor phase、combustion event、per-cylinder/path、bank/collector、forced induction、mechanical/cycle-sync、tip-in/shift/lift/BOV/afterfire、dP/DC、frozen PTR/Radiation。

## App productization

```text
Engineering Profile
→ AudioParameterPackage
→ Golden speed/acceleration + VirtualEngineState
→ Golden PCM
→ portable C++
→ Python↔C++ equivalence
→ Android NDK / AAudio/Oboe
→ profile selector
→ in-car validation
```

## Vehicle order

Hellcat → Ferrari 458 → RX-7 FD → others。

## Current status

- S12 architecture: Verified in software；
- Hellcat AA-C3: Engineering candidate；
- AC8: Pending；
- Human: not passed；
- App realtime: not started；
- R1: missing；
- ESP32: deferred。

## Hard rules

- CI != Human；Human != R1；
- feedback 前不揭盲/调音；
- no master/whole-mix Round2；
- Track-P frozen；
- Android App is current runtime；
- ESP32 not current blocker。
