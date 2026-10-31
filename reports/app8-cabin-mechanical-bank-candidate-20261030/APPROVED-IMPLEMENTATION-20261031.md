# Approved cabin candidate implementation

**Scope:** This directory only; existing protected material and earlier results are read-only. The approved specification is `E:/Tesla_speed/reports/app8-mechanical-bank-research-20261030/C2C-APPROVAL-PLAN.md`. MATLAB remains reserved for the runtime repair agent until released.

- [x] Audit source, identity, event, network, prior B contract and native capture SHA.
- [ ] Add independent contract checks and behavioral tests for correct routing, cache, clocks and calibration.
- [ ] Implement the packaged source, network/modal path and post-Frozen receiver interfaces.
- [ ] Prepare a saved-then-reloaded model builder and runner with explicit signal logs, identity and failure receipts.
- [ ] Perform available non-MATLAB checks and hand off code for runtime review; record all unexecuted tests.

## Runtime sequence after release

Unit tests; save new SLX; close and cold reload; check saved expression, Selectors, connectivity and post-Frozen Sum; Update; active Compile/terminate; model_check; short simulation; exact B0 prefix and Frozen sequential proof; one calibration and freeze; long tracks and anchors only after all gates. A cold repeat requires a new MATLAB process. Record actual code/model/input SHA and MATLAB/Simulink versions. Capture output through explicit `evalc`/`fprintf` files; do not use an empty diary as evidence.

## Review

Pending implementation and authorized runtime execution. No acoustic, vehicle, device or human qualification is implied.
