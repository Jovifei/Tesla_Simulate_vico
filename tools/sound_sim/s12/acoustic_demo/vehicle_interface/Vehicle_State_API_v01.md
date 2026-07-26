# S12 Vehicle State API v0.1

This is a PC-only, localhost-only synthetic interface. It is not an Android API, CAN/OBD reader, vehicle deployment path, realtime mobile DSP implementation, or real-vehicle data source.

## Endpoint

POST http://127.0.0.1:{ephemeral-port}/vehicle_state

The server always binds to 127.0.0.1 and uses an ephemeral port unless an explicit local port is supplied. It accepts JSON only.

Example request:

    {
      "timestamp": 12.34,
      "rpm": 3000,
      "speed": 80,
      "acceleration": 1.2,
      "load": 0.6,
      "throttle": 0.5
    }

| Field | Type | Unit | Transport range | Source |
|---|---|---|---|---|
| timestamp | number | s | 0 to 1000000 | C, synthetic |
| rpm | number | rpm | 0 to 8000 | C, synthetic |
| speed | number | km/h | 0 to 300 | C, synthetic |
| acceleration | number | m/s^2 | -20 to 20 | C, synthetic |
| load | number | fraction | 0 to 1 | C, synthetic |
| throttle | number | fraction | 0 to 1 | C, synthetic |

The runtime converts speed to m/s. Its synthesis safety envelope is 800 to 6000 rpm, so a numeric packet outside that envelope is accepted by transport but produces a safe synthetic fallback rather than a calibration claim or a silent clamp.

## PCM semantics

The input updates at 100 Hz. The first packet of a pair is queued; the second produces exactly one 20 ms PCMFrame: 960 samples, 48 kHz, stereo signed 24-bit. The local runtime keeps the PCM frame in its bounded output path. The HTTP response acknowledges frame availability and never base64-encodes audio into the control endpoint.

Example response:

    {
      "packet_index": 2,
      "fallback_applied": false,
      "pcm_available": true,
      "pcm_sequence_index": 0,
      "packet_to_pcm_ms": 4.2
    }

Malformed JSON, missing fields and nonnumeric values return HTTP 400. Numeric unsafe values such as NaN, negative RPM, RPM above 10000, abrupt acceleration and a timestamp rollback return HTTP 200 with fallback_applied true; the server remains available.

## Future boundary

Future Android Sensor/CAN (not implemented)
                 |
                 v
       JSON vehicle packet
                 |
                 v
     localhost Vehicle State API
                 |
                 v
  Engine Runtime -> PCM stream -> PC output

Android, CAN, OBD, ESP32, I2S, vehicle wiring, real vehicle calibration and realtime mobile qualification remain out of scope.
