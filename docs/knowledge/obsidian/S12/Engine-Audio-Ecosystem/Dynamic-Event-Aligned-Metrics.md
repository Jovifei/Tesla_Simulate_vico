---
tags: [S12, negative-knowledge, dynamics, timing]
stage: Stage-AB-R
---

# Dynamic Event-Aligned Metrics

**NEGATIVE KNOWLEDGE — 0 ms due to window alignment is not instantaneous engine response.**

v1 measured `tip_in_attack_ms` from a whole-clip envelope with no isolated-event
contract, so 0 ms could simply mean the analysis window started at the event
(`0 ms due to window alignment`). A 0 ms value must never be read as "the engine
responds instantly" — and must never mean "no data" either; missing data is
`NOT_MEASURABLE`.

## v2 contract (`event_aligned_dynamic_metrics`)

- Event onset detected from the state trace (throttle tip-in / gear-shift RPM drop /
  throttle close / RPM decay), mapped to the audio sample index via the 960-sample render block.
- Requires >= 250 ms pre-event baseline and >= 500 ms post-event window; scenes without a
  compliant isolated event (lift, idle_return, afterfire in the current grid) report NOT_MEASURABLE.
- Requires a distinct transient (peak-floor > 1 dB) before claiming any timing.
- Outputs: event_onset_ms, acoustic_onset_ms (floor+10% crossing), latency_ms
  (floor+50% crossing), rise 10→90 ms, onset_to_peak_ms, settling_ms (≤ floor+3 dB),
  peak_overshoot_db — plus `resolution_note`.

## Why tip_in still reads 0.0 ms

The offline renderer consumes vehicle state per 960-sample block with no transport
delay, so the acoustic 50% crossing falls inside the same 10 ms analysis frame as the
state onset → latency_ms = 0.0 with latency_frames = 0. The receipt carries
`resolution_note`: this is a frame-quantization statement about render alignment,
NOT a claim of instantaneous engine physics response. Any future transport-latency
claim needs a sub-frame (sample-domain) estimator, not this metric.

## Event grid results (frozen AA-C3 audio)

tip_in MEASURABLE (latency 0.0 ms, quantized), gear_shift MEASURABLE,
lift / idle_return / afterfire NOT_MEASURABLE (no compliant isolated event).
Afterfire peak-vs-body ≈ 20.1 dB (P5) vs ≈ 3.0 dB (parent) RED FLAG retained —
window/timing validated, so it is not a windowing error.

Related: [[AA-C3-Gain-Provenance-v2]], [[Stage-AB-Negative-Knowledge]]
