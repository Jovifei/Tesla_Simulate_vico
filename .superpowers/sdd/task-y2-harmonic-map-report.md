# Y2 fitted HarmonicTimbreMap report

## Result

Y2 is `PASS`: Stage Y timbre-map architectures load a committed deterministic Hellcat fixture map and fail closed if its file, schema, SHA, numeric data, provenance, or boundary metadata is invalid. The map carries only fitted amplitudes; it contains no PCM or external media.

The committed map was generated from source HEAD `2601ef7d04a6ffe50a9302580f62fcdab54ffd85`, before this Y2 metadata/implementation commit. Its file SHA-256 is `BA2687E0028F1588D0EFDC09156D096AE099524536B429B56302C8E32D00B491`; its deterministic fixture SHA-256 is `97ac452d4d00a0c7fe48e074cc4d12d14946094988d2f54ccf837481f14a1570`.

## Implementation

- `harmonic_map_fit.py` validates a strict map inventory and offers deterministic build/load APIs.
- P3 and the WIP P4/P5/P3DP branches inject the fitted map and set `require_fitted_timbre_map=True`; P1/P2/P2H remain direct behavior.
- Persistent engine checks that runtime interpolation data exactly match validated fitted metadata.
- P3 diagnostics expose fitted schema and fixture SHA.

## Evidence

Focused verification completed at `2026-08-30T10:59:26.8303616Z`: `16 passed, 1 deselected in 24.08s`. It includes Y2 map tests, Y3 cycle-sync, executable Y4/Y5 stem checks, relevant Stage-W timbre behavior (excluding the pre-existing replay failure), and the Y1 parent golden. `compileall`, finite/nonnegative JSON validation, and `git diff --check` also passed.

The receipt is `tasks/reports/runtime/s12-stage-y/y2_harmonic_map/y2_harmonic_map_receipt.json`. The next phase is Y3; no Y3-Y6 production module was edited.

## Y2 review-fix addendum (2026-08-30)

- Replaced `stage_y.package._fitted_config()`'s dynamic fixture fitting with `load_committed_fixture_timbre_map()`. The runtime interpolation payload now derives from the validated committed table, and the complete committed metadata is assigned to `fitted_timbre_map` before `require_fitted_timbre_map=True` is set.
- Added explicit fail-closed tests for a nonexistent map path and syntactically invalid JSON. Existing wrong-schema, fixture-SHA, and nonfinite-value checks remain in place.
- TDD evidence: before the production edit, the three new focused cases produced `1 failed, 2 passed`; the expected failure was `KeyError: 'fitted_timbre_map'` in the package configuration contract. After the edit, those cases passed `3 passed`.
- Focused verification: `test_s12_stage_y_harmonic_map.py` passed `8 passed in 4.94s`; `test_y1_default_p3_render_matches_fixed_pre_task_parent_golden` passed `1 passed in 2.96s`; the existing Stage-Y package render smoke completed with no failure output. No Y6 test or production module was changed, and no Y6 failure was observed.

## Y2 postfix evidence repair (2026-08-30)

The final Y2 postfix evidence is bound to source HEAD `2dd4ad639617c0c6e2c9a816cfc91d9cecb1ba3d`, before this metadata-only commit. One focused execution ran the complete Y2 harmonic-map test file and the Y1 P3 parent golden: `9 passed in 7.75s` (UTC `2026-08-30T11:20:38.4610035Z` to `2026-08-30T11:20:46.8950954Z`, exit 0). Its stdout and empty stderr are hash-bound in `y2_harmonic_map_receipt.json`.

The previously recorded `16 passed, 1 deselected` run remains historical compatibility context only; it is not the final Y2 postfix evidence. The deterministic fixture map SHA remains `BA2687E0028F1588D0EFDC09156D096AE099524536B429B56302C8E32D00B491`; its strict fail-closed scope and non-OEM/synthetic boundaries are unchanged. Y2 remains `PASS` and Y3 remains `IN_PROGRESS`.
