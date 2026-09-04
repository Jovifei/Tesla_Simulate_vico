# 01-architecture

Purpose: system architecture, component boundaries, task ownership, data flow, and integration contracts.

Current authoritative entry:

- `01-project-system-architecture.md` — product shell + S12 sound authority + cross-language/ESP32 productization bridge.

Keep these boundaries visible:

- ESP32 product shell vs S12 acoustic-authoring authority;
- Track-P frozen physics vs Track-S acoustic identity;
- Raw analysis PCM vs audition/monitor PCM;
- VehicleState abstraction vs Tesla-specific CAN decode;
- AudioParameterPackage / portable runtime vs platform adapters;
- software evidence vs human evidence vs R1 evidence vs hardware evidence.
