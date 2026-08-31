# S12 Stage Y 最终软件闭包（2026-08-31）

状态：`FINAL_FITTED_MAP_PASS / FULL_S12_PENDING / R1_HUMAN_GATES_OPEN`

本报告记录从 integration tip `3aafda52f8c1b9fe5728591ca087b53fa2baf809` 创建的闭包分支 `agent/s12-stage-y-final-closure`。起始 `origin/main` 为 `c08eb4c0d557c32e0896bef9be4f4eddf5d296ea`，测试源码提交为 `59fe45d`，source-contract HEAD 为 `662eefa`。起始 main 已是 integration 的祖先，无需额外合并。

## 本轮源码调整

- `stage_w/persistent_engine.py`：仅在 `timbre_map_v1 + require_fitted_timbre_map` 时启用 bounded local source-layer coupling：broadband `4.0`、forced blower/turbo layer `2.0`；legacy/formula-map 保持 `0.28`、`1.0`。诊断字段记录 provenance；不改全局增益、PTR/Radiation、FVM、Track-P 或地图数据。
- `stage_x/search_parameters.py`：boost attack/release 使用声明过渡窗口内的 scale-invariant high-band share；短窗零填充至 comparator 的 23-frame roughness trend kernel，避免短帧广播异常。旧 RMS 键保留为诊断，不作为这两个控制的 gate。
- `test_s12_stage_y_reachability.py`：覆盖 fitted/legacy coupling 边界、high-band helper 选择性与增益不变性，以及最终 16 控制契约。
- `stage_w/persistent_engine.py` 的 v4 snapshot 现在绑定 coupling contract；v1/v2/v3 输入显式迁移或 fail-closed，fitted snapshot 不能恢复到 legacy coupling。`stage_y/package.py` 的 renderer config SHA 同时绑定该 contract，防止 v1/v2 重渲染时静默接受 coupling 漂移。

## Final fitted-map 证据

当前 canonical 运行 `y1-final-fitted-map-20260831T183122590736Z` 退出码 `0`，artifact SHA `3609d1dda341c271a0a983fe5e66c1c868746b336cdea151dc50da97dc36b1df`。测试源码 HEAD 为 `f498c99352ad559897b6157d6722d64e05e68a32`；Map SHA `59690572e189d2ca4a5005ea0297c75622dca244112ac3747635d9fb16ac9519`，fixture SHA `060f511881cd2d5994afac7678222bca95f9239620884bf342bb8c054d4c06d1`。原始 fitted-map 运行及其 map/fixture SHA 保留在历史收据中，不再作为当前资格输入。

| 控制 | minus | plus | 目标 |
| --- | ---: | ---: | --- |
| crank inertia | 0.4858 | 0.2755 | high-slew high-band share |
| idle governor | 0.1454 | 0.0429 | idle recovery RMS |
| primary attenuation spread | 0.0210 | 0.0211 | early path balance |
| blower sideband mix | 0.2109 | 0.2347 | narrowband share |
| blower broadband mix | 0.0444 | 0.0458 | narrowband share |
| blower casing mix | 0.3560 | 0.4648 | narrowband share |
| boost attack | 0.0585 | 0.0323 | transition high-band share |
| boost release | 0.0412 | 0.0295 | transition high-band share |
| bypass threshold | 0.0211 | 0.0293 | bypass-window RMS |

The remaining seven controls (four afterfire and three monitor controls) also
passed bilateral finite/SHA/`>0.02` evidence; see the machine-readable artifact
for all 16 rows. This is software reachability only, not human preference,
R1 identity, OEM reproduction, calibration or Profile Freeze.

## Existing phase status

- Y2: committed synthetic Fourier-normalized fitted map, fail-closed loader; PASS.
- Y3: 720°/`4π` cycle-sync P4 and persistent equivalence; PASS.
- Y4: latch/re-arm, 120 ms tails and snapshot/replay; historical `80 passed, 1 skipped`; PASS.
- Y5: per-sample DC/dP, warmup, fractional delay and v3 migration; historical `43 passed`, no skip; PASS.
- Y6 v1: 154 synthetic PCM24 WAVs / 11 scenes / browser playback evidence; preserved unchanged. Because the fitted-map renderer inputs changed, any regenerated package must be a new `s12-stage-y-hellcat-layers-v2` directory; v2 has not been generated in this closure.
- Full S12: the earlier `1369 passed, 2 skipped` receipt at tested HEAD `a73322b1ceebe700fc97073cbf50cfd12b961bbf` is retained as historical and superseded by the canonical fixture-hash repair. One new complete S12 run is still required; its current receipt will be `tasks/reports/runtime/s12-stage-y/final_qualification/full_s12_final_receipt_v2.json`.

## Open-source method boundary

`docs/research/engine-audio-ecosystem/source_registry.json` contains 25 pinned
sources. `source_evidence_receipts.json` and
`source_coverage_matrix.json` bind each source to research-only,
`IMPLEMENTED_CLEAN_ROOM`, `REFERENCE_ONLY`, or `BLOCKED_BY_LICENSE` status.
Ignis has no tracked license and Markeasting's repository MIT license does not
clear individual audio rights; neither source or media is copied into S12.

## Next gate

Focused repository/Track-P/license checks and whole-branch review remain the
bounded verification scope. The next software action is the one complete S12
command on the canonical code HEAD, followed by a clean commit, push to the
integration PR, CI, and merge through that PR only if CI is green. Human
audition, legal synchronized R1, OEM/calibration and Profile Freeze remain
explicit external gates.
