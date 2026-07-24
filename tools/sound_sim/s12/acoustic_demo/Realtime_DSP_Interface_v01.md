# Realtime DSP Interface v0.1

## Status

This is an interface-design contract only. Realtime DSP, Android playback, ESP32 playback, CAN acquisition, and I2S output are **not implemented** by S12 v0.5.

## Input frame

The future consumer receives a timestamped state frame serialized independently of Python objects.

```json
{
  "timestamp": 0.0,
  "rpm": 2000.0,
  "speed": 20.0,
  "acceleration": 0.0,
  "load": 0.36,
  "throttle": 0.36,
  "audio_parameter_package_hash": "sha256"
}
```

`rpm`, `speed`, `acceleration`, `load`, and `timestamp` use the same units and normalized ranges documented by the offline state contract. The consumer must validate the AudioParameterPackage hash before using a frame.

## Output frame

```text
PCM frame: interleaved signed 24-bit stereo samples
sample rate: 48000 Hz
channel count: 2
```

The future latency budget is a C/synthetic interface target of **20 ms end-to-end** from accepted state frame to PCM frame. It is not a measured real-time result and must not be reported as a current capability.

## Future integration boundaries

```text
Android
sensor/CAN -> AudioParameterPackage -> DSP -> PCM frame -> platform audio output

ESP32
CAN -> AudioParameterPackage -> DSP -> PCM frame -> I2S
```

The offline v0.5 renderer remains the reference serialization/format path. A future implementation must independently qualify CPU, memory, output routing, CAN validity, I2S hardware, latency, clipping, and real-vehicle calibration before any product claim.
