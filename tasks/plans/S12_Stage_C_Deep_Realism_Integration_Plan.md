# S12 Stage C Deep Realism Integration

Status: `AUTOMATED_REALISM_CANDIDATE / HUMAN_AUDITION_PENDING`

This branch integrates deterministic pre-PTR equalization, pressure-coupled exhaust rumble, RPM-step shift dynamics, and one state-dependent afterfire model into `render_realism_v10._render_stateful`. FVM, PTR core, Radiation Boundary, Runtime, Android, MATLAB, Simulink, the Track-P guard, `manage_bundle_loudness`, and `_health` remain frozen.

## Execution checklist

- Establish baseline on `main=c08eb4c`, including the three known identity failures and a three-anchor continuous audition package.
- Add one eight-vehicle synthetic profile registry with explicit `C/synthetic` provenance.
- Add `pre_equalization.py`, `exhaust_rumble.py`, and `shift_dynamics.py`; refactor `afterfire_model.py` without adding a second afterfire path.
- Integrate the layers only before the frozen PTR adapter.
- Extend the drive-cycle publisher and metrics to all eight vehicles; keep 30-second compatibility and support the 60-second review cycle.
- Verify layers, deterministic behavior, eight-vehicle rendering, PCM24 health, Track-P, Stage B, identity, and realism suites.
- Publish before/after anchor WAVs, eight-vehicle outputs, metrics, SHA256 evidence, and `S12_Stage_C_Integration_Report.md`.
- Stop at `HUMAN_AUDITION_PENDING`; do not push or merge.

## Layer order

`source -> idle -> enhanced afterfire -> low-frequency body -> exhaust rumble -> shift dynamics -> pre-PTR equalization -> frozen PTR -> edge fade -> fixed whole-cycle loudness -> PCM24`

The prototype's hard-coded centroids, `hash(vehicle_id)` seeds, duplicated afterfire, false 26/6 shift counts, and incorrect `linspace` boom frequency are not evidence and must not be copied.

## Guard naming constraint

The new equalizer file is deliberately `acoustic_layers/pre_equalization.py`, not `ptr_pre_equalization.py`, because the Track-P guard freezes any path containing the substring `ptr`. Do not change the guard or its allowlist.

## Acceptance

All new tests and all touched suites must pass. The report must remain synthetic, uncalibrated, and not an OEM reproduction. Human listening is the only perceptual acceptance gate.
