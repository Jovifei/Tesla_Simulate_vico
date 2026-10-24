# Recorded Hellcat startup and explicit reference PCM comparison

Normal playback previously entered a synthesized idle bank directly. Hellcat now has a separate, validated 6.548-second public recording for an explicitly prepared, stationary DEMO playback session, followed by a 150 ms handoff to the existing continuous voice. Other vehicles, REAL, PREVIEW, QUALIFICATION, S13/S14 and prototype playback do not receive this startup. Existing source WAVs and fixed bank gains are unchanged.

The native session is disarmed by default. MainActivity supplies the explicit DEMO preparation intent; the audio writer cancels pending startup on non-DEMO publication, mute or stop even if it takes the empty-PCM branch. Source/epoch changes cannot resume a consumed one-shot. The browser also supplies its initial input atomically with Worklet initialization, preventing an invalid GPS session from briefly emitting the default DEMO starter. Audio clocks drive traversal and handoff, with owner isolation and no per-sample result allocation.

Native and Web diagnostics separately identify startup frames, output domain and source hash; the original bank-only statistics are not presented as whole-startup statistics. The source and processing credits are available in the native settings and the Web's `audio-credits.txt`.

## Source and qualification

- Original: [Launching sound Challenger](https://commons.wikimedia.org/wiki/File:Launching_sound_Challenger.ogg), Axepas12, 2019-02-10, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- Original Ogg SHA256: `762e3b294362e3d1e37be0b737d6ad4518fd61a6bdbce392be1c850300d0676a`.
- Adaptation: decode, 44.1→48 kHz resampling and one fixed 0.75 playback gain; no AGC, per-window matching, looping, EQ or automatic source fit. This adapted audio remains CC BY-SA 4.0, independently of the code license.
- Adapted WAV SHA256: `1b119ab18364e33b64f91459942433817065034366de9b32f4a70283479edb77`, 314,306 mono Float32 frames, measured peak 0.768711.
- R2 public startup reference only: precise stock trim, hot/cold condition, microphone and synchronized RPM/load remain unverified. It is not a calibrated OEM engine model.

`AcousticReferenceComparator` adds an explicit offline comparison API receiving actual capture and reference PCM. It verifies identities, hashes, supported format/domain, vehicle, length and caller-supplied alignment evidence before computing finite relative feature differences. Missing or unaligned data remains `NOT_EVALUATED` with null errors. The old feature-only extraction API retains its semantics. This does not automatically establish alignment, tune a voice or award OEM similarity.

## Local verification

Parent Web source: `0822de4869b61444f647cb5227886f8b0f89be29`. The previously qualified a95 native empty-map allocation guard is carried forward without changing its PCM arithmetic.

- Node: 96 passed, 0 failed/skipped, including actual Worklet, owner, invalid initial GPS, rate, loader, source-integrity and handoff cases. The package test command now includes all `*.test.mjs` files.
- Android `testDebugUnitTest lintDebug assembleDebug`: PASS, 544 tests = 515 passed + 29 opt-in skipped, 0 failures/errors; lint 0 errors, 6 existing warnings. Final current-tree Gradle verification reused valid incremental outputs; the new native ownership regression was separately executed RED→GREEN, 9/9.
- Independent native review found a pending-arm invalid-REAL→DEMO edge case; the explicit preparation intent and pre-availability cancellation close it. Review outcome: APPROVED_WITH_BOUNDARIES. No phone or road test was performed by that reviewer.
- Local Debug APK SHA256: `fe395115dace6224026579165f3b11b504f2e0dd99810a5fc67e48147adcb00e`, package `com.vico.simulator`, version 1 / 1.0; certificate SHA256 `9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774`. Not installed by this stage.

Full local evidence: `E:\Tesla_speed\reports\hellcat-realism-20261023`; APK packet: `E:\Tesla_speed\review_packages\hellcat-realism-20261024`.

## Still open

The existing continuous bank's slow repetition is not fixed by this one-shot. One isolated coherent-order/noise initialization prototype was measured and rejected: low-RPM slow modulation worsened and the old loudness-compatibility gate failed. Its source and results are preserved outside the product tree, not bundled into the site. Real steady/load/ramp/overrun recordings and further source-aligned validation are required. GT3 RS/Aventador remain intake proposals, not completed product voices. Jovi reported the startup sounded more realistic; complete steady-state, device, road, acoustic and human qualification remain open. No main merge or public deployment is implied by this source checkpoint.
