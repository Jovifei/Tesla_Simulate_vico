# S12 Stage W Waveguide / ENSIM4 Teacher (W4)

Status: `WAVEGUIDE_V1_PASS / ENSIM4_DOCKER_BUILD_PASS_DUMMY_RUN_ONLY`

## Waveguide v1

`stage_w.waveguide` is a clean-room stateful path model. It keeps forward and
round-trip delay histories, computes temperature-dependent arrival samples,
applies an area-ratio reflection coefficient and frequency-independent loss,
and merges paths through a bank stereo collector. It is selectable on
`PersistentEventDomainEngine(path_model="waveguide_v1")`; the Stage-V
`delay_lpf_v1` baseline remains available and unchanged.

Focused evidence: `4 passed`, including impulse state across block boundaries,
one-shot/block equality, equal/unequal header arrival/SHA, and persistent-engine
path-model selection.

## ENSIM4 external teacher

- External checkout: `E:\Tesla_speed\research\engine-audio-ecosystem\ensim4`
- Exact commit: `35b92a6aa5e038d18769d637dc9bedf0346939e1`
- LICENSE SHA-256: `CDFF1D6C75E2B3C954619FDAA0A9917FF0F37ABE754201576C59853059A0305A`
- README/source claim: C23, one-dimensional isentropic exhaust CFD, SDL3, CFD
  on/off control.
- Docker build: Arch Linux container installed clang/make/SDL3 and completed
  `make ENGINE=ENGINE_3_CYL`; Linux binary SHA-256 is
  `0e88fa95ce4ec752acae1c99dca659a56a0ad61edc12ff214977a2082ba413d4`.
- Dummy run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 5s ./ensim4`
  remained live until the controlled timeout. This proves the executable path,
  not a listening result: no real playback device, CFD on/off interaction, CPU
  capture or WAV was produced.
- Disk-audio probe: SDL wrote `sdlaudio.raw` (1,818,624 bytes, F32LE stereo
  48 kHz, SHA `f6ab339213be739aae5925f18a38d13e870a859ca6f8715cb5566e4a9264a498`)
  during the same controlled run. Every sample was zero because no starter/
  ignition keyboard event reached the dummy session; this is runtime plumbing
  evidence only, not engine audio or a CFD ON/OFF comparison.

ENSIM4 remains an offline teacher candidate only. Its C source and output are
not copied into S12 and cannot replace the frozen S12 FVM/PTR/Radiation chain.
