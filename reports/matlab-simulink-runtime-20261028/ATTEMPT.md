# MATLAB/Simulink runtime gate - 2026-10-28

## Current source

- Branch: `local/hellcat-state-contract-20261027`
- Texture source update: `s12_v12_mix_texture_residual.m`
- Fixed-frame MATLAB Function: `s12_v12_model_texture_step.m`
- Candidate contract: `s12_v12_texture_simulink_contract.m`
- Hellcat source model: `tools/sound_sim/s12/playground_v12/vehicles/hellcat_2022_stock/S12_hellcat_2022_stock_v12.slx`
- Exact archive topology audit: `reports/simulink-texture-topology-20261028.json`

## Runtime attempt

The following MCP operations were attempted against the existing MATLAB session:

- `evaluate_matlab_code` with R2026a release/Simulink/PWD probe;
- `model_overview` for the Hellcat v1.2 model;
- `run_matlab_file` for `test_s12_v12_texture_residual_matlab.m`.

All returned `failed to attach to MATLAB session`. A fresh process check found no `matlab.exe`, `MathWorksServiceHost`, or `matlab_mcp_server`, and no listener on the known MATLAB MCP ports. No second MATLAB process was started and no `-batch`/`-nodesktop` command was run.

The same three read-only probes were reattempted after the later source update on 2026-10-28; the attach failure and empty process/listener state were unchanged.

## Evidence boundary

- Static Python contracts: PASS (`35/35` v1.2 source contracts; `8/8` texture/topology contracts).
- MATLAB source changes: present in the isolated branch.
- Simulink archive topology: PASS by read-only ZIP audit; source-to-radiation chain is unchanged.
- MATLAB test: `NOT_RUN`.
- Model edit, Cold Reload, Update Diagram, Active Compile: `NOT_RUN`.
- 90-second Simulink simulation, repeated WAV/PCM SHA, Audio Device Writer, device and human audition: `NOT_RUN`.

## Next controlled action

After one existing-session MATLAB/MCP transport is restored, execute exactly this sequence on a copied candidate model:

1. Copy the Hellcat v1.2 model to an isolated candidate path.
2. Add `Texture Residual` `[960,1]`, `Texture Weight` `[1,1]`, and `s12_v12_model_texture_step`.
3. Replace only `Hellcat Synthetic Source -> Frozen 4D-B Radiation Adapter` with `Source -> Texture Mixer -> Frozen Radiation`.
4. Keep default weight at zero and prove legacy output equivalence.
5. Cold reload, Update Diagram, Active Compile and `model_check`.
6. Run the fixed 90-second trajectory twice with a public texture input and compare PCM/WAV SHA, peak, finite values and block boundaries.

No candidate may be promoted to the default sound bank until runtime, acoustic, device and human gates are separately recorded.
