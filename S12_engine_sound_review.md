# S12 Engine Sound Review

- 审核日期：2026-07-23
- 被审计提交：`5f8cd40471e0f4fe2823628fc8161f6bcc142477`
- 对照物理基线：`c79c24796e77c4ef26eeeb4f457431311473c4e7`
- 审核范围：`tools/sound_sim/s12/acoustic_demo/`、对应 Python 测试及生成的离线 demo。
- 总结：**FAIL**。可重复性、削波、DC offset 和输出标签通过；但新增 PTR、参数来源清单不完整，以及负载变化的连续性不通过。

## 1. 物理边界

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| FVM | PASS | `git diff --name-status c79c247..5f8cd40` 未列出 FVM 源、模型或基准文件。 |
| Radiation boundary | PASS | 未修改既有 radiation boundary/package；新代码只读取 accepted `sprint-4d-b/radiation-boundary-package.json`，并校验其来源提交为 `4afe65a…`. |
| SSP-RK3 | PASS | 差异中没有 SSP-RK3 源、模型或测试文件。 |
| PTR | FAIL | 新增 `acoustic_demo/s12_ptr_network.py`，实现了新的 PTR delay/loss/Tustin transport。它没有修改已验收 radiation package，但按“PTR 不得修改”的字面门禁，新增 PTR 也不合格。 |

## 2. 参数真实性

- **未发现 synthetic 伪装为 OEM：PASS。** `s12_engine_source.py`、`s12_operating_points.py` 及 demo metadata 都明确使用 `synthetic`、`uncalibrated`、`offline`。
- **完整参数来源分类：FAIL。** 操作点网格明确是 synthetic，但没有逐参数的 A/OEM、B/public、C/synthetic 账本。`cylinder_count`、`firing_order`、`cycle_revolutions`、`pulse_sharpness` 和 PTR 的 delay/loss 等值均缺少可审计来源等级与引用（或明确的 C 标签）。因此不能确认“所有 engine 参数”都已归类。

## 3. 声音工程

| 检查 | 状态 | 新鲜实测证据 |
| --- | --- | --- |
| RPM 连续性 | PASS | `rpm-ramp-2000-to-6000` 使用累积 crank phase；中点相邻样本变化为 `0.002276 Pa`，低于全段中位相邻变化 `0.016150 Pa`，未见相位重置。 |
| Load 连续性 | FAIL | `load-step-025-to-100` 在切换处由 `-4.599731 Pa` 变为 `2.664277 Pa`，单帧突变 `7.264008 Pa`；全段中位相邻变化仅 `0.013903 Pa`。这会形成 click 风险，不能称为连续负载变化。 |
| Load 可辨识性 | FAIL | 三个固定 4000 RPM / 0.25、0.60、1.00 load 的 native WAV SHA-256 均为 `65b0fd…304337`。每个 case 独立归一化到同一 0.70 peak，抹除了跨文件的负载幅度差。 |
| Clipping | PASS | 运行时报告 `total_clipping_count=0`；五个 48 kHz mono WAV 解码后 full-scale sample 均为 `0`。 |
| DC offset | PASS | renderer 在归一化前去均值；输出 PCM 的最大绝对平均值为 `0.008754` LSB，远低于 1 LSB。 |
| Phase jump | PARTIAL/FAIL | 线性 RPM ramp 未见 phase reset；但没有独立 phase-jump 质量门禁，且 load-step 的单帧幅度突变本身足以造成听感不连续。不能给整个 demo 的相位连续性 PASS。 |

## 4. 可重复性

**PASS。** 在两个独立临时输出目录完整运行 demo，两个 `sha256-manifest.json` 字节一致，文件哈希映射一致；manifest SHA-256 均为：

`3edcd9b419b59d06df884c4a82039ff2df17aa24b9c91c8a8d598553b86251be`

对应 Python 测试命令也以 `9/9` 通过：

```powershell
python -m unittest discover -s tools\sound_sim\tests -p test_s12_acoustic_audition.py -v
```

## 5. 输出审核

**PASS。** 已生成的 `demo-config.json` 和每个 audition metadata 都写入：`synthetic`、`uncalibrated`、`offline`、`not_realtime_qualified`。被审计的新增 source/test 中未发现“真实车型复制”或 OEM 校准宣传。

## 问题列表

1. **P0 — 物理边界：**新增 PTR implementation，与“PTR 不得修改”门禁冲突。
2. **P1 — 参数溯源：**缺少逐参数 A/B/C 来源账本。
3. **P1 — 负载连续性：**load-step 制造 7.264008 Pa 单帧跳变。
4. **P1 — 负载表达：**固定负载导出的 WAV 完全一致，无法通过独立试听辨识负载级别。
5. **P2 — 自动质量门禁：**尚无 phase-jump/跨 case gain-preservation 的显式阈值测试。

## 建议

1. 将 PTR 实现移出本次受保护范围，或取得对“新增、离线、只读消费 radiation package 的 PTR”这一精确例外的书面授权后再审核。
2. 添加版本化参数账本；每个值明确 `A/OEM`、`B/public`（含链接/文献）或 `C/synthetic`，并使 demo metadata 引用该账本。
3. 将 load-step 改为指定斜率的平滑 ramp，或在过渡处使用短 crossfade/envelope；为最大相邻差分和 phase continuity 建立测试门槛。
4. 保留一个跨 case 固定的绝对输出增益，或另外输出不独立归一化的比较工件，使负载层级可听、可测。
5. 在合并前添加自动 WAV QC：peak/clipping、DC、相邻样本突变、相位连续性、两次 SHA 以及不同 load 结果不得相同。
