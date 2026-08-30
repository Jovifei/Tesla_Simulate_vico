# Y3 cycle-synchronous P4 checkpoint

Status: `FAIL_REPAIRING`; this is not a qualification or selection result.

Source HEAD was `49ef180f4cb2c351d0583bd0459144781a4da54f`. The Y3 patch changes the fixture resampler from a 2π wrap to the four-stroke 4π wrap, removes its unused phase state, and uses the central P4 renderable/candidate inventory in bakeoff, validator, review, and v27 paths. The dedicated phase test first failed because phase 0 and 2π produced identical output, then passed after the full-cycle correction.

The persisted Stage-W focused run `y3-stage-w-bakeoff` ended `4 failed, 8 passed in 103.06s`; logs and hashes are in `tasks/reports/runtime/s12-stage-y/y3_cycle_sync_p4/y3_cycle_sync_p4_receipt.json`. The failure is fail-closed PCM24 export, not a P4-only phase defect: maximum raw peaks were P1 `0.169871537`, P2 `0.455105220`, P2H `0.355640209`, P3 `1.989831651`, P4 `1.989985522`, and P5 `1.989831651`. P3's Y2 fitted-map amplitude is already out of range before P4 stage completion.

No raw-scaling or fitted-map repair was made. P1/P2/P2H and all Y4-Y6 scopes remain untouched; the pre-existing Y4/Y5 snapshot/replay blocker remains separate. A new explicitly authorized amplitude-policy scope is required before Y3 can be revalidated or marked PASS.

## Normalized-map revalidation

Status: `PASS` at source HEAD `bae8e7b768c5e6621678b87ec0535cea47b42d05`.

After the separately authorized Y2 one-sided Fourier-coefficient normalization, Y3 ran exactly one persisted focused verification: `66 passed in 287.05s`. It covered the full Stage-Y cycle-sync suite, Stage-W bakeoff and strict validator, review package, v27 pipeline, Y2 harmonic-map suite, and the Y1 fixed parent-P3 golden. The run proved P4 rendering/inventory and 720-degree semantics remain valid while normalized map outputs meet the PCM24 path; P6 remains the only placeholder. No Y3 source repair, fitted-map edit, or `OUTPUT_SCALE` edit was needed.

The earlier clipping receipt remains preserved as superseded pre-normalization evidence. The active phase is now Y4; no Y4/Y5/snapshot implementation was changed during this revalidation.
