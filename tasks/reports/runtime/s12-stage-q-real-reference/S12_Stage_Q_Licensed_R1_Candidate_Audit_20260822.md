# S12 Stage Q 合法同步录音候选审计（2026-08-22）

状态：`PROCUREMENT_CANDIDATE_NOT_R1 / WAITING_FOR_PURCHASE_OR_WRITTEN_PERMISSION_AND_NUMERIC_SYNCHRONIZED_STATE`

本轮只检索并保存公开商品页、许可页和曲目单 PDF，没有代 Jovi 下单，也没有下载版权原始音频或试听流。候选页面的“同步 take、steady RPM、ramp、gearshift”是供应商描述，不等于已经提供可复核的数值 RPM、Load/Throttle、Gear/shift 时间轴；在取得授权包并完成验收前，不能进入 R1 阶次基线、自动调参或 Profile Candidate。

## 可复核收据

- 外部候选审计：`E:\Claude_allow\Download\s12-licensed-r1-candidates-20260822\candidate_source_audit_v1.json`。
- 候选审计 SHA-256：`082bc43c24ba1aa84f9450fe826244376925bb58c040999ea032396077f8c636`。
- 曲目单状态字段筛选收据：`E:\Claude_allow\Download\s12-licensed-r1-candidates-20260822\tracklist_state_screening_v1.json`。
- 曲目单筛选 SHA-256：`eb185ddcfffe142c97988fe45a4524fecb26bf52a62c81c49a3a3b2d30dffb37`；使用 `pypdf` 解析 Ferrari/Hellcat/RX-7 三份 PDF，均为 `numeric_rpm_trace_present=false`、`load_or_throttle_label_line_count=0`、`state_trace_file_present=false`，只有 `STEADY RPMS`/`RPM Ramps`/`GEARSHIFTS` 等标签，不能把标签当作数值同步状态。
- 公开页面/曲目单快照目录：`E:\Claude_allow\Download\s12-licensed-r1-candidates-20260822\source_snapshots`。
- 原始版权音频下载：`false`；购买行为：`false`。
- Ferrari 商品页的站点直连返回 HTTP 403，使用只读网页快照读取并保留 `retrieval_url` 与 SHA；Hellcat/RX-7 商品页和 Sonniss 许可页通过带 User-Agent 的只读 HTML 请求成功。所有下载物均是网页或 PDF，不是音频。

## 三辆锚定车型候选

| 车型 | 页面公开信息 | 曲目单/页面 SHA | R1 缺口 | 当前结论 |
| --- | --- | --- | --- | --- |
| Ferrari 458 | [Pole Position Ferrari 458 2013](https://pole.se/product/ferrari-458-2013-2/)：F136 F、4.5 L V8、straight pipes；228 文件、20.8 GB、11 个同步 take、steady RPM/ramp/gearshift 描述 | 商品页快照 `5f649fb8740d...78824a`；曲目单 `565232a65620...dbda45` | 未购买；没有 proof-of-purchase；页面未给数值 RPM/Load/Throttle/Gear trace、AGC/后处理合同；straight-pipe 配置不等于原厂状态 | `PROCUREMENT_CANDIDATE_NOT_R1` |
| Dodge Hellcat | [Sonniss Hellcat 2015](https://sonniss.com/sound-effects/dodge-challenger-hellcat-2015/)：6.2 L HEMI V8；196 文件、15.08 GB、96 kHz/24 bit、12 个同步 take、车载/车外、多麦位、steady RPM/ramp/gearshift 描述 | 商品页 `82c292e954e4...367802`；曲目单 `1d0c9444c255...e6f9d` | 未购买；没有 proof-of-purchase；页面未给数值 RPM/Load/Throttle/Gear trace、AGC/后处理合同；需核验原厂/改装状态 | `PROCUREMENT_CANDIDATE_NOT_R1` |
| RX-7 FD | [Sonniss Mazda RX-7 1990](https://sonniss.com/sound-effects/mazda-rx-7-1990/)：1990、2-rotor twin-turbo 13B Bridgeport；208 文件、17.83 GB、96 kHz/24 bit、12 个同步 take | 商品页 `78b6108e5bbc...54634c`；曲目单 `75e60b119cb1...524bad` | 未购买；1990 Bridgeport 与目标 RX-7 FD/原厂配置尚未确认等价；没有 proof-of-purchase、数值 RPM/Load/Throttle/Gear trace、AGC/后处理合同 | `PROCUREMENT_CANDIDATE_NOT_R1` |

省略号仅用于表格可读性；完整 SHA、绝对路径、抓取方法和 URL 位于外部 JSON 收据中。

## 许可边界

官方许可页：[Pole Position EULA](https://pole.se/shop/eula/) 与 [Sonniss Sound Library Licensing](https://sonniss.com/license/) 均表述为购买后的单用户/全球非独占免版税许可，并限制未同步素材复制、转让和共享。两份许可文字还明确禁止将许可音频用于 AI 训练/开发；如果本项目的 Comparator→参数反馈系统被许可方认定为 AI 用途，必须在使用前取得书面范围确认。当前没有购买凭证或书面确认，因此不把候选音频用于分析、听审或调音。

## 取得后 R1 验收清单

1. 保存订单/许可凭证和供应商授权范围；原始音频放在 `E:\Claude_allow\Download` 或 Jovi 指定的仓库外绝对路径。
2. 对每个原始 WAV/BWAV 计算 SHA-256，记录外部路径别名，不将原始版权音频写入 Git。
3. 逐文件核验精确车型、年份、Trim、原厂/改装排气状态、场景和麦克风位置。
4. 必须找到可复核的同步 RPM，并同时绑定 Load/Throttle、Gear/shift、时间轴单位、采集设备、采样率、通道、AGC/后处理；仅有“同步 take”或文件名不够。
5. 生成 `reference_id`、工况切片、R1 manifest 和不确定性范围；只有 R1 gate 全部通过，才允许调用既有 MATLAB/Stage-N/MoSQITo/Comparator 阶次链。

当前门禁仍为：`R1=0`、`automatic_tuning_eligible=false`、`human_feedback=WAITING_FOR_JOVI`。本审计没有改变 YouTube 24 条直连音频的 R3 状态，也没有生成参数修改或 Profile Candidate。
