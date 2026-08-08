## Purpose

对三锚点（Ferrari 458 / Hellcat / RX-7）做逐状态 deep realism 调音，并对预存在的 12 个 pytest 回归做 Track S 内修复，使产品级声浪在频谱真实感与引擎身份分离上达标，且不破坏 §4.2 粗调门禁与冻结物理边界。

## ADDED Requirements

### Requirement: Per-state spectral realism for three anchors
The system SHALL provide, for each of the three anchors (Ferrari 458, Hellcat, RX-7), per-state spectral-target tuning across at least the states idle, steady cruise, acceleration, full pull, lift-afterfire, and idle return, expressed as band-level spectral-energy-ratio targets within Track S source modules.

#### Scenario: Idle-state spectral target met
- **WHEN** the idle-state render of an anchor is evaluated against its reference spectral template
- **THEN** the per-band spectral-energy-ratio error SHALL stay within the §4.2 coarse tolerance and the per-state deep-realism residual SHALL be below the per-state threshold defined in the anchor's tuning manifest.

#### Scenario: Full-pull and lift-afterfire states covered
- **WHEN** the full-pull and lift-afterfire states are rendered for each anchor
- **THEN** each state SHALL have a non-empty spectral-target block committed in the anchor's Track S source manifest, and the afterfire transient SHALL show an energy decay consistent with the reference lift event.

### Requirement: Engine identity separation across anchors
The system SHALL ensure that the three anchors remain mutually distinguishable and distinguishable from their references, so that no anchor's render is confused with another anchor or reference under spectral analysis.

#### Scenario: Cross-anchor spectral separation
- **WHEN** pairwise spectral-distance is computed among the three anchors plus their references across the shared states
- **THEN** every pairwise distance SHALL exceed the identity-separation minimum threshold declared in the realism_reference_manifest, and no two anchors SHALL collapse below it.

### Requirement: Afterfire and lift transient realism
The system SHALL render afterfire / lift transients whose onset timing, broadband burst energy, and decay envelope match the reference anchor behavior within Track S afterfire modules.

#### Scenario: Lift-afterfire burst present and bounded
- **WHEN** a lift event is simulated for an anchor that exhibits afterfire in its reference
- **THEN** the render SHALL contain a detectable post-cut broadband burst whose onset latency and decay time SHALL fall within the reference-specified tolerance band.

### Requirement: Repair of twelve pre-existing pytest regressions within Track S
The system SHALL repair all twelve pre-existing pytest regressions (ferrari rms_bounded + high_freq_grows; hellcat blower shaft lobe; rx7 housing + turbo-lift + acceleration-stem-balance + constant_state; plus five LUFS-RMS integration subtests) exclusively through edits to Track S modules, without modifying any frozen Track P boundary.

#### Scenario: Regression suite returns to green
- **WHEN** the full pytest suite `tests/test_s12_engine_acoustic_identity_v015.py` is executed after the repair
- **THEN** the previously failing twelve tests SHALL pass and the failing-test count SHALL be zero relative to the pre-repair baseline for those cases.

#### Scenario: Freeze boundary untouched
- **WHEN** the repair edits are complete
- **THEN** no change SHALL be present in Track P modules (radiation, PTR core, FVM, runtime, MATLAB), `render_identity_v02._health`, or the `manage_bundle_loudness` signature, as verified by `git diff --check` and an explicit boundary-scope review.

### Requirement: Coarse-gate stability during deep realism
The system SHALL keep the §4.2 coarse acceptance gates (idle centroid abs error ≤ max(25 Hz, target×10%); accel per-band abs error ≤0.05; ≥30% baseline improvement) passing for all eight tuned vehicles after deep-realism edits.

#### Scenario: Coarse gates remain green
- **WHEN** the deep-realism tuning is applied and `publish_identity_v02` runs for the three anchors
- **THEN** the publisher SHALL report PUBLISH OK and the Stage B coarse-gate metrics SHALL remain within tolerance for every affected vehicle.
