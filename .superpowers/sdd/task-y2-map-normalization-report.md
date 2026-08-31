# Y2 fitted-map amplitude normalization report

## Scope and source binding

- Normalization code commit: `293dcb23768d67f54c5c2bd783aa650e6328ebda`.
- Regenerated map: `tools/sound_sim/s12/acoustic_identity_v015/stage_y/data/hellcat_fixture_timbre_map.json`.
- Map SHA-256: `5B609A4CDAD621FE7A0C6979B28694BD7D59CAE4F2202F95CF0A84AA2A12DBBC`.
- Map `created_from_commit` is `293dcb23768d67f54c5c2bd783aa650e6328ebda`; the normalized values are not attributed to checkpoint `75f10ab`.
- Scope remains synthetic fixture only, uncalibrated, not a tuning authority, and not OEM reproduction.

## Repair

`fit_harmonic_map()` now writes one-sided Fourier coefficients: `2/N` for non-DC/non-Nyquist bins and `1/N` for DC or Nyquist. It does not alter `OUTPUT_SCALE` or relax the Stage-V PCM24 finite/clipping guard.

The TDD known-sine regression used a 0.25-amplitude order-2 sinusoid at 4,800 and 9,600 samples. Before the repair it recovered 600.0 and 1,200.0; after it recovered 0.25 for both lengths.

## Focused verification

Command:

```powershell
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_harmonic_map.py tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_cycle_sync.py::test_cycle_sync_uses_full_four_stroke_720_degree_fixture_cycle tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_stage_y_reachability.py::test_y1_default_p3_render_matches_fixed_pre_task_parent_golden -q
```

- Run: `2026-08-30T11:53:20.5991111Z` to `2026-08-30T11:53:28.6945328Z`; exit `0`; `12 passed in 7.26s`.
- Log: `tasks/reports/runtime/s12-stage-y/y2_harmonic_map/logs/y2-normalized-minimal-20260830T205700+0800.log` (SHA-256 `5348A3616F547BEA40648A873F36DE83CDF7014E75418F22D37E88987A430A0C`).
- The harmonic-map file covers deterministic loader/contract checks and generated-map P3/P4/P5 finite, bounded, raw PCM24 write/reopen smoke.
- Fresh 0.20 s `full_load_acceleration` raw peaks: P3 `0.343335953`, P4 `0.355898385`, P5 `0.343330657`; all were finite and below one, and PCM24 reopen clipping was zero.

## Status

Y2 is `PASS`. Y3 remains `FAIL_REPAIRING` at `Y3_CYCLE_SYNC_P4`. Its earlier clipping receipt is retained unchanged as superseded pre-normalization evidence; this Y2 repair does not complete or promote Y3. Y4/Y5 blockers remain out of scope.
