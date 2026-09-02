# S12 Stage AB Resume

## Current state

`AB2_HUMAN_FEEDBACK_GATE`: `WAITING_FOR_JOVI_AUDITION` from post-merge main
`d156f3d729f68df8fd110a802ef16bce7a8f8088` (PR #4 merge). AB0 and AB1 are
complete; AB3+ are blocked on Jovi's V3 audition feedback.

## Phase order

`AB0_POST_MERGE_TRUTH → AB1_AA_C3_PROVENANCE_AUDIT →
AB2_HUMAN_FEEDBACK_GATE → AB3_HUMAN_FEEDBACK_BINDING →
AB4_SOURCE_CAUSAL_ROUND2 → AB5_PROFESSIONAL_FINALIST →
AB6_V4_BLIND_AUDITION → AB7_FINAL_HUMAN_DECISION → AB8_FINAL_QUALIFICATION`

## Recovery rules

- No acoustic parameter changes before `human_feedback/jovi_v3_feedback.json` exists.
- Never open `answers_manifest.html` before feedback receipt + binding.
- At most ONE Round 2, max 3 candidates (AB-R2-A/B/C), distinct hypotheses, source-causal only.
- No whole-mix gain in Round 2 raw candidates (enforced by tests).
- Ferrari / RX-7 / multi-vehicle propagation stays frozen.
- Do not rerun the provenance render unless renderer/config/test inputs changed.

## Key evidence

- Post-merge receipt: `post_merge_truth/stage_aa_post_merge_receipt.json`.
- Provenance artifacts: `provenance/` (taxonomy, variant metrics, Shapley
  attribution, dynamic preservation, LF body guard, blower provenance, audit MD).
- Feedback schema: `human_feedback/jovi_v3_feedback.schema.json`.
- Interim report (15-question format): `STAGE_AB_INTERIM_REPORT.md`.
- Interim execution state: `execution_state.json`.
- v3 audition package: `E:/Tesla_speed/review_packages/s12-stage-aa-hellcat-quality-v3`
  (manifest `b1ea99d3…f0964f`, untouched).

## On feedback receipt

1. Save raw feedback, compute `feedback_sha256`.
2. Reveal B/C identity; write `human_feedback_binding.json`.
3. Map feedback → scene → candidate/stem → metric hypothesis → parameter family → guard.
4. If AA-C3 accepted outright: `HELLCAT_HUMAN_ACCEPTED_R2_DIAGNOSTIC_CANDIDATE`, stop.
5. Else run the single source-causal Round 2; failure ⇒ `MODEL_REDESIGN_REQUIRED`.
