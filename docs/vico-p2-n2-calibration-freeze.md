# N2 calibration freeze contract

Status: PRE_OBJECTIVE_INITIALIZATION_ONLY

This artifact is not objective scoring and does not use held-out data.

Frozen initialization values:

- calibration profile identity:
  `98dec5a954e836a0105241a04e920b8209f239441a51d039a46eb6b4f8e287c0`
- source unit calibration:
  `sourceScale = 13.728409855272066`
- source measurement:
  16 fixed steady fixtures, 3 seconds each, `[1s,3s)` window.
- event unit reference:
  - unit response energy: `331.3820481828321`
  - L2 norm: `18.2039020043`

Rules:

- calibration runs once before objective evaluation.
- calibration uses calibration fixtures only.
- no held-out samples participate.
- no post-failure gain change is permitted.
- CPU and Android consume the same serialized artifact; they do not regenerate kernels independently.
- profile identity, calibration identity and artifact hashes are immutable inputs to trial receipts.

Acceptance metrics remain separate from this initialization step.
