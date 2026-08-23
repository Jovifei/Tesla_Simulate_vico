# S12 v1.2 GT-R / Supra / LFA 模型与音频交付报告

更新日期：2026-08-24
范围：`gtr_r35_2007_stock`、`supra_jza80_rz_stock`、`lexus_lfa_stock`

## 交付边界

本轮新增三套独立 v1.2 source/identity profile、scenario profile 和 Simulink wrapper。
链路为：

`Vehicle Cycle → Engine Identity + Source Layers → frozen 4D-B radiation audio adapter → Stereo Renderer → PCM24/WAV`

全部参数与输出保持：`synthetic / uncalibrated / offline / not OEM clone`。
GT-R、Supra、LFA 的公开录音指标属于 R2/派生研究目标，不是 R1 OEM 标定数据。

## Simulink 证据

| Model | Cold Reload / model_check | Update / Active Compile | 90 s simulation |
|---|---|---|---|
| `S12_gtr_r35_2007_stock_v12.slx` | healthy | PASS | 4500 frames, `[4320000,2]`, clipping 0 |
| `S12_supra_jza80_rz_stock_v12.slx` | healthy | PASS | 4500 frames, `[4320000,2]`, clipping 0 |
| `S12_lexus_lfa_stock_v12.slx` | healthy | PASS | 4500 frames, `[4320000,2]`, clipping 0 |

Compiled dimensions are shared: cycle `[9,1]`, source `[960,1]`, radiation `[960]`, PCM `[960,2]`.
The accepted radiation package is consumed by SHA
`0ea36a3188869e503b48b7e0735bcf64d430abe4d2f6d28b49dcfe3c9cf70d4b` from source commit
`4afe65a67ed21822422f1eb6dbf43fdd627072d3`.

## r4 音频包

根目录：

`E:\Tesla_speed\tasks\reports\runtime\s12-engine-sound-v12\gtr-supra-lfa-v12-20260824-r4\`

每车包含 `full_drive_cycle.wav`、`idle.wav`、`acceleration.wav`、`deceleration.wav`、`afterfire.wav`、profile/scenario snapshot、metadata 与 `SHA256.txt`。

| Vehicle | Full WAV SHA-256 | Peak |
|---|---|---:|
| GT-R R35 | `cffeeb8562b7a2cc733dd92d01931ca15e360e3fc79fc636c900774c38a75377` | 0.07960 |
| Supra JZA80 | `9b0aca1322b25018a0b0deeb6058c3e270dabc69236b7eb10008ab0ed2f113dc` | 0.03597 |
| Lexus LFA | `3a56da8491fdb7b90d7ca6970d10a2e97fe23368e24987ede3e0dbf2f71dd45c` | 0.04915 |

第二次完整重建 `gtr-supra-lfa-v12-20260824-r4-repeat` 的三车 SHA 与上表逐字一致。
所有 WAV 均为 48 kHz、24-bit、stereo、90.0 s、finite、clipping=0。

## 参考指标反馈

以下是 r4 与仓库 R2 派生目标的加速 band-share/idle centroid 对比；这些指标用于方向反馈，不构成 OEM 真实性证明。

| Vehicle | Accel band shares (20–250 / 250–1000 / 1000–4000 / 4000–12000 Hz) | Idle centroid |
|---|---|---:|
| GT-R | 0.1219 / 0.6971 / 0.1671 / 0.0108 | 916.8 Hz |
| Supra | 0.4679 / 0.4901 / 0.0321 / 0.0071 | 1333.0 Hz |
| LFA | 0.0005 / 0.4582 / 0.5413 / 0.0000 | 180.0 Hz |

方向性修复已经体现在三轮反馈中：GT-R 涡轮高频被压低并保留中频 racy；Supra 增加低频 I6 主体并削弱高阶涡轮；LFA 把 30 阶高频 scream 移向较低阶中频。剩余误差说明 v1.2 仍需真实 R1、曲轴同步特征和人工盲听才能继续校准，当前不宣称自动门禁全通过。

## 回归证据

- MATLAB source/adapter/profile regression：`12/12 PASS`。
- MATLAB Code Analyzer：本轮修改的 7 个 `.m` 文件 `0 issue`。
- Python v1.2 reference/source/pilot contracts：`35/35 PASS`。
- Python compileall：PASS。
- Track-P 冻结断言：177 个冻结文件、2 个冻结符号，未修改；两个 v1.2 Track-S 路径有精确 allowlist 豁免。

## 已知限制

- Radiation 部分是已接受 4D-B 边界包的连续音频适配器，不是完整 FVM/PTR 管网仿真。
- 没有 R1 stock/exterior-rear 参考录音，因此没有 OEM calibration、approved profile 或 human PASS。
- 没有进入 Android、CAN、OBD、ESP32、I2S 或实时 DSP。
