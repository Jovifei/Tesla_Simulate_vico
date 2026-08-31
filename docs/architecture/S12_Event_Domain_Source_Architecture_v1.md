# S12 Event-Domain Source Architecture v1

Status: `EVENT_DOMAIN_HELLCAT_ACCEPTED / NOT_R1_QUALIFIED / NOT_PROFILE_FREEZE_READY`.

Stage V is an isolated Python offline source model. It is selected explicitly by
`source_model=event_domain_v1`; the existing `legacy_v015` source remains the
default outside this worktree. No FVM, PTR core, Radiation Boundary, MATLAB,
Simulink, Runtime, Android, ESP32, CAN, or `manage_bundle_loudness` API is
changed.

## Causal flow

```text
VehicleState (100 Hz)
  -> continuous crank/rotor phase and torque state
  -> per-entity event packet and blowdown
  -> per-path fractional delay, temperature-dependent speed, attenuation
  -> bank/collector routing
  -> event-domain afterfire
  -> raw analysis PCM
  -> bounded audition monitor PCM
```

`event_domain_v1` is a clean-room architecture mapping from the pinned
Engine-Sim source study. Engine-Sim is not copied, is not a full FVM solver,
and is not an OEM truth source. All Stage-V parameters are C-level synthetic
assumptions unless a future external reference record explicitly binds them.

## Evidence boundary

Raw PCM is the only input to professional metrics. Monitor PCM is a separate
audition copy with bounded attack/release gain and a -1.2 dBFS ceiling. A
missing or unsynchronised R1 reference produces an explicit unavailable
reference result; it never becomes a calibration or profile-freeze pass.

## Current implementation units

- `event_domain/crank_phase_pll.py`: continuous phase, omega, sync error and
  exposed torque-state traces.
- `event_domain/event_scheduler.py` and `chamber_event.py`: exact event phase,
  entity identity, pressure/blowdown/torque/flow packet.
- `event_domain/exhaust_path.py` and `collector_network.py`: temperature-aware
  sound speed, fractional path delay, per-path attenuation and bank routing.
- `event_domain/afterfire_state.py`: hot/lift/fuel/oxygen/cooldown eligibility;
  events are routed through the same path rather than appended after PCM.
- `stage_v/pipeline.py`: legacy parent versus event candidate and isolated
  monitor output.
- `stage_v/publish.py`: PCM24 reopen, SHA receipts, traces, manifest and
  fail-closed validation.

## Explicit non-claims

Stage-V output is synthetic, uncalibrated, offline, not an OEM reproduction,
not R1-qualified and not profile-freeze-ready. Human listening remains a
separate gate from automated metrics.
