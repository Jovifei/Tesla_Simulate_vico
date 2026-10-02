# C63_HY1 — c2c_930a iteration11

Remote PLAN fully read in original 音浪 chat, after AR2 rejection review. Goal: replace the persistent four-high-Q bark network with reference-envelope finite periodic/stochastic synthesis, improve afterfire response and actual mix contribution, then deliver to existing Android app.

## Frozen contracts
AH/s15, AR1/s16, AR2/s17 acoustic source/profile/read-only. Original low exhaust/intake/pressure/body/rumble, mechanical800/scale9.786453030584157, idle/shift, output EQ/PTR/gain3.7075542301539652, h.40803954754257843,48k mono,35ms controls unchanged. Original six-car bank remains default. Existing dirty Vico branch retained; no new Git remote or unrelated changes.

## Implementation
- [ ] Stage start snapshot, identities, reference split and preregistration.
- [ ] s18 finite source:2048-sample causal minimum-phase response from eight broad200–6300Hz controls, zeroDC/tapered finite tail; original event frames/amplitudes/banks. Old four bark modes absent from S/SE, no arrival jitter.
- [ ] Independent broad noise with fixed seed, power fraction0–25%, state/expected event rate and kernel energy budgets, no live RMS/peak normalization. One preregistered source-scale calibration to T bark energy.
- [ ] Simulated coast gate: valid,RPM≥3300,throttle<.15,load<.2 -> drive target0 via35ms smoothing; queue tails and original lower layers continue.
- [ ] Afterfire: preserve E2 occurrence/thermal/validity/seed; replace90/850 response with synthetic bipolar pressure plus broadband tail, maximum12288samples; cal-statistics only, no reference waveform assets. Independent response RNG and one event-energy calibration.
- [ ] T/S/E/SE renderer plus same-state event-on/off captures; full snapshots/1,96,192,240,256,480,960,4800 partitions; invalid input beforemutation, event and RNG isolation.
- [ ] Broad-envelope and normalized modulation targets from valid SHA-pinned reference distributions, no fabricated reference RPM/load labels; cal/held disjoint, silent idle/overlap exclusions preserved. Continuous fit≤64 full evaluations; event fit≤32; deterministic initializers/no restart; weights/scales fixed beforefirst evaluation; profile freeze before qualification.
- [ ] All branch/actual event metrics;333+297 known numerical regressions and preregistered new tails/overlap/coast/phase/seed cases.
- [ ] Only offline pass: HY1 default-off App entry, exact profile/source/APK/cert receipts; data-preserving install, same-input phone PCM equivalence, independent warmup,10cold+30min, actualinputloss/stopstart/route/cancel/lifecycle/wakeup/perminute. Short new-only listening; human PENDING until Jovi.

## Gates
Raw low stems exactly preserved. Full20–200Hz median absolutechange≤1dB/p90≤1.5. Driven200–4000Hz integratedenergy rise≤1dB; drive/coast separately. Fixed eval coarse-envelope/normalizedmod composite distance improves≥20%, no validgroup worsens>10%; puregain reduction cannotpass. Mechanicaltexture unchanged. Events same-domain attack/tail/interval/relativeamp distance improves≥20%, eachcategory regression≤10%; noillegalcold/open/shift/invalid newevents. Matched known-event windows, raw/distinct/episode/falsepeak/censored separate. Event/background median improves≥3dB with eventenergy rise≤1dB and nosimpleeventgain change. S/E/SE independently qualified. Post-original-output/h peak≤.8413951416451951,finite/clip/lostframes/queueoverflow0.

## Evidence and boundaries
New code: sound/s18/C63HybridSource,FiniteResponseSource,HybridNoise,HybridAfterfire,HybridProfile,HybridRenderer; tests and build/fit/qualify_c63_hybrid tools. App integration only aftergatepass. Reference R2/rights unverified stays local research; APK contains generated parameters only. Use E:/Claude_allow/Download/vico-c63-hy1-20261002-v1. Failure preserves all branch data and returns concrete review; no h rescue or six-car expansion before pilot qualifies.
