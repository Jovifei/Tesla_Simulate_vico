# Source to S12 Traceability

Engine-Sim and SIVE inform event/chamber/path topology; ENSIM4 informs an
offline 1D-CFD teacher boundary; PSOLA/OLA inform phase-aligned cycle
resynthesis; PTR/EONE/DDSP inform state-conditioned pressure/timbre maps; SAE
roughness informs order diagnostics. None of these external sources replaces
S12 FVM/HLLC/SSP-RK3/PTR/Radiation or proves OEM identity.

W3 uses the accepted RuntimePtrAdapter and radiation package by exact SHA. W4
waveguide_v1 is an original S12 implementation and remains selectable beside
delay_lpf_v1. External source code, presets, recordings, weights and binaries
are not copied into S12. Per-source URL/version, license, build/run, callgraph,
reusable idea, forbidden reuse and unresolved questions are joined by id in
`docs/research/engine-audio-ecosystem/source_evidence_receipts.json`.
