# S12 Stage K 三车 Round‑2：真实事件、源级平衡与最终 PCM 证据

## 目标

把 Hellcat Stage L Round‑2 已验证的工程经验迁移到 Stage K 的另外三辆车：

- Mercedes C63 W204 (`c63_w204`)
- Nissan GT‑R R35 (`gtr_r35`)
- Lexus LFA (`lfa`)

本轮不是把 Hellcat 的双螺杆/HEMI 参数复制到三车，也不是宣称 OEM 复刻。每辆车继续使用自己的源模型、曲轴/阶次结构、换挡或收油层与参考目标；共同迁移的是证据方法和声学原则。

## 冻结边界

- Hellcat Stage L v9、Stage K Hellcat v7、Stage K v1 契约保持只读。
- 公共 LF Body、Rumble、Pre‑PTR EQ、Frozen PTR、Edge Fade、响度管理、Track‑P、MATLAB/Simulink、运行时与其他五辆车不得修改。
- 任何正式试听仍是 `synthetic / uncalibrated / vehicle-inspired / not OEM reproduction`，最终状态保持 `PARTIAL / AUTOMATED_GATE_FAIL / UNQUALIFIED_DIAGNOSTIC_ONLY`，不得自动进入 Human PASS、Profile Freeze 或 Approved。
- 不读取反馈 CSV、sealed key 或外部媒体；本轮只记录文字方向和本地可复算数组/PCM 证据。
- 所有既有未跟踪文件和历史包保留，不覆盖、不清理。

## 基线收据（2026‑08‑15）

基线来源为现有 `s12-stage-k-four-vehicle-perceptual-repair-v1` 包与当前候选文件：

| 车型 | candidate profile SHA-256 | baseline PCM SHA-256 | Stage K candidate PCM SHA-256 |
|---|---|---|---|
| C63 W204 | `e6bc219e88d1205c47029becebe40efefd51ff5d38ebcea98e202b6274a537a3` | `a3f7e049a03d4af67e72ccce5f953600e1e6a29282ff5bfef6310c5950a73473` | `4c5d4613b8cc9f5cc05ff108613d9233c3441d34ad5ac9507346861e36850e94` |
| GT‑R R35 | `094a9a861e5e7dd4611d80cc066f18f16ad89579f8e2c7b88858336df096dc7e` | `9cc6a9f93baaf97823caceadfe8a99662098f7c9bc6f79f6dfda1562abb6aa5b` | `52ccc85e2dc8e787d030b8881df1ce270fe5f166ab26cfcbd144a656d78b40d1` |
| Lexus LFA | `ff1f8f461bfc7a4bdd2c1367fe42b291be02041fbdaf1fb27a9401bfe00f8b57` | `891d3d7332ae797e9e88e8da08a0738aa60226bb438830c0e58550964088847e` | `629b3279bc304aead52a6413390ef116889a059dec927b434e34359a69bcde7a` |

Package manifest SHA is `8a3831bc9fbd71c3a56d7fe85520683fba9012c64eef7b66c5d7789c7dac1c79`; ZIP SHA is `d81bc9e77276bf6066c73bf3444239800067f1a1545f43460061c37bd88fdeef`. These are audit anchors, not new qualification claims.

## 迁移原则

1. **源级平衡而非总增益**：加速与高负荷时保持各车的低阶主体，抑制会遮蔽主体的过亮高频；不得用全局 gain、白噪声、固定 tone、压缩器或动态 EQ 解决声学身份。
2. **实际事件而非固定片段**：shift、lift、BOV/overrun、ASG re‑engagement 和 afterfire 诊断窗口必须锚定共享 trace 的真实事件 onset；禁止用 `audio[:duration]` 冒充事件片段。
3. **车型专属物理结构**：C63 保留 cross‑plane bark/body，GT‑R 保留两套 turbo shaft/phase/BOV，LFA 保留 5/10/15 阶族与 ASG/进气重开。三车不得共享 Hellcat twin‑screw/HEMI 层或彼此的事件 stem。
4. **单次压力会计**：primitive stem 修改后逐样本重建所有诊断 aggregate；pressure 只能等于实际 contributor 的一次求和，alias 不得再次计能量。
5. **最终 PCM 证据闭环**：正式 Parent/Baseline/Candidate 共用 `Frozen PTR → edge fade → one fixed whole‑cycle gain → PCM24`；Comfort 只从 Candidate final PCM 做一次 peak‑safe 静态增益。每个 WAV 必须绑定 profile、trace、producer、PCM/frame/duration、SHA 和 ZIP 成员。
6. **可达性与来源**：每个新增/改变的参数必须有独立扰动，能改变目标数组、事件或实际指标；`read/configured` 不能代替 `active`。自哈希 manifest 不能代替生产来源认证。

## 三车 Round‑2 方向

### C63 W204

保留已被接受的加速低频 bark/body；优先降低 4–12 kHz 的事件粗糙度与过平高频，保持 cross‑plane 不均匀事件和收油节奏。候选只从现有 `bark_upper_partial_mix`、`bark_decay_ms`、`mechanical_upper_tilt_db`、`high_rpm_compression`、`mechanical_texture_scale`、`high_rpm_growth_scale` 做低/种子/高值顺序搜索；0–8 s idle 和公共低频层必须字节不变。

### GT‑R R35

保留两套并行涡轮的 shaft state、120° bank phase、BPF 与 boost‑history BOV；修正“涡轮啸叫覆盖 V6 主体”的风险，要求高负荷时 exhaust/combustion 与 intake/shaft 的比例随 load 变化而不是固定 tone。只搜索现有 twin‑turbo 参数，禁止把双螺杆或 Hellcat afterfire 逻辑泄漏进来；BOV 只在真实 closed‑throttle/boost history 事件出现。

### Lexus LFA

保留 V10 5/10/15 阶族、metallic/intake 身份与 ASG torque cut；以真实换挡与 lift 事件重测 dip/settling/overshoot、re‑engagement、intake reopen 和 overrun 衰减。禁止恢复通用 70 Hz boom、固定时间间隔或把 RPM 直接当总响度增益。

## 首轮硬门与停止条件

- 三车 0–8 s primitive、aggregate、pressure 与当前 Stage K 候选逐字节相同；最终 idle 各频带漂移 ≤0.5 dB。
- 24–26 s（第三次换挡后的统一事件窗）低阶主体不得下降；遮蔽主体的高频能量必须下降或保持在车型目标范围内，指标来自重开 PCM 和真实 source arrays。
- 事件诊断必须报告真实 onset/start/end、source stems、非零事件数量；错误工况事件数必须为 0。
- 20–250 Hz 不扩张、250–1000 Hz 严格缩小、reference distance、state availability、Track‑P、PCM24/48 kHz/stereo/finite/clipping/peak 门继续生效。
- 任一车型的 hard gate 失败只保留 `best_diagnostic_<vehicle>_r2`，不写入合格候选，不影响另外两车 baseline SHA。

## 执行顺序

1. 先提交本收据与三车 Round‑2 文字方向；新增 RED 测试覆盖真实数组、事件窗口、aggregate/pressure 会计、最终 PCM/Comfort、receipt/ZIP 来源绑定和三车隔离。
2. 各模块最小 GREEN 后，使用 8–12 s 三个顺序 probe 做逐参数低/种子/高值搜索；不保留长时 SourceRender。
3. 每车最多九个完整 60 s 快照；先 hard gates，再用户方向误差、参考距离、相对基线改变量、candidate ID 字典序。
4. 仅在三车都通过包完整性验证后生成新的不覆盖包 `E:\Tesla_speed\review_packages\s12-stage-k-three-vehicle-round2-v1`；若硬门失败，仍只交付带明确身份的 diagnostic 包。
5. 运行三车 focused、Stage K/J regression、Track‑P guard、冻结 SHA 与 diff 检查；独立复审后再提交本地 commit。不得 push/merge/rebase。
