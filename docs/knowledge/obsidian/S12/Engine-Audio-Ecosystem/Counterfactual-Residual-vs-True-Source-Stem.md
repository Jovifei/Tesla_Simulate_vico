---
tags: [S12, negative-knowledge, causality]
stage: Stage-AB-R
---

# Counterfactual Residual vs True Source Stem

**NEGATIVE KNOWLEDGE — reuse for Ferrari / RX-7 work.**

For Y = render(Uc), the identity

    Y = Y(Uc=0) + [Y(Uc) - Y(Uc=0)]

always holds. But the residual R_c = Y(Uc) - Y(Uc=0) is the
**COUNTERFACTUAL TOTAL EFFECT** of the combustion intervention on the whole
downstream mix — it is NOT automatically an "independent combustion source stem".

Why: every downstream layer (paths, waveguides, transients, dP, PTR) shares
processing interactions with the combustion path (state, filter memory, mixing).
Scaling R_c by g(load) re-injects the *total* causal effect, including shared
interactions, at the reconstruction layer (pre_ptr) — not at the source.

Consequences (Stage-AB P6):

- route kind: `COUNTERFACTUAL_COMBUSTION_RESIDUAL_SCALE`
- `source_causal_eligible = false`, `production_candidate_allowed = false`
- allowed as diagnostic-only attribution, never as a Round-2 candidate

## What a true source stem requires

A source-causal candidate must (a) intervene at the actual source/event
generation parameter, (b) be consumed by runtime, (c) re-render from source
down, and (g) have `first_changed_layer` in combustion/event/source — see
`source_causal_eligibility.json` conditions A-G.

Related: [[AA-C3-Gain-Provenance-v2]], [[Broad-Pre-PTR-vs-Source-Causal-Gain]]
