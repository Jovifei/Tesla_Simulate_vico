# Stage AF — 当前声音优化入口

当前以 `main=f81d3a3...` 的 Engine-Sim-inspired `EngineAcoustics` 为听感基线；Jovi 已实际试听判断方向明显正确。Stage AF 只围绕该 renderer 做 bounded negative feedback，不替换它。

先读：

1. `docs/knowledge/02-stage-af-current-handoff.md`
2. `docs/10-learning/02-engine-acoustic-physical-simulation-playbook.md`
3. `docs/07-debugging/02-acoustic-tuning-pitfalls-and-breakthroughs.md`
4. `docs/05-execution/04-stage-af-local-ai-handoff.md`
5. `docs/08-reports/12-stage-af-main-baseline-and-cleanup.md`
6. `docs/research/engine-audio-ecosystem/stage_af_sources.md`

本地工作台继续使用 `review_packages/serve_dashboards.py`，不开发新后台。
