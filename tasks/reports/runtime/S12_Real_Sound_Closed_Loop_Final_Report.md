# S12 真实声浪闭环总报告

状态：`WAITING_FOR_REAL_REFERENCE_DATA`

> 本报告是当前 HEAD 的等待态审计，不是“本地声浪与真实声浪比较、反馈和调优闭环已完成”的声明。

## 阶段状态

| 阶段 | 当前状态 | 已完成内容 | 未完成内容 |
| --- | --- | --- | --- |
| Q 真实参考 | `REAL_REFERENCE_DATASET_LIMITED` | 15 条候选和未登记媒体已登记，保留路径/SHA/格式/缺口 | 合法授权、R1 元数据和同步 RPM/state |
| R 差异基线 | `BLOCKED_REFERENCE_QUALIFICATION` | R1/R2 资格门、报告模板和 withheld 推荐 | 未运行合格真实比较 |
| S 反馈调音 | `WAITING_FOR_JOVI_HUMAN_FEEDBACK` | 中文听审合同和 SHA/file-ID 绑定合同 | 没有真实 Jovi 听审和调音轮次 |
| T Profile Candidate | `BLOCKED_PROFILE_CANDIDATE_NOT_READY` | Profile Candidate 阻断门和交接模板 | 没有候选参数包或产品交接 |

## 八车型与工况

当前八车型全部没有 R1 资格；已有文件只能作为未授权/未对齐候选，不能进入自动调参。

| 车型 | 已登记候选 | R1 | 可资格指标 |
| --- | ---: | ---: | --- |
| Ferrari 458 | 1 | 0 | 无；待授权和状态绑定 |
| Hellcat | 4 | 0 | 无；待授权和状态绑定 |
| RX-7 FD | 1 | 0 | 无；待授权和状态绑定 |
| Aventador LP700 | 1 | 0 | 无；待授权和状态绑定 |
| C63 W204 | 3 | 0 | 无；待授权和状态绑定 |
| GT-R R35 | 3 | 0 | 无；待授权和状态绑定 |
| LFA | 1 | 0 | 无；待授权和状态绑定 |
| Supra JZA80 | 1 | 0 | 无；待授权和状态绑定 |

已识别的工况提示包括 idle、steady/acceleration、full_pull、shift、lift/afterfire 等；当前窗口均为文件名或旧注释推断，未达到场景资格。

## 指标与人耳边界

- 阶次 / Order-RPM：`NOT_QUALIFIED`，没有同步 RPM。
- 频谱、响度、心理声学：当前没有授权 R2；不复用旧报告数字。
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
- 报告绑定代码提交：`05c6d956f706e1db702591d71ccb82a043642bfd`
- working tree dirty：`false`
- push：否
- merge：否
- PR：否

## 必须补齐的输入

1. 合法可使用的真实车辆原始录音；
2. 精确车型/配置/原厂状态、场景和麦克风位置；
3. 同步 RPM、Load/Throttle、Gear/shift、时间窗口；
4. 采样率、通道、设备和 AGC/后处理合同；
5. 真实 Jovi 中文听审结果及播放元数据。

所有产物继续声明：`synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。
