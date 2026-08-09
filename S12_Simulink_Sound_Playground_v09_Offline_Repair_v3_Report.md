# S12 Script-Configured Simulink Audition Model v0.9 — v3 Offline Repair Report

## Status

`generated but not validated`  
`NOT_READY_FOR_CONTROLLED_REBUILD`

This is an offline source/contract/test repair report, not Simulink runtime evidence. MATLAB, Simulink, MCP, `sim`, and all SLX APIs were not invoked for this v3 repair. No SLX was created, loaded, renamed, moved, or overwritten.

## Evidence identity

| Item | SHA-256 | Length | Status |
|---|---|---:|---|
| Historical pre-repair invalid SLX in existing audit packages | `FA91F46A2F8F6D78586FAE407E795BCEB99AD529F76925A4AF806F9AC73595C0` | 73,921 bytes | Preserved audit evidence |
| Current workspace `S12_Sound_Playground.slx` | `43241395121AD9D71073B030B328195D7D0F28140DEAB8CED41681D1DB853CC5` | 87,428 bytes | Unvalidated generated binary; identity mismatch |

The workspace binary is not represented as the historical invalid evidence. Both binaries remain read-only. This identity mismatch itself blocks a controlled rebuild until independent review explicitly reconciles it.

## Offline source repair coverage

- Stateflow chart configuration now uses named `chart.Inputs`/`chart.Outputs`, fixed `Props.Array` shapes, `double`, and explicit reset inputs.
- The configuration contract is frozen to 48 kHz, 960 samples/frame, 500 frames, 9.98 s StopTime, 10.0 s PCM duration, and 18 packed values.
- Qualification and interactive modes are bound to the existing Manual Switch inputs 2/1 respectively.
- The inspector decodes fixed, nonbus compiled dimensions and exact-compares enumerated top-level semantic links.
- PCM logging, normalization, metrics, promotion, reset, and future canonical migration are fail-closed contracts.

## Offline checks

- Python v3 static contract suite: 10/10 passed.
- `git diff --check`: passed.
- MATLAB test files were not run because this phase prohibits MATLAB invocation.

## Required runtime-only evidence

| Gate | Status |
|---|---|
| Build | NOT RUN |
| Load / Update Diagram / Compile | NOT RUN |
| Simulation | NOT RUN |
| PCM / audio device output | NOT RUN |
| RPM, load, acceleration sensitivity | NOT RUN |
| Repeatability SHA | NOT RUN |
| Runtime equivalence | NOT RUN |

## Independent-review boundary

The referenced external second audit is `S12_Simulink_Playground_v09_Offline_Audit_v2_ChatGPT.md`, SHA-256 `437C47236A19A7DD3E508682C600B7846E24CA3276BFD6A6CA29DCD67301F6A9`. Its file was not present in the workspace, so this package contains only an identity descriptor and does not fabricate a copy.

Only a third independent review may change readiness to `READY_FOR_CONTROLLED_REBUILD`.
