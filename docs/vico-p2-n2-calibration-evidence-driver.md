# N2 pre-objective calibration and evidence driver

This document binds the initialization boundary before any objective or held-out evaluation.

Frozen calibration inputs:

- 16 steady calibration fixtures only.
- 3 second captures.
- RMS window [1s,3s).
- No held-out samples.
- No objective scoring.

Frozen source initialization:

- unit profile identity:
  `98dec5a954e836a0105241a04e920b8209f239441a51d039a46eb6b4f8e287c0`
- source scale:
  `13.728409855272066`

Frozen event initialization:

- legacy unit impulse-response energy:
  `331.3820481828321`
- legacy unit L2 norm:
  `18.2039020043`

The resulting binary artifact is the only allowed source for CPU/Android execution.
Kernel regeneration at runtime is prohibited.

Acceptance metrics remain separate from this initialization step.
