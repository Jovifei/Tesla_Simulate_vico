# S12 Stage F Human Audition Qualification and Profile Freeze Review

状态：`WAITING_FOR_JOVI_AUDITION`（首次交付后停止）

## 目标

修复 Stage E v2 的参数可达性、真实 A/B 文件和评分门禁缺口，生成 Stage F v3 双轮匿名盲听包。自动指标、人耳身份识别、Candidate 优先级和 Profile Freeze 审核保持独立证据层。

## 固定边界

- 仅修改离线 Track-S 声源候选、候选契约、盲听/评分/参考距离工具和报告。
- FVM、PTR core、Radiation Boundary、Runtime、Android、MATLAB、Simulink、Track-P guard、Stage-C 公共 LF/rumble/EQ、正式响度策略均冻结。
- Stage E Candidate v2 与试听包字节保留为 `HISTORICAL / UNSCORED`，不覆盖。
- 不下载参考音频，不删除清理对象，不 push、merge、rebase 或进入 main。

## 执行顺序

1. F0：建立独立 worktree，复核 HEAD、clean status 和 Stage E 证据 SHA。
2. F1：以 TDD 建立 Stage-F candidate schema、逐参数 reachability、pipeline order 和单车隔离。
3. F2：在 final PCM 域重算 idle/acceleration/afterfire reference distance；不足 30% 保持 PARTIAL。
4. F3：生成 v3 listener ZIP、sealed answer key、30 个匿名短片、6 个 60 秒 A/B 文件、预填表单和 SHA256SUMS。
5. F4：实现严格播放环境、答卷完整性、分轮 denominator、confusion、confidence/realism/artifact/A-B 门禁。
6. F5：首次执行硬停止于 `WAITING_FOR_JOVI_AUDITION`；收到真实答卷后最多 v3→v4→v5 三轮窄范围调音。
7. F6：只有自动和人耳门禁同时通过，才生成 `ProfileFreezeCandidate`；不得写 Approved 或进入 Simulink。
8. F7：跑全套回归、写报告、修复 Obsidian frontmatter 和状态冲突；仅本地提交。

## 验收状态

无完整 `blind_responses.csv`、`ab_responses.csv` 和 `playback_context.json` 时，不读取 sealed key、不生成 confusion matrix、不伪造人耳结果。

全部输出保持：`synthetic / uncalibrated / not OEM reproduction`。
