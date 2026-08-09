## Purpose

在三个锚点的 deep realism 调音与人耳盲听门禁全部通过后，收敛并输出产品级 AudioParameterPackage（JSON），该包可确定性地从 Track S 源模块复现，作为 S12 产品的声浪参数交付物。

## ADDED Requirements

### Requirement: Convergence gated on prior acceptance
The system SHALL produce the AudioParameterPackage only after `anchor-deep-realism` per-state targets are met and the `human-audition-gate` reports PASS for all three anchors.

#### Scenario: Package blocked before gates pass
- **WHEN** the package-convergence step runs but the audition gate has not reported PASS
- **THEN** the system SHALL refuse to emit the package and SHALL report the blocking prerequisite explicitly.

#### Scenario: Package emitted after gates pass
- **WHEN** deep realism and the audition gate both report PASS
- **THEN** the system SHALL emit a versioned AudioParameterPackage JSON covering the three anchors with their finalized Track S parameter sets.

### Requirement: Package content completeness
The AudioParameterPackage SHALL contain, per anchor, the finalized source / tuning parameter set, the per-state spectral targets, the afterfire / lift transient parameters, the reference identifier, and a reproducibility manifest (source commit + deterministic render seed).

#### Scenario: All required fields present
- **WHEN** the emitted package is validated
- **THEN** every required field per anchor SHALL be present and non-empty, and a schema validation SHALL succeed.

### Requirement: Deterministic reproducibility from sources
The AudioParameterPackage SHALL be reproducible: rendering from the pinned source commit and seed SHALL reproduce the anchor renders whose metrics were used to clear the gates.

#### Scenario: Reproduce from pinned commit
- **WHEN** the package's pinned source commit and seed are used to re-render an anchor
- **THEN** the re-rendered metrics SHALL match the gating metrics within the package's declared numerical tolerance.
