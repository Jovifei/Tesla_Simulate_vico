# Stage AF — 当前声音优化入口

当前以最新 `origin/main` 中保留的 `EngineAcoustics` 为声音 authority；其已试听过的好声音 lineage 根植于 `f81d3a3`，但动态 SHA 必须现场读取。Stage AF 只围绕该 renderer 做 bounded negative feedback，不替换它。

先读：

1. `docs/knowledge/02-stage-af-current-handoff.md`
2. `docs/10-learning/02-engine-acoustic-physical-simulation-playbook.md`
3. `docs/07-debugging/02-acoustic-tuning-pitfalls-and-breakthroughs.md`
4. `docs/05-execution/04-stage-af-local-ai-handoff.md`
5. `docs/08-reports/14-stage-af-numerical-fixes-and-review-server-20260906.md`
6. `docs/research/engine-audio-ecosystem/stage_af_sources.md`

本地工作台继续使用 `review_packages/serve_dashboards.py`，不开发新后台。H0/H1/H2 数值旗标、IR/Reference provenance、fit/render 一致性和大 HTML 并发刷新规则以 05-execution runbook 与最新 report 为准。
