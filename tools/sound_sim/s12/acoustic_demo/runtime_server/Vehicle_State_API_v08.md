# S12 Vehicle State API v0.8

This is a C/synthetic, PC-only control protocol. It does not provide real vehicle data, Android device-runtime qualification, CAN, OBD, ESP32, I2S, vehicle installation, mobile DSP, calibration, or an OEM sound model.

## WebSocket endpoint

The PC runtime binds only to `ws://127.0.0.1:<port>/state`. It consumes one text JSON object per 100 Hz update and returns one JSON acknowledgement per packet.

The Android Debug Demo is intended for an Android Emulator only: `ws://10.0.2.2:<port>/state` maps to the PC loopback endpoint. A physical Android device cannot reach this loopback-only server; physical-device networking is intentionally outside v0.8.

## C/synthetic packet

```json
{
  "timestamp": 12.34,
  "speed": 80.0,
  "acceleration": 1.2,
  "rpm": 3200.0,
  "load": 0.6,
  "throttle": 0.6
}
```

| Field | Type | Unit | Transport range | Provenance |
|---|---|---|---|---|
| timestamp | number | s | 0 to 1000000 | C/synthetic |
| speed | number | km/h | 0 to 300 | C/synthetic |
| acceleration | number | m/s^2 | -20 to 20 | C/synthetic |
| rpm | number | rpm | 0 to 8000 | C/synthetic |
| load | number | fraction | 0 to 1 | C/synthetic |
| throttle | number | fraction | 0 to 1 | C/synthetic |

The adapter passes the packet through the existing v0.7 `VehicleStatePacket` conversion and `EngineRuntimeApi`. The first 100 Hz packet is queued; the second produces one 20 ms / 960-sample 48 kHz stereo signed-24-bit PCM frame through the unchanged pre-PTR excitation, PTR/radiation adapter and renderer path.

## Acknowledgement

```json
{
  "status": "ok",
  "timestamp": 12.34,
  "fallback_applied": false,
  "pcm_available": true,
  "pcm_sequence_index": 0,
  "packet_to_pcm_ms": 4.2,
  "server_received_monotonic_ms": 12345.6,
  "pcm_ready_server_monotonic_ms": 12349.8
}
```

`pcm_available` is false for the first packet of each pair. The PC protocol simulator measures end-to-end latency from the client monotonic send instant to the corresponding PCM-ready acknowledgement for both packets of every pair. Its formal PC target is p99 below 50 ms; it is not a mobile device latency claim.

Malformed JSON, missing fields and non-numeric values return `{"error":"invalid_packet"}` without ending the server. Numeric unsafe values, including negative/NaN/out-of-envelope RPM, abrupt acceleration and timestamp rollback, continue through the existing runtime safe fallback so the process remains available and does not clip or underrun. If a finite packet timestamp skips more than 1.5 expected 100 Hz intervals, the adapter inserts an internal safe fallback packet before the received packet and sets `gap_fallback_applied: true` in its acknowledgement.

## Future boundary

```text
Android Emulator C/synthetic state
        ↓ WebSocket v0.8
PC Engine Runtime → PCM output
```

Future Android Sensor/CAN/OBD adapter, real network exposure, vehicle integration and mobile DSP require separate authorization and qualification.
