# Dimension investigation, 2026-10-31

## Evidence

- `104325_161`: `runs/approved-20261031-104320-703/02-build.log`
  records rejected `NumberOfDimensions`, `IndexOptionArray`, and
  `IndexParamArray` settings. The block's one-dimensional defaults and its
  proposed two-dimensional selector settings were inconsistent. This was a
  real failed build.
- `112408_106` is a separate failed, unsaved model from the later saved
  `112747_734` candidate. Do not use a later receipt to claim that the user's
  older open model compiled successfully.
- The `112747_734` saved candidate's build receipt reports source `[960,9]`,
  combustion split `[960,2]`, path bus `[960,2]`, mechanical split and
  receiver `[960,1]`. The same receipt reports the Frozen output entering
  the Sum as a one-dimensional 960-element vector, while the other input is
  a two-dimensional `[960,1]` array. The receipt proves the reported compile
  for that model version only; it does not prove the complete requested
  `[960,1]` input contract.
- In the saved `112747_734` model, `Mechanical_Receiver` uses
  `mb_mechanical_direct_step`, which reshapes its input to `[960,2]`.
  `Mechanical_Split` supplies `[960,1]`. The runner temporarily replaces
  that expression with `mb_mechanical_mono_step`. Hence the saved model's
  default receiver expression remains incompatible with its actual input.
- The final retained short-M capture from
  `runs/approved-20261031-121025-642/short-M/capture.mat` has 100 source and
  path frames, but `receiverReport.frames=1` and
  `receiverReport.duplicates=99`. Only 1 of 100 logged mechanical output
  frames is nonzero, although all 100 expected path frames are nonzero.
  Its logged post-Frozen Sum agrees with its two logged inputs to
  `5.21e-18`; the observed fault is the receiver output, not an established
  arithmetic failure of the Sum.

## Isolated fix and validation

- `mb_mechanical_mono_step.m`: removed the value-based duplicate suppression
  that returned zeros for a repeated input. The receiver is a stateless
  scale/bypass calculation; repeated evaluations must return the same output.
  Its counter now records evaluations rather than claiming frame identity.
- `test_approved_cabin_steps.m`: added a regression for repeated nonzero
  frames and mode changes. Existing MATLAB Desktop session: prior code failed
  the regression, then the modified code passed all 5 tests after clearing
  the stale function from MATLAB's cache.
- No model, Frozen file, common source, sound bank, Android file, or long
  simulation was changed/run by this task.

## Remaining

The changed function has not yet been verified in a fresh isolated SLX by
Update Diagram, compiled-port assertions, `model_check`, and real short
simulation. The builder already uses the mono receiver in its source, but the
existing saved candidate still uses the incompatible direct receiver. Create
a new uniquely named candidate and receipt instead of overwriting historical
evidence. If strict two-dimensional `[960,1]` is required on both Sum ports,
convert the Frozen 1-D vector inside the new isolated model and verify that it
does not alter the Frozen model or PCM values.
