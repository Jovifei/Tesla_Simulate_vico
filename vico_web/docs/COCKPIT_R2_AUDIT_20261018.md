# PR39 Cockpit R2 — 2026-10-18

## Scope and actual access

Jovi requested a deeper product/UI/control audit, improvements and actual GitHub commits. Base is PR39 `4b3555bda8faf076e4659cf0296817d513817c82`; PR base stays `codex-remote-stage-20261011-integration`. No main merge, server/DNS changes, Android changes, new WAV/gain/source fitting or third-party source/media copying.

Tesla_speed workspace_info was actually attempted twice and returned HTTP 400 connection error. The repository was instead read through the existing GitHub connector. CI artifact 12017729218 from run 38834487497 was downloaded: ZIP SHA256 `6b7e059212cc73e59c2895c24a6023fd6ba13b57317d40078721e0e20d9ffde1`; its 123 listed file hashes and base webCommit were verified before editing.

Target inspection: the public https://tslbox.top/ homepage was read on this date. Its published flow is selecting a sound, controlling volume/character, permitting positioning and explicit start. It describes browser-local synthesis and speed/acceleration-derived RPM/shifts. These are statements on that page, not an independent sound-quality or privacy certification. The drive URL could not be fetched in this environment. Browser navigation to both the target and localhost was rejected by policy (`ERR_BLOCKED_BY_ADMINISTRATOR`); no override was attempted. Therefore this is not a pixel-exact or audible equivalence claim. Offline screenshots render only our authored markup, with visibly labelled example telemetry.

## Product gaps and changes

The previous implementation's passing build proved software operation, not target-like presentation or better sound. The old side control panel consumed cockpit space; volume was hidden inside diagnostics; the existing engine had no alternative instrument layout. R2 uses a full-width dual-ring cluster, optional large-digit layout, central virtual gear/load, bottom scenario/pedal deck and always-accessible volume/start/stop. Cyber and minimal remain the two independent color themes. Six cars use the actual catalog, not invented OEM specifications or borrowed logos.

`index.html`/`style.css`: replace the debug-style side panel while retaining unique production element IDs and hash routes. Add a clearly separated instrument-layout selector. One DOM and one audio owner, not two copies of the player. Redline ticks come from each selected catalog entry; speed digits remain actual stats and are never a slider-target animation. GPS stays visibly experimental. No aggressiveness/timbre slider is added without a real, separately qualified algorithm contract.

`src/cockpit.js`: presentation only, called by real `app.mjs` select/update consumers. Finite/clamped display coordinates, stale reset, persistent layout, no audio/network/GPS/navigation calls or independent render timer. Arc tick labels are thousands of RPM; the adjacent number/readout is RPM. The speed dial ends at 160; its arc saturates while the numeric speed is not truncated.

`src/app.mjs`: preserve AudioSession, source/owner cancellation and run-bound diagnostics; add display calls and four fixes below. Close the settings drawer on changing vehicles. Preserve explicit start and GPS consent, no autoplay. Engine mode remains switchable only while stopped.

## Reproduced control defects

Five focused app tests were run against the actual base app body with explicit VM DOM/AudioSession stubs: 1 PASS / 4 FAIL (expected RED). These are UI control tests, not browser audio tests.

1. Rejected requestFullscreen promise escaped its event handler. R2 catches the failure, displays a message and leaves the run untouched. The API may reject: https://developer.mozilla.org/en-US/docs/Web/API/Element/requestFullscreen .
2. Keyboard accelerator lost focus before keyup and had no release handler. R2 releases keyboard demand exactly once on blur and ignores secondary pointer takeover/late releases after mode changes.
3. Invalid input cleared speed but retained apparently current RPM/gear/load and RPM arc. R2 clears all current instruments; raw historical diagnostics remain intact and honestly scoped.
4. A delayed or programmatic event from the hidden manual slider could replace a DEMO input. R2 checks actual mode/view before dispatch; scenario dispatch is likewise DEMO-only.

New tests: `test/cockpit.test.mjs` (8) and `test/cockpit_app.test.mjs` (5), 13/13 PASS, no skips. The original Node suite is retained; final CI must run the complete tree. No assertion or old rejection was removed.

## Algorithm call audit — no new acoustic qualification

`app.mjs` -> `AudioSession.start` -> checked same-origin catalog/bank/WAV byte hashes -> AudioWorklet -> `LiveEngine` -> `Powertrain` and `BankRenderer` -> resampler -> user playback GainNode -> destination.

The sample clock advances the existing 20 ms DEMO/manual controller. Powertrain consumes each bank's actual ratios and shift envelope. Renderer performs RPM/load bank interpolation, canonical phase, H8 seam correction, the existing bounded normal envelope and independent event playback. Run-scoped diagnostics remain tied to actual source/bank identity. No replacement sine-wave demo or canned MP3 was introduced.

GPS uses reported browser speed with expiry and explicitly suppresses events; it is not the Android REAL/IMU qualification. GainNode volume and browser/resampler/speaker output are distinct from preClipPeak. A worklet frame count is not human listening, and visual alignment cannot remove the known 0.55 s texture. No sound improvement is claimed.

`core.mjs`, `session.mjs`, `worklet.mjs`, `appearance.js` and all 114 bank files were byte-compared against the downloaded 4b artifact and remained unchanged (118 protected files). app.mjs is intentionally changed UI/control glue; do not claim all four previous app/core/session/worklet files are unchanged.

## Actual evidence and remaining gates

Remote: 13 focused Node tests PASS; baseline 4 expected RED failures; eight offline layout captures including cyber/minimal, dual/digital, 1280x600 and portrait. Landscape bounds/stop hit tests passed. These offline captures do not run AudioWorklet and contain labelled illustrative values. Browser navigation was BLOCKED, not PASS. Real-browser acceptance is NOT_RUN in this environment; supplied `tools/browser_cockpit_review.py` runs the new cases against an actual SHA-bound release.

Local must keep and rerun existing browser_smoke/browser_lifecycle (real six cars, hash/runId freshness, 33 lifecycle results), plus browser_cockpit_review for 2 themes x 2 layouts x 4 viewports, live layout switches, contained fullscreen denial, keyboard focus loss and stale indicators. Unsupported fullscreen is explicitly recorded, never silently counted as a tested feature. Error/skip/empty results are not PASS.

Original Kotlin parity can be reused only for the unchanged algorithms/assets; do not pretend the old result was rerun. Rebuild from final Git SHA, verify all new static file hashes, and independently receive the exact source before deployment.

## Release constraints

The last user receipt reports the shared host at 98% disk and an unrelated root route returning 502. Neither was remeasured here. No upload/extract/release switch or automatic cleanup was performed. Local publication must first inspect current bytes/inodes, active release and retained rollback path. Provision sufficient free space for archive, expanded release and bounded test logs; do not delete Owner data, frozen evidence or other sites. Keep existing Nginx/DNS/security configuration. Only after new local/browser evidence passes, use the existing versioned release procedure, compare the live catalog SHA, test anonymous HTTPS six-car start/stop/layout/theme, and retain 4b rollback. This source delivery is not an automatic public-release switch.
