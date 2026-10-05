# REAL virtual-drive candidate replay

This package is synthetic engineering evidence, not road accuracy, human listening acceptance or OEM calibration. Base c7789afe8dd287980e7a8fba052b133ca3cc35ac; original Python S12 authoring, all bank bytes/gain/ratios and renderer DSP remain unchanged. The candidate is REAL-only; DEMO and reference remain legacy.

- `final-raw-budgets.json`: 72 actual-controller/renderer cases, six profiles, GPS1Hz sample-and-hold/IMU50Hz, declared reported uncertainty0 or2, 40s each. No simulated speed measurement noise in these cases. It does not replace the separate bounded-GPS-noise regression
- `actual-renderer-ab.json`: same-bank C63 comparison to the actual c778 controller; includes the +9.96dB 70km/h cruise RMS change, which is an audition risk and not a realism score
- `changed-test-expectations.json`: initial failing old tests and specific contract changes, avoiding a false green from counting shift afterfires as releases
- `replay/`: exact bank/source identities, actual Kotlin replay and sensitivity commands. Only original bank DTOs are extracted to avoid Android AssetManager in this offline runner; no acoustic stub replaces the real renderer

## Commands

Run from a full repository checkout with its SHA-pinned JVM dependencies. The baseline commit must be available to `git show` when current source differs. Use new output directories. These commands create roughly46MiB per drive variant/profile, plus compiled sources and receipts. No device actions occur.

```bash
python vico_app/tools/python/run_sensor_jvm_tests.py --deps "$PINNED_JVM_DEPS" --build-dir /tmp/vico-policy-jvm-new
python -m unittest discover -s vico_app/tools/python -p 'test_virtual_drive_wiring.py' -v
python review_packages/vico-real-drive-20261004/replay/run_replay.py --repo . --deps "$PINNED_JVM_DEPS" --output-dir /tmp/vico-baseline-new --variant baseline --profile c63_w204_v6
python review_packages/vico-real-drive-20261004/replay/run_replay.py --repo . --deps "$PINNED_JVM_DEPS" --output-dir /tmp/vico-candidate-new --variant candidate --profile c63_w204_v6 --reported-uncertainty 0
python review_packages/vico-real-drive-20261004/replay/run_replay.py --repo . --deps "$PINNED_JVM_DEPS" --output-dir /tmp/vico-uncertain-new --variant candidate --profile c63_w204_v6 --reported-uncertainty 2
python review_packages/vico-real-drive-20261004/replay/run_replay.py --repo . --deps "$PINNED_JVM_DEPS" --output-dir /tmp/vico-lifecycle-new --variant candidate --scene lifecycle
python review_packages/vico-real-drive-20261004/replay/run_grid.py --repo . --deps "$PINNED_JVM_DEPS" --output-dir /tmp/vico-grid-new
```

Other verified profiles: hellcat_v6, ferrari_458, gtr_r35, lfa, supra_jza80. `--reported-uncertainty unknown` keeps null and exercises the explicit2m/s policy buffer, without claiming measured precision. The provider value is an estimate, not an absolute bound.

Drive replays check raw above-budget/hardClip/nonFinite counts and fail if any case violates them; completed failed cases remain inspectable. Lifecycle runs use actual mapping/gate/renderer, inspect the pending afterfire/shift cursors, and deliberately hide the invalid snapshot. They do not exercise Android AudioTrack or microphone output. The source/compiled-source hashes and bank SHA receipt bind each run.

The27,216-case grid isolates road-load/normalization/shift-curve sensitivity and acceleration noise on exact GPS values. It is not a GPS-error guarantee. Paired hysteresis checks exact piecewise critical points; separate unit tests cover the22↔36km/h, u2/null case. The retained pre-fix diagnostic demonstrates the u0 overconfidence limitation; zero reported uncertainty is not proof that GPS is exact.

See [policy and remaining limits](../../docs/vico-real-drive-policy-20261004.md) and [project debugging lessons](../../docs/07-debugging/03-vico-input-and-loop-click-lessons-20261004.md). Any listening uses conservative volume and the same output protection; do not normalize A/B separately or label higher RMS as better sound.
