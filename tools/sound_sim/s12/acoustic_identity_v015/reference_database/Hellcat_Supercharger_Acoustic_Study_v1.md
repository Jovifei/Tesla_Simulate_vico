# Hellcat Supercharger Acoustic Study v1

Status: `C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction`.

This bounded research note does not claim a recording is OEM, does not
calibrate absolute loudness, and does not infer rotor tooth count or exact
gear-mesh frequencies.

## Evidence split

### Official hardware facts (A)

Public Stellantis material describes the Hellcat family as using a twin-screw
supercharger, publishes a 2.36:1 drive ratio, gives an approximately 14,600
rpm maximum blower speed, and describes an electronic bypass path:

- [Stellantis Challenger Hellcat engine article](https://blog.stellantisnorthamerica.com/2015/11/10/can-you-name-that-engine-day-ii/)
- [Stellantis Hellcat bypass and specification article](https://blog.stellantisnorthamerica.com/2022/08/15/the-cat-is-back-2023-dodge-durango-srt-hellcat-most-powerful-suv-ever-returns-to-dodge-lineup/)

These facts constrain architecture, not the emitted pressure waveform.

### Public listening context (B/R2)

[DodgeGarage's Hellcat driving review](https://www.dodgegarage.com/news/article/video/2022/05/driving-every-modern-dodge-performance-vehicle-on-the-road-and-track-part-ii)
is used only for a qualitative cue: deep V8 exhaust pressure remains the body
while a distinct blower whine appears as load rises. Vehicle configuration,
microphone position, distance, AGC, equalisation and playback level are
unknown, so this source cannot provide a numeric target.

### Engineering context (B)

The [SAE twin-charger NVH study](https://saemobilus.sae.org/articles/nvh-integration-twin-charger-direct-injected-gasoline-engine-2014-01-2087)
supports treating a supercharger as a narrow-band order family with casing and
intake transfer effects. It does not measure this project's Hellcat.

## Stage H model hypothesis

```text
engine RPM
  -> 2.36:1 shaft phase
  -> 11.8-order lobe family
  -> 23.6-order upper family
  -> four-events-per-revolution V8 sidebands
  -> load/throttle/boost envelope
  -> boost-history-dependent bypass release
  -> synthetic intake/casing transfer
```

The sidebands and bypass are deterministic stems. There is no white noise,
random crackle, fixed-frequency tone, or global gain masquerading as a blower
state. The 2.36/11.8/23.6 numbers are source-architecture seeds; only the 2.36
drive ratio is an official hardware fact. The remaining amplitudes, sideband
depth, attack/release and transfer choices are C-level candidate assumptions.

## State target matrix

| State | Exhaust | Supercharger |
|---|---|---|
| idle | Dominant, low and heavy | Low, partly masked |
| cruise | Stable body and mechanical floor | Light continuous whine |
| acceleration | Body remains the anchor | RPM/load/boost rise |
| shift | Torque interruption and impact | Short dip, then re-establish |
| full pull | Exhaust remains present | Clear but non-harsh order family |
| lift | Decay and deterministic afterfire | Boost-history-dependent bypass release |

## What is not claimed

No OEM pressure map, rotor geometry, gear-mesh order, microphone transfer,
absolute level, calibrated loudness or production approval is present. The
Stage H package is a named engineering audition package; it must stop at
`WAITING_FOR_JOVI_NAMED_CALIBRATION` until Jovi supplies feedback.
