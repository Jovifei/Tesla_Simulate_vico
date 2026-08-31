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
