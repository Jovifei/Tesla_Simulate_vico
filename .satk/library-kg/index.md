# Simulink Library Knowledge Index

## Gate Status

- Audit date: 2026-07-13
- Custom reusable block libraries: none
- `reuse-libraries.json`: `confirmed_none = true`
- Block policy: prefer customer libraries, with built-in fallback enabled
- Sprint 0.5 permitted blocks: built-in Simulink and Stateflow blocks

## Indexed Blocks

No project-owned or third-party reusable Simulink block libraries were found,
so there are no custom blocks to index. MathWorks libraries such as `fl_lib`,
`nesl_utility`, `dspsnks4`, and `dspvision` are product libraries rather than
customer libraries and are not duplicated here.

`library.kg.Populate.run` and `runIncremental` were invoked after the official
`confirmed_none` configuration was saved. Both correctly produced no custom
block entries and no generated index, so this empty index records the resolved
gate without inventing library content.

## Sprint 4B Model Policy Audit

- Audit date: 2026-07-16
- Controlled model: `tools/sound_sim/s12/models/fvm_ref/s12_euler_fvm_fanno_ref.slx`
- Blocks used: built-in Constant, MATLAB Function, and To Workspace blocks
- Custom or third-party Block Library links: none
- Policy decision: permitted by `fallbackToBuiltins = true`; no new reusable
  customer library was introduced and `confirmed_none` remains valid
- Structural check: `model_check(["all"]) = healthy`

The model contains only the exact local Darcy-friction source update. The
frozen HLLC, MUSCL-minmod, positivity-preserving, and SSP-RK3 models remain
separate controlled dependencies selected by the adapter.

## Sprint 4C Model Policy Audit

- Audit date: 2026-07-16
- Controlled models:
  - `tools/sound_sim/s12/models/fvm_ref/s12_euler_fvm_transient_wave_ref.slx`
  - `tools/sound_sim/s12/models/pipe_ref/s12_transient_pipe_g_closed_ref.slx`
  - `tools/sound_sim/s12/models/pipe_ref/s12_transient_pipe_g_open_ref.slx`
- Blocks used: built-in Simulink/Stateflow for the FVM reference and built-in
  Simscape Gas blocks for the two Pipe(G) cross-checks.
- Custom or third-party Block Library links: none. The existing
  `confirmed_none` library decision and built-in fallback remain valid.
- Structural evidence: the FVM model is `model_check(["all"])` healthy. The
  two Pipe(G) models each reproduce the known conserving-port inspector false
  positives; their complete connection graph and runtime behavior are verified
  separately and the warnings are not suppressed or recast as healthy.
