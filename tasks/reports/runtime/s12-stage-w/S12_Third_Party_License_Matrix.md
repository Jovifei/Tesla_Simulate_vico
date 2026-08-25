# S12 Stage W Third-Party License Matrix

The canonical machine-readable source list is
[`docs/research/engine-audio-ecosystem/source_registry.json`](../../../../docs/research/engine-audio-ecosystem/source_registry.json).
The checkout/build evidence and fixed LICENSE hashes are in
[`source_build_receipts.json`](source_build_receipts.json) and
[`license_receipts.json`](license_receipts.json).

| Class | Fixed evidence | S12 treatment |
|---|---|---|
| MIT | Engine-Sim, ENSIM4, DasEtwas, VehicleNoiseSynthesizer | Clean-room concepts only; no assets, presets or source copied into S12 in this stage. |
| CC BY-NC 4.0 | PTR model | Research-only; code, dataset and weights are excluded from Runtime. |
| No LICENSE | Granular Engine Audio, ESP32 RC | All-rights-reserved boundary; concepts only. |
| Conflicting license | FiveM simulator | Its Apache LICENSE conflicts with README's MIT claim; build passed but all code and game assets remain prohibited. |
| Commercial/papers | Fubos, REV, AudioMotors, Krotos, Nemisindo, QNX, EVx, Ansys, papers | Public documentation/method reading only. |

No third-party source, raw media, preset, IR, dataset, weight or binary is
committed in S12. All references stay research context and cannot prove OEM
identity, R1 qualification or product readiness.
