# Hellcat 状态合同与三路离线对照 Harness

日期：2026-10-27（Asia/Shanghai）

## 范围

本阶段由 Jovi 授权方案 A，仅在隔离工作树 `hellcat-state-contract-20261027` 实现：

- 真实录音状态合同 `vico.recorded.state-contract.v1`；
- 许可、源身份、同步状态、RPM/load/gear、720° phase、独立 holdout 的 fail-closed 校验；
- 固定 60 秒、不中途 reset 的三路离线对照 harness；
- 不修改默认声库、Android 路由、APK、MATLAB、设备或公网。

## 实现

- `vico_web/tools/recorded-state-contract.mjs`：缺证据返回 `INSUFFICIENT_EVIDENCE`，不估算或填充 RPM/load。
- `vico_web/tools/three-way-offline-study.mjs`：三路身份固定为 `RECORDED_PRIMARY`、`LEGACY_BANK`、`GENERIC_PHYSICS`；只有合格合同和三个真实 `Float32Array` 60 秒/48 kHz 输出才写出 `.f32le`。
- 固定轨迹为 `15 s idle → 15 s acceleration → 15 s high-rpm → 10 s coast → 5 s idle`，`resetCount=0`。
- 所有输出执行有限值和 `[-1,1]` 峰值校验；报告仍把产品候选设为 `false`，因为人耳、设备、道路和 OEM 资格未完成。

## 验证

- RED：模块不存在时新增合同/研究测试失败，记录于 `E:/Tesla_speed/reports/recorded-engine-optimization-20261027-red.log`。
- 聚焦 GREEN：8/8，通过 `recorded-engine-optimization-20261027-focused-final2.log`。
- 完整 Web 回归：171/171，通过 `recorded-engine-optimization-20261027-web-final.log`。
- `git diff --check`：PASS。
- `python scripts/update-project-progress.py --check`：PASS。

## 当前结论

软件边界已建立，但没有新的合格 Hellcat 多工况录音被生成或接入。当前产品声库、启动实录和既有失败实验保持不变；没有 RPM/load/phase 数据时，三路研究只能返回 `INSUFFICIENT_EVIDENCE`。下一门是取得合法、同源并带同步状态轨迹及独立 holdout 的多工况采集，然后再运行真实三路离线对照。

Hub revision 报告尝试因该隔离工作树不属于注册仓库而失败，未伪造发送结果。

最终回归：web-final-after-length-gate.log，171/171；账本 --check PASS；diff-check PASS。
