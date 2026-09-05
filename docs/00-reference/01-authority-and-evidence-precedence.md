# 项目权威、Reference 与证据优先级

更新：2026-09-05
状态：`ACTIVE_AUTHORITY`

## 1. 冲突时谁说了算

```text
Current user decision
> Current GitHub remote truth
> Current authority/status docs
> Canonical long-term memory
> Historical reports/specs/plans
> Old chat summaries
> External sources
```

外部开源项目从来不是本工程行为真值；它只提供 method/reference。

## 2. Reference 等级

### R1 — Formal calibration reference

必须同时具备：合法可用的原始 WAV/FLAC、明确车型/配置/stock 状态、录音位置与链路、AGC/后处理状态、同步 RPM，并尽量有 load/throttle/gear/shift。R1 才能支持正式 Order-RPM、正式标定和更高级别 Profile Freeze。

### R2 — Governed engineering reference

可用于相对工程比较/参数研究，但不具备完整 R1 条件。必须保留来源、rights/status、SHA、场景和不确定性。

### R3 — Private diagnostic reference

用于工程启发和人耳 A/B，不能被写成 OEM truth。

特别规则：`stage_ad/extract_reference_audio.py` 能从 YouTube/Bilibili 提取片段，但**工具存在不代表拥有内容权利**。只有用户明确授权且使用符合平台条款/版权要求时，才允许生成私有 R3 试听材料；默认：

```text
R3 public extract
→ human A/B diagnostic only
→ NOT automatic Stage-AD optimizer input
→ NOT R2/R1
→ NOT product asset
→ NOT redistribution asset
```

如果未来获得单独 rights receipt 和更完整 metadata，应创建新的 canonical registry record，而不是修改旧 R3 label。

## 3. Human evidence

正式盲听包必须 immutable。反馈流程：

```text
raw feedback
→ save verbatim
→ SHA256
→ verify package/manifest
→ reveal blind mapping
→ binding receipt
→ engineering interpretation
```

Stage AD 的非盲 diagnostic audition 与官方 V3 blind package 分离，不能覆盖 V3，也不能直接给 `Human accepted` 状态。

## 4. Software / acoustic / product evidence

- 软件测试只证明实现/回归正确。
- reference metric 只证明在定义的指标上更接近。
- Human feedback 判断真实感/车型身份。
- Android 实测证明产品 realtime 体验。
- R1 决定正式真实标定边界。

## 5. 永久禁止的证据跳跃

```text
CI PASS → sound realistic              FORBIDDEN
metric better → Human PASS             FORBIDDEN
public WAV → rights-cleared R1          FORBIDDEN
repository code license → audio rights FORBIDDEN
Human PASS → OEM calibrated            FORBIDDEN
```
