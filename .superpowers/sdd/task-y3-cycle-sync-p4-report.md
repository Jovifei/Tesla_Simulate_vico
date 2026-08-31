# Y3 cycle-synchronous P4 checkpoint

Status: `FAIL_REPAIRING`; this is not a qualification or selection result.

Source HEAD was `49ef180f4cb2c351d0583bd0459144781a4da54f`. The Y3 patch changes the fixture resampler from a 2π wrap to the four-stroke 4π wrap, removes its unused phase state, and uses the central P4 renderable/candidate inventory in bakeoff, validator, review, and v27 paths. The dedicated phase test first failed because phase 0 and 2π produced identical output, then passed after the full-cycle correction.

The persisted Stage-W focused run `y3-stage-w-bakeoff` ended `4 failed, 8 passed in 103.06s`; logs and hashes are in `tasks/reports/runtime/s12-stage-y/y3_cycle_sync_p4/y3_cycle_sync_p4_receipt.json`. The failure is fail-closed PCM24 export, not a P4-only phase defect: maximum raw peaks were P1 `0.169871537`, P2 `0.455105220`, P2H `0.355640209`, P3 `1.989831651`, P4 `1.989985522`, and P5 `1.989831651`. P3's Y2 fitted-map amplitude is already out of range before P4 stage completion.

No raw-scaling or fitted-map repair was made. P1/P2/P2H and all Y4-Y6 scopes remain untouched; the pre-existing Y4/Y5 snapshot/replay blocker remains separate. A new explicitly authorized amplitude-policy scope is required before Y3 can be revalidated or marked PASS.

## Normalized-map revalidation

Status: `PASS` at source HEAD `bae8e7b768c5e6621678b87ec0535cea47b42d05`.

After the separately authorized Y2 one-sided Fourier-coefficient normalization, Y3 ran exactly one persisted focused verification: `66 passed in 287.05s`. It covered the full Stage-Y cycle-sync suite, Stage-W bakeoff and strict validator, review package, v27 pipeline, Y2 harmonic-map suite, and the Y1 fixed parent-P3 golden. The run proved P4 rendering/inventory and 720-degree semantics remain valid while normalized map outputs meet the PCM24 path; P6 remains the only placeholder. No Y3 source repair, fitted-map edit, or `OUTPUT_SCALE` edit was needed.

The earlier clipping receipt remains preserved as superseded pre-normalization evidence. The active phase is now Y4; no Y4/Y5/snapshot implementation was changed during this revalidation.

## Postfix review-fix: P4 20 ms partition equivalence

The review finding was that the Y3 tests did not directly compare P4's one-shot full-state render with repeated 20 ms calls through one `PersistentEventDomainEngine(..., cycle_sync_model="fixture_v1")`. Commit `c4b06e6897f449b05f6e30a2f29f72dc0624475e` adds that test only; no production, Y2-map, `OUTPUT_SCALE`, Y4, or Y5 file changed.

The test builds the committed fitted Hellcat configuration and a deterministic 20-frame full-load trace. It compares a fresh one-shot P4 engine with a separate persistent P4 engine called once per state frame, requires stable cycle-sync and PLL object identities, requires monotonically continuous 960-sample counters, and compares concatenated raw, post-PTR, and monitor PCM with exact array equality.

Final postfix evidence is `y3-postfix-20260831T043010185968Z`: the complete Y3 cycle-sync file ran from `2026-08-31T04:30:10.223585+00:00` to `2026-08-31T04:30:15.883292+00:00`, exited `0`, and recorded `5 passed in 5.09s`. The execution receipt SHA-256 is `0899B9C303CD24B13A78CD94231F5596E5C137B5CB3C282AF46B4C2FFE46E80D`; stdout SHA-256 is `BA0317834D46412437CF7A189D268D969F579F3857E1C7C13B77CB8E425F36AD` and stderr is empty. The prior `9 passed in 50.93s` capture is retained only as historical output with unknown start/end/exit; it is not final postfix evidence.

The prior `66 passed in 287.05s` normalized-map run remains the broader integration evidence. This postfix record closes the review's missing P4 invariant without promoting it into R1, OEM, real-device, hardware, or human-audition evidence.
