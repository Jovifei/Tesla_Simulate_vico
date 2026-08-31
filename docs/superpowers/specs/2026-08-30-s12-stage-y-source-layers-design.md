# S12 Stage Y — 声源层落地与参数可达性设计规格

日期: 2026-08-30
状态: 待 Jovi 审阅书面 spec（各设计段已口头批准；尚未进入 implementation plan）
基线: Stage X `f1714b969ecd033e991e04cfc59df06a05e3685a`（`agent/s12-stage-x-r2-engineering-selection`）
Stage W 远端（只读参考，禁止 force-push）: `7d4e49b52b73696af703a1380d83663208c5a897`

本文是 Stage Y 的设计规格，不是实现计划。实现计划在本 spec 获批后由 writing-plans 另写。

## 1. 问题

Stage W 建成了可持久的事件域引擎、frozen PTR 接入和 bake-off 渲染。Stage X 拆开了工程预选与正式资格门，并对 Hellcat 做了搜索。结果是：硬门通过，软门失败，`NO_MEASURABLE_IMPROVEMENT_AFTER_REDESIGN`。27 个搜索参数里 16 个不可达。P4 仍是占位。`TimbreMap4D.default()` 是解析公式，不是从循环提取的谐波地图。开源研究笔记覆盖面高，运行时方法落地约 25–35%。听感仍像合成器。

根因不是 Prompt 不够长，也不是缺一次 64 点搜索，而是缺的声源层没有进渲染器，且现有旋钮有一半拧了不响。

## 2. 目标与非目标

### 2.1 本轮目标（必须）

1. 把 16 个不可达参数修到真正改变 Hellcat post-PTR PCM 和声明的目标指标。
2. 按已研究项目做 clean-room 方法迁移，落地三层声源：谐波地图、循环级重合成、工况瞬态。
3. 在上述层之后补 ignis / Engine-Sim 思路的 DC、压力导数、delay-line warmup，不拷贝其 C++。
4. 用合成发动机循环 fixture 跑通算法与架构；真录音以后再填，不阻塞本轮。
5. Hellcat 作为唯一垂直切片，产出可试听的 Parent vs 分层 Candidate 包。
6. 在层落地后做一次有界听感优化，但不以 15% 工程预选门作为通过条件。

### 2.2 本轮明确不做

Ferrari 458 与 RX-7 迁移；R1 正式资格；Profile Freeze；OEM 匹配宣称；把 ENSIM4 CFD 放进 Runtime；修改 FVM / HLLC / MUSCL / SSP-RK3 / positivity；修改冻结辐射包数学或 `RuntimePtrAdapter` 核心；修改 Track-P MATLAB/Simulink、Runtime 协议、Android、ESP32；把 Engine-Sim / ignis / VNS / FiveM 源码或 GTA 音频提交进 Git；使用 `rdoerfler/ptr-model` 的 CC BY-NC 权重或数据；合入 main；force-push Stage W。

### 2.3 本轮可以宣称 / 不可以宣称

可以宣称：层已存在且被消费；16 个旋钮可达；Hellcat fixture 试听包可播放；Parent SHA ≠ Candidate SHA。

不可以宣称：声音已通过正式工程预选；OEM / 标定 / 人耳 PASS；R1 资格；Profile 冻结。

## 3. 已锁定决策

- 切分：一份 Stage Y spec，内部强制分阶段，不是两个独立 sub-project。
- 顺序：Y1 可达性 → Y2 谐波地图 → Y3 循环重合成 → Y4 工况瞬态 → Y5 dP/DC/warmup → Y6 Hellcat 试听。
- 录音：合成循环 fixture。现有 Hellcat R2 仅作诊断对照，不是拟合老师，也不是正式资格老师。
- 15% 中位改善：只写入诊断 JSON，不是阶段通过条件。
- 物理链：Y5 进入同一 spec，不降级为纯研究笔记。
- 基线策略：保留 `PersistentEventDomainEngine`，在其上补层，不重写整个声源。

## 4. 架构

### 4.1 信号链

```
VehicleState 20 ms block (RPM, load, throttle, gear)
        → PersistentEventDomainEngine (phase, events, paths, collector)
        → Y2 HarmonicTimbreMap (loaded table, not formula default)
        → Y3 cycle-sync P4 grains on the same crank clock (mix, not a second clock)
        → Y4 state transients (tip-in / lift / shift / BOV) after collector
        → Y5 DC + dP + delay-line warmup on collector pressure (or equivalent)
        → Frozen RuntimePtrAdapter / Radiation (unchanged math)
        → post-PTR raw PCM
        → audition monitor (policy-tunable, isolated from raw)
```

Y1 不新增声源层，只修复上述链中已有参数的消费与可观测性。

### 4.2 分支与隔离

- 新分支: `agent/s12-stage-y-source-layers-and-reachability`
- 新 worktree: `E:\Tesla_speed\worktrees\s12-stage-y-source-layers`
- 从 Stage X exact commit `f1714b969ecd033e991e04cfc59df06a05e3685a` 创建
- 外部研究 clone: `E:\Tesla_speed\research\engine-audio-ecosystem\`（已有 engine-sim / ensim4；本轮补 ignis 与 markeasting checkout，只读 LICENSE 后记入 registry）
- 默认不 push Stage Y，除非后续明确授权；禁止 push/force-push Stage W；禁止 merge main；禁止创建 PR

### 4.3 方法到层的映射（clean-room）

| 层 | 借鉴来源 | 允许落地 | 禁止 |
|---|---|---|---|
| Y1 可达性 | Stage X 探针本身 | 接线、状态、指标移动 | 用 master gain 冒充可达 |
| Y2 谐波地图 | Fubos 工作流、order-synthesis 论文 | fixture → RPM×order 表 → 运行时查表 | 商业 `.eng`、未授权录音 |
| Y3 P4 | REV / PSOLA / OLA 思路 | 循环对齐 grain、共享曲轴时钟、块连续 | 版权拉转录音进 Git |
| Y4 瞬态 | VNS / Igniter 公开工作流 | 状态层、equal-power crossfade、迟滞、one-shot stem | GTA/FiveM 资产、无 LICENSE 的 granular 源码 |
| Y5 音频链 | Engine-Sim / ignis 公开方法 | DC、dP、delay-line warmup | 拷贝 C++、`.mr`、IR 资产 |
| 离线教师 | ENSIM4 | 可选对照笔记；不进 Runtime | CFD 内核进 Android/ESP32 |
| PTR 论文模型 | rdoerfler/ptr-model | 脉冲包络概念（已有） | CC BY-NC 代码/权重 |

`yoshiomiyamae/engine-sound-simulator` 仓库不存在，不得再列入来源。

## 5. 阶段规格

每一阶段通过条件包含：实际 WAV 渲染、重开校验、SHA 与基线不同、阶段收据 JSON、focused tests 绿。禁止阶段输出仅为 markdown。

禁止结束状态：`PLAN_READY`、`RESEARCH_COMPLETE_ONLY`、`SPECIFICATIONS_ONLY_NOT_RENDERED`、`WAITING_FOR_R1`、`ONE_PHASE_COMPLETE_WHAT_NEXT`。

缺少 R1 只保持 `FORMAL_R1_REFERENCE_MISSING`，不停止 Y1–Y6。

### 5.1 Y1 — 参数可达性

对象（Stage X `parameter_reachability.json` 中 `PARAMETER_NOT_REACHABLE`）：

`crank_inertia`、`idle_governor`、`primary_attenuation_spread`、`blower_sideband_mix`、`blower_broadband_mix`、`blower_casing_mix`、`boost_attack`、`boost_release`、`bypass_threshold`、`afterfire_reservoir_rate`、`afterfire_ignition_delay`、`afterfire_location_mix`、`afterfire_energy`、`monitor_attack`、`monitor_release`、`monitor_max_makeup`

规则：每个参数在其声明的 architecture / scenes / stem 上，基线与 ±delta 必须同时满足：post-PTR（monitor 类参数则 monitor stem）字节或 SHA 不同；声明的 target metric 移动超过现有探针容差 0.02；不得仅改变总音量使所有频带同比例缩放。不合格回火工况 afterfire 计数保持 0。

探针必须使用每个参数在 `search_parameters.py` 里声明的 architecture / scenes / stem，禁止再用整次运行的默认 P2H 去测 P3 专用旋钮。

Y1 通过条件：这 16 个参数在各自声明的探针上全部变为 `PARAMETER_REACHABLE`。允许且仅允许下列延期：若某个参数的唯一消费者是 Y2 才存在的拟合地图（而非当前已有的 `timbre_mixes` 字段），则标 `DEFERRED_TO_Y2`，并成为 Y2 阶段门的一部分。Afterfire 与 monitor 已在 Stage W 引擎中存在，不得延期到 Y2。inertia / governor 必须在 Y1 内接到相位/PCM；若指标不敏感，改探针到能看见 cycle ripple 的量，而不是把参数标掉了事。

### 5.2 Y2 — HarmonicTimbreMap

离线：`harmonic_map_fit.py` 读取合成循环 fixture（多 RPM 稳态循环，无第三方 PCM），提取各阶幅值、可选相位、宽带包络，写出 git-safe JSON。

运行时：Hellcat 加载该 JSON。`TimbreMap4D.default()` 公式不得再作为 Hellcat 运行时音色表。地图开 vs 关必须 SHA 不同。地图文件损坏或缺失：拒绝初始化，不得静默退回公式。Y1 标为 `DEFERRED_TO_Y2` 的 timbre 类参数必须在本阶段变为 `PARAMETER_REACHABLE`。

### 5.3 Y3 — Cycle-sync P4

`cycle_sync_resynth.py` 是真正的 renderer。Fixture grain 按曲轴相位索引，与事件域共用 `PersistentEventDomainEngine` 的 phase / omega，禁止第二套时钟。OLA 保证 20 ms 块边界无 click（沿用 Stage W click 合同）。`bakeoff.py` 中 P4 不得再为 `REFERENCE_RECORDING_RIGHTS_PENDING` 占位。无权利录音时输入只能是合成 fixture。

### 5.4 Y4 — 工况瞬态

`state_transients.py` 提供 tip-in、收油、换挡、BOV 的独立 stem，在 collector 之后、PTR 之前混合。equal-power crossfade。状态迟滞，避免节气门噪声导致层抖动。合格 vs 不合格回火：路径、到达时间、SHA 必须不同；错误工况 afterfire 计数为 0。不得在最终 PCM 上直接叠加 pop。

### 5.5 Y5 — DC / dP / warmup

`audio_chain_dp.py`：去直流、压力（或压力导数）混合、delay-line 在开始出声前进入热机状态。对照 ignis / Engine-Sim 的公开音频链描述做 clean-room。消融：链路开 vs 关 SHA 不同。3000×20 ms 块连续与一次性 60 s 在已声明浮点容差内等价。仓库树不得出现 Engine-Sim 或 ignis 源文件。

### 5.6 Y6 — Hellcat 试听与有界优化

包路径：`E:\Tesla_speed\review_packages\s12-stage-y-hellcat-layers-v1\`

每场景至少：A Parent；B Y1 后事件域；C +地图；D +P4；E +瞬态；F +dP 链；G 选定混合的 monitor。

场景：热怠速、1200/2000/3000 rpm 稳态、tip-in、全油、换挡、收油、合格回火、不合格回火、怠速回落。

两页：Timbre Review（响度匹配）与 Dynamic Review（保留 idle→WOT）。中文听审说明。提交门：可播放、时长大于 0、SHA 匹配、必需文件存在、Parent SHA ≠ Candidate SHA。包内无第三方版权 PCM。

听感优化：一次有界 Parent vs 最终混合对比，禁止 64 点自动搜索。15% 指标只作诊断。人耳否决某层不撤销该层“已落地”的工程状态，只记录 `HUMAN_LAYER_NOT_ACCEPTED`。

## 6. 模块与文件

允许修改：

- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/persistent_engine.py`（接线与状态，不改成每块重建）
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/timbre_map.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_w/bakeoff.py`
- `tools/sound_sim/s12/acoustic_identity_v015/stage_x/search_parameters.py` 及可达性驱动
- 新建 `.../stage_y/harmonic_map_fit.py`
- 新建 `.../stage_y/cycle_sync_resynth.py`
- 新建 `.../stage_y/state_transients.py`
- 新建 `.../stage_y/audio_chain_dp.py`
- 新建 `.../stage_y` 测试与 `tasks/reports/runtime/s12-stage-y/` 状态机
- Obsidian 托管区块与 `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/`
- `docs/research/engine-audio-ecosystem/source_registry.json`

冻结：见第 2.2 节。`legacy_v015` 默认输出必须保持不变（有回归测试证明）。

## 7. 数据合同

### 7.1 HarmonicTimbreMap JSON

必须包含：`schema`、`vehicle_id=hellcat`、`source=synthetic_fixture`、`rpm_axis`、`order_axis`、`amplitude`、可选 `phase` 与 `broadband_envelope`、`fixture_sha256`、`created_from_commit`。不得内嵌 PCM 样点。

### 7.2 Fixture

合成、确定性、可 SHA。存放在测试/runtime 路径，不冒充 R1/R2 真车录音。标记 `FIXTURE_ONLY`、`NOT_TUNING_AUTHORITY`、`NOT_OEM`。

### 7.3 执行状态机

`tasks/reports/runtime/s12-stage-y/execution_state.json` 记录 Y1–Y6 的 `NOT_STARTED|IN_PROGRESS|PASS|FAIL_REPAIRING`、commit、evidence。中断后从该文件恢复，禁止从 Stage V 重开。

## 8. 错误与非阻塞

硬阻塞：Stage X 基线 commit 不可得且无本地副本；Git 对象损坏；磁盘不可写；冻结 Track-P 基线被不可恢复破坏。

非阻塞：无 R1；无新的 Jovi 听审；MATLAB 未开；某个 GitHub 项目构建失败；Obsidian 路径歧义（完成仓库镜像并记录）；Y6 人耳不喜欢某一层。

外部构建失败：保存日志，继续读源码做 clean-room。命令超时：查 PID/日志/产物，禁止无证据重复启动。超过 2 分钟的命令必须写 `tasks/reports/runtime/s12-stage-y/logs/`。

## 9. 测试

修改期间：只跑 Stage Y focused 与被改模块测试。

阶段结束：Stage Y focused + Stage V 事件域回归 + Stage W persistent/bakeoff 中与声源相关的测试 + Track-P 守卫（若触及冻结树则必须）。

最终 HEAD 只跑一次：

```
python -m pytest tools/sound_sim/s12/tests tools/sound_sim/s12/acoustic_identity_v015/tests -q
```

另加：compileall、JSON finite、WAV reopen、SHA manifest、试听包校验、许可证与外部媒体扫描、`git diff --check`、Obsidian 链接检查（仓库镜像）。

收据字段：command、started_at、ended_at、exit_code、pass/fail、log SHA、HEAD SHA。禁止引用旧的 1015 或 1205 作为本轮证据。

## 10. 知识库

更新 `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/`：Stage Y 状态页、ignis / markeasting 来源页、方法到文件的溯源。托管区块 `<!-- S12-STAGE-Y:AUTO:BEGIN -->` 不覆盖用户正文。个人 Obsidian Vault 仅在路径明确时同步；歧义则只完成仓库镜像。

## 11. 成功状态

允许向 Jovi 汇报的成功态：

`STAGE_Y_LAYERS_LANDED`  
`HELLCAT_REACHABILITY_REPAIRED`  
`P4_RENDERER_EXISTS`  
`HARMONIC_MAP_CONSUMED`  
`TRANSIENTS_LANDED`  
`DP_CHAIN_LANDED`  
`WAITING_FOR_JOVI_LAYER_AUDITION`  
`FORMAL_R1_QUALIFICATION_PENDING`  
`NOT_PROFILE_FREEZE_READY`

无听感改善时仍可关闭工程环，但必须同时带：

`LAYERS_LANDED_HUMAN_NOT_ACCEPTED` 或等价层级记录，且不得把“未听”写成“已改善”。

## 12. 设计选择记录

未采用“只修可达性再调 EQ”：Stage X 已证明残缺旋钮搜索不能解决合成器味，且目标包含声源层落地。

未采用“用 ignis 重写整个引擎”：会丢弃 Stage W/X 的持久状态与 frozen PTR 合同，超出本轮范围。

采用“现有事件域上分阶段补层”：保住已验证的 20 ms 流式与 PTR 接入，同时把 Fubos / REV / VNS / ignis 方法变成可运行代码。
