# Recursive search additions (2026-08-30)

These sources were not in `source_registry.json` at Stage W close, or were named in a Prompt but do not exist.

## markeasting/engine-audio

- URL: https://github.com/markeasting/engine-audio
- Demo: https://markeasting.github.io/engine/
- License: MIT on code; sample banks need a separate rights check
- Method: WebAudio **soundbank** loops driven by RPM/throttle, not a physical cylinder model
- S12 mapping: state-driven clip banks and drivetrain clock. Same family as VNS, opposite of Engine-Sim
- Reuse: schema and crossfade ideas only. Do not import third-party engine samples into Git
- Status: RESEARCH_NOT_CHECKED_OUT as of 2026-08-30

## xevrion/ignis

- URL: https://github.com/xevrion/ignis
- License: must be read from the checkout LICENSE file
- Method: clean-room Engine-Sim descendant. Constraint-solved crank; lumped gas; audio-rate exhaust-port flow; DC remove; pressure derivative; delay-line pipe resonances. Author states it is not a port of Engine-Sim C++
- S12 mapping: the missing Engine-Sim audio chain pieces (dP, DC, pipe delay-line) without copying Ange's source
- Forbidden: copying ignis C++ into S12; using it as OEM truth
- Status: RESEARCH_NOT_CHECKED_OUT; **highest-value unread physical-audio repo**

## MeFisto94/engine-sound-sim

- URL: https://github.com/MeFisto94/engine-sound-sim
- Method: Rust library, physical pressure waves, realtime-oriented, no rigid-body solver
- S12 mapping: secondary to DasEtwas / waveguide_v1
- Status: RESEARCH_NOT_CHECKED_OUT

## Engine-Simulator/engine-sim-community-edition

- URL: https://github.com/Engine-Simulator/engine-sim-community-edition
- Binary distribution of Engine-Sim. No extra algorithm source
- Use: listen/compare. Do not vendor the zip

## yoshiomiyamae/engine-sound-simulator

- URL claimed in Stage U/W prompts: https://github.com/yoshiomiyamae/engine-sound-simulator
- Result: **repository does not exist** (user profile has unrelated repos)
- Action: drop from all future Prompt source lists

## GameSynth Engines (Tsugi)

- URL: https://tsugi-studio.com/web/en/products-gamesynth.html
- Commercial procedural vehicle engine model
- Public-docs workflow only
