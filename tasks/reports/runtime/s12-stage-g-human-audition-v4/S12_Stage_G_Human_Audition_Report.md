# S12 Stage G — Automatic Qualification and Blind Audition v4

## 状态

```text
AUTOMATIC QUALIFICATION: PARTIAL / AUTOMATED_GATE_FAIL
HUMAN AUDITION: WAITING_FOR_JOVI_AUDITION
PROFILE FREEZE: NOT_PERFORMED / WAITING_FOR_JOVI_AUDITION
```

本报告的证据快照来自本地分支 `agent/s12-stage-g-qualification-closure`，基线为
`e38fe62f423b1fb220e9daedf5f4ef291bcc5849`；代码证据提交为 `dd7bc41`，当前文档交接提交为
`ed82694`（后续若仅更新本报告，Git tip 会相应前移）。本轮禁止 push、merge、rebase、main、
Simulink、Runtime、Android 和任何冻结 Track-P 文件修改。

## 已完成

- 为 Ferrari 458、Hellcat、RX-7 FD 建立严格的 Stage-G candidate schema、loader 和 renderer。
- `candidate=None` 保持 Stage-C `_render_stateful` 路径；候选 overlay、具名瞬态整形均在公共 Pre-PTR EQ 前。
- 每个公开参数做独立确定性扰动；10/10、10/10、11/11 参数分别被实际消费，`unused=[]`，证据见 `stage_g_parameter_reachability.json`。
- 用同一连续 60 秒 trace 生成 labelled final-PCM evidence，窗口固定为 idle `0–8 s`、acceleration `8–26 s`、afterfire/lift `36–46 s`，只施加一次 whole-cycle loudness gain。
- 生成 `S12_Blind_Audition_Package_v4`：30 个匿名 8 秒短片、6 个真实 60 秒匿名 A/B 文件、预填 30 行 blind 表和 3 行 A/B 表、独立 answer-key ZIP、SHA256 清单。
- listener ZIP 防泄漏扫描：车型名、baseline/candidate、seed、source hash、private answer token 均为 0；密封答案内容未读取。

## 自动参考距离结果

比较域是最终 PCM，四频段为 20–250、250–1000、1–4k、4–12k Hz：

```text
eligible states: 9/9 available
mean improvement: -0.00245936826038626 (-0.2459%)
no state worse than 10%: true
mean improvement >= 30%: false
```

各状态改善率：

| 车型/状态 | improvement |
|---|---:|
| Ferrari idle | +0.4652% |
| Ferrari acceleration | -0.5673% |
| Ferrari afterfire | -0.1105% |
| Hellcat idle | ~0% |
| Hellcat acceleration | +0.2650% |
| Hellcat afterfire | -0.4039% |
| RX-7 idle | -0.0652% |
| RX-7 acceleration | -1.7984% |
| RX-7 afterfire | +0.0017% |

因此没有降低 30% 阈值、没有改公式、没有用参考 RMS/LUFS 投机，自动状态必须保持 `PARTIAL`。

## 管线与冻结边界

```text
Independent Source
→ Idle Dynamics
→ Deterministic Afterfire
→ Low-Frequency Body
→ Exhaust Rumble
→ Shift Dynamics
→ Named Transient Peak Shaping
→ Common Pre-PTR Equalization
→ Frozen PTR
→ Edge Fade
→ One Fixed Whole-Cycle Gain
→ PCM24
```

Stage G 只扩展离线 Track-S candidate、reference evidence、package 和 scoring 工具。FVM、PTR core、Radiation Boundary、Runtime、Android、MATLAB、Simulink、Track-P guard/baseline/allowlist 均未改动。

## 测试证据

- Stage-G focused（不含 package contract）：17 passed。
- Stage-G package contract：2 passed。
- Stage-C realism：9 passed。
- Identity：58 passed / 78 subtests passed。
- Track-P guard：21/21 passed；独立 `assert_track_p_unchanged.py` 报告 180 个冻结文件和 2 个冻结符号摘要匹配。
- 全套 `tools/sound_sim/s12/tests` + `acoustic_identity_v015/tests`：474 passed / 232 subtests，耗时 664.83 s。
- `compileall`、`git diff --check`：PASS。
- `verify_remaining_vehicles.py` 对非锚点车型的旧健康阈值仍输出 informational FAIL；这不是 Stage-G 三锚点门禁，本轮没有篡改其阈值。

## 人耳硬停止

当前没有 Jovi 的真实答卷、播放环境或 A/B 偏好，因此：

- 不读取 sealed answer key；
- 不生成 confusion matrix；
- 不生成虚构结果；
- 不创建 ProfileFreezeCandidate；
- 不声称 Human PASS、Approved、OEM reproduction 或 calibrated。

请只返回以下三份文件后再进入评分：

```text
listener/blind_responses.csv
listener/ab_responses.csv
listener/playback_context.json
```

下一阶段最多执行 v4→v5→v6 三轮窄范围候选迭代；每次只修改失败车型，另两车 PCM SHA 必须保持不变。只有自动门禁和 Jovi 单听者人耳门禁同时通过，才进入 `PROFILE_FREEZE_REVIEW_PENDING`。

## 限制与声明

所有声源、候选参数和目标比较均为 `synthetic / uncalibrated / not OEM reproduction`。自动测试证明代码健康、确定性和身份可分，不证明真实车辆复刻；盲听身份识别与“比 Stage C 更真实”是两个独立门禁。

## Obsidian 影子知识库同步

Stage-G 知识库更新已由独立受限任务完成并校验：8/8 YAML 页面通过、24/24 内部链接解析、0 broken links。最终页面 SHA-256 摘要：项目概览 `30560129879d468114d44f1e1f21af745c7023747651a94bf331bd842bc05af2`、总体计划 `2c1af32a0486efc091ad34289a2757597254a7197df9cd47e15c77f8af91cadb`、当前进度（追加最终快照后）`30d21a676654b3dffe33b62fb97f82b76b868d1bca8e34ea527867320d4dab93`、工作流 `d084c78041dd1a197ffbe9110e0756320f12346c3a716b2064512cb243b26911`、索引 `3fd1c241990a754d2f205045e612632931f151dfe85423129d3ed810f4415be3`、技术事实 `64516bb5d13cb35a569ebc1375e8ca4c158721da9b13404efb0f25725b2c640b`、Stage-F 历史 `1e025e9260f676dd31293f1b3a614c3365ea47b65c7f0fc3504707a791999bdd`、Stage-G 新页（追加最终快照后）`a7e27c349c0099d77009bb79869b794ba90e7da796811895bb1f753acb098afe`。
