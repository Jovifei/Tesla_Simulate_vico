# Fixed mounting, qualified events, and local test sessions

Candidate based on d6b109bffcb5b286b042f714690a948bfc67f236. This is a testable fixed-mount implementation, not arbitrary phone orientation or demonstrated road accuracy.

## Fixed mounting contract

Park first. Complete stationary calibration, choose which physical phone side points forward, and explicitly confirm the fixed installation. The saved choice does not persist trust. Calibration/input-session changes, backgrounding, or manual movement invalidate trust. Returning between app pages alone does not invalidate it. A natural-portrait device is required; screen rotation does not remap sensor axes. Tilt and yaw changes are not automatically detected: move the phone, invalidate and reconfirm while parked. Bias is bound to all three axes in the current calibration session. GPS speed remains separately visible when mounting is untrusted; real synthesis is withheld.

Android sensor axes follow the device's natural orientation, independently of screen rotation: https://developer.android.com/develop/sensors-and-location/sensors/sensors_overview#sensors-coords

## Event contract

REAL afterfire uses fresh original IMU sample identity, separate epoch and qualified arm/release episodes. Repeated control publications cannot advance dwell. Both GPS and IMU source identities are mandatory. A genuine new gear transition may emit its one shift event in the same control frame even when IMU sample identity repeats; it cannot arm a release or defer that shift event until another IMU sample. Recovery clears episodes, preserves cooldown, and requires a new complete arm/release sequence. Candidate engineering values are 150 ms arm, 80 ms release and 350 ms cooldown, not acoustic or road validation. Synthetic frozen reference controller logic is preserved.

## Automatic local logging

Starting sound requests a session automatically. Metadata preparation, file writes, finalization, APK hashing and export run away from the audio writer. Mandatory CONFIG precedes dependent records; unready/config/queue gaps are counted. Audio diagnostics use a bounded primitive ring. The collector samples routing metadata into a cached code; audio only reads that code. AudioTrack underrun reads remain platform calls and require device performance measurement.

Logs contain fixed numeric schemas, build/profile/unit/config identities, sensor callback/source times, accepted and rejected GPS callbacks, IMU bias/mapping, published control/model states, software UI acknowledgements, event requests/consumption and audio window statistics. They contain no coordinates, microphone audio, account data, credentials or network uploads. GPS no-speed callbacks have null speed rather than a fabricated zero.

Schema: evidence/vico-session-schema-v2.json. Source times and IDs remain integer nanoseconds, not floating-point identifiers. UI acknowledgement is a double-requestAnimationFrame software observation, not physical pixel timing. It reads the actual displayed value and unit; 70 km/h can correctly display about 43.5 mph. Old pages, frames from an earlier recording, duplicates and backwards acknowledgements are rejected.

Audio row/event consumption time is captured immediately before that block's renderer call, before blocking AudioTrack submission. Render/write durations are separate window maxima; written frames and out-of-range submitted PCM samples are sums over blocks_in_window. clip_count only counts submitted post-envelope PCM outside [-1,1], and is not a pre-clamp sound-bank clipping measure. Event logs distinguish model requests from audio-owner observations; missing joins/configurations stay unknown rather than fabricated.

The bounded queue is 512 records, each session at most 32 MiB, retention at most 20 sessions/256 MiB. No automatic deletion is performed. Stop waits for bounded normal audio tail, then requests asynchronous flush. Capacity/I/O failure is visible and partial files remain exportable. Export is explicit: Downloads/VicoTests on Android 10+, system document picker on Android 7–9. No remote upload is performed.

## Verification and limits

Cloud pure Kotlin production/test modules: 140/140 passed; browser DOM tests 25/25; input wiring 14/14; offline analyzer 6/6. Actual production controller black-box tests cover jitter, release dwell, source loss, duplicates, recovery and immediate real shift events. Fixed-axis tests cover all six signs and calibration/session invalidation. Recorder tests cover bounds, partial/failure, generation races, CONFIG ordering and retained export data.

These checks do not compile Android-only adapters, prove AudioTrack timing, verify screen pixels, signing compatibility, actual GPS road accuracy or listening quality. Exact-commit Android compile/unit/lint/APK CI and an appropriate device build are required before installation. No intermediate safety-only build was installed. Road validation needs a parked setup, independent speed reference and a passenger/operator; do not operate settings while driving.
