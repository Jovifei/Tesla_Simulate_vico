# Vico input timing diagnostics — 2026-10-03

## Scope and identity

This is an observational diagnostics change on the existing PR37 branch, based on `6e795571a2e8619142ba419efff2e314e5a081f4`. It does not alter source selection, freshness thresholds, GPS requests, smoothing, calibration thresholds, audio, or permissions. Recording still starts only through the existing user action; export still writes the existing local CSV. No coordinates, altitude, bearing, device identifiers, network telemetry, or automatic recording were added.

The source/code/test/workflow patch SHA-256 is `29b241dded3058007dbdae82e01564dd6ed754910cf51bab00fd97005192547f`. Reports/receipts are outside that patch hash.

The independent compatibility chain is deliberately separate:

1. Integrated main baseline `6e4cf1437972caf383baab3f987de0ebf2db373d`
2. Previously reviewed calibration patch `dfeea1d0521def6ca12a0926f0a01a5284af5d24d17fc50afeb1f5320a8000e0`
3. This diagnostics patch

Both the direct PR37 baseline and the main-plus-calibration prerequisite chain produce identical changed source bytes. All 13 integration-different main files remain untouched. [PR37 receipt](evidence/vico-input-diagnostics-20261003-pr37.json) and [main compatibility receipt](evidence/vico-input-diagnostics-20261003-main.json) bind the baselines, prerequisite, exact patch, before/after hashes, JVM source hashes, and tests. This focused source replay is not an integrated-main Android build or device qualification.

## Why it is needed

The earlier timing repair document requires later device trials to distinguish source-fix time, receipt time, publication time, update frequency, and available speed uncertainty. Previously, source times disappeared at the provider callback and the local CSV retained only time/speed/acceleration/RPM/frequency/profile. Repeating one GPS fix at the UI tick rate was indistinguishable from new same-speed measurements.

The new immutable snapshot preserves source identity and timing through provider selection, Activity consumption, local state JSON and CSV. Freshness expiry retains the last accepted identity for observation while validity becomes false and existing live values zero as before. Explicit lifecycle clears remove the metadata. Rejected measurements cannot change it. Batch speed, timestamp and uncertainty come from the same selected usable fix.

A single immutable bridge snapshot now binds speed/acceleration/GPS state, primitive sensor axes, DEMO mode and diagnostics together. The JS bridge captures it once; pause clears displayed input and diagnostics coherently. Audio-control inputs and recording behavior are unchanged.

## Clock and interpretation contract

All `*_elapsed_ns` fields use Android elapsed real time in nanoseconds since boot, including sleep. GPS source time is `Location.elapsedRealtimeNanos`; IMU source time is `SensorEvent.timestamp`; callback, publication and consumption times use `SystemClock.elapsedRealtimeNanos()`. Publication time is captured at the start of the provider's dispatch/freshness snapshot, immediately before the frame is delivered. Callback receive time is separate from freshness-validation time, so diagnostics cannot make an already-stale sample valid.

These differences measure the input pipeline only. They are not physical vehicle lag, sound-output/speaker latency, or ground-truth sensor accuracy. The GPS accuracy value is the provider's optional estimated speed uncertainty in m/s, not observed error. Actual GNSS frequency and truth accuracy require independent real-device evidence. Distinct timestamps in exported rows count distinct published measurements; coalesced intermediate callbacks are not a full raw-provider event log.

JSON encodes 64-bit nanoseconds as exact decimal strings to avoid JavaScript integer rounding above 2^53. CSV keeps exact integer text. Age is finite milliseconds measured at publication. Missing timestamps or invalid clock comparisons remain null/empty rather than zero-age. Wall time is used only by the unchanged export filename convention.

## Append-only CSV / JSON schema

The first six columns remain byte-for-byte compatible in name/order/format/meaning:

`time_s,speed_kmh,accel_mps2,rpm,freq_hz,profile`

Sixteen diagnostic columns follow, producing 22 columns total. They are also available in the additive native `inputDiagnostics` object:

- `diagnostics_version`: 1
- `input_session`: local provider-start counter, no personal/device identity
- `source_mode`: REAL or DEMO
- `drive_input_mode`: LIVE, PREVIEW or REFERENCE_BYPASS
- `publish_elapsed_ns`, `consume_elapsed_ns`
- `gps_sample_elapsed_ns`, `gps_received_elapsed_ns`, `gps_age_ms`, `gps_valid`
- `gps_speed_accuracy_status`, `gps_speed_accuracy_mps`
- `imu_sample_elapsed_ns`, `imu_received_elapsed_ns`, `imu_age_ms`, `imu_valid`

When no accepted GPS sample exists, accuracy status/value are null. With an accepted sample, API 24/25 reports UNSUPPORTED_API without invoking API 26 methods. On API 26+, absent accuracy is NOT_REPORTED; negative/nonfinite reported values are INVALID; finite nonnegative values are AVAILABLE. Genuine reported zero remains zero. Unavailable/invalid accuracy never rejects an otherwise accepted speed fix.

DEMO values are explicitly marked and cannot masquerade as fresh physical data; real-input validity remains separate from DEMO's synthetic GPS flag. PREVIEW marks the existing substituted DrivePoint path. The existing reference bypass still skips CSV rows; its current local state uses REFERENCE_BYPASS instead of inventing reference measurements.

A commit-pinned audit read 1,755 authored source/tool/test/documentation candidates across the repository and found no reader or exact-six-column assertion for App-export `vico-trace-*.csv`. The positional 11-column `SoundModelTest` CSV is a separate reference fixture and remains untouched. External spreadsheets/scripts are outside that source-level compatibility claim.

## Verification and remaining gates

Tests were written before the new APIs/formatter: the new Kotlin tests first failed compilation for absent APIs, and all three new wiring checks failed against the baseline. Those are test-first scaffolding/wiring results, not behavioral Android execution. Independent review found and corrected the concurrent bridge snapshot and DEMO coherence gaps before publication.

The final patch passed on both isolated chains:

- 52 pure JVM tests, all passed; no failures, ignored or assumption-skipped tests
- 9 executable calibration UI tests, all passed
- 10 source-wiring checks, all passed

Coverage includes repeated versus same-valued fresh samples, delayed batch selection, source/receive/publish/consume lag decomposition, exact unchanged 3,000 ms GPS and 250 ms IMU expiry, unavailable versus genuine zero uncertainty, invalid samples, lifecycle and mode transitions, integer precision, Locale-independent 22-column CSV compatibility, immutable array copies, and concurrent publication.

Android adapter compilation, Android unit tests, lint and APK generation are NOT_RUN at publication and must be established by hosted CI for the exact new commit. No APK installation, coordinates collection, road latency/GNSS accuracy trial, or human acoustic acceptance occurred. Prior device receipts remain bound to their original commits; neither this patch nor the main compatibility replay upgrades them.

Platform references: [Location speed uncertainty](https://developer.android.com/reference/android/location/Location#getSpeedAccuracyMetersPerSecond()), [sensor timestamp clock](https://developer.android.com/reference/android/hardware/SensorEvent#timestamp), [elapsed real time](https://developer.android.com/reference/android/os/SystemClock#elapsedRealtimeNanos()).
