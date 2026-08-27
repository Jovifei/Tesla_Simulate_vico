# S12 Stage W Forced-Induction Timbre Map (W6)

Status: `TIMBRE_MAP_V1_PASS / HARMONIC_BASELINE_PRESERVED`

`timbre_map_v1` is an opt-in source branch. RPM × load × boost and throttle
drive harmonic amplitudes, sidebands, deterministic broadband noise, casing
resonance and intake resonance. Configured spool time constants and blow-off
gain/decay are consumed by the persistent forced-induction state; naturally
aspirated configurations do not emit BOV output. The existing `harmonic_v1`
fixed family remains the baseline. The branch is suitable for an offline
bake-off; it is not an OEM blower/turbo calibration or embedded CPU proof.

Focused Stage-W tests: `103 passed, 1 skipped`.
