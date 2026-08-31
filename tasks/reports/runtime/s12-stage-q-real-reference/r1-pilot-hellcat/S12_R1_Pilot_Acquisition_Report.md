# S12 R1 Pilot Acquisition Report

状态：`WAITING_FOR_R1_PILOT_DELIVERY`

试点记录：`hellcat_full_pull_01`；车型：`hellcat`。

## 当前门禁

- `delivery`：`MISSING`

## 保护边界

原始 WAV/FLAC、视频、PCM 和状态 CSV/JSON 只允许留在 E:\Claude_allow\Download 外部目录；本报告只写路径、SHA、授权范围和验证结果，不复制原始媒体。

没有通过 rights、SHA、时间同步和 raw_audio_intake 四个门之前，不运行 MATLAB rpmordermap/ordertrack/orderspectrum，不运行 Comparator，不生成数值参数建议，不修改声源。

## 收到真实文件后的顺序

raw_audio_intake → Stage Q canonical merge → 状态窗口绑定 → MATLAB 阶次/心理声学 → Comparator 差异报告 → 中文 A/B → 一车一问题一参数组有界调音 → 回归 → 第二轮 A/B。
