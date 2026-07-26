# S12 Runtime App Interface v0.1

This document specifies a future App-to-runtime contract. It is a PC simulation contract only: no HTTP listener, WebSocket, Android client, CAN reader, phone hardware, or audio-device driver is implemented here.

## Vehicle-state ingress

Future `POST /vehicle_state` or WebSocket messages use JSON:

```json
{
  "speed": 60.0,
  "acceleration": 0.5,
  "timestamp": 123.0,
  "rpm": 2050.0,
  "load": 0.35,
  "throttle": 0.35
}
```

- `speed` is km/h; `acceleration` is m/s²; `timestamp` is seconds.
- `rpm`, `load`, and `throttle` are optional only for PC simulation. If missing, `parse_app_vehicle_state` uses the C/synthetic fallback `rpm = clamp(800 + 20*speed + 100*acceleration, 800, 6000)` and `load = clamp(0.30 + 0.10*acceleration, 0, 1)`.
- The fallback is not vehicle calibration and must not be used as a CAN or OEM claim.

## PCM egress

The runtime emits one 20 ms PCM frame per callback:

```text
VehicleState -> EngineSoundRuntime.audio_callback(state) -> PCMFrame
```

- 48 kHz, signed 24-bit little-endian, stereo.
- 960 samples per channel per frame.
- A future App reads `AudioParameterPackage v0.2`, sends state updates at 100 Hz, and consumes frames from a bounded PCM queue.

## Future transports

```text
Android sensor / future CAN adapter
        -> POST /vehicle_state or WebSocket
        -> AudioParameterPackage v0.2 + runtime
        -> PCM frame queue
        -> future audio device adapter
```

The v0.6 implementation opens no transport and writes no full WAV file. Android integration, actual audio playback, realtime qualification, vehicle calibration, ESP32, I2S, and CAN hardware remain unimplemented.
