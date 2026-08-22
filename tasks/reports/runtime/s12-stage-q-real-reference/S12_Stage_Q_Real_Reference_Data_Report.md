# S12 Stage Q 真实参考数据报告

状态：`REAL_REFERENCE_DATASET_LIMITED` / `WAITING_FOR_REAL_REFERENCE_DATA`

## 结论

本轮只审计外部本地参考，不把公开或来源不完整的音频伪装成 R1 真实标定数据。原始音频没有复制进 Git；仓库只保存路径指针、SHA-256、音频容器信息和缺口。当前没有任何记录满足 R1，因此 Stage R 的真实阶次基线、自动参数建议和调音闭环不能启动。

## 车型覆盖

| 车型 | 记录数 | 可读取 | R1 | R2 | 当前状态 |
| --- | ---: | ---: | ---: | ---: | --- |
| Ferrari 458 | 1 | 1 | 0 | 0 | `WAITING_FOR_REAL_REFERENCE_DATA` |
| Hellcat | 4 | 4 | 0 | 0 | `WAITING_FOR_REAL_REFERENCE_DATA` |
| RX-7 FD | 1 | 1 | 0 | 0 | `WAITING_FOR_REAL_REFERENCE_DATA` |
| Aventador LP700 | 1 | 1 | 0 | 0 | `WAITING_FOR_REAL_REFERENCE_DATA` |
| C63 W204 | 3 | 3 | 0 | 0 | `WAITING_FOR_REAL_REFERENCE_DATA` |
| GT-R R35 | 3 | 3 | 0 | 0 | `WAITING_FOR_REAL_REFERENCE_DATA` |
| LFA | 1 | 1 | 0 | 0 | `WAITING_FOR_REAL_REFERENCE_DATA` |
| Supra JZA80 | 1 | 1 | 0 | 0 | `WAITING_FOR_REAL_REFERENCE_DATA` |

## 记录审计

| 记录 | 场景提示 | 格式 | 时长 | SHA-256 前 12 位 | 证据等级 | 可用于调音 |
| --- | --- | --- | ---: | --- | --- | --- |
| `aventador_lp700_accel` | acceleration | 48000 Hz / 2 ch / 16 bit | 177.365s | `7dccc0bd4a55` | `R3` | 否 |
| `c63_w204_close_downshift` | shift | 48000 Hz / 1 ch / 16 bit | 12.014s | `4e7600abe78d` | `R3` | 否 |
| `c63_w204_headers_backfire` | afterfire | 48000 Hz / 1 ch / 16 bit | 62.009s | `3261aa79236a` | `R3` | 否 |
| `c63_w204_performance_accel` | acceleration | 48000 Hz / 1 ch / 16 bit | 143.787s | `534605237d62` | `R3` | 否 |
| `ferrari_458_accel` | acceleration | 48000 Hz / 2 ch / 16 bit | 212.160s | `22b0d0e1da61` | `R3` | 否 |
| `gtr_r35_nismo_accel` | acceleration | 48000 Hz / 1 ch / 16 bit | 119.993s | `dd3bd936f5d5` | `R3` | 否 |
| `gtr_r35_tomei_close` | afterfire | 48000 Hz / 1 ch / 16 bit | 30.014s | `4aeed8ff74b8` | `R3` | 否 |
| `gtr_r35_tuned_backfire` | afterfire | 48000 Hz / 1 ch / 16 bit | 68.661s | `0058a67bda86` | `R3` | 否 |
| `hellcat_burble_tune` | afterfire | 48000 Hz / 1 ch / 16 bit | 11.014s | `c062f3b8fd31` | `R3` | 否 |
| `hellcat_redeye_downshift` | shift | 48000 Hz / 1 ch / 16 bit | 25.014s | `4090dd9fa0f7` | `R3` | 否 |
| `hellcat_redeye_leave` | full_pull | 48000 Hz / 1 ch / 16 bit | 39.014s | `e5c29a92428b` | `R3` | 否 |
| `hellcat_stock_accel` | acceleration | 48000 Hz / 1 ch / 16 bit | 142.803s | `cf2ecf83c894` | `R3` | 否 |
| `lfa_full_accel` | full_pull | 48000 Hz / 2 ch / 16 bit | 90.430s | `ec75623d44c7` | `R3` | 否 |
| `rx7_fd_13brew` | acceleration | 44100 Hz / 2 ch / 16 bit | 63.948s | `c3458bd392e8` | `R3` | 否 |
| `supra_jza80_stock` | acceleration | 48000 Hz / 2 ch / 16 bit | 16.695s | `ccde31e8ec6e` | `R3` | 否 |

## 不能进入 R1/R2 的原因

- 缺少 Jovi 明确授权或可审计的合法来源记录。
- 没有任何记录绑定同步 RPM trace；不能执行 R1 阶次资格或自动调参。
- 没有可靠的 Load/Throttle、Gear/shift、麦克风位置和 AGC 记录。
- 公开/改装候选不能被当作原厂 OEM 参考。

目录中另发现 `12` 个未登记音频文件；它们只记录在 manifest 的 `unmapped_external_media`，不进入分析或调音。

## 后续必须补齐的输入

1. 有权使用的真实原始录音；不得只提供公开视频链接或无法确认权限的下载文件。
2. 精确车型/年份/市场/配置、原厂或改装状态及麦克风位置。
3. 与音频同步的 RPM；同时提供 Load/Throttle、Gear/shift 和场景起止点。
4. 录音设备、采样率、通道及 AGC/后处理说明。
5. Jovi 确认允许用于本地分析、派生特征和听审的授权记录。

在这些资料到位之前，Stage Q 只能保持 `REAL_REFERENCE_DATASET_LIMITED / WAITING_FOR_REAL_REFERENCE_DATA`；不会生成真实差异合格报告，也不会修改车型参数。

边界：所有产物继续标记 `synthetic`、`uncalibrated`、`vehicle-inspired`、`not OEM reproduction`。
