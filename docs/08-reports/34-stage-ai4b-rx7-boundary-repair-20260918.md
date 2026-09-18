# Stage AI-4B — RX-7 boundary repair and real-material validation (2026-09-18)

## Scope and result

This repair addresses the Stage AI-4A finding that RX-7 `09_steady_mid` began with a near-full-scale step after a 20-sample zero prefix. The 4×/8×/16× reconstruction peak was therefore above 1.0 even though the int16 sample peak was below full scale.

The repair is a versioned, opt-in boundary policy:

- `rx7_start_boundary_fade_v1`
- common stereo linear ramp over 24 frames (`0.5 ms` at 48 kHz)
- applied after the existing linked soft ceiling and before int16 quantization
- leaves frames after the first 24 unchanged
- leaves the default `boundary_policy=None` path unchanged
- does not change K/C, the 1.0 true-peak gate, source parameters, IR, seed, Reference or global gain

The output policy remains `linked_soft_ceiling_v1` with K `0.90` and C `0.94`. The boundary receipt is separate from the output-guard receipt.

## Code and tests

Local repair branch: `local/stage-ai4b-rx7-boundary-repair-20260918`

Source commits:

- `2fe82596a7acd4f2e9f835801f91a48d73bdd9fe` — boundary helper, engine receipt, CLI scope and RED/GREEN tests
- `fdabb4a937eb5b6d8351e5d5461db209c8f25a90` — RX-7-only boundary-policy routing for the feedback loop

Focused validation:

- AI-4B boundary tests plus existing remaining-vehicle/reference-feedback tests: `29 passed`
- Extended focused set including AI-4A true-peak/evidence: `82 passed`
- Track-P frozen check: exit `0`, 180 files/2 symbols unchanged
- compileall: exit `0`
- `git diff --check`: exit `0`

Current HEAD full S12:

`1715 passed, 3 skipped, 1 warning, 232 subtests passed in 2601.28s (0:43:21)`; exit code `0`.

The one warning is the existing invalid escape sequence warning in `test_s12_stage_k_gtr_parallel_turbo_v3.py`.

## Real RX-7/Aventador run

Fresh run (old runs untouched):

`E:\Tesla_speed\review_packages\s12-stage-ai4b-rx7-boundary-feedback-20260918-v1`

- run `ARTIFACTS.json` SHA: `547b4e655d1a03bed6b906d33abc96dd8fbf9a9edc7c43d4dc9d2ca968d26d73`
- `summary.json` SHA: `2b537f4f8cd482ea551509ee3a03e7d5ee36a346409268cf8afdf82fe20845bd`
- `promotable=false`, `human_status=NOT_EVALUATED`
- fixed output policy: `linked_soft_ceiling_v1`, K `0.90`, C `0.94`
- boundary policy is present only on RX-7; Aventador records report `boundary_policy=null` and retain the default path

RX-7:

- status: `RELATIVE_IMPROVEMENT_VALIDATED`
- trials: `23`
- baseline → selected parameter: `rotary_pulse_width_scale 1.0 → 1.15`
- train loss: `0.7524179333 → 0.7505825621`
- independent validation: `0.6298975992 → 0.6290873714`
- off-switch: `10/10`
- selected maximum 4× peak: `0.9375417135`
- selected maximum 16× peak: `0.9381369771`
- all ten selected scenes: 16× peak ≤ 1.0
- post-guard clip, emergency clip, identity clip and post-identity clip counts: all `0`

Aventador retained its established result and default boundary path:

- status: `RELATIVE_IMPROVEMENT_VALIDATED`
- trials: `25`
- selected parameters: `v12_intake_mix=1.25`, `v12_scream_mix=0.775`, `v12_wail_mix=0.925`
- train loss: `0.7782814707 → 0.7758840044`
- validation: `0.6338016382 → 0.6281315657`

## Waveform identity evidence

The old A WAVs remain unchanged. Comparing old qualified A to the repaired RX-7 baseline:

- only the declared start boundary window is changed;
- all PCM differences occur within the first 24 frames;
- frames after frame 24 are byte-equal for all ten scenes;
- no old package, C Reference, IR or source WAV was overwritten.

Comparison receipt:

`E:\Tesla_speed\review_packages\s12-stage-ai4b-rx7-boundary-feedback-20260918-baseline-compare.json`

SHA: `6db1aa8306b1a02b48ed58a3eb07a9a1006795bf992c2f96fd6d768bed7ebe71`

The true-peak run summary is external to the sealed run directory:

`E:\Tesla_speed\review_packages\s12-stage-ai4b-rx7-boundary-feedback-20260918-v1-truepeak-summary.json`

SHA: `df35782affe0003bcf9670488ea7cbb7d822285d8677205c6be4b614db25a76b`

For RX-7, every selected record carries `boundary_repair` with `fade_frames=24`, `stereo_link=common_frame_ramp`, nonzero waveform delta, and `modified_frames=24`. For Aventador the receipt is an explicit disabled no-op.

## Interpretation and limits

The original AI-4A blocker is repaired in the new candidate output contract. This is a local boundary repair candidate, not a claim that the original A WAV has been silently replaced. The old A remains the immutable comparison source; the repaired baseline/tuned WAVs are in a fresh run.

The real recordings remain R3, unsynchronized and unverified. The numerical decrease is a relative diagnostic result, not a similarity percentage, OEM match or Human PASS. The next human decision is whether the 0.5 ms boundary ramp is acceptable acoustically before any promotion or richer A/B/C repackaging.
