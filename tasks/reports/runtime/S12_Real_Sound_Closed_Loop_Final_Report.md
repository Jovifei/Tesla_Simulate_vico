# S12 真实声浪闭环总报告

状态：`R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED / WAITING_FOR_JOVI_HUMAN_FEEDBACK`

> 本报告是当前 HEAD 的等待态审计，不是“本地声浪与真实声浪比较、反馈和调优闭环已完成”的声明。

## 阶段状态

| 阶段 | 当前状态 | 已完成内容 | 未完成内容 |
| --- | --- | --- | --- |
| Q 真实参考 | `REAL_REFERENCE_DATASET_LIMITED` | 原有目录审计加 3 条明确 CC/CC0 许可的 R2 参考；RX-7 仅新增 1 条 R3 旋转机械演示 | R1 元数据和同步 RPM/state |
| R 差异基线 | `R2_LIMITED_COMPARISON_COMPLETE / R1_BLOCKED` | Ferrari 458、Hellcat、Supra 已完成未增益分析信号的 R2 频谱/响度/心理声学相对比较；R1 SHA-bound MATLAB/MoSQITo 输入准备仍在 | R1 阶次资格、自动调参、真实人耳反馈 |
| S 反馈调音 | `WAITING_FOR_JOVI_HUMAN_FEEDBACK` | 中文听审合同和 SHA/file-ID 绑定合同 | 没有真实 Jovi 听审和调音轮次 |
| T Profile Candidate | `BLOCKED_PROFILE_CANDIDATE_NOT_READY` | Profile Candidate 阻断门和交接模板 | 没有候选参数包或产品交接 |

## 八车型与工况

当前八车型全部没有 R1 资格；已有文件只能作为未授权/未对齐候选，不能进入自动调参。

| 车型 | 已登记候选 | R1 | 可资格指标 |
| --- | ---: | ---: | --- |
| 法拉利 458 | 2 | 0 | R2 频谱/响度/心理声学；无阶次 |
| 道奇 Hellcat | 5 | 0 | R2 频谱/响度/心理声学；无阶次 |
| 马自达 RX-7 FD | 2 | 0 | R3 定性旋转纹理；无 R2/R1 |
| 兰博基尼 Aventador LP700 | 1 | 0 | 无；待授权和状态绑定 |
| 奔驰 C63 W204 | 3 | 0 | 无；待授权和状态绑定 |
| 日产 GT-R R35 | 3 | 0 | 无；待授权和状态绑定 |
| 雷克萨斯 LFA | 1 | 0 | 无；待授权和状态绑定 |
| 丰田 Supra JZA80 | 2 | 0 | R2 频谱/响度/心理声学；无阶次，代际未核实 |

已识别的工况提示包括 idle、steady/acceleration、full_pull、shift、lift/afterfire 等；当前窗口均为文件名或旧注释推断，未达到场景资格。

## 指标与人耳边界

- 阶次 / Order-RPM：`NOT_QUALIFIED`，所有新增公开素材都没有同步 RPM。
- 频谱、响度、心理声学：Ferrari 458、Hellcat、Supra 均只有 R2 相对数字域结果；不输出真实性百分比，不复用旧报告数字。
- 瞬态：没有同步 Gear/shift/state；不进入自动门。
- 人耳：真实 Jovi 反馈行数为 0；Stage P fixture 不算人耳反馈。
- 真实性百分比：禁止输出。

## 调音与交接

- 调音轮次：0。
- 车型 source/profile 参数修改：0。
- `approved_profile_candidate/`：未生成。
- Profile Freeze：未授权。
- Simulink、Runtime、Android、ESP32、CAN、实车部署：未进入。
- Track-P：按边界未修改。

## 当前提交与 Git 状态

- 分支：`agent/s12-stage-q-real-reference-calibration`
- 报告绑定提交：`770149c`（本轮修正三条 R2 口径、检索边界和任务接力记录）；此前 R2 公开许可素材与差异报告提交为 `1a8dc38`。
- working tree dirty：`false`（本次绑定前的干净提交）
- push：是
- merge：否
- PR：否

## 必须补齐的输入

1. 三个锚点的 R1 真实车辆原始录音及同步 RPM、Load/Throttle、Gear/shift；
2. 精确车型/配置/原厂状态、场景、麦克风位置和 AGC/后处理合同；
3. 真实 Jovi 中文听审结果及播放元数据；R2 结果不能替代 R1 或人耳反馈。

本轮 R2 结果：`tasks/reports/runtime/s12-stage-r-real-sound-difference/web-authorized-20260822/`；原始媒体仅存于 `E:\Claude_allow\Download\s12-web-authorized-20260822`，Git 只保存许可、路径和 SHA-256。

所有产物继续声明：`synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。
