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
