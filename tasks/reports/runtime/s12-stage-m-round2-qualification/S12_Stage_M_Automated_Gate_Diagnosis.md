# S12 Stage M Automated Gate Diagnosis

All eight vehicles remain `DIAGNOSTIC_ONLY`. Relative B/R2 summaries are retained as evidence but are not promoted to raw-recording targets, so parent/candidate errors and improvements remain `null`.

## Attribution categories

- A: candidate actually worsened
- B: reference window misalignment
- C: reference recording operating condition mismatch
- D: R2 recording unsuitable for an absolute gate
- E: source/final-PCM domain mixing
- F: loudness copy used in raw analysis
- G: reference extractor and comparator method mismatch
- H: parameter unreachable for the selected metric
- I: event-qualification logic failure
- J: actual state regression
- K: metric cannot represent the human target

## Vehicle/scenario records

- `ferrari_458` / `idle`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `ferrari_458` / `acceleration`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `ferrari_458` / `shift`: confirmed categories C, D, G, H, I, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `ferrari_458` / `afterfire`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `hellcat` / `idle`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `hellcat` / `acceleration`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `hellcat` / `shift`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `hellcat` / `afterfire`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `rx7_fd` / `idle`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `rx7_fd` / `acceleration`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `rx7_fd` / `shift`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `rx7_fd` / `afterfire`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `supra_jza80` / `idle`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `supra_jza80` / `acceleration`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `supra_jza80` / `shift`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `supra_jza80` / `afterfire`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `aventador_lp700` / `idle`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `aventador_lp700` / `acceleration`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `aventador_lp700` / `shift`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `aventador_lp700` / `afterfire`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `c63_w204` / `idle`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `c63_w204` / `acceleration`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `c63_w204` / `shift`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `c63_w204` / `afterfire`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `gtr_r35` / `idle`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `gtr_r35` / `acceleration`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `gtr_r35` / `shift`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `gtr_r35` / `afterfire`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `lfa` / `idle`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `lfa` / `acceleration`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `lfa` / `shift`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.
- `lfa` / `afterfire`: confirmed categories C, D, G, H, K; hard gate `False`; `withhold auto-tuning; obtain legally usable, state/RPM-bound reference or Jovi named feedback`.

LFA source evidence is the actual ASG re-engagement array aligned to three shifts: 3 events, 0 wrong-condition events, eligible true. Ferrari's named shift event receipt is ineligible (two expected events missing). Hellcat is independently compared as the actual Stage-L v9 diagnostic candidate; this report does not relabel it as v6 or qualify it.
