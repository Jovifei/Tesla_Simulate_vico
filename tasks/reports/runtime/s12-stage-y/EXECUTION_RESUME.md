# Stage Y Resume

## Current final-review status

`Y9_FINAL_QUALIFICATION`: final committed fitted-map reachability and the
complete software regression are PASS;
the fresh P3/post_ptr selected-16 receipt proves bilateral finite PCM, SHA
change and target movement above `0.02`. The repair is limited to bounded local
fitted-map source-layer coupling (`broadband=4.0`, `forced_layer=2.0`); legacy
formula-map behavior, global gain, PTR/Radiation, Track-P and v1 audio remain
unchanged. The canonical fixture-hash repair was qualified by the current full
S12 receipt: `1370 passed, 2 skipped`, exit `0`.

Authoritative current proof: `final_qualification/y1_final_fitted_map_reachability_receipt_v2.json`,
`y1_reachability/final_fitted_map_canonical/parameter_reachability.json`, and
`final_qualification/full_s12_final_receipt_v2.json`. The old
formula-map receipt is historical and must not be relabelled. The existing v1
package remains intact; if the changed fitted-map renderer is packaged, create
v2 in a new directory.

- Main HEAD: `62b3759c9e8026e62b4aa2cefeb0a3fbc73597aa` (PR #2 merged; CI run `33435858345` PASS; Stage Y software evidence PASS).
- Branch: `agent/s12-stage-z-open-source-proof`
- Worktree: `E:/Tesla_speed/worktrees/s12-stage-z-open-source-proof`
- Y0 setup receipt: `9dffb65dc885e4b272f0286a6dc1350b83f66a4d` from base Stage-X `3d433e30f2c0238d65baed321aa70355a626ceb6`.
- Y1 evidence HEAD: `e0436dcdf82d0c6acfcc3a05c7195b91790caffc` (`e0436dc`); the runtime-resolved live HEAD at probe start was the same.
- Y2 fitted harmonic map: `PASS`. The current committed map is `tools/sound_sim/s12/acoustic_identity_v015/stage_y/data/hellcat_fixture_timbre_map.json` (file SHA-256 `59690572E189D2CA4A5005EA0297C75622DCA244112AC3747635D9FB16AC9519`, fixture SHA `060F511881CD2D5994AFAC7678222BCA95F9239620884BF342BB8C054D4C06D1`), generated from the canonical fixture-hash repair; the old map hash remains historical. The fitter stores one-sided Fourier coefficients (`2/N`, with DC/Nyquist `1/N`); `OUTPUT_SCALE` and PCM24 validation were not changed. It is `FIXTURE_ONLY`, `NOT_TUNING_AUTHORITY`, and `NOT_OEM`.
- Current phase: `Y9_FINAL_QUALIFICATION` (`PASS`); final fitted-map receipt and the current full S12 receipt passed.
- Historical full S12 receipt: `full-s12-final-20260831T170006408730Z`, tested HEAD `a73322b1ceebe700fc97073cbf50cfd12b961bbf`, `1369 passed, 2 skipped`, exit `0`; it is retained but superseded by the map-hash input change.
- First canonical rerun attempt `full-s12-final-20260831T184449809820Z` at HEAD `65b33744fd9134cbebff7516013e4b912c4d09d6` is retained as `full_s12_final_receipt_v2_failed_track_p.json`: `1368 passed, 2 skipped`, exit `1`. The only two failures were Track-P guard checks caused by CRLF line endings in the newly added v2 Y1 receipt; no functional S12 test failed.
- Current full S12 run `full-s12-final-20260831T192757092203Z` at tested HEAD `dbf6fa27aab73b41f71399593e3a4673958c8e36` passed `1370 passed, 2 skipped`, exit `0`. The normalized stdout log SHA is `d05204b08679fc04ffcca39c8a6a3f74d28fbea0dbacd859f95f62e2f4819283`; stderr is empty with SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Final fitted-map evidence head: `f498c99352ad559897b6157d6722d64e05e68a32`; receipt run `y1-final-fitted-map-20260831T183122590736Z`; corrected artifact SHA `3609d1dda341c271a0a983fe5e66c1c868746b336cdea151dc50da97dc36b1df`.
- Snapshot schema v4 now binds `timbre_layer_coupling`; v1/v2/v3 inputs are explicitly migrated or rejected fail-closed, and fitted snapshots cannot restore into legacy coupling. Package renderer config hashes include the same coupling contract.
- Y3 cycle-sync P4 is `PASS`. Final postfix evidence is source head `c4b06e6897f449b05f6e30a2f29f72dc0624475e`, whose new test proves P4 one-shot-versus-persistent-20-ms exact equivalence. The hash-bound run `y3-postfix-20260831T043010185968Z` executed `test_s12_stage_y_cycle_sync.py` from `2026-08-31T04:30:10.223585+00:00` to `2026-08-31T04:30:15.883292+00:00`, exited `0`, and recorded `5 passed in 5.09s`. Its execution receipt SHA-256 is `0899B9C303CD24B13A78CD94231F5596E5C137B5CB3C282AF46B4C2FFE46E80D`; stdout SHA-256 is `BA0317834D46412437CF7A189D268D969F579F3857E1C7C13B77CB8E425F36AD` and stderr is empty. The earlier `9 passed in 50.93s` capture remains preserved only as historical output with unknown start/end/exit, and is not final postfix evidence. The preceding normalized-map integration run (`y3-normalized-focused-20260830T214700+0800`) remains retained at `bae8e7b768c5e6621678b87ec0535cea47b42d05`: it covered Stage-Y cycle-sync, Stage-W bakeoff/strict validator/review/v27, Y2 harmonic-map checks, and the Y1 P3 parent golden (`66 passed in 287.05s`). All three evidence records are bound in `tasks/reports/runtime/s12-stage-y/y3_cycle_sync_p4/y3_normalized_revalidation_receipt.json`.
- The original `y3-stage-w-bakeoff` clipping receipt is retained unchanged as superseded pre-normalization evidence. Y2's separately authorized Fourier-coefficient normalization fixed that amplitude defect; this revalidation did not modify the map or `OUTPUT_SCALE`.
- The Y4 snapshot/replay blocker is closed with exact default and fitted-timbre-map replay evidence. Y5 closes the separate pressure-chain state boundary: the post-commit receipt `y5_dp_chain-20260831T060110031436Z` ran the dedicated Y5 file with `S12_RUN_SLOW=1`, exited `0`, and recorded `19 passed in 15.15s`; its subprocess bounds, source head, and stdout/stderr hashes are bound in `tasks/reports/runtime/s12-stage-y/y5_dp_chain/logs/y5_dp_chain-20260831T060110031436Z.json`.
- Y2 receipt: `tasks/reports/runtime/s12-stage-y/y2_harmonic_map/y2_harmonic_map_receipt.json`. The normalized map was built from source-code HEAD `293dcb23768d67f54c5c2bd783aa650e6328ebda`; its historical receipt remains retained while the canonical fixture-hash repair is qualified by the current Y1 v2 receipt. The focused map/loader/contract, P3/P4/P5 raw/PCM24 smoke, Y3 720-degree semantic, and Y1 parent golden passed `12 passed in 7.26s`. The combined log is `y2_harmonic_map/logs/y2-normalized-minimal-20260830T205700+0800.log` (SHA-256 `5348A3616F547BEA40648A873F36DE83CDF7014E75418F22D37E88987A430A0C`).
- Current canonical Y1 artifact: `tasks/reports/runtime/s12-stage-y/y1_reachability/final_fitted_map_canonical/parameter_reachability.json` (SHA-256 `3609d1dda341c271a0a983fe5e66c1c868746b336cdea151dc50da97dc36b1df`), with map SHA `59690572e189d2ca4a5005ea0297c75622dca244112ac3747635d9fb16ac9519` and fixture SHA `060f511881cd2d5994afac7678222bca95f9239620884bf342bb8c054d4c06d1`.

Do-not-rerun-long-task: do not rerun the final fitted-map selected-16 probe or
the full S12 suite unless source/test inputs change or a new final HEAD is
explicitly being qualified; use the hash-bound receipts above for recovery.
The historical 128-second formula-map run remains retained and is not final-map
evidence.

## Resolved Y4 replay blocker

Snapshot schema v2 persists path-filter state, model identity and active transient state. The post-review run `y4_transients-20260831T054158832732Z` used source `fc92a68`, ran from `2026-08-31T05:41:58.865088+00:00` to `2026-08-31T05:42:27.099645+00:00`, exited `0`, and recorded `80 passed, 1 skipped in 27.65s`. It covers event latches/re-arm, full 120ms tails, all four diagnostics, atomic rejection, enabled streaming/reset, persistent/timbre replay and P4. Receipt: `tasks/reports/runtime/s12-stage-y/y4_transients/y4_transients_receipt.json`. Y5 evidence is now complete for its bounded scope; Y6 package/audition work is next and remains human-audition/R1-gated where applicable.

## Y5 final snapshot compatibility evidence

Source `1f3a9cb` emits historical snapshot v3; current source emits v4 with explicit v1/v2/v3 migration. Legacy zero v1 restores fresh chain state, pre-Y5 v2 is accepted only for chain-off targets, and complete Y5 v2 is fully validated before migration. Final run `y5_dp_chain-20260831T063530651080Z` used `S12_RUN_SLOW=1`, actual exit0, UTC 2026-08-31T06:35:30.681154+00:00 to 2026-08-31T06:36:00.256467+00:00, and reports 43 passed in 28.92s (no skip). It includes 3000x960/60s equivalence, enabled engine replay, Y4/P4 and default golden. Final receipt: `tasks/reports/runtime/s12-stage-y/y5_dp_chain/y5_dp_chain_receipt.json`.

## Y6 published package

`E:/Tesla_speed/review_packages/s12-stage-y-hellcat-layers-v1` contains 154 synthetic PCM24 stereo WAVs, eleven scenes (idle20s, others8s), and two Chinese review pages. Production source `0916969`, exit0; manifest SHA `9376d90c57e4efad7dc1e9b8ce15e09f1ed2c124f23a753d389039664506826c`. Browser loaded77 players per page and sampled Parent/F/Monitor playback successfully. Receipt: `tasks/reports/runtime/s12-stage-y/y6_audition/y6_audition_receipt.json`. This v1 package is historical and remains untouched; the fitted-map coupling change requires a new v2 package if regeneration is requested. PR/CI/main integration is complete; human audition, legal R1, OEM/calibration, Profile Freeze, Runtime and hardware gates remain unaccepted.
