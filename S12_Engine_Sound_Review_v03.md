# S12 Engine Sound Review v0.3

- 审核日期：2026-07-24
- 审核对象：Engine Sound Design Layer v0.2（`8b86157..b1bce86`）与 Engine Sound Vertical Slice v0.3（`5d406c4`）
- 审核范围：`5f8cd40471e0f4fe2823628fc8161f6bcc142477..5d406c4ee86bb4601e178676db9e5ad3e004f206`
- 方式：只读代码/差异审核、Python 回归、两次独立临时目录完整渲染、逐 WAV PCM 解码和 metadata/manifest 比对。
- 总结：**FAIL**。受保护数值边界、WAV 质量、频谱响应、确定性和禁止性宣传均通过；但完整参数分类和规定的声链顺序有 Major 缺口。

## 1. 工程边界审核

| 受保护项 | 状态 | 新鲜证据 |
| --- | --- | --- |
| FVM | PASS | 审核范围内 `models/fvm_ref` 无差异。 |
| HLLC | PASS | `test_s12_hllc_flux_ref.m` 及其实现目录无差异。 |
| MUSCL | PASS | `test_s12_muscl_minmod.m`、FVM 模型目录无差异。 |
| Positivity | PASS | `test_s12_pp_ssprk3_contract.m`、benchmark/validation 无差异。 |
| SSP-RK3 | PASS | `test_s12_ssprk3_periodic_ref.m`、`test_s12_ssprk3_sod_ref.m` 及 FVM 模型目录无差异。 |
| Radiation Boundary | PASS | `validation`、`benchmark` 与 accepted radiation package 均无差异。 |
| PTR 核心数学模型 | PASS | `acoustic_demo/s12_ptr_network.py` 在 v0.2/v0.3 范围内无差异；新层只调用 `run_ptr_network`。 |

## 2. 数据真实性审核

### 通过

- v0.2 的 `engine_sound_parameter_ledger.json` 中 24 个设计参数和 4 个阶次条目均为 `classification: C/synthetic`、`source: synthetic`，且加载器会拒绝缺失该标记的 ledger。
- `engine_order_profile.json`、design/vertical-slice metadata 和生成报告均将产物声明为 synthetic；未发现把这些值说成 OEM 数据或实车标定的数据源。

### FAIL — Major：并非所有 engine 参数都具备逐项 A/B/C 分类

以下实际参与 v0.3 链路的数值没有纳入上述分类 ledger：

- `EngineSourceConfig` 的 cylinder count、firing order、cycle revolutions、pulse sharpness、sample rate；
- `s12_operating_points.py` 的 RPM/load grid 及 pressure-amplitude table；
- `vehicle_state.py` 的 `SPEED_PER_RPM_MPS=0.01` 和各 demo RPM/load/speed/acceleration 轨迹。

它们处在 synthetic 模块或带有泛化的 synthetic 文案，但并非逐项、可哈希引用的 `A/真实来源`、`B/公开资料` 或 `C/synthetic` 参数账本。因此“所有发动机参数均已分类”的门禁不成立。未发现 synthetic 冒充 OEM；问题是分类覆盖不完整。

## 3. 声音链路审核

要求链路：`RPM / Speed / Acceleration / Load → Engine Order → Harmonic → Transient → PTR → WAV`。

### 已实现并验证

- RPM 与 Load 会进入 `synthesize_four_stroke_trajectory` 和 `render_sound_design`；RPM 连续积分到 order phase，Load 连续改变 order/transient 权重。
- Engine order、harmonic、transient、stereo mixing 与 WAV renderer 都存在；WAV 由 deterministic 24-bit stereo renderer 写出。

### FAIL — Major：输入消费与 PTR 位置不符合规定链路

1. v0.3 `_render_case` 的实际顺序是：`RPM+Load → synthetic pressure source → PTR → order/harmonic/transient sound design → WAV`。PTR 是 design layer 的纹理输入，而不是要求中的 transient 后、WAV 前的下游处理；order/harmonic/transient 并未送入 PTR。
2. `VehicleStateSeries` 会验证 `speed = RPM × 0.01` 和 `acceleration = d(speed)/dt`，但 `to_order_schedule()` 只传递 RPM/Load；sound design 自行从 RPM/Load 计算 rate。Speed 和 Acceleration 没有作为独立声学输入被消费。

因此不能将当前 v0.3 宣称为已满足四输入、指定顺序的完整声链。该结论不表示 PTR 核心数学模型被修改；第 1 节已证明其未变。

## 4. 音频质量审核

两次独立完整渲染产生 8 个 WAV：5 个 vertical-slice case 及 low/mid/high load comparison。

| 检查 | 状态 | 实测 |
| --- | --- | --- |
| Sample rate | PASS | 8/8 为 48,000 Hz。 |
| WAV format | PASS | 8/8 为 2 channel、24-bit PCM。 |
| Clipping | PASS | 8/8 PCM full-scale samples 为 0；renderer metadata `clipping_count=0`。 |
| DC offset | PASS | 最大绝对通道 DC 为 `1.709e-9` normalized，低于 C/synthetic 门限 `0.001`。 |
| Discontinuity | PASS | 8/8 最大相邻样本步进不超过 `0.009442` normalized，低于 C/synthetic 门限 `0.15`。 |
| Phase jump / RPM ramp click | PASS（离线范围） | 新鲜回归中的 `test_rpm_ramp_preserves_phase_and_stays_click_free` 通过；相位由逐样本 RPM 累积，不重置。 |
| 突然音高变化 | PASS（离线范围） | acceleration case 为连续 `1000→6000 RPM` trajectory；阶次频率随逐样本 RPM 线性积分。未做真人主观听感或实车对比。 |

峰值相邻步进最大的主 case 是 `high_load.wav` 左通道 `0.009441`；最大 DC 出现在同一主 case 右通道，仍远低于门限。

## 5. 频谱审核

**PASS（synthetic order contract）。** 订单模型使用 `f = order × RPM / 60`：acceleration case 的 RPM 范围为 `1000→6000`，故 fundamental 为 `16.667→100 Hz`、second/firing 为 `33.333→200 Hz`、third 为 `50→300 Hz`；生成的 `sound_analysis.json` 记录相同的开始/结束频率。

Load comparison 的已生成 WAV metadata 也显示 order RMS 单调增大：

| Load | order 1 RMS | order 2 RMS | order 3 RMS |
| --- | ---: | ---: | ---: |
| 0.0 | 0.033015 | 0.013177 | 0.002732 |
| 0.5 | 0.066030 | 0.061779 | 0.012749 |
| 1.0 | 0.099046 | 0.110144 | 0.022765 |

这是 synthetic 参数和投影频谱的一致性证据，不是实车 order spectrum 或 OEM 声纹验证。

## 6. 确定性审核

**PASS。** 两次独立临时目录运行 `run_vertical_slice` 后：

- `manifest.json` 字节完全一致；
- `SHA256.txt` 字节完全一致；
- 两个 manifest 的 SHA-256 均为 `3f8f03927c10e4d6ed4d7b5adcbd0eba624518e23c4856615b6a570b91afa629`；
- 所有 manifest 控制文件的 SHA-256 已逐项重算匹配。

同时运行：

```powershell
python -m unittest discover -s tools\sound_sim\tests -p "test_*.py" -v
```

结果为 `28/28` 通过。

## 7. 文档审核

**PASS。** 生成的 manifest、WAV metadata 和 vertical-slice report 均明确标记：`synthetic`、`uncalibrated`、`offline`、`not_realtime_qualified`（文案形式为 “not realtime-qualified”）。报告明确 OEM calibration、real vehicle measurement、Realtime DSP、Phone integration 均为 `NOT COMPLETED`。

审计范围内没有肯定式的“真实发动机”“OEM复刻”或“已经标定”宣传。出现的 “not an OEM engine clone” 是明确否定，不构成该禁止性宣传。

## 问题列表

| 严重等级 | 问题 | 状态 |
| --- | --- | --- |
| Critical | 无。受保护 FVM/PTR 等数学边界未被修改。 | — |
| Major | Engine source、operating point 与 vehicle-state 参数没有逐项 A/B/C 分类和来源锚点。 | OPEN |
| Major | 实际声链是 `source → PTR → design`，而非要求的 `order/harmonic/transient → PTR → WAV`；Speed/Acceleration 亦未作为独立声学输入消费。 | OPEN |
| Minor | 质量阈值与频谱仅为 C/synthetic 合同；尚无校准麦克风、主观听评或实车/公开参考谱的独立验证。 | OPEN |

## 下一步建议

1. **先关闭 Major，再进入 Realtime DSP。** 以保持 FVM/HLLC/MUSCL/positivity/SSP-RK3/radiation/PTR 核心冻结为前提，明确声链架构：若 PTR 必须在 downstream，则让 order/harmonic/transient 的目标信号经适配器进入 PTR；否则更新需求与命名，不能把当前拓扑说成满足该链路。
2. **建立 AudioParameterPackage。** 版本化、可哈希，并覆盖 source config、operating grid、vehicle-state mapping、trajectory、design ledger 和单位；每个数值必须有 A/B/C、来源、rationale、适用范围和不可声称 OEM 的限制。
3. **Realtime DSP。** 仅在以上两项通过后，为固定采样率、状态平滑、限幅、CPU/内存预算和 deterministic/offline equivalence 建立独立资格；当前 v0.3 不能证明实时适用性。
4. **Phone Integration。** 放在 AudioParameterPackage 和 Realtime DSP 资格之后；当前离线 WAV 只能作为 UI audition 资产，不能作为已完成手机集成或实车音效的证据。
