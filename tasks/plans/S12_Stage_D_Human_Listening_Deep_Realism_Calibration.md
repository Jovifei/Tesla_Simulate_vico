# S12 Stage D Human Listening Deep Realism Calibration

Execution contract: `a5d048145c29b20d687376c0b73226bc4a2435c7`, branch `agent/s12-stage-c-realism-integration`.

Status is initially `AUTOMATED_REALISM_CANDIDATE / HUMAN_AUDITION_PENDING`. Stage D may only extend offline Track-S candidates and audition tooling. FVM, PTR core, Radiation Boundary, Runtime, Android, MATLAB, Simulink, Track-P guard, and the fixed loudness manager remain frozen.

The verified chain is:

```text
independent source -> idle -> deterministic afterfire -> low-frequency body
-> exhaust rumble -> shift dynamics -> pre-PTR EQ -> frozen PTR -> PCM24
```

The implementation must use TDD, keep `candidate=None` bit-identical to Stage C, evaluate references in final-PCM space, generate two anonymous 15-trial rounds, and stop at `WAITING_FOR_JOVI_AUDITION` until Jovi returns the sealed response sheet.

Reference data is limited to the existing `reference_database`; all targets remain B/R2 relative, synthetic calibration remains C/synthetic, and no OEM or calibrated claim is permitted.
