# S12 Stage Y 更改与问题状态（2026-08-31）

状态：`WIP / FINAL_FITTED_MAP_NOT_QUALIFIED`。本次是保存工作进度的本地提交，不是发布或资格通过；不 push、不合并、不修改音频。

## 本次保存的更改

| 文件 | 更改与作用 |
| --- | --- |
| `stage_x/search_parameters.py` | P3/P5 timbre-map 探针装载正式 committed map；探针证据记录 schema、fixture SHA、map 文件 SHA。新增共用 post-PTR 窄带归一能量 helper，三个声层使用固定 3000 rpm、load/throttle=0.8、2.5 秒工况。 |
| `stage_y/harmonic_map_fit.py` | 新增 `configure_committed_fixture_timbre_map()`，复用严格 loader 填充 table、完整 map 元数据及 require flag。 |
| `tests/test_s12_stage_y_reachability.py` | 新增 committed-map 配置传递、频带选择性/增益不变性、固定工况与三个声层可达性契约测试。当前存在预期未闭合的失败，不应当作绿色基线。 |

以上路径均相对于 `tools/sound_sim/s12/acoustic_identity_v015/`。没有修改 DSP、PLL、冻结 PTR、地图数据或正式试听包。

窄带指标取最后一秒 PCM，转 mono 后使用 Hann 窗 FFT，以目标频带能量除以非 DC 总能量。sideband 中心来自增压轴传动比；broadband 来自现有 `index*0.017 + phase*0.31`、`index*0.041 + phase*0.73`、`index*0.097` 公式；casing 来自曲轴阶次 4.7/9.3。频带半宽为 2 Hz，不是任意频点扫描。

## 已完成的阶段证据

- Y2：committed synthetic harmonic map 严格加载；FFT 使用正确的 one-sided `2/N` 系数（DC/Nyquist 为 `1/N`）。
- Y3：P4 使用 720°/4π 曲轴周期，架构 inventory 与 validator 对齐，流式分块等价有单独测试。
- Y4：四类瞬态 latch/re-arm、120 ms 尾音、完整 diagnostics、原子 snapshot/replay；阶段最终结果为 80 passed、1 skipped。
- Y5：逐样本 stereo DC/dP、fractional delay、一次性 warmup、snapshot v3 及旧版本安全迁移；含 60 秒等价的阶段结果为 43 passed、无 skip。
- Y6：现有 v1 包有 154 个 48 kHz/stereo/PCM24 WAV、11 个场景、两页中文试听；文件哈希及浏览器解码/抽样播放通过。

这些是各自源码版本的阶段证据，不是本次重新运行的全量结果。v1 包位于 `E:/Tesla_speed/review_packages/s12-stage-y-hellcat-layers-v1/`，保持原样；它不代表人耳接受或最终参数可达性通过。

## 当前为什么还不能完成

旧 Y1 canonical 16/16 使用公式默认 map，而最终 bakeoff/package 使用 committed fitted map。配置不同，因此旧收据不能证明最终路径的 16 个参数全部可达。旧收据保留，不重写成新证据。

此前固定模型频带的定向诊断结果如下；它们不是本轮 canonical 复验：

| 控制 | minus 相对移动 | plus 相对移动 | 对照双向 >0.02 门 |
| --- | ---: | ---: | --- |
| sideband mix | 0.2128799 | 0.2380784 | 达到 |
| broadband mix | 0.0020768 | 0.0020806 | 未达到，约为要求的十分之一 |
| casing mix | 0.3540159 | 0.4634793 | 达到 |

另外，boost attack/release 与 bypass 的最终 map 包络观测尚未闭合，不能推断为通过。完整 S12 还没有运行，Vault 也尚未同步本轮状态。

## 本轮最小检查

运行 `python -m pytest`，选择 `test_s12_stage_y_reachability.py` 中以下三个节点：

- `test_p3_reachability_probe_receives_committed_fitted_map`
- `test_post_ptr_narrowband_energy_share_is_gain_invariant_and_selective`
- `test_y1_blower_spectrum_trace_is_fixed_condition_probe`

实际结果：`1 failed, 2 passed in 1.57s`。失败断言比较 `0.9999999999862014 == 0.9999999999862017`，属于浮点严格相等问题；本次未修改它，也没有降低 0.02 可达性门。该测试问题与 broadband 未达到可达性门是两个独立问题。

## 下一步与授权边界

1. 修正数值不变性测试的合理浮点比较，不改变可达性门。
2. 完成最终 map 的 boost/bypass 指标验证；broadband 若需要实际源层能量配平，应先获得该范围授权，不能用全局音量或降低阈值掩盖。
3. 所有最终路径参数通过后，生成新的 source/map-bound 收据，再做最后一次完整 S12 和知识库同步。
4. 若以后改变实际声音，保留 v1，不覆盖当前试听证据，另行生成获授权的新包。

本次“提交与更新文档”不视为同意源层配平。R1、OEM、Profile Freeze 和 Jovi 人耳接受均未通过；缺少 R1 不阻塞本轮软件修复。

恢复入口：[EXECUTION_RESUME](../../tasks/reports/runtime/s12-stage-y/EXECUTION_RESUME.md)、[执行状态](../../tasks/reports/runtime/s12-stage-y/execution_state.json)、[最终 map 可达性缺口](../../tasks/reports/runtime/s12-stage-y/final_qualification/fitted_map_reachability_gap.json)。
