# Live-input quality safety candidate — 2026-10-04

Status: software safety candidate, **not a road-accuracy or listening pass; do not install as a completed driving fix**.

## What the diagnosis established

The actual Android route is `SensorProvider → MainActivity → AudioEngine → MatlabV6SoundBankEngine → MatlabPowertrainController`. GPS speed is already m/s × 3.6; fresh synthetic 0–70 km/h input reaches the dashboard as 70 km/h. A persisted mph setting correctly displays approximately 43 mph for 70 km/h. This explains a possible numerical match, not proof of the reported road incident. The preference is preserved and the unit is now prominent.

The previous 3-second retention could label a 2.8-second-old 42 km/h reading “good” while a controlled acceleration trajectory had reached 70 km/h. Loss then supplied 0 to the powertrain and recovery supplied 70, although loss of measurement does not establish stopping. Reported speed uncertainty was diagnostic-only. Device-Y bias calibration does not establish vehicle longitudinal acceleration.

## Explicit contract

- `InputQualityPolicy` separates GPS and IMU quality. `FRESH`, `UNVERIFIED`, `STALE`, `LOW_QUALITY`, `UNAVAILABLE`, and synthetic provenance remain distinct.
- Initial engineering thresholds are configurable in the pure policy: GPS freshness 1.5 seconds, IMU freshness 250 milliseconds, maximum reported speed uncertainty 2 m/s. The GPS age permits a nominal 1 Hz update plus 0.5 seconds of delivery margin; the uncertainty threshold equals 7.2 km/h, **not a measured accuracy guarantee**. These are safety-policy candidates awaiting outdoor evaluation. Missing or unsupported uncertainty is explicitly `UNVERIFIED`, never “good”; it remains speed-usable for compatibility.
- Fresh GPS remains visible even when IMU or mounting direction is unavailable. An unknown/low-quality/old velocity is displayed as “—”, not vehicle parking. Raw pipeline km/h remains separately labelled for diagnosis.
- Real driving uses an explicit measured-input API. Synthetic DEMO, PREVIEW, and QUALIFICATION callers must name their source; they cannot share the measured controller’s gear/history.
- An unusable measured frame cannot advance real gear, inject an artificial zero-speed stop, or trigger an event. A recovered epoch re-anchors time, throttle, RPM and gear within the existing hysteresis; it does not replay a series of fabricated shifts. Events are quarantined for the existing minimum-shift interval after re-anchoring (C63: 0.35 s); baselines keep updating, and release events need fresh post-window arming rather than deferring a recovery-window release.
- A monotonic continuity epoch survives skipped intermediate snapshots. The audio writer checks source/epoch and the measurement deadline independently of the UI thread, clears pending legacy transient events on discontinuities, suppresses recovery events, and uses a bounded event-free fade tail rather than replaying stale input indefinitely.
- The experimental S15 renderer has no transient-only reset contract. It is therefore restricted to explicit QUALIFICATION input; REAL or unqualified input stops the prototype with an error and latches it closed until explicit re-preparation. Ordinary manual prototype+DEMO is also rejected in this safety candidate. The bounded debug smoke marks its generated sequence QUALIFICATION. Stop/fade consumes only the previous verified snapshot with new event triggers suppressed, so restoring REAL input after an experiment stop cannot create a false prototype failure. Legacy pending event cursors are cleared on the writer stop edge. The frozen experimental renderer may drain its already-running tail during bounded stop fade; that experimental tail is not claimed to be event-free. Frozen S15/N2 acoustic source is not modified.
- The original pure synthetic/reference controller calculation remains available for frozen fixtures. That compatibility does not authorize unclassified states in live playback.

## Deliberate remaining limitation

This safety candidate marks the vehicle mounting frame **unconfirmed**. Static calibration cannot enable it. Consequently REAL synthesis is paused while valid GPS speed remains visible; explicit demo/qualification paths remain separate. This is a fail-closed engineering checkpoint, not completion of the requested acceleration experience, and it is not a replacement phone installation.

The next step is a small, parked-only fixed-mount setup with human-readable phone-direction choices, persistent selection separate from current-session trust, and an explicit re-confirmation rule after moving the phone. Tilt/screen changes can detect only some movements; no claim will be made that gravity alone detects horizontal rotation relative to the vehicle. Arbitrary mounting and automatic longitudinal projection are not implemented here. No GPS-coordinate differentiation or unbounded IMU integration was introduced as a substitute for valid acceleration.

## Verification scope

New regressions exercise the real pure Kotlin policy and powertrain, expired/skipped epochs, first and second recovery frames, fresh 0–80 km/h input, device-axis rejection, unit conversion, and the actual dashboard update callback. Audio-writer and pending-event regressions are included in the Android test selection. Existing calibration and sensor ordering/freshness tests remain in the gate.

Android adapter compilation, lint, APK and actual renderer integration require the exact published commit’s hosted CI. Browser screenshots could not be produced in the cloud shell because Chromium socket creation is blocked; DOM behavior tests are not visual acceptance. No private traces, coordinates, background recording, network telemetry, device installation, road driving, or listening acceptance are part of this change.
