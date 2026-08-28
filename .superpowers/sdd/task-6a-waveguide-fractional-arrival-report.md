# Task 6A: Persistent fractional waveguide delay and truthful arrival

## Scope

Implemented only in the Stage-W waveguide/persistent engine focused path and
its focused tests. No metadata, receipts, evidence, Vault, Track-P, push,
merge, PR, or full-S12 changes were made.

## RED

From clean baseline `49a8613`, the new tests were run before production edits:

```text
python -m pytest -q \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py::test_waveguide_half_sample_delay_reports_exact_arrival_without_zero_delay_leak \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py::test_fractional_waveguide_block_split_matches_one_shot \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py::test_fractional_waveguide_snapshot_and_reset_restore_stream_exactly \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py::test_afterfire_readback_reports_exact_and_emitted_arrival_without_early_pcm
```

Result: `3 failed, 1 passed`; failures were the expected missing fractional
delay state, waveguide reset API, and exact afterfire arrival diagnostics.

## GREEN

```text
python -m pytest -q \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_waveguide.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_persistent_engine.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_afterfire_localization.py \
  tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_w_final_remediation.py
```

Result: `93 passed, 1 skipped in 34.49s`.

## Implementation

- Added bounded persistent linear-interpolated fractional delay state to the
  waveguide and persistent engine path/collector lines.
- Preserved snapshot/restore and added deterministic reset for delay state.
- Removed the waveguide zero-delay direct component; causal output begins at
  the integer emitted sample index.
- Preserved integer arrival compatibility while exposing
  `arrival_samples_exact` and `arrival_sample_index` for physical fractional
  timing. Afterfire route/readback diagnostics carry scheduled and exact
  arrival values.
- Kept temperature-dependent sound speed, attenuation, frequency loss,
  routing, and bounded state behavior intact.

## Concerns

- Fractional interpolation is causal and deterministic across block splits;
  floating-point results may differ at approximately `1e-16` between one-shot
  and split processing, so the equivalence test uses a `1e-15` absolute bound.
- `arrival_samples` remains the legacy zero-based integer delay count;
  `arrival_sample_index` is the first emitted PCM sample index and
  `arrival_samples_exact` is the physical fractional position.
