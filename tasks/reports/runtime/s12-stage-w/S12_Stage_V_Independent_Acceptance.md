# S12 Stage V Independent Acceptance (W0)

**Exact tip:** `03f45432bd56f348d618ed69f25dfea86bc98a6f`
**Branch under audit:** `agent/s12-stage-w-ecosystem-bakeoff`
**Audit boundary:** remote commit contents and fresh Stage-V focused execution; local Stage-V runtime WAVs are not part of the commit.

## Verdict

`PARTIAL / P2_EVENT_DOMAIN_PROTOTYPE_BASELINE`

The Stage-V commit is a valid clean-room event-domain prototype. Its configuration, event scheduling, chamber packet, path delay, collector, afterfire eligibility, raw/monitor split and package validators are real code. It is not yet a persistent 20 ms engine state machine, a combustion-to-crank feedback loop, a post-PTR Stage-V pipeline, or a reference-qualified acoustic improvement.

## Requirement audit

| Area | Status | Evidence and exact gap |
|---|---|---|
| Exact tip / commit scope | PASS | `git show 03f4543`; 37 committed files; no generated WAV/ZIP in commit. |
| Source-model selection | PARTIAL | `event_domain_v1` is a diagnostic label and pipeline entry; no runtime selector that switches persistent engines. |
| Legacy regression | PASS | Stage-V regression tests preserve deterministic `legacy_v015` source calls; full historical suite is the baseline, not a Stage-W proof. |
| Event phase | PARTIAL | `event_scheduler.py` consumes `event_phase_deg`; phase is not derived from firing order and crank geometry. |
| Firing order | FAIL | `firing_order_evidence` is validated as a permutation but is not used to derive event phase. |
| Crank state | PARTIAL | `CrankPhasePLL` persists only within one renderer invocation; each `render_event_domain` call creates a new PLL. |
| Combustion torque feedback | FAIL | PLL `combustion_torque` is a load-derived formula; it does not consume scheduled chamber event torque. |
| Acceleration input | FAIL | `acceleration_mps2` is interpolated and passed to PLL validation, but does not affect dynamics or sound. |
| Path delay / attenuation | PASS | Fractional delay, temperature-dependent sound speed and per-path attenuation are consumed. |
| Collector topology | PARTIAL | `bank_assignment` drives routing; `collector_assignment` is metadata only and does not select topology. |
| Afterfire eligibility | PARTIAL | State gates and cooldown exist; `d_rpm`, `ignition_delay`, `event_location` and path identity do not control propagation. |
| Forced induction | PARTIAL | RPM/load state and turbo/blower branches exist; output remains a fixed harmonic sine family rather than a timbre map. |
| Raw / monitor isolation | PASS | Separate audio arrays, bounded gain trace and PCM24 validation are implemented. |
| Candidate grid | PARTIAL | Candidates render/reopen/compare, but the grid covers only `full_load_acceleration`; idle/lift/afterfire grid coverage is absent. |
| Comparator | PARTIAL | Three pair records exist; with the current external evidence class, reference is pointer-only and no automatic selection is allowed. |
| Frozen PTR/Radiation | FAIL | Stage-V `stage_v.pipeline` calls `render_event_domain` and does not call `_apply_frozen_ptr` or `RuntimePtrAdapter`. |
| External Runtime | NOT_APPLICABLE | Explicitly outside Stage-V commit scope; no Stage-W runtime proof yet. |
| Third-party notice | PASS | `THIRD_PARTY_NOTICES.md`, pinned Engine-Sim study and clean-room declaration are committed. |
| Runtime artifacts | NOT_VERIFIABLE_FROM_REMOTE | Runtime packages are deliberately untracked and outside the commit. |
| Obsidian closure | FAIL | Existing project pages were loaded, but Stage-W ecosystem notes and repo mirror are not yet present. |

## Known risk answers A–N

| ID | Question | Result |
|---|---|---|
| A | Is combustion torque from real events? | **No.** Load-derived proxy only. |
| B | Is acceleration consumed? | **No.** Input is validated/interpolated only. |
| C | Does firing order drive phase? | **No.** `event_phase_deg` is authoritative at runtime. |
| D | Does collector assignment drive topology? | **Partial.** Bank map drives routing; collector label does not. |
| E | Does transfer IR execute convolution? | **No.** `transfer_ir` is provenance metadata only. |
| F | Does event location change path? | **No.** Location is recorded; renderer uses round-robin entity placement. |
| G | Does ignition delay change event time? | **No.** It is recorded, not applied. |
| H | Is `d_rpm` consumed? | **No.** It is passed into the scheduler but not used in eligibility or timing. |
| I | Is forced induction still a fixed sine family? | **Yes, for Stage V.** Harmonic coefficients are fixed formulas. |
| J | Does renderer preserve state across independent calls? | **No.** New PLL and full buffers are created per call. |
| K | Does Stage-V pipeline call frozen PTR/Radiation? | **No.** It stops at source-domain pressure. |
| L | Does one-shot/block cover the whole renderer? | **Partial.** Existing equivalence evidence covers the output rerender path, but `block_size` only controls PLL chunks; source/path/afterfire are batch-rendered. |
| M | Does candidate grid cover idle/lift/afterfire? | **No.** Only full-load acceleration is searched. |
| N | Are Reference/Parent/Candidate scenes consistent? | **No evidence.** Current reference is pointer-only; external R3 lacks synchronized RPM/state. |

## W1–W6 entry order

1. Add a persistent 20 ms engine object with snapshot/restore and a real streaming path.
2. Feed scheduled chamber torque into free dynamics while retaining measured-RPM tracking mode.
3. Reuse the frozen `RuntimePtrAdapter` only after source-domain tests pass; do not modify the package.
4. Add stateful waveguide and localized afterfire before any audio bake-off.
5. Replace fixed forced-induction sine formulas with an explicit timbre-map branch.

All results remain `synthetic / uncalibrated / vehicle-inspired / not OEM reproduction / NOT_R1_QUALIFIED / NOT_PROFILE_FREEZE_READY`.
