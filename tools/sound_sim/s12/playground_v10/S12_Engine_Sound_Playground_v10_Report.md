# S12 Multi-Configuration Engine Sound Playground v1.0 Report

## Verified evidence

- Seven independent top-level models use the shared `S12_PTR_Renderer_Core_v10.slx` Model Reference.
- All seven completed structural checks, cold reload, Update Diagram, and two deterministic 90-second simulations.
- Every simulation produced 4,500 frames of `[960, 2]` PCM at 48 kHz; all samples were finite and peak magnitude remained below one.
- The public renderer generated two complete package runs per profile. The two `SHA256.txt` lists matched byte-for-byte for every profile.
- The Dashboard path has model-level sensitivity evidence: RPM, load, and acceleration changes produce distinct PCM.
- The cycle test confirms no overrun events for `off` and lower synthetic event energy for `subtle` than `aggressive`.

## Deterministic model PCM SHA-256

| Profile | PCM SHA-256 |
|---|---|
| inline3_turbo | `5087ce9376a68edf173947d080ce8785f14762c41e3e31fdfea31b7df4673a4e` |
| inline4_sport | `76865c47b442c908ba00a42ec1e858c1dd3386e7a099a42026787033d10ffb94` |
| inline5_character | `6ef8dc0b3e4b23900f02629386e22b4273c33390a3110c1370a8557e6e6ba934` |
| inline6_smooth | `80cea6a2c3e2d950a2f80fb3051137af1565b126d78094aca31658969814a435` |
| v6_sport | `28545e395b8f5bb9e624a35ad00ff23fea1801ad3b999d6a9a062f83370ab765` |
| hellcat_style_supercharged_v8 | `50aeeacdf52a1bf51760d00182f86569ff9d7c52895d341e98a0ca0c3ecdba4c` |
| ferrari_style_high_rev_v8 | `7021eadd3513ccd53fe508e49d370efee5fcdc41c405abb028f41cb89488c435` |

## Limitations

The profile names describe synthetic style directions only. This work is not OEM-calibrated, not based on real-vehicle measurements, does not claim a vehicle clone, and is not qualified for real-time deployment, Android, CAN/OBD, ESP32/I2S, or vehicle use.
