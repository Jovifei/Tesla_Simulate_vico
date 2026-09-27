# Third-Party Notices

Stage V uses a clean-room Python implementation of the architecture described
by the open-source Engine-Sim project. No Engine-Sim C++ source, `.mr` engine
script, impulse response, recording, or audio asset is copied into this
repository.

Reference project: [ange-yaghi/engine-sim](https://github.com/ange-yaghi/engine-sim)

Pinned research commit: `85f7c3b959a908ed5232ede4f1a4ac7eafe6b630`

The upstream project is MIT licensed. The Stage-V study records source-level
observations and architectural traceability; the implementation in
`tools/sound_sim/s12/acoustic_identity_v015/event_domain/` is original and
retains the S12 synthetic/uncalibrated boundary.

## Oboe 1.11.0

The Android `:player` module uses the pinned Google Maven Prefab artifact
`com.google.oboe:oboe:1.11.0`; no Oboe source, recordings, IRs, or presets are
copied into this repository. Upstream release tag: [google/oboe 1.11.0](https://github.com/google/oboe/tree/1.11.0).

- License: Apache License 2.0.
- Exact upstream `LICENSE` text SHA-256: `CFC7749B96F63BD31C3C42B5C471BF756814053E847C10F3EB003417BC523D30`.
- The license text is packaged at `android_vehicle_sound_demo/player/src/main/assets/third_party_licenses/oboe-1.11.0-LICENSE.txt` and is viewable in the app.
- Local Maven mirror used for this workstation build: AAR SHA-256 `316F31CE92F07725A41556CB1EC0790B348E36B55791DF9E5E44976E1F652C30`; POM SHA-256 `59CC07B4E094F080A24CE3B8C4F6859D1DBFCAB1B41551405247008DC8AD4062`. The mirror is outside Git under the approved download directory.
- No upstream `NOTICE` file exists at the pinned release tag.
