# Y5 pressure audio chain closure

Status: `PASS` for the bounded Y5 dP/DC/fractional-delay/warmup and snapshot scope at source commit `34318d60541b3d4b2615541f0120caf90d4348b8`.

The RED capture reproduced the known block-size dependency: the old one-mean-per-block DC update produced a stream-vs-one-shot maximum absolute difference of `3.537902585315153e-06` at `48000 Hz`. The repair keeps the existing pre-PTR dry/delay mix (`0.65/0.35`) and dP mix (`0.35`), replacing the block mean with persistent per-sample, per-channel DC state. Fractional delay remains linear interpolation over persistent stereo history.

`PressureAudioChain` now validates sample rate, delay, stereo shape, finite inputs, and empty input before state mutation. Warmup is automatically applied once for `max(int(0.1 * sample_rate_hz), 1)` samples, its output is discarded, and warmup is not counted as caller audio. Snapshot schema `s12.stage_y.pressure_audio_chain.v1` covers DC, dP predecessor, delay history, warmup state/topology, and sample counter with atomic validation/restore. An active engine rejects missing or null chain state rather than claiming exact replay.

`PersistentEventDomainEngine` only wires the chain snapshot and diagnostics. The chain remains opt-in (`audio_chain="dp_v1"`); default `audio_chain="off"` behavior, fitted map, transient layer, PLL, output scale, and frozen PTR remain untouched.

## Verification

The required post-commit focused receipt is [y5_dp_chain-20260831T060110031436Z.json](../../tasks/reports/runtime/s12-stage-y/y5_dp_chain/logs/y5_dp_chain-20260831T060110031436Z.json), bound to the source commit above. Its subprocess captured actual UTC bounds `2026-08-31T06:01:10.057555+00:00` to `2026-08-31T06:01:25.726980+00:00`, exit `0`, and `19 passed in 15.15s` with `S12_RUN_SLOW=1`. stdout SHA-256 is `b631f03b92f153fac8d301a532821a3f4e93f602ecddbf123fb77b5950322d9d`; stderr is empty (SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

That run covers DC removal, stereo isolation, integer/fractional delay, empty/nonfinite/invalid input, invalid constructor state, one-time configured-rate warmup, atomic chain/engine snapshots, enabled engine streaming/replay, active-chain missing-state rejection, P3/off-vs-dP/on post-PTR SHA ablation, the Stage-W click contract, and the deterministic `3000 x 960` (60 s) one-shot/stream equivalence with maximum absolute difference below `1e-9`.

The pre-commit affected Y4 regression run also passed `80 passed, 2 skipped in 19.47s` across the Y5, Y4 transient, and persistent-engine focused files. No full S12 run, push, merge, or PR was performed.

Y5 is now `PASS`; the next bounded phase is Y6 package work (`IN_PROGRESS`).
