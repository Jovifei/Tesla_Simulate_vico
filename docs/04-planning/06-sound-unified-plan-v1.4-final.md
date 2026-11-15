# 特斯拉声浪模拟统一执行方案 v1.4 定稿（双边共识版，业主终审通过 2026-11-15 20:16）

- 日期：2026-11-15；合成：Muse（PM）
- 状态：**业主终审通过 2026-11-15 20:16**；双边共识已达成。命名（T1–T4 + C0）两边第三轮一致；状态词汇 v1.4 FROZEN（ChatGPT 第四轮与 Gemini 第四轮枚举表、字段名、递进、废止清单、911 代码处理完全一致）；M4、RX-7、响度、C2C 范围四项第二轮已一致。**执行未授权**（Step 1 主机冒烟测试除外，业主已另行批准并派给 dot）。双线并行（方向 A engine-sim + C2C Simulink/Frozen）比较的基线原则不变。
- 评审过程：第一轮独立方案 → 第二轮交叉对齐（命名第二次换位、状态词汇各提一套）→ 第三轮钉死轮（命名收敛、状态词汇仍差一套）→ 第四轮状态词汇最终钉死（两边同一套表，收敛）。
- 评审方：Gemini（Argon，高）/ ChatGPT（极高）。
- 来源：各轮回复全文（`chatgpt/gemini-sound-alignment-round*-reply-20261115.md`）。第一轮两份执行方案全文为执行细节依据（四输入契约、T0–T4 脚本、20 车清单等），本稿只冻结对齐轮次定下的规范，不重复抄录执行细节。

## 一、命名与轨迹套件（已收敛）

| 类型 | 唯一命名 |
|---|---|
| 四条冻结共同轨迹（热车） | T1、T2、T3、T4 |
| 统一冷启动测试 | C0 |
| 车型专属冷启动 | C0_<vehicleId> |
| 车型专属工况覆盖 | H_<vehicleId> |

- T0 正式废止，不设置双重别名。
- 配套规则：T1–T4 现有冻结文件及其 SHA-256 哈希为最高权威；版本化确定性生成器只读校验 T1–T4，不重生成、不覆盖，仅增量生成 C0 与 H 场景；START_COLD 通过 scenario_config.json 下发，不增加第五个控制输入；四输入契约不变；C0 的统一测试参数不作为各车型的 OEM 冷启动真值。
- 评测矩阵计数：首轮 10 个声音包（方向 A × 9 车 + C2C × 1 车 Hellcat）在 T1–T4 下为 40 个热车基准单元，加 C0/C0_<vehicleId> 的 10 个冷启动单元，总计 50 个正式评测单元；H_<vehicleId> 在 50 个正式单元之外独立统计。

## 二、BMW M4 基线（已收敛）

| 字段 | 统一冻结值 |
|---|---|
| 产品 ID | m4_f82_s55_stock |
| 车型 | 2015 BMW M4 Coupe F82，非 Competition |
| 发动机 | S55B30T0，2,979 cc |
| 变速箱 | 原厂 6MT（7DCT 为合法原厂配置，但不作默认基线，后续另建 DCT 配置版本） |
| 功率/扭矩 | 317 kW / 431 PS，550 Nm（431 PS ≈ 425 bhp，不得写作 431 bhp） |
| 最高发动机转速基准 | 7,600 rpm |
| 模板 | inline6.json（与 Supra JZA80 共用基础结构模板，独立车型配置包覆盖双涡管排气与标定参数） |

## 三、RX-7 术语与基线（已收敛）

- 车型基线：Mazda RX-7 FD3S / 13B-REW，原厂；Spirit R 可成为后续车型变体，不作为首批唯一基线。
- 模型类型：wankel_2rotor_side_intake_peripheral_exhaust（侧进气口 + 周边排气口）；“周边／端面排气口”混合表述不接受。
- 增压：原厂顺序双涡轮，独立配置；基础资产 classic_rotary.json 仅作为历史模板。
- 模型门禁：MODEL_INCOMPLETE（readiness_status 阻塞分支态）；方向 A 完成转子室容积与端口流量模型扩展并通过独立验证前，不得进入正式声音验收、不得混入活塞机验收池。

## 四、状态词汇 v1.4 FROZEN（已收敛）

字段一：catalog_status（只表达车型身份与模板归属，不表达模型是否完成）

| 枚举值 | 含义 |
|---|---|
| TEMPLATE_RESERVED | 通用基础模板，尚未指定为具名车型目标 |
| TARGET_LOCKED | 具名车型目标已冻结，具有明确的 vehicle_id 和基础模板映射 |

字段二：readiness_status（只表达参数、模型与声学证据的技术就绪程度）

| 枚举值 | 含义 |
|---|---|
| SPEC_UNVERIFIED | 车型身份已登记，必要技术参数尚未完成来源核验 |
| SPEC_VERIFIED | 车型身份及必要技术参数已通过可追溯来源核验 |
| MODEL_INCOMPLETE | 已发现模型缺少必要能力，属于阻塞状态，禁止进入正式模型验收 |
| MODEL_VALIDATED | 模型必要能力、数字测试及对应边界验证通过，可进入正式声学评审准备 |
| ACOUSTIC_CALIBRATED | 基于合格参考完成预声明声学校准及客观检查，不代表业主人工试听通过 |

递进规则：

- 正常递进：SPEC_UNVERIFIED → SPEC_VERIFIED → MODEL_VALIDATED → ACOUSTIC_CALIBRATED。
- 模型缺陷阻塞路径：SPEC_VERIFIED → MODEL_INCOMPLETE → MODEL_VALIDATED；缺陷修复后必须重新完成模型验证；规格修订或证据失效时，允许有审计记录地回退。
- TEMPLATE_RESERVED 的通用模板不强制填写车型级 readiness_status，可使用 null；锁定的具名车型必须填写有效就绪状态。
- 前端非调试模式上架点亮硬门禁：必须同时满足 catalog_status == "TARGET_LOCKED" 且 readiness_status == "ACOUSTIC_CALIBRATED"，并经业主人工试听门签字通过。
- 四道人工／设备／座舱／真车验收门保持独立，不加入上述技术状态链；ACOUSTIC_CALIBRATED 不代表业主听感通过。

废止词清单（不再允许写入新的正式 manifest）：RESERVED_TEMPLATE、MODEL_READY、UNVERIFIED_DRAFT、OEM_VERIFIED、VALIDATED_READY、SPEC_UNVERIFIED 的其它非正式同义写法，以及 verification_status 字段名。MODEL_INCOMPLETE 保留，但只能出现在 readiness_status 中。旧证据和历史 manifest 保持原样，通过显式版本化映射读取，不直接覆盖历史记录。

⚠️ 两处细微口径差异（补充说明，非冲突，终审时请看一眼）：

1. Gemini 第四轮的废止字段名清单另含 model_status；ChatGPT v1.4 未提及 model_status。本稿按两边共同清单冻结，model_status 是否一并废止由终审定。
2. Gemini 允许 MODEL_INCOMPLETE 从 SPEC_UNVERIFIED 或 SPEC_VERIFIED 转入；ChatGPT v1.4 的阻塞路径只写从 SPEC_VERIFIED 转入。本稿按 ChatGPT v1.4 冻结；是否放宽入口由终审定。

## 五、响度归一化规则（已收敛）

- 单车/单路线静态增益锚定法：保留 -16 LUFS 目标参考值，严禁对每条轨迹单独做 LUFS 归一化。
- 每个（车型，技术路线）组合在预声明的参考校准集（如 T2/T3 基准段）上只计算并锁定唯一一个静态增益值（applied_static_gain_db），无差别应用于该组合下的全部 C0/T1–T4 及 H_<vehicleId> 试听文件。
- 完整保留未归一化的原始输出集；严禁在后处理链使用逐段 AGC、动态响度匹配或事后软削波。
- 每份试听产物元数据强制记录 4 项审计字段：integrated_lufs、true_peak_dbfs、applied_static_gain_db、headroom_limited。

## 六、C2C 首轮范围（已收敛）

- 方向 A：覆盖首批 9 款车。C2C 线：首轮仅覆盖 Hellcat（1 款车）；底声未获业主试听接受前，C2C 线绝不横向扩展其他车型，也不接入换挡/回火特效。
- 双线直接 A/B 盲听对决仅在 Hellcat 单车上进行。
- 前端注册首批 9 款车型的切换入口，但仅点亮并允许播放已通过验证的声音包（未通过或 MODEL_INCOMPLETE 的声音包在非调试模式下置灰不可选）。

## 七、第二批变体钉死（已收敛）

| 目标 | 冻结值 |
|---|---|
| 911 GT3 RS | 992 代 4.0L 自然吸气水平对置六缸；发动机代码 UNVERIFIED 待来源核验（MA1.76 与 EA9A1.5 均不得预先写成已核实代码；代码字段标注 CODE_PENDING_SPEC_VERIFY；相关规格验收未完成前不得升级为 SPEC_VERIFIED） |
| 1969 Charger R/T | 原厂选装 426 HEMI（不能写成所有 1969 Charger R/T 的标准发动机） |
| 2019 Ram 2500 Heavy Duty | 6.7L Cummins 涡轮柴油直六；ISB 精确型号标识及对应传动配置继续作参数核验，不将未核实代码当作已验证值 |
| Ducati Panigale V2 | 2020–2024 款 955cc Superquadro；2025 年新一代 890cc 使用独立 ID 和 profile，严禁混用 |
| Porsche Taycan Turbo S | NON_ICE_EVAL_TRACK，不适用内燃机点火、燃烧阶次、发动机冷启动等指标，适用独立电驱声音评价条件 |

归属数量：首批 9 个车型目标 + 第二批 11 个车型目标 = 20 个具名车型身份；20 个基础模板中，classic_british_i6 是唯一 TEMPLATE_RESERVED 的通用模板，其余按已定映射分配；两类数量分别统计，不混淆。

## 八、终审决议记录（业主终审通过 2026-11-15 20:16）

1. 已批准：本定稿 v1.4 获业主终审通过（2026-11-15 20:16，整包批准）。第四节末两处细微口径差异（model_status 是否废止、MODEL_INCOMPLETE 入口是否放宽）未裁定，记待业主定，本文保留原表述。
2. 执行授权：本共识为方案定稿，执行未授权（Step 1 主机冒烟测试已另行批准并派给 dot，不在此列）；后续实现、测试、车型注册表及评审 manifest 统一遵循 v1.4，须业主批准后派活。
3. 待核验事项：911 GT3 RS 发动机代码（官方技术资料核实后填入）；Ram ISB 精确型号标识及传动配置（参数核验）。

## 附：对齐简史

- 第一轮：两份独立方案（ChatGPT 四输入契约 + C0/H 体系；Gemini T0–T4 脚本 + 20 车清单）。
- 第二轮：命名第二次交叉换位（ChatGPT 采 T1–T4+C0，Gemini 采 T0–T4）；状态词汇各提一套；M4/RX-7/响度/C2C 四项一致。
- 第三轮：命名收敛（两边同定 T1–T4+C0）；状态词汇 ChatGPT 取合并版、Gemini 守旧版。
- 第四轮：状态词汇两边同一套表（M 方案，v1.4 FROZEN）。收敛。
