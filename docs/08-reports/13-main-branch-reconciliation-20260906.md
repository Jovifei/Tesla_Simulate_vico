# 主分支合并与审查入口（2026-09-06）

## 用户要求与本次实际处理

本次按用户要求统一最近的开发历史到 main。合并不是重新启用被人耳否决的 Stage AE，也不是用旧分支覆盖最新 main。所有后续修复必须在本次合并提交之上继续。

已在远端建立回退引用：`archive/main-before-reconciliation-20260906`，指向原 main `f81d3a3aa1b32fcd35aa8b66a253492c70ed47b4`。不改写或删除历史。

## 已核实的分支关系

| 分支 | 本次检查的 HEAD | 处理 |
|---|---|---|
| main | f81d3a3aa1b32fcd35aa8b66a253492c70ed47b4 | 第一父提交；保留已被 Jovi 认为较相像的 EngineAcoustics 声音路径 |
| docs/full-technical-audit-20260905 | 96252ee178e49157e363f84d6a42fd9f04fd4ea1 | 已是原 main 祖先，不需要重复覆盖 |
| s12-stage-ad-closed-loop-calibration | 2045dfb21adb0a75fdfbad080817a5818a7f8227 | 与原 main 在243d926处分叉；声音代码已通过另一集成提交进入 main。本次通过 AE 父链记录其已处理历史 |
| s12-stage-ae-canonical-physical-convergence | cb033134e4d546b5c88b5990c75350f7be9fe771 | 合并历史，显式拒绝其默认 renderer/UI 替换；只复用独立 partitioned_convolver 数值工具 |
| s12-stage-ae-canonical-physical-convergence-copy | cb033134e4d546b5c88b5990c75350f7be9fe771 | 与 AE 同提交，无独有内容 |
| s12-stage-af-physical-closed-loop | a759a41a3b4ad41f58f3bafba9f27b100f8c8998 | 合入围绕现有 EngineAcoustics 的参数适配器、闭环、原工作台绑定及生成产物清理 |
| s12-stage-af-physical-closed-loop-copy | 8ae00a6eebc83ece2ee9ddfb4767366da58f571b | 已是 AF 祖先，无独有内容 |

这里的“合并”是经审查的多父提交与内容冲突解决，不是将每个旧分支的每个文件重新恢复。没有对几十条历史实验分支一律采用最新写入覆盖。

## 合并内容决定

合并树基于 AF 的 `c2323719aa161536d7642b0e30f1f845423b4696`，该树包含原 main 的成功声音代码。保留 `stage_ad/engine_sim_acoustics.py::EngineAcoustics`、`stage_ad/build_unified_dashboards.py`、原 HTML 模板、`review_packages/serve_dashboards.py`。

拒绝 AE 中将 EngineAcoustics 降为 teacher、将 Dashboard 默认改接 PersistentEventDomainEngine、另建试听 UI、用无 IR 默认配置代替已调好声音的内容。AE 人耳结论仍为 HUMAN_FAIL；合并历史不等于 HUMAN_PASS。

单独保留 AE 的 `partitioned_convolver.py`，放入 Stage AF。这是 FFTConvolver 架构启发的独立 Python 数值工具，不会默认替换声学模型。其完整流式调用需整块输入；Python 实现仍有分配，不宣称 Android 实时安全。

AF 已从当前树移除重复生成的 WAV/Base64 HTML 与历史大 ZIP，生成器、原服务台、文本证据保留。原试听内容仍可由回退引用恢复；不要在本地删除尚未备份的唯一声音资产。历史 Git 体积不会因为当前树删除而自动消失。

## 合并前真实验证状态

- AF 专用 CI 34013959532：SUCCESS。
- Stage-Y CI 34013959535：完整 Python 回归1434 passed、10 skipped、232 subtests passed；Track-P通过；整体失败在旧检查脚本读取不存在的 `executable_count` 字段。
- 后一工作流实际检出 PR merge ref d1fc7bd8703bf8fa3757f6c4c53797536f305c9e，不把其运行元数据误说成直接检出 a759。
- 后续修复应从真实 scorecard rows 验证执行证据，不能伪造 aggregate 字段或放宽门禁。

## 后续工作与资格

先读本次合并后的 main，再修点火相位、时间延迟、卷积裁切、换挡包络和评分盲区。默认保留原声音；修正使用可审计开关及独立候选目录。fit、render、dashboard 必须消费同一模式及最终参数。实际 IR 与真实参考 WAV 的本地试听尚未执行，不宣称声音更真实、Human PASS或OEM标定。

当前仍是声学算法阶段；最终是 App 采集速度/加速度、推导虚拟发动机状态、选择车型并实时播放。ESP32后置。