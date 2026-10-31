# Isolated Simulink startup smoke plan

Purpose: in the currently connected MATLAB Desktop/MCP session, verify that a new, minimal model can exercise the existing private source/identity, event/modal and bank-network research functions without changing any protected project artifact. This is not the approved full candidate signal path or an acoustic audition.

- [x] Capture fresh protected SHA-256 and Git status/diff under this candidate directory.
- [ ] Test the unique-name smoke wrapper for repeat evaluation, changed duplicate input, frame ordering and deterministic reset; then implement and rerun.
- [ ] Put one new model under `isolated-model`, route a native-looking 9x1 packet into the wrapper, and log a finite diagnostic output. Use `model_edit` for structural changes; save only the new model.
- [ ] Cold-close/reopen, update diagram, actively compile/terminate, call `model_check`, then run a 0.04 s fixed-step `SimulationInput` smoke and independently check frame count, input clock, finite output and wrapper evaluation history. Stop on any issue.
- [ ] Save model metadata, test/command/return receipts, protected-file comparison, and explicit limitations.

The existing private components are preliminary. No Frozen, calibration, 90 s drive, WAV/PCM or human/device qualification is claimed by this model. The original user startup script and all prior model/source/soundbank/Android artifacts are protected.

## Stopped

The four smoke-wrapper tests produced an unexpected error after implementation; per the parent instruction, no fix, model construction or simulation was attempted. Details: `SMOKE-FAILURE.md` and `smoke-test-transcription.json`.
