# N2 binary artifact correction

Status: PRE_OBJECTIVE_INITIALIZATION_ONLY

The N2 artifact is now the complete immutable profile payload.

Stored:

- header/version
- fixed dimensions
- identity
- source/random/event scalars
- source/occurrence/response seeds
- eight 4096 continuous responses
- three 12288 event responses
- coefficients

Import reconstructs N2Profile and recomputes identity. CPU and Android must load this artifact; no default kernel generation is permitted.

Calibration remains before objective evaluation:

- sourceScale: 13.728409855272066
- event initialization uses measured legacy unit L2: 18.2039020043

No held-out data or objective score is involved in artifact creation.
