# 03-protocols

Purpose: BLE UUIDs, CAN frames, MQTT topics, OTA payloads, and future USB CDC contracts.

Rules:
- Keep wire contracts explicit and versioned.
- Do not rename or reuse protocol fields without a migration note.
- BLE `0xfff0`, compatibility `0xffe0`, and `ffe8` config behavior must remain easy to find.
