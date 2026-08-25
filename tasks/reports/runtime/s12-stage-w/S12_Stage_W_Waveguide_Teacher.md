# S12 Stage W Waveguide / ENSIM4 Teacher (W4)

Status: `WAVEGUIDE_V1_PASS / ENSIM4_BUILD_BLOCKED_TOOLCHAIN`

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
- Build attempt: `make ENGINE=ENGINE_3_CYL` / `make ENGINE=ENGINE_8_CYL`
  could not start because this Windows host has no `clang`/`make`; WSL exposes
  only `docker-desktop` and no usable Linux distribution. No build/run/audio
  PASS is claimed.

ENSIM4 remains an offline teacher candidate only. Its C source and output are
not copied into S12 and cannot replace the frozen S12 FVM/PTR/Radiation chain.
