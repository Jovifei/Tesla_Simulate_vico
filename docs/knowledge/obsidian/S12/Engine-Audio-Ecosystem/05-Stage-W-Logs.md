# Stage W Logs

- W0: independent Stage-V audit — `PARTIAL`.
- W1/W2: persistent 20 ms engine, 3000-call/60 s equivalence, snapshot/restore,
  event torque feedback and firing-order-derived phase — `PASS`.
- W3: frozen PTR adapter and post-PTR raw split — `PASS`.
- W4: waveguide_v1 — `PASS`; ENSIM4 checkout/build attempt — `BLOCKED_TOOLCHAIN`.
- W5: dRPM/ignition-delay/location afterfire — `PASS`.
- W6: harmonic_v1 versus timbre_map_v1 and true `hot_idle_20s`/`complete_cycle_60s`
  windows — `PASS`.
- W9: P1/P2/P2H/P3/P5 bake-off render — `PASS` as diagnostic; selection withheld.

Task5D current validation/source/test head is `fcf74f3`; v24 local evidence was
generated at audio head `5038194` as one fresh 0.20 s block-aligned diagnostic
set (180/45/45 WAVs); historical `bakeoff_long_v3` remains the 20/60 s evidence.
No raw external media is committed.
The current focused verification is `141 passed, 1 skipped`; the 3000-block
gate is documented as `1 passed in 92.50s` (fresh measured run `92.06s`).

The next gate is a rights-bound synchronized Reference and then W10 multi-
reference selection plus human review.
