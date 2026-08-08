## Purpose

建立人耳盲听混淆矩阵门禁，以参考/竞品样本作为混淆项，要求三锚点盲听辨识率达到阈值后才允许进入产品级 AudioParameterPackage 收敛，使产品收敛具备客观前置条件。

## ADDED Requirements

### Requirement: Blind listening sample set generation
The system SHALL generate a blind-listening sample set composed of anchor renders and reference / competitor confusion renders, each labeled only by an opaque random code, together with a structured blind-listening form.

#### Scenario: Opaque-coded sample set produced
- **WHEN** the human-audition-gate preparation step runs for the three anchors
- **THEN** it SHALL emit a set of `ab.wav` (or equivalent) files with opaque random identifiers and a blind-listening form that contains no anchor / reference names, and the mapping from code to identity SHALL be stored separately and sealed.

### Requirement: Confusion matrix construction
The system SHALL aggregate listener responses into a confusion matrix reporting, per anchor, correct-identification rate and cross-confusion rates against references and competitor confusion items.

#### Scenario: Matrix captures identification rate
- **WHEN** listener responses are collected for the blind sample set
- **THEN** the resulting confusion matrix SHALL report, for each anchor, the correct-identification rate and the largest cross-confusion rate, and the matrix SHALL be persisted as a versioned artifact.

### Requirement: Audition gate threshold enforcement
The system SHALL block product convergence unless every anchor's blind correct-identification rate meets or exceeds the configured threshold and no cross-confusion rate exceeds its configured ceiling.

#### Scenario: Gate passes when threshold met
- **WHEN** the confusion matrix shows all three anchors above the identification threshold and all cross-confusions below the ceiling
- **THEN** the human-audition-gate SHALL report PASS and SHALL permit downstream AudioParameterPackage convergence.

#### Scenario: Gate blocks when threshold unmet
- **WHEN** any anchor's identification rate is below threshold or any cross-confusion exceeds its ceiling
- **THEN** the human-audition-gate SHALL report FAIL and SHALL prevent AudioParameterPackage convergence until the condition is remediated and the gate is re-run.

### Requirement: Gate is reproducibility-stable
The system SHALL make the gate outcome reproducible: re-running the gate on the same sealed sample set and response data SHALL yield the same PASS / FAIL verdict.

#### Scenario: Determinism of verdict
- **WHEN** the gate is executed twice on identical inputs
- **THEN** the PASS / FAIL verdict and the reported rates SHALL be identical across both runs.
