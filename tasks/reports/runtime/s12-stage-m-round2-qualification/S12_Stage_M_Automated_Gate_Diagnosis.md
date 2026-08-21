# S12 Stage M Automated Gate Diagnosis

All eight vehicles remain `DIAGNOSTIC_ONLY`. No record has a legally usable, provenance-bound, scenario/RPM-matched external waveform, so target/error/improvement values are deliberately `null` rather than invented.

## Attribution categories

- A: transport/formal PCM health evidence; B: adverse legacy/internal trend; C: external-recording provenance unavailable; D: scenario/RPM binding unavailable; E: hard-gate metric failure; F: source/trace data defect; G: no real-reference identity score; H: reachable tune plan; I: LFA ASG event verification; J: independent Stage-L diagnostic scope; K: automatic tune withheld.

## Vehicle records

- `ferrari_458` / `full_cycle`: categories C, D, G, K; internal delta `0.0`; `do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `hellcat` / `full_cycle`: categories C, D, G, K, J; internal delta `0.5099887087125348`; `do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `rx7_fd` / `full_cycle`: categories C, D, G, K; internal delta `0.0`; `do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `supra_jza80` / `full_cycle`: categories C, D, G, K; internal delta `0.0`; `do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `aventador_lp700` / `full_cycle`: categories C, D, G, K; internal delta `0.0`; `do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `c63_w204` / `full_cycle`: categories B, C, D, G, K; internal delta `0.36072198346811`; `do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `gtr_r35` / `full_cycle`: categories B, C, D, G, K; internal delta `0.43370287008584346`; `do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `lfa` / `full_cycle`: categories C, D, G, K, I; internal delta `0.07804468311428873`; `do not auto-tune against R2; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.

LFA source evidence is the actual ASG re-engagement array aligned to three shifts: 3 events, 0 wrong-condition events, eligible true. Hellcat is independently compared as the Stage-L v9 diagnostic candidate; this report does not relabel it as v6 or qualify it.
