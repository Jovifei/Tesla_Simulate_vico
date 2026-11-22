# v1.4 Android and Web candidate

The candidate starts from the APP8 release-source commit `953d22041836a55fc50c6347045b8982bdfdc1ca`. Both surfaces use the projected [M0 registry](https://github.com/Jovifei/Tesla_Simulate_vico/blob/40b7b0d0f2e68d833c03dd90ffc317ebae3dbb7c/tools/sound_sim/v14_contract/vehicle-registry.json). Its SHA-256 is `ff5d9a31199f102dd3267857b98086b174002aa7f5ce990d335ef4b61622d3f5`. The nine planned targets appear locked. A target requires an actual accepted package bound to Jovi's signoff before it can play. The runtime trust binding has not been supplied.

Android's `library.html` and `dashboard.html` now receive catalog and mode status from the existing bridge. The dashboard distinguishes audition, drive, simulated and phone-estimated inputs. Mode changes stop the active session before switching. Missing and stale values are cleared. A package-internal synthetic fixture exercises atomic Throttle/RPM/Load/Gear validation, increasing frame IDs, input expiry and stale-owner rejection through the existing audio-state path.

Web exposes audition and drive modes, validates the projected registry and fails closed on deep links. The same worklet and session handle playback and control readback. The 390-pixel factory instrument corrections from the post-PR #39 line are included and tested. Throttle and gear have synthetic transport/readback coverage. Their acoustic effects and actual driving telemetry remain unverified.

| Verification | Actual result |
| --- | --- |
| Android offline Gradle JVM tests | 74 passed across eight targeted classes |
| Android HTML fixtures | 5 Node scripts passed |
| Android lint and Debug build | `lintDebug` and `assembleDebug` exited 0 |
| Web Node tests and build | 188 passed and local build exited 0 |
| Local 390×844 browser | Nine entries locked, deep link rejected, no overflow or page errors |
| Browser audio seam | A muted AudioContext and the existing AudioWorklet read back all four synthetic controls and produced finite, nonzero PCM |

The Debug APK SHA-256 is `8b32ad80e8897afb11acda592d2b8064345db0c72ce6157d42fdb2630ccc53b1`. [Run identity and test details](validation.json)

Android WebView/bridge runtime on a device, audible native QA playback, real approved package playback, the new formal S12 review page, owner audition, external speakers, static cabin and dynamic vehicle are `NOT_RUN`. The existing S13 review path and historical sound assets are retained. The isolated draft does not change the product ledger's existing acceptance states.
