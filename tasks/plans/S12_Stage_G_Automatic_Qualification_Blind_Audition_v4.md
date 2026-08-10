# S12 Stage G 自动资格债务关闭、盲听 v4 与 Profile Freeze Review

状态：`IN_PROGRESS`（首次执行必须在生成 v4 包后停止于 `WAITING_FOR_JOVI_AUDITION`）

## 约束

- 基线：Stage F `e38fe62f423b1fb220e9daedf5f4ef291bcc5849`。
- 工作树：`E:/Tesla_speed/worktrees/s12-stage-g-qualification-closure`。
- 只修改离线 Track-S 候选、参考分析、试听封装、评分与文档。
- 不修改 FVM、PTR core、Radiation、Runtime、Android、MATLAB、Simulink、Stage C 公共层或 Stage F 历史字节。
- 不下载新音频，不 push、merge、rebase，不删除清理清单中的任何文件。
- 所有声学结论保持 `synthetic / uncalibrated / not OEM reproduction`。

## 阶段

- [ ] G0：冻结基线、包和 Obsidian SHA，建立任务账本与独立工作树证据。
- [ ] G1：实现状态专属 reference target loader，拒绝 fallback/zero-fill/renormalize。
- [ ] G2：生成带明确 idle/acceleration/afterfire 窗口的最终 PCM reference evidence。
- [ ] G3：建立 Stage G candidate schema、逐参数可达性诊断与 v4 candidates。
- [ ] G4：执行 final-PCM reference-distance、identity 与三锚点自动门禁；失败保持 PARTIAL。
- [ ] G5：实现严格双轮评分器，分轮/分车/分场景输出完整人耳门禁。
- [ ] G6：生成匿名 30 题、三组 60 秒 A/B、sealed key、预填表和 SHA 清单。
- [ ] G7：首次生成后停止等待 Jovi；仅收到真实答卷后最多 v4→v5→v6 窄范围迭代并生成 Freeze Candidate。
- [ ] G8：运行完整验证、生成报告、同步 Obsidian、只做本地提交。

## 验收状态

首次交付只能是：`WAITING_FOR_JOVI_AUDITION`，或因自动门禁失败而附带 `PARTIAL / AUTOMATED_GATE_FAIL`。
没有完整答卷不得读 sealed key、生成 confusion matrix、声称 Human PASS 或进入 Simulink。

