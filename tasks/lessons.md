# Lessons Learned
## 2026-08-01: 声学身份验收必须优先于参数和测试数量

Pattern: 三个 profile 即使通过频谱质心、阶次能量和谐波比例门槛，只要仍共享 excitation generator、瞬态包络和全帧归一化，闭眼试听仍可能像同一个模板。

Rules:
1. 不同发动机架构必须拥有独立事件调度、相位状态和增压/转子状态机；只允许共享源后基础设施。
2. A/B 必须在相同 Vehicle State 与单位 RMS 下比较时间结构、order spectrum、stem isolation 和瞬态响应，不能用 SHA、名称或总 RMS 证明身份。
3. 自动指标是防回归门禁，不替代 Jovi 的闭眼试听；报告只能写 metric-supported candidate，除非 Jovi 已确认人耳明显可分。
4. 离线响度只能使用每车固定 bundle gain，禁止逐帧或逐片段 AGC 把转速和响度重新耦合。

## 2026-07-31: 车型身份不能只靠阶次表和后端频谱差异

Pattern: Hellcat、Ferrari 458 与 RX-7 即使配置了不同 order surface，若仍复用同一燃烧、机械、流量和瞬态生成机制，经过相同 PTR/Radiation 后仍会缺少可听的发动机身份；仅在 renderer 或 EQ 后端补色不能解决时间结构缺失。

Rules:
1. 身份必须在 PTR 前作为独立 Engine Identity Layer 建模，并由单独的、全参数带 A/B/C provenance 的 profile 驱动；不得宣称 OEM measured 或真实车型复刻。
2. Ferrari 的高转身份要由随 RPM 连续增长的高频谐波和尖锐激励验证；Hellcat 的机械增压 whine 必须是与 V8 排气分开的可测声层并随负荷增强；RX-7 必须使用转子脉冲与 turbo/turbine 时间结构，不能只是 EQ。
3. 身份验收至少同时比较同 RPM 的 spectral centroid、order energy、harmonic ratio，并为三车型提供 idle、acceleration、lift、full-pull 的独立试听素材。
4. 身份层只允许接入 source -> bank mixer -> frozen PTR/Radiation 的既有前端；禁止改动 FVM、PTR core、Radiation boundary、runtime latency 或 Android protocol。

## 2026-07-30: 车速、转速与听感响度必须分层建模

Pattern: 将驾驶循环中的速度或转速上升隐含成持续增大的输出响度，会让加速段单调变响、停车怠速也失真地偏响；这不代表发动机或排气的真实声源级变化。

Rules:
1. 必须区分发动机转速（决定阶次频率）、负载/节气门/燃烧事件（决定声源强度）、挡位与传动比、排气/进气传播，以及固定麦克风到车辆的距离和指向性。
2. 怠速声源级必须由独立 idle/load 条件控制，不能沿用加速段的强度或自动增益；车辆静止不等于录音一定更响。
3. 没有经审计的固定机位、已知距离、关闭或可补偿自动增益的参考媒体时，公开视频只能作为 R2 听感研究，不能直接拟合绝对响度或速度-响度曲线。
4. Jovi 的听感纠正是模型验收失败信号；先建立可解释的声源级合同和情景级响度回归，再调整任何 gain 或发布试听文件。

## 2026-07-29: MATLAB MCP 清理必须保留当前 Codex 的 active stdio root

Pattern: 为解决历史 MCP/watchdog 膨胀，Agent 按 `matlab-mcp-server.exe` 名称停止所有匹配进程，误杀当前 Codex 任务的 active root。MATLAB Desktop 未崩，但本任务持有的 stdio pipe 被切断，后续工具调用返回 `Transport closed`。

Rules:
1. 清理前必须按 PID、父 PID、创建时间、watchdog 关系、当前 client/server log 区分 stale/unowned root 与当前 active root；不得只按同名可执行文件批量处理。
2. 当前 active root 必须保留，除非已有同一动作内的 Codex MCP bridge reattach 方案。仅有“停止所有 MCP/watchdog”的授权，也不能跳过该活跃传输归属门禁。
3. `Transport closed` 后只允许对明确新建的单一 existing-session root 做一次只读探测；再次失败即停止自动重试，标记 `BLOCKED_APP_LEVEL_MCP_REATTACH`。
4. MATLAB Desktop/MathWorksServiceHost 与 `127.0.0.1:31516` 存活时，不得把 stdio 传输失败归因于 MATLAB 崩溃或重启 MATLAB；需要恢复的是 Codex bridge。

## 2026-07-21: MATLAB compatibility helpers必须使用char元胞参数，局部函数必须先闭合再声明同级 helper

Rules:
1. `rmfield` 的字段列表在 MATLAB 中使用 `{'Category','Case'}` 这类 char 元胞；不要传入包含 string scalar 的元胞，否则会在所有 runner 路径上报 `MATLAB:rmfield:FieldnamesNotStrings`。
2. 新增 local helper 前先复核前一个函数的 `end`。遗漏一个 `end` 会把 helper 变为嵌套函数，外层入口会报 `UndefinedFunction`，并连带破坏历史 report tests。
3. 统一长任务脚本必须捕获普通失败后写结构化摘要；错误文本需要规范化为单行 ASCII 后再 JSON 序列化，并在关闭文件后用 `jsondecode` 自校验，避免失败证据本身不可解析。

## 2026-07-21: 数值等价门禁失败必须输出 case 与每个比较量，不能只报笼统失败

Rules:
1. 一条等价门禁同时比较 state、radiation、dt、residual、diagnostics、probe 时，失败消息必须给出 N、step count 与所有差值；通用“differs”文本不能支持根因判断。
2. one-step 的 uniform PASS 只覆盖固定点，不能证明多步 trace、残差和 diagnostics 的外部等价。
3. 在差值向量到手前，不得修改边界公式、容差、PP、HLLC、MUSCL 或 positivity；先审计新旧公式与采样语义并保留 fail-fast 证据。

## 2026-07-21: 外部等价的微小状态差也必须保持 reference 的精确固定点分支

Rules:
1. 外部 runner 使用 `isequal(interiorState, ambientState)` 直接返回固定点时，生成的 MATLAB Function chart 必须保留等价的 `all(interior == ambient)` 早返回；不得以代数上等价的重算替代。
2. PP diagnostics 含离散 limiter/activation 计数；即使 state 误差低于数值容差，舍入扰动仍可改变整数计数，因而不能放宽 diagnostics 容差或忽略该差异。
3. 出现“state 近零、diagnostics 整数差”的组合时，先逐项比对 reference 的固定点、分支和运算顺序，再动任何物理公式、阈值或冻结模型。

## 2026-07-21: SLX 重复性必须区分容器字节与模型语义，并规范化 Windows archive 路径

Rules:
1. Simulink 每次保存会更新 `coreProperties` 时间戳、Model/窗口 UUID、调度编辑器序列化和缩略图；raw `.slx` SHA 只能留作审计，不得作为确定性语义门禁。
2. 重复性门禁必须对所有模型内容做归一化 archive 哈希：保留 block diagram、Stateflow、系统、workspace 和数值内容；仅排除已逐条证明为 editor-only 的 `thumbnail`、`ScheduleCore`、`ScheduleEditor`、`windowsInfo`，并规范化 `coreProperties` 时间戳和 blockdiagram UUID。
3. `unzip` 在 Windows 返回反斜杠路径；在任何 allowlist 比较前必须统一为 `/`，否则看似正确的排除规则根本不会命中。
4. 报告中随容器变化的 `candidate_sha256` 必须保留为 run audit 字段，但从 stable-report 比较中移除；不能以此放宽 model semantic 或数值比较。
5. 用户要求复用现有 Desktop 执行时，主 Agent 必须自己使用唯一串行 MCP 调用并监控结果；不得把可执行验证无说明地交回用户。若本会话没有可用入口，必须先明确说明。

## 2026-07-21: `struct([])` 也不能作为带字段结构体的下标写入模板

Rules:
1. `struct()` 与 `struct([])` 都没有字段；MATLAB 对第一次 `array(index)=itemStruct` 仍执行字段兼容性检查，不能把它们当作“typed empty”模板。
2. 结构体 collector 的第一项必须直接赋值 `collection=item`，后续才追加；共享 helper 要拒绝非 scalar struct 和字段不一致项。
3. 静态检查只能证明 source contract，不能替代 MATLAB 结构体运行时语义；对语言语义不确定的修复先查官方资料或最小真实运行证据，再向用户宣称修复。

## 2026-07-21: MATLAB 结果矩阵不能用零字段 struct 预分配后再写入有字段结果

Rules:
1. `repmat(struct(), ...)` 与 `struct([])` 都是零字段结构体，不能接收 `runFeedback` 或其他带字段结构体的下标赋值；首项直接赋值后追加，或使用显式完整字段清单预分配。
2. 修复首个失败循环时必须扫描同类结果数组；feedback、external-equivalence 和 performance 等后续门禁采用同一收集模式时应一次性以同一合同覆盖。
3. 静态函数体提取必须锚定精确函数声明和下一个函数声明，不能让跨行 `.*` 从脚本首个主函数开始吞掉目标；否则“通过”的测试并没有审计目标实现。

## 2026-07-21: feedback clone 必须替换完整的 bootstrap 扇出，而不是只替换首个输入

Rules:
1. 从 one-step model 派生 Unit Delay feedback clone 时，先审计 `U0/X0` 的全部目的端口；每个 SSP-RK3 stage 的原始状态输入和每个 radiation stage 的原始辐射状态输入都必须替换。
2. 分支源不能靠 `delete_block(U0/X0)` 隐式清理。应逐个目标端口读取既有 line，以 `delete_line(model, sourcePort, destinationPort)` 删除该分支，再接入 memory，最后才删除已无连接的 bootstrap Constant。
3. 普通 `connect` 保持 fail-closed，禁止静默覆盖已连接目标端口；只有名称明确的 `replaceInput` 可执行受控替换，且必须验证端口已释放。
4. 反馈拓扑合同必须静态锁定四条 state 和四条 radiation 基准输入；否则 one-step PASS 或零 warning model_check 不能证明多步 feedback 可用。

## 2026-07-21: 先重建 formal candidate，再把 zero-warning `model_check` 当作后续门禁

Rules:
1. one-step generator 的拓扑修复只存在于脚本源代码时，旧 formal candidate 仍保留旧端口结构；统一 runner 必须先事务性重建 candidate，再做独立 `model_check`。
2. 对刻意不参与数值主路径的 PP 输出，必须显式接 `Terminator`；不能以忽略 `unconnected_ports` 警告、放宽零警告门禁或修改冻结 PP 来绕过。
3. 重新构建后必须核对 one-step JSON 的 `candidate_sha256` 和 `frozen_pp_sha256`，且所有固定尺寸 update/simulation case 通过，才允许继续 model_check。
4. 无 crash、未保存模型的确定性脚本或 model_check 失败可以离线修复后在同一稳定 Desktop 重跑；只有 access violation、新 crash dump 或模型完整性漂移才要求停止并请求重启。

## 2026-07-20: 构建模板与正式输出必须路径分离并通过重复运行门禁

Rules:
1. 事务脚本不得把同一 candidate 路径同时作为模板输入和成功后的正式输出；第一次写入后，第二次运行必须仍能定位稳定源模型。
2. 模板块从冻结/稳定源模型读取，formal candidate 只作为输出；transaction backup 仅用于 rollback/audit，不能成为长期运行依赖。
3. one-step 成功后必须验证重复运行；第二次 build/update/sim 失败时，先检查输入输出路径复用，再归因数值模型或 MATLAB 环境。
4. 模板源 SHA、formal candidate SHA 和报告 SHA 应分别记录；首次 PASS 后的二次失败不能抹杀已验证的首次证据。

## 2026-07-20: 同一个 ambient 输入不得混用 primitive 与 conservative 语义

Rules:
1. `ambientState=[rho;rho*u;E]` 进入生成 chart 后必须先统一通过 `primitive` 解码；禁止在另一分支把 `ambient(3)` 直接当压力。
2. small-signal 门禁触发时先验证零扰动固定点和单位/表示合同，不能通过放宽阈值掩盖状态表示错误。
3. 内联生成公式必须逐项对照正式 reference 的 `rho0/p0/c0` 数据流，并用零扰动 `outgoing=0` 静态 fixture 锁定。
4. 连续集成失败超过三次时重新审计生成-source 架构边界；本次确认 fixed-size one-step 架构可保留，缺口在生成 chart 缺少独立编译/固定点门禁。

## 2026-07-20: MATLAB Function chart 的带冒号 error 必须同时提供消息文本

Rules:
1. 生成给 MATLAB Function/Stateflow Coder 的 `error` 若首参数是 `domain:component:id`，必须提供第二个固定消息文本参数。
2. 修复时扫描全部生成 source，而不是只修诊断指出的第一个 chart；同一 source 被复制到多个 chart 时用静态计数锁住全部实例。
3. 在请求下一次 MATLAB 集成前，静态门禁必须证明 identifier-only error 数量为 0。

## 2026-07-20: Simulink Constant 的 1-D 默认值会破坏行列矩阵合同

Rules:
1. State-space `A/B/C/D` 和 state 输入通过 Constant block 注入时，显式设置 `VectorParams1D='off'`，保留 `1xN` 与 `Nx1` 的方向；不能依赖默认 1-D 向量推断。
2. 维度错误应在信号源头修复，保持已经验证的矩阵公式不变，不用逐元素展开掩盖传播合同问题。
3. `Simulink.FileGenConfig` 对象只能通过 `fileGenControl('setConfig','config',cfg)` 恢复；`'set'` action 只接受名称-值参数。
4. file-generation config 会影响 MATLAB path；cleanup 必须先恢复 config，最后恢复精确 path 快照。

## 2026-07-20: `run` 脚本的资源清理必须使用函数作用域，block 参数以目标版本为准

Rules:
1. 会由 `run(...)` 重复执行的 MATLAB 脚本，不得在顶层创建长期存活的 `onCleanup` 变量；用单一局部主函数包住事务执行，让 cleanup 在函数返回或报错时确定执行。
2. 新入口变量不得复用旧 base-workspace cleanup 名称，避免覆盖旧对象时先触发过期回调。
3. Simulink block 参数不能从其他版本或其他 block 类型类推；目标 R2026a 运行时拒绝的参数立即删除，并用静态合同锁住禁用项与保留项。
4. MATLAB 未崩溃且错误栈进入用户脚本时，分类为确定性脚本缺陷；不要上升为 runtime、MCP、PP 或 Stateflow blocker。

## 2026-07-19: MATLAB/Stateflow metadata extraction must normalize before MCP

Rules for metadata and contract scripts:

1. Normalize property-name casing, empty values (`inherit`/default), and
   char/string/cell/numeric return shapes before applying assertions.
2. Cover empty, scalar, vector, missing-field, and inherited-value fixtures in
   static/mock checks before an MCP call.
3. Do not attribute script field/shape failures to MATLAB, Stateflow, or the
   model; complete script-side fixes in the parent session first.
4. Keep one safe-scope read/normalize/validate/report operation in one call;
   use transactional output so a failed extraction cannot overwrite a valid
   report.

## 2026-07-18: R2026a MATLAB Function chart 脚本必须是 scalar char

阶段 3 的内存 smoke 中，给 `Stateflow.EMChart.Script` 传入字符串数组导致脚本未正确写入，随后产生“输出参量 `y` 未定义”和输出尺寸欠定的误导性诊断。规则：构造 MATLAB Function chart 脚本时使用单个 scalar `char`（例如 `sprintf(...)`），再做固定维度编译 smoke；该错误与 driver/PP 数值逻辑无关。

## 2026-07-18: 已有 agentic MATLAB 时禁止 -batch 启动新实例

Jovi 纠正：Sprint 4D-B 接手时，已有 agentic MATLAB 37988 运行，我用 matlab -batch 启动新实例做 smoke，触发 mwhomesessionmanager_impl.dll GTP 线程 access violation 崩溃。崩溃污染全局状态，导致后续所有 MATLAB 启动（含 Jovi 桌面端）都崩溃，Jovi 不得不重启电脑。

Rules:
1. 已有 agentic MATLAB 会话运行时，禁止 matlab -batch / matlab -nodesktop -r 启动新实例；agentic session 和普通 session 共享 Home Session Manager / GTP 全局状态，新实例崩溃会污染这些状态。
2. MATLAB 自动化只用 MCP evaluate_matlab_code 复用现有会话（matlab-mcp-server.exe --matlab-session-mode=existing，stdio JSON-RPC via node_repl）。
3. access violation 是硬门禁，首次崩溃立即停止启动尝试，不重试 -softwareopengl/-nodesktop 等变体（lessons 2026-07-15 已预警）。
4. 崩溃后保存 crash dump 路径+SHA+进程清单+最小复现到 tasks/reports/runtime/sprint-4d-b/，请 Jovi 重启电脑清理状态，不要继续尝试启动新实例。
5. R2026a API 兼容：find_system 搜索条件在名称-值前；checkDiagram 不存在用 set_param update+sldiagnostics；Stateflow data 用 sfroot().find 最稳健。
6. 详见 Obsidian: 03-项目记忆/tesla-speed/07-MATLAB环境与崩溃治理经验.md。

## 2026-07-18: 重启桌面 MATLAB 前必须先关闭旧 MCP 会话

本次恢复协调中的补充教训：即使 Codex 没有直接执行 `-batch`，只要旧 agentic MATLAB/MCP 会话仍存活，就不能让 Jovi 启动第二个桌面 MATLAB。重启前必须关闭 Codex/MCP watchdog，并确认没有 `matlab.exe` 或 `matlab-mcp-server.exe` 残留；重启后先单独验证 MATLAB 桌面端稳定，再重新建立 existing-session MCP 连接。

## 2026-07-13: Benchmark 产物必须从 Canonical Result 单向生成

Sprint 0.5 验证：Markdown、CSV、JSON 和 PNG 若分别维护数据，会产生 acceptance 漂移与无意义 diff。PNG 的 `tIME` 元数据即使像素完全一致也会造成二进制变化。

Rules:
1. Case 只在 analyze/accept 阶段计算一次指标与 acceptance；Report 只能读取 Canonical Result，不得重算。
2. 所有视图使用固定文件名、排序和 `%.12g` 数值格式；不写当前 wall-clock 时间。
3. PNG 输出后移除 `tIME` chunk，并用跨目录字节对比测试确定性；不能只比较肉眼或像素。
4. 普通运行写 ignored `benchmark/out/`；accepted baseline 只能用显式 token 从 passing manifest 提升。

## 2026-07-13: model_edit 后必须显式保存再做磁盘重载验证

Sprint 0.5 首次连接 periodic SSP-RK3 stage model 时，`model_edit` 返回成功且内存测试可见连线，但未 `save_system`；关闭后磁盘模型仍未连线。

Rules:
1. 每批 `model_edit` 结构修改后立即 `save_system`，再关闭并从磁盘重新加载。
2. GREEN 不能只依赖同一 MATLAB 会话中的已加载模型；至少一次冷重载专项测试。
3. 提交前同时运行 `model_read`/`model_check` 与行为测试，结构成功响应不能替代持久化证据。

## 2026-07-14: 冻结 Simulink 数值模型的模式扩展应优先派生模型，而不是追加动态端口

Sprint 2 首次尝试把 reconstruction selector 接入已冻结的 SSP-RK3 和 periodic FVM MATLAB Function 图。Stateflow 的新标量输入改变了既有动态状态端口的尺寸传播，导致 `[3xN]` 状态和标量常量出现一维/二维不匹配；`model_check` 健康不足以证明模型可编译。

Rules:
1. 若模式输入会影响冻结模型的 Stateflow 维度推断，保留冻结模型并创建命名清晰的专用派生模型，由 adapter 显式选模。
2. 模型模式切换的回退证据必须比较最终状态和守恒残差，并将一阶 Full Benchmark 的非运行时指标逐项对照 accepted baseline。
3. `model_check` 后仍须执行冷重载行为测试；Stateflow 的端口宽度问题只能由实际 compile/sim 发现。

## 2026-07-14: MATLAB 结构体数组新增字段必须在完成预分配后统一添加

Periodic SSP-RK3 adapter 先给第一个结果添加 `reconstruction`，随后尝试写入缺少该字段的第二个 `runOne` 结果，MATLAB 报“在不同结构体之间进行下标赋值”。

Rules:
1. 结构体数组的公共字段由构造函数一次性提供，或在所有元素生成后统一添加。
2. 每次扩展 adapter result schema 后，都要运行 multi-dt smooth-wave 回归；单步或单结果测试无法覆盖这个问题。

## 2026-07-13: Child Claude final-only JSON 需要 90 秒完成边界

Jovi 纠正：连续三次 Child Claude 调用都有不同 `processId`、空 `launchError`，并在约 30.5 秒精确终止，stdout/stderr 均为空。这证明子进程已成功启动，只是 CLI 在任务完成前不流式输出 JSON，被 30 秒总超时过早终止；不能据此判断 API key、模型、派发或子进程启动失效。

Rules:
1. Child Claude 使用 30 秒存活检查、90 秒总完成边界；同步调用方至少等待 100 秒。
2. 非空 `launchError` 是启动失败；正常结束但无有效 JSON 是结果畸形；到 90 秒被终止是完成超时；进程仍存活且 stdout/stderr 为空只是运行中。
3. 诊断保留 `processId`、`launchError`、elapsed、`Success`、`TimedOut`、`Turns`、`Result`、`Stderr` 和 `RawStderr`；不得把“无流式输出”单独当作卡死证据。
4. 只有最终结构化结果可以被接受；90 秒超时仍不接受部分输出，并按新会话重派、三次后主代理接管的门禁处理。

## 2026-07-15: Sprint 4B 先做 Simulink standalone create/run smoke，access violation 是硬门禁

Sprint 4B 的 source/boundary RED→GREEN 已通过，但 R2026a standalone MATLAB 在 `new_system`、受控 rename-save 和已有 PP 模型单步运行中均以同一 `0xc0000005` access violation 在约十秒终止；同时 Simulink MCP 无法附着会话。此时不能通过复制 `.slx`、手工 XML、外部脚本替代或伪造 model_check 绕过“新增受控 FVM 模型”要求。

Rules:
1. 涉及新 `.slx`、Stateflow 或 model reference 的 Sprint，先运行无副作用 `new_system` smoke 和既有模型单步 smoke；两者均通过后再开始模型结构编辑。
2. 若 standalone crash，保留 crash dump 路径、命令、时间、退出码、旧模型哈希和未生成模型的证据；用 tasks blocker report 记录，不把未验证结论写入 Obsidian。
3. 只要新模型、model_check、Full qualification 或 report-only 依赖该 runtime，就把它视为真实硬阻塞；不得提交 failed-test WIP 或推进 accepted baseline。
4. runtime 恢复后从受控 RED 和已绿 source/boundary contracts 继续，先验证旧模型运行，再重新尝试 `model_edit`；不要假设崩溃期间的缓存或工作区状态可复用。

## 2026-07-12: 将 Child Claude 纳入有门禁的执行候选

Jovi 补充：后续遇到适合外派的执行工作，可以使用全局 `child-claude` skill。

Rules:
1. 先比较 Codex 直接执行成本和派发、复核、纠错成本；只有预期净节省明显时才派发，不能因为任务可并行就默认外派。
2. 文件任务始终传绝对 `-WorkingDirectory`，在 dispatch slip 中写清唯一目标、允许路径、验收和禁止范围。
3. 只读审计限制为不超过 5 个已知文件，使用 `Read,Glob,Grep`、`MaxTurns 3`、`TimeoutSeconds 60` 和诊断文件；超时后不盲目重试。
4. 写任务必须显式允许 `Write` 或 `Edit`；Codex 必须检查结构化结果、实际 diff 并独立运行验收，不能直接接受 Child Claude 的成功声明。
5. Codex 始终保留计划、集成、代码审查和最终验证责任。

## 2026-07-09: Read the Whole ESP-IDF Log Before Calling It a Failure

Correction from Jovi: he pasted the actual EIM/PowerShell build output after saying VSCode still could not compile.

Root cause: the pasted log contained scary non-fatal lines (`micro-ecc` submodule out of date, `fatal: Needed a single revision`) but the end of the log clearly said `Project build complete` and generated `tesla_simulate_vico.bin`.

Rules:
1. For ESP-IDF build logs, always classify by final exit status and terminal success marker first: `Project build complete`, generated `.bin`, and command exit code.
2. Treat CMake/Git text in the middle of the log as diagnostic evidence, not automatically as a build failure.
3. When a user says VSCode cannot compile, ask or inspect whether the failure is build, flash, monitor, or extension UI state; these are different root causes.
4. If ESP-IDF installation cleanup requires network submodule fetches, verify whether the warning blocks build before mutating the toolchain directory.

## 2026-07-09: ESP-IDF Build Proof Must Capture Stderr Like VSCode Does

Correction from Jovi: I said the project could compile, but his VSCode/PowerShell path still failed.

Root cause: the machine PATH had `D:\Python\Python3.14\Scripts\ninja.exe` version `1.13.0` ahead of ESP-IDF's bundled `ninja 1.12.1`. ESP-IDF printed an unsupported-ninja warning to stderr. A plain build could continue, but VSCode/log-capture/strict PowerShell could treat that stderr as a `NativeCommandError`.

Rules:
1. For ESP-IDF build proof on Windows, run at least one verification with stderr captured, for example `.\scripts\esp-idf.ps1 build *>&1 | Tee-Object ...`, not only a plain terminal build.
2. Always check `where.exe ninja` and `ninja --version` when ESP-IDF build behavior differs between VSCode and terminal.
3. Project build helpers should prepend the ESP-IDF bundled Python, Ninja, and CMake paths before calling `export.ps1`.
4. If a warning can break the user's actual tool path, report it as a real environment risk, not merely "non-blocking".

## 2026-05-21: 需求澄清 — 用户原话的精确解读

**教训**: 当用户说"不需要X"时，务必确认X的范围。

**经过**: 用户最初说"不需要屏幕，能串口打印就行"。我理解为"不需要屏幕"。
Claude 理解为"不需要按钮"。经过四轮争论后，用户明确：**"不需要屏幕和按键"**。
双方各错一半——我加了不该加的按键，Claude 漏掉了不该漏的"屏幕"二字。

**规则**: 
1. 用户的原话逐字记录，不要自行扩展
2. 如果两个 AI 对同一句话有不同解读，直接向用户确认
3. 不要花六轮争论一个可以通过"Jovi，你具体是指 A 还是 B？"解决的问题

# Lesson: Never Skip Pins on Schematic Symbols (2026-05-31)

ESP32-S3-WROOM-1 N16R8: 44 physical pads, not 24.
ALL pins must be shown on schematic symbol, not just connected ones.
Left:  GND,3V3,EN,IO0-IO21 (25 pins)
Right: IO26(NC/Flash),IO33-37(NC/PSRAM),IO38-IO48,3V3,GND (19 pins)
IO34=PSRAM NC -> potentiometer moved to IO1.
Rule: Count ALL pins first, list them all, then connect nets.
Speed is never an excuse for incomplete symbols.

# Lesson: Altium SchLib Context Is Volatile (2026-05-31)

When using `eda-agent` direct bridge library commands, do not assume the active document remains a SchLib after each library mutation.

Rules:
1. Before every `library.create_symbol`, `library.set_current_component`, `library.add_pins`, or symbol-geometry edit, explicitly call `application.set_active_document` for `MyComponents.SchLib`.
2. Save the library before placing newly created symbols into SchDocs; otherwise `place_sch_components_from_library` can return `RESOLVE_FAILED` even though `library.search` later finds the symbols.
3. Direct command `generic.set_sheet_size` requires `style=A3`, not `size=A3`; `generic.sch_set_sheet_size` is not a valid bridge action.

# Lesson: Placeholder Schematics Are Not Hardware Schematics (2026-05-31)

Correction from Jovi: the `_CDX6` rebuild was unacceptable. It used crude placeholder symbols, floating net labels, oversized notes, and disconnected/red-crossing wires. AD reported many warnings, BOM still contained stale/duplicate parts, and every sheet violated normal schematic drafting standards.

Rules:
1. Do not call a schematic "rebuilt" if components are only boxed placeholders with floating net labels. Real schematic pages need readable symbols, sensible pin orientation, real wires/ports/power ports, values/MPNs where known, and clean annotation.
2. Do not use `design_validate passed=true` as success when warnings are dominated by floating labels, duplicate nets, missing models, duplicate designators, off-grid objects, or unconnected objects.
3. After clearing/rebuilding, verify BOM and compiled project no longer contain stale old components. Query components by sheet and compare against the intended BOM; screenshot review matters.
4. Notes are not a substitute for circuit implementation. Keep notes small and outside the circuit area.
5. If a first architecture produces unreadable pages across multiple sheets, stop and re-plan. Do not keep patching coordinates.
6. Safer recovery action after a failed AD rebuild: back up the failed result, restore the pre-change hardware backup, then design a real symbol/wiring strategy before touching SchDoc again.

# Lesson: Do Not Trust Merged BOM Status Markers (2026-06-05)

Correction from Jovi: another AI produced `Tesla_BOM_20260604_agent_all.tsv` with many C-code corrections, but the final merge still retained wrong rows and duplicate refdes. Some rows marked `✅` were still wrong, for example `C84258` was labeled red LED even though LCSC shows it is a white LED, and ESP32-S3-WROOM-1-N16R8 used an incorrect C code instead of `C2913202`.

Rules:
1. A merged BOM is not valid until refdes uniqueness is checked across the entire file. Duplicate designators like `U3`, `D3`, `R10`, `L4`, and overlapping capacitor ranges must block release.
2. Never trust `✅`, `verified`, or agent status text without independent C-code lookup against LCSC/JLCPCB/EasyEDA pages.
3. For each BOM row, verify at least: supplier code, manufacturer part number, value/model, package/footprint, and whether the part is a substitute or exact match.
4. If a row is marked `TODO`, `经验值`, `候选替代`, or has unclear stock/package evidence, keep it out of a production PCBA BOM or mark it `需复核`.
5. When multiple agents produce partial BOMs, the final merge must delete superseded wrong rows; do not keep both the wrong row and the corrected row.
6. Record an audit report beside the BOM before presenting it as usable for ordering.

# Lesson: Audit the Audit Baseline Before Accepting BOM Criticism (2026-06-05)

Correction from Jovi: another AI audited the Tavily BOM and correctly found many refdes mapping errors, but it also treated `Tesla_BOM_20260604_agent_all.tsv` as if it were a clean truth source. That merged TSV still has duplicate designators and known wrong rows, so an audit can be directionally right while its final recommendation is still unsafe.

Rules:
1. Before comparing two BOMs, first validate the baseline BOM itself: unique refdes, no stale rows, no duplicate page-local designators, and no status markers hiding wrong C codes.
2. For schematic-derived BOMs, never assume `J10/J11/J12` or `U5/U6/U7/U8` from an older AD/TSV file are still current. Check the current EasyEDA/AD schematic state or the latest verified design record.
3. Treat cross-page duplicate refdes as a release blocker. If `R10` exists on both MCU and CAN pages, any row-level comparison can falsely accuse the other BOM of using the wrong value.
4. When a reviewer says "actual should be X", record which source establishes "actual": current schematic, exported BOM, design spec, or an older candidate BOM.
5. Do not accept "use this one as the base" unless that file passes structural and C-code audits. Candidate pools are not production BOMs.
6. Tool errors matter: if Tavily or another MCP returns `socket hang up`, `stream aborted`, or partial results, log the failed query and verify through another source before writing a confident C-code conclusion.

# Lesson: Search Failure Is Not Negative Evidence for LCSC Parts (2026-06-05)

Correction from Jovi: I previously wrote that `C86367` was not proven to be `SMBJ5.0A`. A later direct LCSC extraction confirmed `C86367` is Changzhou Starsea Elec `SMBJ5.0A`, with key attributes `TVS DIODE 5VWM 9.2VC SMB(DO-214AA)`.

Rules:
1. If a search query does not return a part page, do not conclude the C code is wrong. Mark it as "not yet verified" and try direct URL extraction: `https://www.lcsc.com/product-detail/<Ccode>.html`.
2. For LCSC/JLC parts, prefer direct page extraction over search snippets when resolving conflicts.
3. If Tavily returns `socket hang up` or a page extraction omits table fields, retry with another source or direct URL before publishing a negative finding.
4. When correcting a previous audit error, edit the old audit report as well as writing a new response, so the next AI does not inherit a stale false warning.
5. Multi-page duplicate refdes can explain how a conflict was created, but it does not make the production BOM valid. A JLCPCB order BOM must still have full-board unique designators.

# Lesson: Stock Numbers Do Not Validate a BOM C-Code (2026-06-06)

Correction from Jovi: another AI changed R3 1kΩ 0805 from `C17513` to `C232761` because it believed `C232761` was LIZ `CR0805F81001G` with high stock. Direct LCSC extraction showed `C232761` is actually onsemi `MB8S`, a bridge rectifier in SOIC-4. The correct LIZ `CR0805F81001G` code is `C101404`, while `C17513` also directly verifies as UNI-ROYAL 1kΩ 0805.

Rules:
1. Never accept a replacement C-code from a stock claim alone. Verify component class, MPN, value, tolerance, power rating, package, and footprint.
2. If a row says "LIZ CR0805F81001G", direct-extract that exact C-code and ensure the page title/MPN matches. A mismatch like `C232761 = MB8S` is a release-blocking error.
3. A high-stock wrong part is worse than a low-stock correct part. Keep the correct low-stock row or mark TODO until a verified replacement is found.
4. Connector availability matters separately from pin count. `C5116482` matches 1x3P, but if LCSC says `Not available now`, it remains a procurement risk, not a solved BOM row.
5. After splitting a BOM line into `54a/54b`, recompute row count and status count; do not keep saying "54 rows" if there are 55 data rows.

# Lesson: Cross-Audit Timing and Document State (2026-06-06)

When AI-A audits a BOM and AI-B responds with corrections, AI-C (the next reviewer) must check the CURRENT file state, not just the documents' descriptions of the file state.

Rules:
1. Before judging "file still has error X", read the actual file. The response document may describe an older state than the file currently holds.
2. C13850 example: the response document says "保留📋C13850" but the actual BOM file already has `⚠️C134973`. Document descriptions and file state can diverge.
3. When an audit response says "已修正", verify the correction actually landed in the target file, not just that the response document describes it.
4. LCSC 404 is strong evidence a C-code doesn't exist (C69851). Search failure is NOT evidence (C86367). Distinguish between direct-URL-404 and search-no-results.
5. Both the reviewer and the responder agreed: "从 EasyEDA 导出唯一位号 BOM" is the only correct path to an ordering BOM. When multiple parties converge on the same conclusion, prioritize it.

## Verify Stock on Current Direct Product Pages, Not Cached Summaries (2026-06-06)

- Pattern: Another audit claimed `C910544` MAX98357AETE+T had stock=0, but the current LCSC direct product page showed the correct part, package, and in-stock quantity. Search snippets, category pages, EasyEDA library state, and older audit notes can be stale or disagree with the direct product page.
- Rule: For BOM procurement status, verify the current LCSC/JLC direct product page正文 first. Record whether the evidence came from direct page, search snippet, EasyEDA model, or cached category page.
- Rule: Header candidates such as `C5116482` and `C5156614` can be type-correct while still unusable for ordering if the direct page says `Not available now` or `Out of Stock`; mark these as procurement risk, not solved.
- Rule: When a BOM file changes between audits, explicitly state the timestamp/current line state before accepting or refuting older reports.

## LCSC Does Not Carry Automotive Diagnostic Connectors (2026-06-07)

- Pattern: OBD-II 16P DLC Type B 母座在 LCSC 搜索无结果。LCSC/JLCPCB 面向消费电子/工业，不销售汽车诊断座。
- Rule: 对于汽车专用连接器 (OBD-II, CAN bus diagnostic port)，不要在 LCSC 费时搜索。直接建议淘宝/1688 搜 "OBD2 母座 16P 带线" 手工焊接。
- Rule: 淘宝采购的元件不能用于 JLCPCB SMT 贴装，必须手工焊接或标记 DNI。
- Rule: PTC 自恢复保险丝 5A+ 需要 2920 或更大封装，SMD1206/1812 物理极限约 2A。搜索时直接限定封装规格。

## F3 PTC 5A 封装变更记录 (2026-06-07)

- Pattern: 原设计指定 F3 = PTC 5A 1812 封装 (`FUSE-SMD_1812`)，但 LCSC 上 5A PTC 最小可用封装是 2920。
- Solution: C6165172 BORN SMD2920-500/24N (5A hold, 24V, 2920)。PCB 布局需确认 2920 空间。
- Rule: 如果 PCB 已按 1812 layout，换 2920 前必须检查 footprint 兼容性。

## LCSC 排针搜索陷阱：同名不同料 (2026-06-07)

- Pattern: BOOMELE `2.54-1*5P` 在 LCSC 有两个 C 码：C50950 = CONN **SOCKET** (母座)，C138801 = CONN **HEADER** (公针) 但是 **Right Angle** (弯脚)。同理 `2.54-1*3P` 也有母座和公针版本。
- Solution: 当精确匹配的预切排针无货时，改用 1x40P 长排针裁切。C2337 BOOMELE 2.54-1*40P 直针公排针，库存 81k+，$0.16/条，1 条裁出 5P+5P+3P。
- Rule: LCSC 搜索排针时，必须验证 Key Attributes 中的 "CONN HEADER" (公) vs "CONN SOCKET" (母)，以及 "Through Hole" (直) vs "Right Angle" (弯)。同 MPN 不同 C 码可能是完全不同的元件。
- Rule: 排针无货时优先考虑长排针裁切策略 (1x40P → NxP)，而非逐个搜索短排针替代料。

## 待验证 C 码不能进入严格下单 BOM (2026-06-07)

- Pattern: 合并报告把 `C32346` 保留为 1mH CMC 待验证项，但直链核查显示它实际是 EPSON `Q13FC13500004` 32.768kHz 晶振/SMD3215。`C72043` 也不是 0805 绿色 LED，而是 0603 且不可用。
- Rule: `📋`、经验值、待验证项必须默认进入阻塞/手工页，不能进入 JLCPCB SMT 下单页。只有直链确认 C 码、MPN、封装、关键规格和可用状态后才能进入 `下单BOM`。
- Rule: 对 CMC、电感、PTC 这类封装/电流敏感器件，即使找到功能替代料，也不能偷偷替换进 BOM；如果封装变大，必须先确认 PCB footprint。
- Rule: 生成严格 BOM 时必须展开为 `1 refdes = 1 row` 并检查全表唯一位号。跨页重复如 `U3/D3/R10/C10-C14/C21/C22` 必须输出位号修正清单并同步原理图、PCB 和 CPL。
- Rule: 如果 spreadsheet artifact 工具初始化失败，记录错误原因并使用可验证的备用生成工具；但最终仍要做供应商编号、重复位号和错料剔除校验。

## BOM 二次审核：错料确认与模块内置晶振 (2026-06-07)

- Pattern: 外部审核指出 `C2054018` 是 F1 PTC 的 CRITICAL 错料；EasyEDA/LCSC 器件库核实它实际是 Microchip `DSPIC30F6012AT-30I/PT` TQFP-64 MCU。此前只写“未完成直链确认”不够明确，下一位 AI 可能继续拿它当候选 PTC。
- Rule: 对保险丝、PTC、CMC 这类保护/EMI 器件，若 C 码核实为完全不同器件类型，必须写成 `CRITICAL wrong code / DNI`，不能只写“待确认”。
- Pattern: `C910544` 被另一份审核列为库存 CRITICAL，但当前 LCSC 直达页显示 `MAX98357AETE+T`、`TQFN-16-EP(3x3)` 且有现货。库存判断具有时效性，旧审核或搜索摘要不能覆盖当前直达页。
- Rule: 库存争议用当前 LCSC/JLC 直达页裁决；如果直达页有货，只保留“下单当天复查库存”的普通风险，不升级为 CRITICAL。
- Pattern: `C5380316` 是正确 40MHz 晶振，但设计采用 `ESP32-S3-WROOM-1` 模块，Espressif 官方模块框图已包含 40MHz crystal。正确 C 码也可能因为设计上下文错误而不该贴装。
- Rule: 模块类器件要先检查模块 datasheet 的集成元件。若模块已集成晶振、flash、PSRAM 等，不要把裸芯片外围件放进 SMT 下单 BOM；移到 DNI/设计待确认，并同步 EasyEDA PCB/CPL。

## 替代料不能只按“同类器件”采纳 (2026-06-07)

- Pattern: 二次审核提出 `C968441` 作为 F1 PTC 替代。直达页确认它确实是 Jinrui `JK-SMD0805-050-16V` 0805 PTC，但它是 500mA hold / 16V 等级，不能自动替代 BOM 原标的 `2A 0805`。
- Rule: PTC 替代料必须同时匹配 hold current、trip current、maximum voltage、封装、焊盘和应用位置。若只是“PTC 且有货”，只能记为候选，不得进下单 BOM。
- Pattern: 二次审核提出 `C95572` 作为 L1 CMC 替代。直达页确认它是 TDK `ACT1210-510-2P-TL00` CMC，但规格为 51uH/200mA/SMD-4P，应用为 CAN-BUS/FlexRay；不满足旧 L1 `1mH/12V 电源路径` 语义。
- Rule: CMC 替代料必须先确认用途是信号线、CAN 总线、USB 数据线还是电源输入。信号线 CMC 不能直接替代电源路径 CMC/电感，即使 C 码、库存和封装都看起来合理。

## 文档归类和版本命名不要破坏工程结构 (2026-06-12)

- Pattern: `docs`、`hardware`、`hardware_lc`、`hardware_lc2` 中混有 PRD、计划书、审核稿、BOM 候选、终版 BOM 和 EDA 工程文件。若只看文件名，很容易把历史稿、候选池或失败工程当成当前入口。
- Rule: 项目自有文档可以在文件名后追加 `__类别-v日期-来源-状态`，并维护 `docs\DOCUMENT_RENAME_MAP_vYYYYMMDD.tsv` 和 `docs\DOCUMENT_INDEX_vYYYYMMDD.md`。
- Rule: 不要批量重命名 `docs\reference`、`node_modules`、EasyEDA skill 内部文件、`.SchDoc`、`.PrjPcb`、`.eprj2`、`.epro2` 等工具依赖文件。工程目录用 README 标注版本和用途，而不是改动工程文件名。
- Rule: 命名里的 `candidate`、`draft`、`history`、`review` 不能作为终版依据；当前入口必须在文档索引中明确标为 `current` 或 `final`。

## EasyEDA PCB 放置 API 需要小批量和上下文校验 (2026-06-07)

- Pattern: `pcb_Document.importChanges('9f57e4e51b43a5a2')` 在关联 PCB 上返回 `false`，PCB 组件数仍为 0。不能假设“从原理图导入变更”一定会生成 footprint。
- Solution: 用终版 BOM 的 LCSC C 码调用 `lib_Device.search(C码)`，再用 `pcb_PrimitiveComponent.create(device, TOP, x, y)` 创建 footprint，并随后设置 designator/supplierId。
- Rule: 每次调用 PCB API 前先打开 PCB 文档 `dmt_EditorControl.openDocument(pcbUuid)`；`sch_PrimitiveComponent.getAll` 和 `pcb_PrimitiveComponent.getAll` 都依赖当前文档上下文。
- Rule: EasyEDA bridge `/execute` 约 30 秒会超时；批量创建元件必须拆成小批，建议每批 3-6 个。超时后先枚举 PCB，可能已有部分对象被创建。
- Rule: `pcb_PrimitiveComponent.create()` 偶发 `Cannot read properties of null (reading 'attrsMap')`，`getAll()` 偶发 `Cannot read properties of null (reading 'map')`；遇到时重新打开 PCB 文档、缩小批次、跳过已存在位号后重试。
- Rule: 超时重试可能造成重复位号；补放前必须比较期望位号和当前 PCB 位号，删除重复对象后再继续。

## 嘉立创 Pro 控制链路不要和 Altium MCP 混用 (2026-06-13)

- Pattern: 用户同时提供 `E:\easyeda-api-skill` 和 `E:\project\EDA_agent` 时，容易把 Altium 的 `eda-agent` MCP 当成嘉立创 Pro 控制入口。
- Rule: 嘉立创 Pro / EasyEDA 操作用 `easyeda-api-skill`，链路是 `bridge-server.mjs -> run-api-gateway.eext -> eda.* API`；`E:\project\EDA_agent` 只用于 Altium Designer / AD。
- Rule: 每次 EasyEDA 操作前先查 `http://127.0.0.1:49620/health`，再查 `/eda-windows`。只有 `edaConnected=true` 且窗口数大于 0，才能调用 `/execute`。
- Rule: 如果 `node scripts\bridge-server.mjs` 报 `ERR_MODULE_NOT_FOUND: Cannot find package 'ws'`，先在 `E:\easyeda-api-skill` 执行 `npm install`。
- Rule: `/health` 返回 ok 但 `edaConnected=false` 时，不是 API 代码错误，而是嘉立创 Pro 侧 `run-api-gateway.eext` 没安装、没启用、没权限或没连上。
- Rule: `ws://127.0.0.1:8765/bridge/ws` 是 EasyEDA MCP 配置面板路径，和 `easyeda-api-skill` 的 `http://127.0.0.1:49620/execute` 是两条不同链路。当前项目优先使用后者。

## EasyEDA 原理图重绘 API 细节 (2026-06-13)

- Pattern: `SCH_PrimitiveWire.create()` 文档写 `Array<number> | Array<Array<number>>`，但当前 EasyEDA bridge 对二维点数组 `[[x1,y1],[x2,y2]]` 返回 `create failed!`。
- Rule: 创建 wire 必须使用扁平数组 `[x1, y1, x2, y2]`；不要用二维点数组。
- Pattern: 部分 LCSC 库器件搜索成功但 `sch_PrimitiveComponent.create()` 仍会失败，错误为 `create failed!`。
- Rule: 批量放置时每个器件必须 try/catch；失败后降级为视觉规范框并记录供应商/封装/DNI 状态，不能让单个器件中断整页。
- Pattern: `SCH_PrimitivePin.create()` 只能在符号编辑器使用，普通原理图页创建后不可查询，`sch_PrimitivePin.getAll()` 返回 0。
- Rule: ESP32-S3 44-pin 验证不能靠普通原理图页的 standalone pins；必须用 `LIB_Symbol.openInEditor()` 进入符号编辑器创建/验证 44 个 symbol pins，再把符号关联为 device 替换 `U3_MCU`。
- Rule: `C50144` 搜索返回多个候选，首项可能不是 `TPA3116D2DADR`；`C2337` 也会返回无关 IC。用 C 码搜索后必须按 MPN/名称二次筛选。

## 原理图不能用 BOM 摆放或视觉框冒充 (2026-06-13)

- Pattern: 用户要求“先画原理图”，但批量脚本把重点放在 BOM 行、供应商编号和占位视觉框上；虽然操作的是 schematic page，不是 PCB，但视觉结果不像规范电路原理图。
- Rule: 原理图优先任务必须先满足电路阅读习惯：真实符号、真实网络、模块从左到右、少量局部注记、线不穿器件、文字不压线。BOM 属性和供应商编号是次要属性，不能主导布局。
- Rule: 库器件创建失败时，不能默认用大矩形视觉框替代并宣称完成；应先选择通用原理图符号或自建 Sch symbol，实在无法放置才标为阻塞。
- Rule: “只画原理图”不等于放 PCB footprint，也不等于按 BOM 表格摆件；执行前要明确当前操作对象是 EasyEDA schematic page，并用截图或对象审计证明页面可读。

## EasyEDA 库写权限失败时不要伪装 44-pin 已完成 (2026-06-13)

- Pattern: 当前 EasyEDA 会话 `getPersonalLibraryUuid()` 返回 `undefined`，`getProjectLibraryUuid()` 返回 `project`，但 `LIB_Symbol.create('project', ...)` 返回空；继续调用会报 `failed to create symbol ESP32-S3-WROOM-1-N16R8-44PAD-JOVI-FINAL`。
- Rule: 遇到库写权限/库 UUID 不可用时，不得用 stock 41-pin ESP32-S3 器件冒充 44-pin 完成。可以临时放 stock 器件保持页面网络，但必须在页面文字、验证报告和 todo 中明确标为阻塞。
- Rule: 旧 AD `*_CDX6` 44-pin 符号不是 EasyEDA 工程库符号，不能导入/复用为当前嘉立创原理图真值，除非先转换并在 EasyEDA 中验证 pin count。
- Rule: 44-pin 释放条件只有一个：在 EasyEDA 当前工程中 `sch_PrimitiveComponent.getAllPinsByPrimitiveId(U3_MCU) == 44`，并且 `IO1 -> POT_IO1`、`IO34/IO33-37 -> NC/PSRAM`。

## EasyEDA 长脚本超时后必须断点审计跨页污染 (2026-06-13)

- Pattern: 剩余 5 页批量重画脚本触发 bridge 30s timeout，实际已经写入了前几页并在断点附近把 `J10_JTAG` 残留到了 `5_Storage_LED`。
- Rule: `/execute` 超时后不要直接重跑整批脚本。先枚举每页 components/wires/texts/designators，找出已完成页、被清空页、跨页残留，再用单页脚本修复。
- Rule: 每页重画后必须检查该页 designator 清单，尤其确认 Test Header 对象不残留到 Storage/LED 页，Audio connector 不残留到 CAN 页。

## EasyEDA 裁切排针不能直接用 1x40 符号画到原理图 (2026-06-13)

- Pattern: BOM 采购可用 `C2337` 1x40P 长排针裁切，但如果原理图也直接放 1x40P 符号，`4_Audio_Output` 和 `6_Test_Header` 会出现巨大 40-pin 器件，页面不可读。
- Rule: 原理图阅读优先于采购裁切策略。JTAG/UART/测试口等应画实际使用 pin 数的 2x5、1x4、1x6 等短符号；采购备注再写“可由 1x40P 裁切”。
- Rule: 每页模块框必须和实际电路块对应；框不是替代连线，框内仍需真实 component pin wires 和 net label。
- Rule: 如果新增 wire/bus API 返回成功但 `getAll()` 数量不增加，不能宣称主干线已画好；以实际 pin-level wires 和页面审核报告为准。

## EasyEDA wire 自动合并会污染原理图网络 (2026-06-13)

- Pattern: 为了把孤立器件连起来，脚本用跨页面长 rail 把同名网络接到多个 pin。EasyEDA 在相交/贴近 pin 的情况下会自动把 wire 合并成同一个 primitive，甚至把后续创建的不同 net 线并入已有 primitive，审计中出现 Power 页只剩 `+12V_PA` 等异常 net 集合。
- Rule: 嘉立创 Pro 原理图不能用跨全页长 rail 粗暴连接多个网络。每个网络必须局部、短距离、点对点走线，跨功能块使用正规的 net label/port；不同 net 的线不得相交或共用端点。
- Rule: `sch_PrimitiveWire.create()` 返回 `create failed!` 或 wire net 集合异常时，必须停止批量写入并重新审计，不得继续铺线。
- Rule: 原理图风格整理要先做一页小样并用截图/对象 net 集合确认，再扩展到全页。不要一次性对 6 页执行大规模自动布线。
- Rule: 如果页面已经被自动合并污染，下一步应从最近的 EasyEDA 对象快照或工程备份恢复，再按“单页、点对点、无交叉”方案重做。

## EasyEDA 工业控制器风格是当前验收基准 (2026-06-13)

- Pattern: 用户提供了工业控制器参考图后，页面不能只满足“有器件/有网络名”，还必须满足横版图纸、坐标边框、右下角标题栏、模块框对应真实电路、短线点对点连接、跨模块用清晰网络标签的阅读习惯。
- Rule: 当前嘉立创原理图验收以 `1_Power` 的短线风格作为样张；优化 `2_MCU_Core`、`3_CAN_Interface` 时必须先截图比对模块框是否包住真实器件与导线，再用 API 查对象/net 集合。
- Rule: 模块框必须服务于电路阅读，不能压标题栏、不能和器件错位、不能作为连线替代。每个框左上角放中文模块标题，框内仍要有真实 wire/net label。
- Rule: MCU 页按参考图风格处理：MCU 大符号居中，左侧放电源/USB/BOOT/RST/JTAG/去耦，右侧放外设网络映射；如果 ESP32-S3 仍是 41 pin stock 符号，必须继续标为 release 阻塞，不能验收为最终版。
- Rule: 用户指出不能验收时，不得用“部分完成”结束；必须继续按单页小步修复、截图复核、记录阻塞项，直到工具限制或真实 release 阻塞被明确证明。

## EasyEDA 中文文本不要通过 PowerShell stdin 中转 (2026-06-13)

- Pattern: 使用 `@' ... '@ | python -` 从 PowerShell stdin 执行含中文的脚本时，中文内容会在进入 Python 前变成 `?`，随后 EasyEDA 页面出现 `????` 标题。
- Rule: 嘉立创原理图中文标题/注释必须使用 UTF-8 磁盘脚本或明确的 Unicode 转义生成 JS，再调用 `/execute`。执行后立刻 `sch_PrimitiveText.getAll()` 反查文本内容，确认没有问号污染。

## MCU 页必须按参考主控页重排而不是贴边映射 (2026-06-13)

- Pattern: `2_MCU_Core` 只把外设 netport 放到右侧页边、用大框圈住 MCU，会形成“框图/贴边标签”效果，不符合用户给的工业控制器 MCU 页参考图。
- Rule: MCU 页必须以 MCU 大符号为视觉中心，左侧放电源、USB、复位/BOOT、去耦、调试口，右侧单独放整齐的“外设管脚映射”表。外设映射不能越过图纸坐标边框，不能压标题栏，不能挤在 MCU 符号和图框之间。
- Rule: 任何 MCU 页优化完成前必须用截图确认：主控居中、左右分区清楚、右侧映射表不越界、底部标题栏不被模块框覆盖；只用 API 统计对象数不够。

## 后续裁决优先于早期原始要求 (2026-06-15)

- Pattern: Codex v1.5 继续坚持早期 `PERIPHERAL 2x3` 和 MCP2515 DNI 限制，忽略了 Jovi 后续已明确倾向 `2x2` 与允许 MCP2515 DNI 占位。这样会让计划书内部出现“旧要求”和“新裁决”互相打架。
- Rule: 当 Jovi 给出后续明确裁决时，必须把它写成当前最高优先级约束，并同步撤回或标注覆盖旧反驳，不能继续用“原始要求”压过最新确认。
- Rule: 计划书里的历史复审表可以保留，但必须注明“已被 YYYY-MM-DD 裁决覆盖”，否则执行者会读到两个相反结论。
- Rule: 对布局类争议要按当前真实功能块数量裁决：本项目 PERIPHERAL 现阶段是 Audio_Chain、WS2812B+MicroSD、Encoder+Pot、DNI/预留四个功能群，因此 2x2 比 2x3 更可实施；未来新增真实外设超过 4 块时再重新审议。

## ESP32-S3-WROOM-1 模块脚号优先官方 No./Pad (2026-06-15)

- Pattern: 多个计划把 ESP32-S3 的裸芯/库容器字段、旧自定义 44-pad 表和 WROOM-1 模块 pin definitions 混在一起，导致 `Pin51`、`Pad35/36=3V3`、`IO1=Pin2` 等错误可能被执行者当成 release 连接。
- Rule: 对 `ESP32-S3-WROOM-1-N16R8`，release pin truth 必须先按 Espressif 官方 WROOM-1 模块 pin definitions；当前裁决为 `3V3 = No.2/Pad2`，`POT_IO1 = IO1/No.39`。
- Rule: Altium `lib_get_pin_list` 是库一致性验证，不是覆盖官方模块 pin definitions 的权威。若库符号与官方 No./Pad 表冲突，先修库或替换符号，不能按错误库号硬连。
- Rule: 裸芯式 `Pin51-54`、`56-pin` 容器字段、`Pad35/36=3V3`、多组 `7x100nF` 去耦只能作为风险/反驳记录；模块外部去耦放在 No.2/Pad2 旁，目标 `1x10uF + 1x100nF`。

## 计划正文、todo、lessons 必须一起消除旧口径 (2026-06-15)

- Pattern: Codex 计划书已经升级到 v1.7，但 `tasks/todo.md` 的执行原则仍残留 `PERIPHERAL` 当前优先 `2x3`。这说明只更新主计划正文不够，执行入口仍可能把旧错误重新带回上下文。

## EasyEDA pin 引出加网络标签是当前布线样式基准 (2026-07-08)

- Pattern: Jovi 认可的原理图布线样式是：从器件真实 pin 拉出短线，在短线端点或边界处放置清晰网络标签，例如 `LED_DATA`、`SD_CS`、`I2S_BCK`、`+3.3V`、`GND`。这比漂浮文字标签或孤立器件更符合工业控制器原理图阅读习惯。
- Rule: `/hd_wire` 做跨模块/跨页信号时，先从 pin 精确端点拉出短线，再把 net label 接在线上；标签必须接触 wire 或有效电气节点，不能悬空。
- Rule: MCU、接口、外设页的信号扇出优先采用“pin -> 短线 -> 网络标签”的边界形式；模块内部仍优先真实 pin-to-pin 短线连接。
- Rule: 每次 Jovi 纠正后，必须同步检查三个位置：`docs/plan/codex_*`、`tasks/todo.md`、`tasks/lessons.md`。只改其中一个不算完成。
- Rule: 对旧错误词必须做反向扫描，确认它们只出现在 `反驳/不接受/历史覆盖/阻塞/错误示例` 语境，不能出现在当前执行原则、当前验收门或下一步任务中。
- Rule: 多 Agent 摘要里的“已修复/已覆盖/100% 覆盖”不是证据。必须读目标文件当前内容并用 `rg` 验证残留词。

## 规则层和执行层必须同步修改 (2026-06-15)

- Pattern: DeepSeek 错误记录指出规则层已经改成 `Pad2` 和模块单入口去耦，但 Phase 执行命令层仍放 `7x100nF` 和旧电容。MIMO 错误记录也显示多处内部一致但一起错。Codex 后续如果只改规则，不改执行步骤，仍会把错画进原理图。
- Rule: 每次吸收/反驳计划后，必须同时扫描当前规则区、Phase/Task 执行步骤、放置命令、坐标表、审计 JSON 示例、`tasks/todo.md` 执行原则。规则层和执行层有任何不一致，都不能进入 Altium。
- Rule: 每个关键 IC 的引脚表必须有 datasheet 来源；库查询只验证当前符号是否匹配官方真值，不替代 datasheet。
- Rule: 电源反馈、电荷泵、USB CC、CAN 终端/保护等关键电路必须查 datasheet 或计算验证。内部一致不等于正确。
- Rule: 若执行步骤仍出现 `DIODE_SMA`、`LED_0805`、`CAP_0402` 等通用占位 `lib_reference`，该命令旁必须写 `BLOCKING: 执行前替换为正确符号或标 DNI`；否则视为 release 风险。
- Rule: Altium 跨页连接方式必须现场确认 Net Identifier Scope。不能假设 NetLabel 跨页有效；默认以 Port/Power Port 等正规对象维护跨页连接。

## 同名引脚不能跨器件套用语义 (2026-06-15)

- Pattern: TPA3116D2、MAX98357A 都有类似 `SD`、`GAIN` 的控制脚，但语义完全不同。若只看计划摘要或按“名字像”推断，容易把 MAX98357A 的 `SD_MODE`、TPA3116D2 的 `MUTE/SDZ/GAIN/SLV` 混用，导致左右声道、静音、关断、增益全部接反。
- Rule: 每个音频 IC 的控制脚必须按官方 datasheet 单独裁决，不能从另一个器件迁移规则。当前 AD 计划中：TPA3116D2 增益只认 `GAIN/SLV`，`AM0/AM1/AM2` 只作频率/AM 避让；MAX98357A `SD_MODE` Low=shutdown，High=left，`RSMALL/RLARGE` 上拉决定 right/mix。
- Rule: 对 `MUTE`、`SD`、`SDZ`、`SD_MODE`、`GAIN`、`GAIN_SLOT`、`AM0/AM1/AM2` 这类控制脚，必须写清“上电默认态、运行态、关闭态、是否 MCU 控制”。任何只写一个电阻值或一个 GPIO 而不写极性的计划，都不能直接落图。
- Rule: 若计划里出现 `AM0/AM1 增益`、`AM2=HIGH -> 500kHz`、`GAIN/SLV 直连 GND=20dB`、`GPIO8=H 使能 MUTE`、`SD_MODE->GND=左声道`，必须视为旧错并回到 datasheet。

## 电源保护值必须带负载预算和 variant 边界 (2026-06-15)

- Pattern: 把 USB-C VBUS PTC 从 0.5A 改成 2A 或 1.5A，如果没有连续/峰值电流、温度降额、压降、USB-C 源能力、连接器额定和反灌路径分析，只是在计划里换数字。
- Rule: USB-C Standard 5V 默认不采用 `PTC 2A`。优先 eFuse/current-limit load switch 或 1.5A PTC 候选；2A 只能作为 `adapter-only / 5V-2A-source / DNI / 重新计算后审批` variant。
- Rule: USB-C 保护后电源、Premium buck 输出电源、系统 5V 必须用不同网名表达保护前、保护后、汇合后节点，不能用同名 Power Port 硬并。需要 power mux、ideal diode、load switch 或跳线/DNI 明确仲裁。
- Rule: WS2812B bulk 电容不能脱离 LED 数量、线长、MLCC DC bias、供电阻抗和 PTC/eFuse 限流来裁决。当前默认是每颗 100nF + 支路 10uF MLCC；22uF 钽只作为经计算的升容候选，不是默认。

## Agent 摘要不能替代 datasheet 和当前库审计 (2026-06-16)

- Pattern: DeepSeek/MIMO 同时声称“已确认/已修正”时，仍可能残留错误值或旧操作记录；例如 TPA3116D2 `GAIN/SLV 悬空=20dB`、MAX98357A `SD_MODE 370k`、SY8088 `Pin1=VIN`、LM2596 输出电容一口咬定 `470uF`。
- Rule: 多 Agent 一致只能提高复核优先级，不能作为 release 证据。关键 IC 必须以官方 datasheet + 当前 Altium `lib_get_pin_list` + footprint/pad map 三方对齐后才允许落图。
- Rule: TPA3116D2 Master 20dB 当前按 TI datasheet：`GAIN/SLV` 使用 `R1=5.6k -> GND, R2=open`；任何 `GAIN/SLV 悬空=20dB` 都视为旧错。
- Rule: MAX98357A 在 `VDDIO=3.3V` 时，right channel 使用 datasheet `RSMALL=210.2k`，mono mix 使用 `RLARGE=634k`；`370k` 不能作为 release 右声道值。
- Rule: SY8088A1AAC SOT23-5 datasheet pinout 为 `Pin1=EN, Pin2=GND, Pin3=LX, Pin4=IN, Pin5=FB`；若库中 Pin1/Pin4 交换，先修库，不按错库硬连。
- Rule: LM2596 输出电容和二极管按 datasheet 选择逻辑裁决：输出电容看低 ESR、纹波电流、输出电压和瞬态；捕获二极管电流额定至少按最大负载和短路工况评审，当前项目优先 SS54 或同等级 >=5A Schottky，SS34 不作 LM2596 默认捕获二极管。
- Rule: 若库符号是 0-pin 空壳或 pin/footprint 不一致，该器件进入 Phase 0 BLOCKING；计划书不得把“后续修库”与“可以继续画图”混在一起。

## EasyEDA 放置流程必须先走 codex_hardware_eda/codex_hd_put (2026-06-17)

- Pattern: 之前直接在嘉立创 Pro 中批量落器件时，容易出现页面框不包围真实电路、器件孤立无连线、重复自由文本标签、API 盲猜、C 码搜索第一项错料、ESP32 41 pin 冒充 44 pin 等问题。
- Rule: 后续凡是“打开 EasyEDA/JLCEDA 工程、设置页面、创建页面、搜索器件、放置元器件、连线、模块框、逐页审核”的任务，必须先加载 `C:\Users\Admin\.codex\skills\codex_hardware_eda\SKILL.md`，再按 `codex_hd_put` 子 skill 执行。
- Rule: `codex_hd_put` 是原理图优先流程，不允许默认修改 PCB/CPL；每页必须先放真实器件、短线真实连接、再加模块框和 net label，最后截图和对象/net 查询审核。

## Skill 命名与编码必须通过 quick_validate (2026-06-19)

- Pattern: 用户/Agent 自定义的 `hd_put`、`hd_wire` 下划线目录看起来清晰，但 `skill-creator` 的 `quick_validate.py` 会直接报错：skill 名必须是 lowercase letters/digits/hyphens。
- Rule: 面向 Codex 自动发现和标准验证的 skill 必须使用 hyphen-case，例如 `hd-put`、`hd-wire`；下划线目录只能作为兼容副本或项目内部资料，不应作为最终发布路径。
- Pattern: PowerShell `Set-Content -Encoding UTF8` 在部分环境会写入 UTF-8 BOM，导致 `quick_validate.py` 报 `No YAML frontmatter found`，即使肉眼看到第一行是 `---`。
- Rule: 写入 `SKILL.md` 后必须验证前三字节是 `45 45 45` 或直接跑 `quick_validate.py`；若出现 BOM，用无 BOM UTF-8 重写后再验证。

## hd_put / hd_wire 必须把工业控制器风格拆成执行门槛 (2026-06-19)

- Pattern: 只说“参考工业控制器原理图风格”不够，Agent 容易画出孤立元件、空框、长线、漂浮标签或标题栏压线。
- Rule: `/hd_put` 必须负责页面结构和元件放置验收：四功能域分页、A3/A4、黑框、中文标题、左到右信号流、保护靠近连接器、去耦/上下拉/反馈靠近对应 pin、模块框包真实对象。
- Rule: `/hd_wire` 必须负责真实连线和 net 验收：模块内短线真实连接，跨模块/跨页才用 net label，电源上/GND 下，禁止漂浮标签、长线穿器件、重复自由文本和 `IO34` 业务网。
- Rule: 放置 skill 不能默认大规模连线，连线 skill 不能默认大规模放件；如果页面布局无法短线连通，必须回到 `/hd_put` 重排，而不是在 `/hd_wire` 里硬拉长线。

## 修改 skill 时先确认是流程修改还是原则追加 (2026-06-19)

- Pattern: Jovi 要求优化 `/hd_put`、`/hd_wire` 时，可能只想增加绘图原则，而不是重写已有步骤。若 Agent 直接重排 Phase/Procedure，会破坏用户已经调好的调用习惯。
- Rule: 后续修改已安装 skill 前，先判断用户要求属于“流程步骤变更”还是“原则/经验追加”。当用户明确说“不准改流程步骤”时，只能新增原则段落、references 或验收规则，不得改现有标题、步骤编号和执行顺序。
- Rule: 修改完成后必须对比 `^## ` 标题列表，证明流程结构未被重写。

## hd_wire 绝不能执行 hd_put 的元件放置职责 (2026-06-19)

- Pattern: 执行 `/hd_wire` 布线时，Agent 把“放置元件”步骤也执行了，导致职责混淆。这是严重流程边界错误：布线 skill 不能为了补缺件、修布局或让连线更容易而执行元件搜索/创建/移动。
- Rule: `/hd_wire` 必须是 wiring-only。禁止调用 `eda.lib_Device.search()`、`eda.sch_PrimitiveComponent.create()` 或任何元件/页面创建、删除、移动、替换操作。
- Rule: `/hd_put` 完成后必须向 `/hd_wire` 交接 component snapshot；`/hd_wire` 每个模块和页面完成后必须确认 component snapshot 不变。
- Rule: 若 `/hd_wire` 发现缺件、错件、元件位置不适合短线连接、页面框/标题缺失，必须停止并退回 `/hd_put`，不能自己补放或重排。
- Rule: 判断 `/hd_wire` 是否越界的核心证据是组件数量、primitive id、designator/name、manufacturer id、位置、页面列表是否变化；任何变化都视为 critical scope violation。

## hd_wire 可移动既有元件但不可改变元件集合 (2026-06-19)

- Pattern: 上一版把“移动元件”也列为 `/hd_wire` 禁止项，过度收紧，导致无法为了短线、避免穿器件、满足模块框和工业控制器布线原则而调整已有元件位置。
- Rule: `/hd_wire` 允许移动已有同页元器件来满足布线原则，但必须记录 before/after position 和移动原因。
- Rule: `/hd_wire` 禁止改变元件集合和页面结构：不得 search、create、add、delete、replace、re-source、跨页移动元件，也不得创建/删除/重命名页面或补放缺失符号/模块框/标题。
- Rule: `/hd_wire` 的 snapshot 验证应拆分字段：component count、primitive id、designator/name、manufacturer id、pin count、page 必须不变；position 允许变化但必须有 movement log。

## 原理图连线必须是端点到端点的电气连接 (2026-06-21)

- Pattern: `/hd_wire` 曾把一根孤立线段当成“连线”，没有从一个元器件引脚连接到另一个元器件引脚或合法电气节点。这会让截图看起来有线，但 netlist/ERC 仍是断路。
- Rule: `/hd_wire` 中每根 wire 必须有 source endpoint 和 destination endpoint，端点必须是元器件 pin、合法 local rail/node、junction、power/GND symbol 或真实接触的 net label。空白坐标、图框、标题、注释、近似贴近 pin 都不是合法端点。
- Rule: `/hd_wire` 连线顺序固定为 GND -> +12V/+12V_PA/VBUS_USB/+5V/+3.3V 等电源 -> EN/RESET/FB/上下拉/保护链等 support nets -> USB/CAN/I2S/SPI/UART/LED/POT 等功能信号 -> final net pass。
- Rule: `/hd_put` 必须提前放好页面结构对象：A4/A3 usable bounds 内的黑色功能块矩形、红色中文标题、关键电源网络标签、跨页信号标签/port。若这些对象缺失或跑到纸外，不能把问题推给 `/hd_wire`。
- Rule: Codex 自动发现使用 hyphen-case 顶层 skill；Claude 的 `hd_put/hd_wire/hd_plan/hd_check` 应同步到 Codex 的 `hd-put/hd-wire/hd-plan/hd-check`，否则 Codex 搜不到完整工具链。

## hd_wire 必须连接真实电路而不是堆 power/GND 端口 (2026-06-20)

- Pattern: `/hd_wire` 把每个 GND pin 都接到一个独立 GND power symbol，导致 SY8088 EN/GND 重叠、LED 下方多个 GND、POWER 页元件散落但没有真实元件到元件连接。
- Rule: `/hd_wire` 先画元件引脚到元件引脚、元件引脚到局部 rail/节点的真实短线；power/GND symbol 只作为电路边界、rail 边界或跨页入口，不允许“一 pin 一个 power port”。
- Rule: 两端器件必须在有意义的电路路径中：电阻两端不能都是同一个 rail，电容不能只接 GND 一端，LED/上下拉/反馈/去耦必须能追踪到功能节点和回路。
- Rule: `POWER` 页必须按 source/protection/filter/regulator/output caps/rails/load 的功能链路连接；元件散落、只有端口没有链路视为 `/hd_wire` FAIL。

## EasyEDA Pro 导线端点必须使用 pin 原始浮点坐标 (2026-06-20)

- Pattern: 移动元件后导线不跟随，是因为 wire endpoint 使用 `Math.round(pin.x)`/`Math.round(pin.y)`，而 EasyEDA Pro pin 坐标可能是 `360.319`、`645.089` 这类浮点数，视觉贴近但电气未连接。
- Rule: `/hd_wire` 创建导线前必须重新查询当前 pin 坐标；wire endpoint 使用原始 `pin.x`/`pin.y`，或 API 要求字符串时使用 `Number(pin.x).toFixed(6)` 与 `Number(pin.y).toFixed(6)`。
- Rule: 禁止在原理图导线端点上使用 `Math.round()`、`parseInt()`、整数网格吸附或手写近似坐标。若端点与 pin 坐标不一致，删除 malformed wire 并用 fresh pin query 重建。

## EasyEDA hd_put 必须页内局部查询并防超时误页污染 (2026-06-21)

- Pattern: `/hd-put` 使用长脚本批量创建页面、端口和元件时，bridge 请求可能超时，但 EasyEDA 端仍继续执行或停在中间状态，导致后续元件落到归档页或错误页面。
- Rule: `/hd-put` 每次创建元件前必须重新 `openDocument(page.uuid)`，并使用 `sch_PrimitiveComponent.getAll(undefined, false)` 做当前页局部 designator 检查；禁止用全工程 `getAll(undefined, true)` 判断“本页已存在”。
- Rule: `/execute` 超时后不得直接重跑整批脚本。先枚举每页 components/rectangles/texts/wires/designators，清理误页对象，再按页面小批量补放。
- Pattern: `createNetPort()` 创建的是 net port component，不是普通器件；`sch_PrimitiveComponent.modify(id,{x,y})` 对 net port 会报“仅当器件类型为元件时允许使用该函数进行修改”。
- Rule: 端口位置错了不要用普通 component modify 硬移；应删除错误 net port 后在正确页面/坐标重新 `createNetPort()`，或降级为红色文本标签并记录为结构对象。
- Rule: A3/A4 修改 API 返回成功后仍必须反查页面 `titleBlockData.Size` 和对象坐标；如果 A3 未实际生效，按 A4 安全边界放置并记录工具限制。

## ESP32-S3 当前 EasyEDA 符号按 41 引脚含 EPAD 验收 (2026-06-21)

- Pattern: 之前把 `U3_MCU pinCount == 41` 一律写成 44-pin release blocker，但 Jovi 明确纠正当前 ESP32 符号是 41 引脚，末端包含 `IO42/RXD0/TXD0/IO2/IO1/GND/EPAD`。
- Rule: 后续 `/hd-put` 与 `/hd-check` 对当前 EasyEDA 工程中的 `ESP32-S3-WROOM-1-N16R8`，先按 Jovi 给出的 41-pin/EPAD 表验收，不得继续沿用旧的 44-pin blocker 结论。
- Rule: 新验收重点是 `pinCount == 41`、`IO1 -> POT_IO1`、`IO34/IO33-37` 不作为业务网、`GND/EPAD` 后续由 `/hd-wire` 明确接 GND。
- Rule: 若未来换用新的 ESP32 库符号或 datasheet 版本，必须先导出当前符号 pin list 与官方模块 pin definitions 对照，再决定是否恢复 44-pad 要求。

## /hd-put 不能用空框和散件冒充工业控制器原理图 (2026-06-21)

- Pattern: 当前 EasyEDA placement 截图中出现模块框不包围真实器件、空白大框、框线压标题栏、端口贴边/漂浮、归档空页与 release 页混淆等问题，虽然对象统计通过，但视觉和交接都不符合 `/hd-put`。
- Rule: `/hd-put` 模块框必须根据真实器件 bounding box + padding 生成；没有真实器件或手工/DNI 对象的空框不得通过验收。
- Rule: `/hd-put` 完成后必须同时做截图级审核和 API 坐标审核；对象数量、out-of-bounds=0 不能替代“框与模块对应、标题栏避让、页面不是空画面”的工程阅读性检查。

## EasyEDA bridge 提交大脚本时优先用 ReadAllText，标题栏状态必须反查 (2026-06-21)

- Pattern: PowerShell 用 `Get-Content -Raw` 包装 `/execute` payload 时，`ConvertTo-Json` 可能把脚本内容包成 `{\"code\":{\"value\":...}}`，bridge 会报 `Missing "code" field (string)`。
- Rule: 往 EasyEDA bridge `/execute` 发送长脚本时，优先使用 `[System.IO.File]::ReadAllText(path)` 读取代码，再构造 `@{ code = $code } | ConvertTo-Json`。
- Pattern: `modifySchematicPageTitleBlock()` 可能返回成功，但 `showTitleBlock` / `Size` / `Width` / `Height` 未真正落盘。
- Rule: 修改页面标题栏、A3/A4 后必须再次查询 `getCurrentSchematicPageInfo()` 或 page list，不能只信 API 返回 `ok=true`。

## EasyEDA 原理图导线 API 必须二次验真，USB 引脚列禁止贴线建总线 (2026-06-21)

- Pattern: `sch_PrimitiveWire.create()` 可能返回带 `primitiveId` 的对象，但随后的 `sch_PrimitiveWire.getAll()` 仍返回 `0`；“create 返回值”不能证明导线已真正落在图上。
- Rule: 每次创建导线后，必须立刻用新请求再次 `getAll()` 或按 `primitiveId get()` 验证导线已持久化；若未持久化，则视为创建失败，不得继续整页布线。
- Pattern: 在 USB-C 这类单侧密集引脚器件上，若直接沿引脚列画竖向总线，会把 `GND/VBUS/CC/D+/D-` 意外短在一起。
- Rule: 对单侧密集引脚器件，必须先从 pin 拉短 stub 到引脚列外侧，再在外侧建立竖干线/横干线；禁止把公共总线压在引脚列上。

## EasyEDA GUI 布线前必须先锁定画布焦点并做单线回读 (2026-06-21)

- Pattern: `computer-use` 现在可以在 EasyEDA GUI 中真实落线，但 EasyEDA 的当前焦点不稳定；同样的 `Ctrl+Z` / `Delete` 在 wire 上并不总是生效。如果没先确认焦点就在画布，继续整页连线很容易留下脏线。
- Rule: 用 GUI 落线时，每一组动作都按固定节奏执行：`Escape -> 点击画布空白处拿焦点 -> 启动导线工具 -> 落一根线 -> bridge 读回 wire list`。只有读回正确，才允许继续下一根。
- Rule: GUI 撤销不稳定时，不要假设 `Ctrl+Z` 已经成功。必须再次 `getAll()` 验证 wire 是否消失；若仍存在，再走可验证的删除路径。
- Rule: bridge 删除 wire 时使用 `primitiveId[]` 数组调用 `eda.sch_PrimitiveWire.delete(ids)`，不要单个 id 逐个删后就假定成功。

## Child-Claude 必须作为受约束单任务 worker 使用 (2026-07-06)

- Pattern: Jovi 再次明确，复杂项目中不应让 Claude Code 连续自主推进到底；Codex 必须做总控、拆窄任务、审核 diff 和验证结果，Claude Code 只执行单个受约束任务。
- Rule: 每次派发 child-claude 前必须写清任务卡：目标、范围、路径边界、允许工具、验收标准、必须输出的结构化字段。
- Rule: 优先使用 `C:\Users\Admin\.claude\skills\child-claude` 和本机 Claude Code CLI 链路；除非链路不可用，不优先引入 HTTP wrapper 或额外服务层。
- Rule: 子 agent 的返回不能直接视为完成。Codex 必须复查改动范围、读 diff/文件、跑可用验证，并明确接受、打回或拆下一任务。
- Rule: API key、模型 profile、base URL 等密钥或凭据只允许存在本机配置/环境中，不得写入仓库、任务文件或最终报告。

## Child-Claude profile 环境变量引用必须实际烟测 (2026-07-06)

- Pattern: profile 中写 `ANTHROPIC_AUTH_TOKEN="$MIMO_API_KEY"` 后，Claude Code 可能不会按预期展开变量，导致接口收到字面量并返回 `401 Invalid API Key`。
- Rule: profile 中不要保存明文 key；实际 token 放 User env，`Invoke-ChildClaude.ps1` 运行时解析 env-ref 到临时 settings 文件，调用结束后删除临时文件。
- Rule: 修改 child-claude base URL、模型或 token 后，必须用默认 profile 发一个最小只读 smoke test，并记录 `Success`、`ModelUsed`、`Stderr`，不能只看 json 配置。

## KiCad CLI 未在 PATH 的环境下也要恢复可用 (2026-07-08)

- Pattern: 上一轮中 `kicad-cli` 未加入 PATH，导致误判 v1 工程被 CLI 阻塞；实际上 KiCad 已安装在非标准目录。
- Rule:
1. 不要把“未在 PATH 可见”直接等同于“工具缺失”。本地脚本必须尝试常见安装目录并打印最终命中路径。
2. 当命令返回非零码时，先核对是否为功能上可接受的预期码（例如 ERC `--exit-code-violations` 的 5）。
3. 任何闭环记录必须区分“工具可达性问题”与“设计规则违规问题”。

## KiCad PDF 存在不等于专业工程原理图完成 (2026-07-08)

- Pattern: 5.4 输出了 `output\schematic.pdf`、SVG、BOM、netlist，但图纸仍是 `project:*` 占位符、简单连线和标签堆叠；把“可导出”当成“图纸完成”会误导后续决策。
- Rule: KiCad 原理图验收必须同时检查文件输出和视觉/电气结构：页面横版、坐标边框、标题栏、模块分区、中文标题、真实核心符号、左到右信号链路、保护器件靠接口侧。
- Rule: 对硬件图纸不得只用“PDF 文件存在/pytest 通过/ERC 可输出”作为完成证据；必须打开或解析 PDF/SVG，证明页面不是空图、占位图或散件列表。
- Rule: release 图纸中如果仍含泛用占位符或缺少真实核心 IC/连接器符号，必须标为未完成，不得包装成 v1 原理图完成。

## KiCad 生成器不能用网络端点反推完整芯片引脚 (2026-07-08)

- Pattern: 生成器只从 `nets.endpoints` 收集 pin 名，导致未连到当前 v1 网络的芯片引脚完全消失；USB/TVS/稳压器等被画成 P1/P2 方框，ESP32 也只显示业务网脚，视觉上像“芯片就一个引脚”。
- Rule: release 原理图的核心 IC、连接器、接口保护器件必须有显式 pin table；网络端点只能决定哪些 pin 被连线，不能决定器件有多少 pin。
- Rule: 生成 PDF 前必须用测试检查核心器件最小 pin count 和关键 pin 名，例如 ESP32-S3 >= 41 pins，CAN transceiver >= 8 pins，USB-C/SD/WS2812/DAC/AMP 有对应接口 pin。
- Rule: BOM/制造字段应默认隐藏或移到不遮挡位置；不能让 `MPN/LCSC/TBD/Assembly/Source` 堆在符号上方影响审图。

## 独立计划任务优先走 subagent-driven-development (2026-07-08)

- Pattern: 在有明确执行计划、而且任务之间可拆分时，我仍然容易把工作堆在主上下文串行推进，错过并行子 agent 的效率优势。Jovi 明确提醒，当前仓库已经提供 `$subagent-driven-development` 技能，应该直接使用。
- Rule: 只要任务满足“已有计划 + 可拆独立子任务 + 当前会话内继续执行”，先检查并使用 `E:\Tesla_speed\.agents\skills\subagent-driven-development\SKILL.md`。
- Rule: 主 agent 负责拆任务、写 brief、整合结果、跑最终验证；子 agent 负责单个窄任务实现或审查，不把所有执行都压在主上下文。
- Rule: 用户点名某个本地 skill 可用时，先切到该 skill 再继续执行，不要只口头认同。

## EasyEDA wiring must verify hidden netflag coordinate crossings (2026-07-08)

- Pattern: A wire can look visually correct but pass through a one-pin netflag coordinate, silently shorting nets, e.g. CANL first route crossed the +5V flag at (475,520).
- Prevention: after creating EasyEDA wires, query single-pin netports/netflags and test every new orthogonal segment against unrelated netflag coordinates before saving or expanding to the next module.
- Correction: delete malformed wire primitives and rebuild with offset lanes that avoid unrelated electrical nodes; do not rely on screenshots alone.

## 声浪算法状态必须区分基础代码与仿真定参 (2026-07-08)

- Pattern: 讨论“根据速度、加速度生成不同声音”的声浪算法时，容易把当前单正弦/RPM 占位实现说得像已经完成产品级声浪模型。
- Rule: 回答音频算法完成度时必须明确区分：当前固件是否已有可编译占位链路、是否已有速度/油门/RPM 映射、是否已有加速度/jerk/负载分层声浪、是否经过 MATLAB 或等价仿真探针定参。
- Rule: 没有 MATLAB/仿真曲线、参数扫描、波形听感验证和固件定点化验证前，不得声称速度/加速度差异化声浪算法已经集成完成；只能标为待算法建模与移植。

## Git commit 与远端 push 必须分开汇报 (2026-07-08)

- Pattern: 本地 `git commit` 完成后，我把“提交完成”说得像 GitHub 远端也已经更新，导致 Jovi 在官方仓库页面看不到新提交。
- Rule: 以后涉及 Git 交付时必须明确区分三种状态：本地 commit 已生成、远端 push 已完成、GitHub 页面/远端 HEAD 已验证。
- Rule: 用户要求“提交到 GitHub/远端/主分支”时，不能停在本地 commit；必须执行 `git push origin main` 或明确说明 push 失败原因，并用 `git ls-remote origin refs/heads/main` 或等价命令核对远端 HEAD。
- Rule: 如果之前 remote 使用代理地址，用户点名官方仓库时必须确认 `origin` 是 `https://github.com/Jovifei/Tesla_Simulate_vico.git`，再 push。

## IRAM 风险不能用“能编译”带过，公开中文文档必须读回验真 (2026-07-09)

- Pattern: `idf.py build` 通过但 `idf.py size` 显示 IRAM `16383 / 16384` 时，容易把“可编译”误报成“release clean”。
- Rule: 任何 release 结论必须同时报告 build、size、size-components 和 IRAM headroom；若 IRAM 只剩 1 byte，只能标为风险未关闭或显式接受，不能标为完成。
- Rule: 优化 IRAM 前先做归因：查 app 级 `IRAM_ATTR`，看 `size-components` / `size-files`，再做单变量配置实验；不要直接建议换 MCU。
- Pattern: 公开文档中文可能因为编码或复制来源出现 mojibake，肉眼没重读就会把乱码推上 GitHub。
- Rule: 修改中文 README/roadmap/backlog 后必须用 `Get-Content` 或 `rg` 读回，并扫描 `鍥|绋|鐩|寰|宸|鈥|乣|�` 等常见乱码字符。

## MATLAB / Simulink MCP 验收必须覆盖 skill 依赖闭包 (2026-07-11)

- Pattern: MATLAB MCP 核心连接、工具箱探测、Simulink MCP 工具入口均通过后，仍可能因必需 skill 未注册或 `.satk` 自定义库策略未声明，无法创建最小 Simulink 模型。
- Rule: 不得把“配置完成”表述为“完整验收通过”。必须分别验证核心 MCP 调用、Simulink 工具入口、相关 skills 是否可触发、`.satk` 自定义库决策、最小模型创建/读取/检查。
- Rule: 对没有自定义 Simulink 库的工作区，先明确记录 `confirmedNone: true`，再继续建模；不要跳过 `setup-custom-libraries` 的前置决策。

## MATLAB 增补产品后必须做冷启动验收 (2026-07-11)

- Pattern: MPM 产品清单显示安装成功，并不代表 MATLAB 桌面能够稳定启动；本次在新增物理建模产品后发生 GTP 线程访问冲突。
- Rule: 每次向既有 MATLAB 增补产品后，先关闭旧会话，再启动一个全新 MATLAB 会话验证稳定启动、`ver` 产品可见性和基础命令执行；不可只凭 MPM 清单或安装日志宣布完成。
- Rule: 若重置偏好、禁用用户 Java、软件 OpenGL 和单线程启动均不能恢复，停止局部修补，保留偏好备份并使用精简产品集重装。

## MATLAB 重装后必须同时刷新共享会话与 Simulink extension (2026-07-11)

- Pattern: 重装后的 Codex MCP 配置和扩展文件仍存在，但 `sessionDetails.json` 可残留指向已退出的 MATLAB PID，且新 MATLAB 会话默认没有运行 `satk_initialize`。结果会表现为基础 MCP 无法附着，或 Simulink MCP 工具报“函数未识别”。
- Rule: 每次重装或新建 MATLAB 会话后，先检查 `sessionDetails.json` 的 PID 是否存活；在当前 MATLAB 执行 `shareMATLABSession`，再执行 `addpath(<simulink-toolkit>); satk_initialize`，并用 `detect_matlab_toolboxes` 和一个 `model_read` 或 `model_check` 做真实验收。
- Rule: 对长期使用的工作站，将上述 Simulink 初始化放进 `Documents\\MATLAB\\startup.m`，但保留 `try/catch`，使工具包问题只告警、不阻止 MATLAB 正常启动。

## 声浪仿真必须标明物理层级与实际工具箱调用 (2026-07-11)

- Pattern: 点火顺序、齿比、回火校准和固定共振器能产出有辨识度的声音，但不能等同于燃烧、管内非定常气体动力学、热声传播、车身/座舱传递函数和录音自动拟合已经完成；一个只有 RPM/负载输出的 Simulink harness 也不等同于物理发动机模型。
- Rule: 报告仿真时必须分别列出输入状态、燃烧/动力学、排气声学、传播/播放链路、实录拟合五层，并明确每层是已实现、经验近似还是未实现；同时列出实际执行过的 MATLAB 工具箱，不能因“已安装”就写成“已使用”。
- Rule: 高频机械纹理和回火 crack 只能作为由 RPM、负载、燃烧状态和参考特征门控的独立可校准支路；必须用分频带、谱平坦度、谱通量和瞬态误差验收，禁止用固定白噪声掩盖缺失的物理模型。

## 品牌声浪必须先做车型独立参考分析 (2026-07-11)

- Pattern: 第一版 Hellcat、R35 GT-R、W204 C63 共用同一发动机脉冲和回火生成器，仅改变增压层、增益和爆裂次数，导致三款车辨识度不足，尤其回火音色几乎相同。
- Rule: 任何品牌车型声浪实现前，必须分别锁定原厂/改装状态明确的真实加速、收油、回火和换挡参考，提取发动机阶次、频谱重心、脉冲包络、事件间隔和换挡切火时长。
- Rule: 公共框架只能共享输入、输出、混音和验证接口；点火时序、排气共振、增压器模型、换挡状态机和回火生成器必须允许车型专用实现，不能只靠统一波形乘不同增益。
- Rule: 自动测试通过和 WAV 可生成不等于听感通过。品牌声浪必须经过车型间可辨识度检查和 Jovi 主观试听，才能扩展下一批车型。
## 回火不能只按频带手工拟合 (2026-07-11)

- Pattern: V2 虽然把 Hellcat、GT-R、C63 分成不同回火函数并匹配了粗频带占比，但仍由人工选择正弦、噪声和衰减参数，真实回火的起音、燃爆脉冲、排气管尾振和事件间隔没有从录音反推，因此听感仍不像真车。
- Rule: 回火校准必须从每款车状态明确、近排气口的多个真实事件中提取派生参数：onset、attack、双阶段 decay、频谱残差、低频 body modes、宽带 crack 比例、事件间隔和 cluster size。
- Rule: 不得把原始版权音频或截取样本复制进产品；只允许保存可解释的数值参数、短 FIR/共振器系数和统计结果，并记录来源与改装状态。
- Rule: 换挡声必须与变速箱类型一致，分别建模 torque cut、clutch overlap/slip、RPM smoothstep drop、re-engagement 和 shift transient，不能只使用统一线性 RPM 下降加一个音效。
## 换挡顿挫必须来自主轨动力学

- 用户说的换挡声不是额外叠加的短促音效，而是扭矩切断、RPM 回落、燃烧脉冲变弱、离合器重新接合共同造成的主轨顿挫。
- 禁止用独立宽带噪声或短促“呲”声代替换挡；独立换挡层只能提供很弱的机械/排气细节。
- 每次调整都要核对换挡发生时刻、换挡前后 RPM、主排气包络和重新接合斜率。

## 长回火必须是非平稳事件序列

- 长回火不能重复一个固定音调；每次爆裂需要音高漂移、强度衰减、间隔变化、左右排气路由和共振尾音变化。
- 加速换挡回火、收油减速回火和持续 burble 必须分别建模，不能只在一个固定工况触发。

## 噪声层必须接受可听性审计

- 宽带随机噪声在低负载或中段裸露时会产生沙哑、廉价的合成感，尤其是自然吸气车型。
- 噪声只能作为低电平纹理，并需按 RPM、负载和发动机阶次调制；主音色必须由燃烧脉冲、谐波和共振器承担。
- 交付前必须导出分层轨并检查每个时间段的噪声占比，不能只看全局频谱和 RMS。

## 稀疏事件特征必须排除静音帧 (2026-07-12)

- Pattern: 对回火这类占比很小的音频层做频谱平均时，若把静音帧算进活跃样本，会把拟合目标和参数搜索误导到错误方向。
- Rule: 特征提取函数必须同时支持行向量、列向量和多声道输入；活跃帧阈值至少取分位数与峰值相对门限中的较高者，并用单元测试覆盖两种单声道方向。
- Rule: 自动拟合输出必须保存全部候选、目标特征、最优特征与客观误差；第一次扫描若未达到频带目标，保留为 iteration 证据，不得覆盖或称为最终试听版。

## 新物理参数不能掩盖旧版听感回退 (2026-07-12)

- Pattern: C63 V6.0 参数更多且通过结构测试，但回火峰值主导全局归一化，使加速声比 V4 弱约 16 dB；少量平均频谱指标也掩盖了高频与事件持续时间退化。
- Rule: 每次升级必须把用户认可的旧版作为 A/B 基线，锁定加速 RMS、回火相对峰值、1--4 kHz/4--12 kHz 占比、事件数、单簇持续时间和全局压缩状态。
- Rule: 新增物理参数必须进入实际计算或明确标为未接入，不能用参数数量代替有效性证明。
- Rule: 分轨只能在超峰值时衰减，禁止把微弱分轨单独放大到满幅后判断最终混音比例。

## Child Claude 写任务必须保留结构化诊断 (2026-07-12)

- Pattern: 简单受限写入可在 18 秒内成功，但更复杂的单文件函数任务仍可能在 120 秒超时；不能把一次超时误报为全局配置失效。
- Rule: 写任务必须显式允许 `Write` 或 `Edit`，给出唯一目标路径、路径边界、内容和验收；失败时记录 `Success`、`TimedOut`、`Turns`、`Result`、`Stderr`、`RawStderr`，并检查是否留下文件。
- Rule: 简单 smoke test 只证明 API、模型和写工具链可用，不证明复杂任务一定能在相同时限完成。

## 发动机“撕裂感”必须进入点火事件本体 (2026-07-12)

- Pattern: 将“撕裂感”理解成高频电子噪声或连续非线性失真，会让主排气仍然平滑，只在表面增加沙哑感，与真实车辆断断续续的燃烧脉冲不同。
- Rule: 撕裂感优先由逐点火事件的幅值离散、相关缺口、缸间差异和少量曲轴角时序抖动产生；附加 rasp/噪声只能是低电平、RPM/负载门控的辅助层。
- Rule: 各随机声学层使用独立随机流。调整燃烧变化时，必须用测试证明回火事件时刻和回火 stem 不发生非预期改变。
- Rule: 角度单位必须注明参考周期。当前 `cyclePhase` 表示 720 度四冲程周期，曲轴度转相位弧度应使用 `pi/360`，不得按 360 度周期误换算。
- Rule: 网络录音的低频比例会受路噪、风噪、麦克风和驾驶工况影响；频带目标用于方向约束，不能为了匹配单个比例强行破坏车型的发动机阶次和排气结构。

## 高保真目标不得由执行者自行降阶 (2026-07-12)

- Pattern: 用户要求 MATLAB/Simulink 发动机物理仿真，但执行者为了尽快产出可听结果，自行把目标降为压力脉冲、延迟线和经验共振器；虽然报告过边界，仍没有先询问用户是否愿意投入更长时间建设完整模型。
- Rule: 当完整 1D 气体动力学、缸压、阀门流量和声学传播可实现但成本更高时，必须先向 Jovi 列出高保真与降阶方案、时间和验证差异，由 Jovi 决定；不得默认选择更快的降阶方案。
- Rule: 新模型的每个关键参数必须标记为“官方/论文/测量/识别/假设”，并给出来源、适用工况、置信度和敏感度；未知参数先检索和识别，不允许静默填经验值。
- Rule: Simulink 模型必须承载可检查的物理子系统和信号链。MATLAB 脚本只能用于参数装载、测试、拟合和导出，不能替代核心燃烧、阀流、管网与声学模型。

## 版本演进必须同步留根且子 Agent 草稿必须复核 (2026-07-12)

- Pattern: 声浪版本连续迭代后，若只保留音频和代码，后续很难回答每版为什么变化、哪些结论已验证；子 Agent 根据有限资料起草历史时也可能补出没有证据的版本细节和日期。
- Rule: 每个重要版本必须同时记录目标、触发原因、方程/参数变化、A/B 基线、失败结果、验证证据、产物路径和 Git 提交；Obsidian 总历史只链接这些事实来源。
- Rule: 子 Agent 可负责受限资料的初稿，但主 Agent 必须检查版本号、日期、已完成/计划边界和物理术语；无法从来源证明的内容必须标为重建或删除。
- Rule: MATLAB 测试文件修改后先 `clear <test_function>; rehash` 再执行绝对路径 `runtests`，测试名仍显示旧函数时不得接受结果。

## Simscape 长仿真必须先做量纲和边界审计 (2026-07-12)

- Pattern: 5 ms 管路仿真超过三分钟且 Stop 无响应，根因不是单纯算力不足，而是初始压力数值以 Pa 命名却配置成 MPa，并把 700 K 气体管壁直接接到 Thermal Reference。
- Rule: 新 Simscape 网络首次运行前逐项打印参数值与单位，重点核对初始状态、nominal 值、热边界和理想源；先运行毫秒级短工况并记录耗时，再扩大 StopTime。
- Rule: 理想 Reservoir 会钳制连接节点压力。压力波传感器不能直接放在理想压力边界节点，必须通过已说明的有限阻抗终端连接。
- Rule: 长仿真优先用短 StopTime 和异步状态轮询验收；若停止命令无响应，用户重启后先保存 WIP 和诊断，不重复盲跑相同配置。

## Riemann 波位指标必须来自波系定义 (2026-07-14)

- Pattern: Lax 初版将全域最大的两个密度梯度直接标作接触面和激波；稀疏扇内部梯度会超过接触跳变，导致接触位置被错误归类，虽然 L1 误差和守恒仍然通过。
- Rule: 有精确 Riemann 解时，接触、激波和稀疏波头/尾的真值位置必须由同一 star-region/wave-pattern 求解给出，不能由全域梯度排序反推。
- Rule: 一阶耗散下的数值稀疏波前沿必须采用已命名、可重复的 level-set 定义；本项目采用 5% fan-amplitude 前沿，仅作为诊断而非 acceptance 阈值，并用独立单元测试锁定该定位器。

## Simulink 资格输出必须落盘并冷重载 (2026-07-14)

- Pattern: Stateflow 脚本已更新不等于受控 `.slx` 的新 To Workspace 结构已经持久化；同名旧模型仍在 MATLAB 内存时，adapter 可能模拟旧端口并使 benchmark 缺少诊断字段。
- Rule: 每次新增 Simulink 结构输出后，必须 `model_edit`、显式保存、关闭、冷重载，并同时检查磁盘模型中目标 block/connection 与实际 `sim` 输出；`model_check` 不能替代该运行时证明。
- Rule: 数值资格 adapter 必须只使用受控磁盘模型。若同名模型可能已加载，应在无未保存用户编辑的受控模型前提下关闭并重载，避免内存缓存污染 baseline。

## 常值解析分量不能伪造空间阶 (2026-07-14)

- Pattern: periodic entropy wave 的解析速度和压力为常值；其 L1 误差迅速落在浮点舍入噪声，网格加密后会出现无意义的负 observed order。
- Rule: 仍完整报告 rho/u/p L1，但空间精度门禁只作用于具有可分辨解析变化且空间误差主导的 rho；必须明确标注 u/p 为 round-off 限制，不能调低二阶阈值或把噪声当退化。

## report-only 必须保留 Canonical JSON 的原始字节 (2026-07-14)

- Pattern: MATLAB `jsonencode` 的 NaN 会写为 `null`，而 `jsondecode` 读回空数组；report-only 若重写 manifest，可能只因表示差异而改变 SHA-256。
- Rule: report-only 可以从解析后的 Canonical Result 渲染派生产物，但必须复制来源 manifest 原始字节；验收仍只读取 manifest 内既有状态，报告不得重新计算 acceptance。

## 长规格附件必须先恢复原文再判断授权边界 (2026-07-14)

- Pattern: Sprint 3 的完整数值设计随附件提供，但聊天内联内容在 `muscl_minmod` 处截断；若只依据截断文本，会把已经批准的 global LF anchor、CFL、整步拒绝和共享通量限制误判为缺失授权。
- Rule: 长规格疑似截断时，先读取用户指定附件、确认编码和完整行数，再判断是否需要澄清；附件中的已批准设计是当前任务的权威输入，不能用猜测补全，也不能重复要求架构确认。
- Rule: 对 S12 正性模式，文档必须区分“设计已冻结”“RED/实现已开始”“qualification 已通过”；任何一个未发生都不能提前写成已验证结果。

## Child-Claude liveness 与跨目录写入必须分开控制 (2026-07-14)

- Rule: child 每 30 秒只做 liveness 检查，90 秒整体 timeout 才构成超时；运行中但尚无 final JSON 不是自动卡死。每个失败包使用新 session 和独立 diagnostics，连续三次失败后由主 Agent 接管。
- Rule: child 写入前必须得到 Jovi 对精确目标目录和写入范围的批准；`WorkingDirectory` 只覆盖共同父目录，跨目录时仅用 `AdditionalDirectories` 显式授予已有父目录。主 Agent 必须复查最终 diff，且不得使用 `bypassPermissions`。

## Sprint 3 report-only 必须复制 Canonical JSON 原始字节 (2026-07-15)

- Pattern: Sprint 3 qualification 的派生 Markdown/CSV/PNG 可以由 decoded Canonical Result 重建并保持一致，但 `benchmark-result.json` 若重新 `jsonencode`，会因运行时字段或 NaN/null roundtrip 表示造成 SHA-256 漂移。
- Rule: 所有 report-only 入口必须在渲染派生产物后，把 `SourceManifest` 原始字节复制到输出目录的 `benchmark-result.json`；Report 不重新计算 acceptance，也不重写机器清单。
- Rule: Qualification 通过后仍要显式比较 full/report-only 以及 accepted-baseline/report-only 的每个受控 artifact SHA-256；只看 Markdown 或 PNG 一致不够。

## Positivity qualification 的压力算例要显式区分普通 CFL 与 stress CFL (2026-07-15)

- Pattern: Sprint 3 普通 Full cases 使用 `pp_requested_cfl=0.35` 以保持 nominal no-retry 证据；double-rarefaction stress 需要独立 `requested_cfl=0.45` 才能触发 shared flux limiter 并验证强稀疏边界。
- Rule: Stress case 的 CFL 必须在 profile/case config 中显式记录并由测试锁定，不得从全局 CFL 静默继承或运行时偷偷改写。
- Rule: PP 验收必须同时报告 cell/interface/anchor/final partial rho/p、activation count、theta、retry/reject、clipping/fallback/invalid-stage 零计数和守恒残差；不能只报告最终 cell rho/p 为正。

## MATLAB batch 包装失败要和数值失败分开记录 (2026-07-15)

- Pattern: `matlab -batch` 的 PowerShell 引号错误会表现为 startup/SATK 通过但命令未执行，或 MATLAB 报语法错误；这不是 solver/test failure。
- Rule: 对 batch 验证要检查目标 marker 行，例如 `S12_FINAL_AFTER_FIX_TOTAL=61 PASS=61` 或 `S12_SPRINT3_QUALIFICATION_STATUS=passed`；只有 marker 出现且 exit code 为 0 才能作为验收。
- Rule: 若 MCP attach 失败，可用日志化 batch 作为替代，但必须轮询进程、stderr 和日志尾部，避免 600 秒工具超时吞掉真实结果。

## Simscape 参数单位和热端口拓扑必须逐项审计 (2026-07-15)

- Pattern: `model_edit` 新建 Gas 模型时，库块默认显示单位可能是 `kJ`、`MPa` 或 `microPa*s`；只写数值而不显式匹配 `J/(kg K)`、`Pa`、`Pa*s` 会导致初始化失败或错误物理量级。
- Rule: 新建 Simscape 交叉验证模型必须把每个受控参数与权威模型逐项核对“值、单位、运行时属性和边界位置”，并用短工况先证明初始化及稳态，再运行 Full。
- Pattern: 五段 Pipe(G) 若共用一个 Perfect Insulator 节点，会把各段 H 端口连成共同热节点，长管结果反而比单段更差；绝热边界不等于允许不同部件共享热状态节点。
- Rule: 分段绝热模型每段必须使用独立 Perfect Insulator；`model_read` 要确认每个 `Pipe_i.H` 只连接自己的绝热端，再用分段精度改善作为行为证据。

## 跨类别 Benchmark 不应继承无关 Solver 合同 (2026-07-15)

- Pattern: `cross_validation` case 加入全套 registry 后，`muscl_minmod_pp` 全套入口曾把 Euler positivity 字段合同附加到 Fanno/Simscape case，导致原有 PP contract 回归失败。
- Rule: scheme-specific acceptance 只应用于实际使用该 scheme 的数值 Solver case；解析/Simscape cross-validation 必须保留自身合同，不能为了统一入口而承担无关字段。

## Fanno 平衡律必须使用边界通量与源项闭合 (2026-07-16)

- Pattern: 把首末 cell-center 状态当作实际边界通量，或沿用无源 Euler 的“全局动量不变”，会把边界 stencil 误差和壁面摩擦源项错误记入资格残差。
- Rule: Fanno 的质量、能量与动量账必须使用实际 characteristic boundary state；动量验收使用“边界动量通量 + 壁面 Darcy 源项”的 control-volume 闭合，不再要求动量全局不变。
- Rule: 受 validation-only 边界 stencil 控制的热力学 profile 指标要明确 control-volume 范围；正式 profile 阈值作用于最细网格，同时用全网格单调下降和 finest-better-than-coarsest 锁住离散质量，不能事后放宽阈值。

## Accepted baseline 必须从包含实现的干净提交生成 (2026-07-16)

- Pattern: dirty WIP 的 Canonical Result 会把 `source_commit` 记录为旧 HEAD，即使 acceptance 和 report-only 哈希都通过，也不能成为新实现的 accepted baseline。
- Rule: 先提交 contracts、implementation 和 qualification；再从干净 qualification HEAD 运行 Full，核对 manifest `source_commit` 和 clean tree，最后显式 promotion 并独立提交 baseline。
- Rule: report-only 仍复制 Canonical JSON 原始字节；只有全部受控产物逐文件 SHA-256 一致，且历史 baseline 无 diff，才允许 promotion。

## MATLAB access violation 恢复只记录相关性，不宣称因果 (2026-07-16)

- Pattern: 结束孤儿 MathWorksServiceHost/Monitor 后，MCP attach、`new_system`、冻结 PP one-step 和新 Fanno 模型 smoke 同时恢复；但单次前后关系不足以证明后台进程是唯一根因。
- Rule: 状态写作 `resolved_for_current_session`；若 `0xc0000005` 复现，先保留 crash dump、进程状态、正在运行的模型和最小复现，再按受控 smoke 门禁恢复，禁止修改数值算法规避运行时崩溃。

## 全量 MATLAB 回归禁止对模型目录使用 genpath (2026-07-16)

- Pattern: `addpath(genpath(s12Root))` 把 `.slx` 所在目录加入 MATLAB path 后，旧测试中的 `exist(fullPath,"file")` 对 Simulink 模型返回 `4` 而不是预期 `2`，造成 7 个与数值无关的假失败。
- Rule: S12 全量回归使用仓库原命令 `cd(s12Root); runtests('tests')`；单入口只加入明确需要的 `benchmark/`、`validation/fanno/`，不得用 broad `genpath` 污染模型发现语义。
- Rule: 遇到同一 Actual/Expected 模式的批量失败，先检查 path、loaded-model 和 workspace 状态；不要修改旧测试或模型去适配会话污染。

## Canonical schema 要由实际结果反向做 drift 测试 (2026-07-16)

- Pattern: schema minor 4 曾遗漏 25 个实际 Sprint 4B metric 字段、重复 `retry_count`，且 order/sequence 共用同一字段名；顶层 validator 无法发现这种机器合同漂移。
- Rule: benchmark contract 必须验证 `fieldnames(Canonical metrics)` 全部属于 schema catalogue，catalogue 字段唯一；order 与 execution sequence 使用不同字段并在 adapter/case/result 间精确相等。
- Rule: 任何被报告为“zero clipping”的子算例都要有显式 acceptance 字段。Uniform Friction Decay 使用一次自然 CFL 步精确到达目标时间，不依赖最后一步裁剪。

## Sprint 4C 静态分析路径数组必须是 string/cell 容器 (2026-07-16)

- Pattern: 用 `[...]` 连接多条 MATLAB char 路径会生成一条无分隔符的长字符串，导致 `checkcode` 报“无法打开文件”，与被检代码质量无关。
- Rule: 批量 Code Analyzer、测试或模型路径必须使用 string array 或 cell array，并在汇总前打印文件数。路径聚合失败先修正检查入口，不把它解释为数值或模型失败。
- Rule: Simscape conserving-port inspector 的既知假阳性必须逐模型保留告警数量和独立 runtime/connection-graph 证据；不能用“behavioral pass”把 `model_check` 警告改写成 healthy。

## Accepted baseline 的 clean-tree 证明必须写入 Canonical Result (2026-07-16)

- Pattern: 只有 `git_commit` 而没有 `working_tree_dirty` 时，source commit 不能单独证明 Full 是从干净树生成；手工修改 manifest 会破坏审计链。
- Rule: Benchmark runner 通过 `git status --porcelain` 自动写入 logical `environment.working_tree_dirty`；新的 Full 必须验证 qualification commit 精确匹配且该字段为 `false`，再进行 report-only 和 promotion。
- Rule: MCP 的单次响应超时不等于 MATLAB Full 已失败。若进程仍有 CPU 活动且尚未写 artifact，保留同一 clean-commit 运行并只读监控；只有完整 manifest 和逐 artifact hash 才能构成 acceptance 证据。

## 非 Euler 验证 case 不得继承 PP solver gate (2026-07-17)

- Pattern: Sprint 4D-A 的 `radiation_impedance` case 在 `all` +
  `muscl_minmod_pp` 入口中，被原先“排除少数类别”的负向条件错误附加了
  Euler PP stage/positivity checks；物理 reference 通过但 suite 被误判失败。
- Rule: scheme-specific acceptance 必须使用“实际使用该 numerical solver 的
  case 类别”显式白名单，而不是持续补充排除列表。频域 radiation、解析、
  Simscape、Fanno 与 transient validation 不应承担 HLLC/MUSCL/PP 字段合同。
  每新增非 Euler category，至少回归其在所有 reconstruction 入口中不会被
  附加 PP checks。

## Simscape model_check 假阳性必须用精确 waiver 治理 (2026-07-16)

- Pattern: Sprint 4C 的两个 Pipe(G) 模型在 R2026a `model_check(["all"])` 下各产生 21 个 conserving-port `unconnected_ports` 警告，但 FVM 模型 healthy，且 Pipe(G) 模型的连接图、运行时 cross-validation 与确定性 benchmark 都通过。
- Rule: 不得把这类模型称为 healthy，也不得全局禁用或宽泛允许 Simscape warnings。waiver 必须绑定工具 release、模型路径及 SHA-256、check ID、完整有序警告签名、expected count、原因、替代验证和 review status；模型内容、工具 release、数量或签名任一漂移都必须重新审计。
- Rule: MCP 对长 MATLAB Full 的响应超时后，先以同一会话的 CPU liveness 和已保存 `results` 变量恢复最终测试证据；不要并发或重复启动第二个 Full 回归。

## 冻结 Simulink 模型必须在干净会话冷编译后才可复用 (2026-07-17)

- Pattern: Sprint 4D-B 的早期合同在已有 MATLAB 会话中通过，但在 crash/restart
  后，冻结 PP step 的 Stateflow 输入维度不能重新推导；缓存通过不等于干净编译
  可复现。
- Rule: 在任何新 adapter 或 Full matrix 前，必须运行 `new_system`、关闭/冷重载
  模型并执行被冻结 step 的单步 smoke。若该 smoke 失败，不得把问题归因给新
  boundary、不得修改 HLLC/MUSCL/PP 公式规避，也不得继续生成 accepted baseline。
- Rule: 对 `.slx` 元数据的诊断性修改必须先记录原模型 hash；除非获得专门授权
  并经过独立回归，不得把这类 binary diff 混入 Sprint 功能提交。

## 2026-07-21: JSON empty object is a MATLAB type boundary, not a generic struct

Rules:
1. `jsondecode` may represent an empty JSON object or a heterogeneous JSON object array as a cell-shaped value; normalize both list and item boundaries before any `fieldnames` or dot access.
2. The list normalizer must turn a struct array or cell list into scalar structs. The item normalizer must unwrap singleton cell layers until it reaches either an empty value (canonical empty struct) or one scalar struct; reject all other shapes explicitly.
3. A qualification orchestrator must not try report-only after Full has failed before producing a passing manifest. Record it as skipped, preserve the primary failure, and rerun only after the whole root-cause class is repaired.

## Stateflow 动态尺寸标记不是可忽略的 SLX metadata (2026-07-18)

- Pattern: 冻结 PP 模型的工作树 `.slx` 与 HEAD 比较时，`chart_16.xml` 的
  Stateflow data 条目出现 `isDynamic=1`，同时 blockdiagram/system XML 变化；
  这可能改变编译时尺寸推导，即使原 HEAD binary 已在干净会话通过。
- Rule: 只有 archive/XML 审计能证明为纯 metadata 才能恢复冻结 `.slx`。一旦
  发现 interface、size、dynamic-size、block parameter 或连线语义差异，必须保留
  审计副本并停止资格推进；不得将 `git restore` 当作诊断性 binary 改动的默认清理。

## 边界 ghost state 必须参与冻结 PP 的 CFL 预算 (2026-07-17)

- Pattern: 4D-B 的驱动 source 只存在于左 ghost state；若 dt 仅由物理 cell
  的 `max(abs(u)+c)` 计算，冻结 PP stage 会正确发现 ghost state 波速更高并
  返回 `CflClipped`，随后外层 retry 会掩盖为“普通性能问题”。
- Rule: validation-only characteristic drive 的 dt 上界必须包含物理 cells、正/
  负 source-amplitude envelope 和当前 radiation ghost；显式记录共享 stage dt，
  nominal benchmark 的 retry/reject 必须为零。不得通过运行时静默缩步把该 CFL
  不一致伪装成稳定性。

## 外部每步 Simulink 调度不能作为 N=800 Full runner (2026-07-17)

- Pattern: 即使启用 Fast Restart，外部 MATLAB loop 仍需为 SSP-RK3 每个物理步
  调用三次 `sim`；最小 radiation run 已实测 `151` 步/`62.99 s`，无法支撑四档
  N=800 的长期基准。
- Rule: 需要长时/细网格资格时，必须把多步调度置于受控模型或等价的单次仿真
  组合中，并复用而非复制冻结 numerical core。不可为了缩短运行而减少物理传播
  窗口、隐式降 CFL、跳过 full grid 或把未完成 output 提升为 baseline。

## 夜间连续授权不覆盖活动 MATLAB 的安全边界 (2026-07-23)

- Pattern: Jovi 已授权在每阶段自审、普通实现失败持续修复并继续后续垂直切片；
  但旧 nightly MATLAB child 越过硬门限且没有任何可接受终态。
- Rule: 将连续授权视为对已批准范围内的实现授权，而不是对活动 MATLAB 的
  杀进程、第二实例、MCP 重连或并行 qualification 授权。硬门限只可做一次可见
  Stop/Ctrl+C；未安全退出前，旧输出仅保留诊断价值，源码/模型/config/schema/
  threshold 不得与其并发修改。

## MATLAB Desktop 启动崩溃是自动化生命周期缺陷时必须先修复触发条件 (2026-07-23)

- Pattern: 先前由 agent 在现有 agentic session 旁启动 `matlab -batch` 及其变体，
  触发 GTP/Home Session Manager access violation。本次旧 Desktop 已退出后，仍有
  15 组 `matlab-mcp-server.exe` root/watchdog 存活；两次普通 Desktop 启动均再次
  产生同一 `GTP_*` / `mwhomesessionmanager_impl.dll` 崩溃族 dump。
- Rule: 不得将这种情况笼统表述为“不是代码问题”。S12 数值源码没有进入崩溃栈，
  但自动化启动/会话生命周期代码是已知触发条件，必须先修复和隔离。
- Rule: 在要求 Jovi 打开 MATLAB Desktop 前，先用只读进程门禁证明
  `MATLAB.exe=0`、`matlab-mcp-server.exe=0`、其 watchdog=0；若 MATLAB 不在运行，
  只停止经命令行核验的 MATLAB MCP root/watchdog，绝不触碰 MATLAB 或
  MathWorksServiceHost。任何 access violation 后不再尝试启动变体；重启后必须先
  手动稳定 Desktop，随后才允许一个 existing-session MCP。
- Rule: 此主机的 `C:\Users\Admin\.codex\config.toml` 必须保持
  `[mcp_servers.matlab] enabled = false`。全局自动注册会在没有 Desktop 时并发孳生
  多组 existing-session root/watchdog；不可为了自动化便利重新启用它。
- Rule: 若 `sessionDetails.json` 的 PID 已不存在，在确认 `MATLAB.exe=0` 和所有 MCP
  helper 为 0 后，将该单一注册文件移入同目录 quarantine，而不是让下一次启动附着到
  失效会话或删除用户的 MATLAB 偏好。

## Simulink 库块显示名中的换行必须保留为真实字符 (2026-07-26)

- Pattern: v0.9 builder 将 `dspsnks4` 的 Audio Device Writer 显示名中的 XML `&#xA;`
  误写为 MATLAB 字符串字面量 `\n`；MATLAB 不解析该转义，`add_block` 因找不到模块而失败。
- Rule: 从 `.slx` XML 转录 block path 时，`&#xA;` 必须写为 `newline`（或真实换行），
  不能写 `\n`。为每条包含该字符的库块路径增加源码契约测试，并先做静态 archive 核验。

## MATLAB Function block 的脚本属于 Stateflow chart，不属于 SubSystem 参数 (2026-07-26)

- Pattern: v0.9 builder 将 `simulink/User-Defined Functions/MATLAB Function` 创建后的对象当成普通
  block，并尝试 `set_param(..., "Script", ...)`。R2026a 将其公开为 SubSystem，因没有该参数而失败。
- Rule: 创建 MATLAB Function 后，通过 `sfroot` 精确查找其 `Stateflow.EMChart`，验证唯一性后赋值
  `chart.Script`。不得猜测 SubSystem mask 参数；为 builder 保留该路径的源码契约测试。

## 没有可调用 MATLAB 会话工具时，不得把执行与调试负担转交给用户 (2026-07-26)

- Pattern: v0.9 需要实际 Simulink 构建，但当前 Codex 会话没有 `matlab`、`model_edit`、`model_read`
  或 Desktop computer-control tool；仍先写了 builder，再要求 Jovi 连续执行和回传错误。
- Rule: 在任何 MATLAB/Simulink 实现前，先核验本会话的可调用工具。若没有安全的 existing-session
  控制面，必须在首次写代码前如实报告阻塞，不得把正常构建、测试或连续排错改为用户的人工执行步骤。

## 新建 Subsystem 的默认 In1/Out1 必须显式移除或复用 (2026-07-26)

- Pattern: v0.9 builder 新建 Subsystem 后直接添加命名端口，但没有移除自动创建的 `In1 -> Out1`
  旁路。顶层按端口号连接时接入了默认标量端口，Dashboard 的 19 元配置向量未到达 MATLAB Function。
- Rule: 对 builder 创建的每个 Subsystem，先删除默认 `In1` 与 `Out1`，再添加设计端口和连线；
  结构测试必须断言每个子系统的 input/output port count 和顶层连接顺序，不能只断言 block 名存在。

## 审计 SHA 与工作区同名二进制必须分离记录 (2026-07-26)

- Pattern: v0.9 审计合同记录的旧无效 SLX SHA 为 `FA91...95C0`，而工作区同名 SLX 的只读 SHA 为 `4324...3CC5`；将二者视为同一证据会让后续 rebuild 的输入身份失真。
- Rule: 所有二进制证据均须同时记录路径、长度、SHA 和来源包。发生同名 SHA 不一致时，立即冻结为 `WORKSPACE_BINARY_IDENTITY_MISMATCH`，保留两份只读副本，禁止用当前工作区二进制代替历史证据，也不得启动重建，直至独立审核完成协调。

## Simulink 审计“生成成功”不等于“可控重建就绪” (2026-07-26)

- Pattern: builder 源码可被静态修正，`.slx` 仍可能是修复前或未验证二进制；若提前把 source fix、SLX generation 或 Python static test 描述为 Simulink 成功，会掩盖 Load/Compile/Simulation/PCM/Audio/Sensitivity/Repeatability 的独立门禁。
- Rule: 对 Simulink 任务固定逐层标注 `generated but not validated`，直到每一层有对应运行证据。独立审计未给出 `READY_FOR_CONTROLLED_REBUILD` 前，授权转换、orchestrator 和 runner 只能作为 future-only source contract，不能启动 Desktop/MCP、加载或修改 SLX。
- Rule: evidence role 必须含 path、SHA、size、role、mutable、allowed operations；历史无效证据与工作区未验证二进制不得合并。审计报告原文不在工作区时，只能放 SHA/reference descriptor，不能伪造副本。

## v0.9 受控重建的源码哈希与运行证据必须物理隔离 (2026-07-26)

- Pattern: v4 的递归 source-tree SHA 同时覆盖 playground 下的未来 transaction、authorization claim 和临时构建目录；preflight 在 authorization 前写 JSON 会使被授权 SHA 自行漂移。另有 runner 吞掉仿真异常、只用多变量场景比较敏感性、且 compile cleanup 回调捕获了旧状态值的风险。
- Rule: 所有 transaction、claim、progress、cleanup、promotion、PCM/WAV 和 final JSON 必须写到源树外的 runtime root；source hash 只能列举不可变 `.m/.json/.py` 合同和命名测试，并在 preflight、authorization、build、promotion、final report 边界重验。
- Rule: compiled 属性只能在 `update → active compile → inspect → term` 的单一 helper 内读取，cleanup 必须共享 active-compile 状态并保留 primary failure。未来 runtime runner 必须把 failure JSON 落盘后 rethrow；repeatability 使用独立输出目录，敏感性只能改变一个 `[18,1]` 输入元素。

## v0.9 审计包绝不允许混合 source snapshot (2026-07-26)

- Pattern: v5 ZIP 的 canonical `source/` SHA 与根目录报告 SHA 不同，说明 staging 或报表在冻结源快照前后发生了混用；先前“新鲜解压 self-test”没有实际重算并交叉核对全部声明。
- Rule: 每轮审计只能从一个明确 canonical workspace root 复制一次 source/test。冻结该副本后才计算 immutable source SHA，并由同一变量生成 root summary、reports self-audit、identity manifest 与 delivery message。自检必须重新计算 source SHA、解析所有声明，并拒绝顶层孤立 `.m`/测试副本或重复 basename。生成的报告/manifest 不应进入 source SHA 作用域，以避免自指哈希。

## v0.9 离线敏感性指标必须与被控因果量一致 (2026-07-26)

- Pattern: 将约 3 kHz 至 Nyquist 的宽频能量称作 harmonic/order energy，会把无关频段和窗泄漏计入 load 敏感性；直接比较两条 PCM 的全局 peak/energy，又会把 acceleration 的局部 transient 混同为整体响度变化。
- Rule: future load gate 必须按 `rpm/60*order` 的冻结 order-centered bands 计算 1--4 阶能量，并冻结 order2/order1 比值门限；future acceleration gate 必须只在冻结 transient window 内分析 `varied_pcm-base_pcm` 的 delta energy/RMS/peak。两者均须有不调用 MATLAB 的 source-equivalent 数值测试，且不得据此宣称 Simulink PCM 已验证。

## Simulink future-only 控制合同必须与被审计对象解绑历史序号 (2026-07-27)

- Pattern: v0.9 前几轮将 `audit_version`、历史报告 SHA 和 ZIP identity 写死在 future authorization 源码；同时 scenario 的 configuration frame 与 workspace signal 有两套可漂移表示，锁释放又在主锁消失后才建立证据。静态修复即使通过，也不能成为本次或未来审核的批准依据。
- Rule: 源码只冻结 authorization schema，外部 authorization 必须用当前审核报告、ZIP、ZIP 内 immutable source SHA、当前工作区 source SHA、双 SLX evidence SHA、preflight SHA 和单次 authorization ID 显式绑定。任何 frame 变更必须走唯一 finalization；任何 release 在删除主锁前先落盘 blocking intent，并以 qualification report 加 release-completion receipt 的两阶段证据收口。离线测试只能证明合同，不得宣称 Build/Compile/Simulation/PCM/Audio 成功。

## 产品闭环授权取代离线审计版本时必须立即切换终点 (2026-07-27)

- Pattern: 第七次离线审核之后，新授权明确要求停止继续生成审计 ZIP，改为 Runtime Proof 驱动的 Simulink 调音、参数包、PC Runtime 与 Android 产品闭环。如果继续增加 v8/v9 离线审计版本，即使静态测试更完整，也偏离了用户真正要验证的运行链。
- Rule: 新授权取代旧停止条件后，删除本轮尚未交付且只服务旧审计版本的新增文件，保留根因证据，并把第一门禁改为真实 Runtime Proof。没有唯一稳定 Desktop/existing-session 控制面时只完成离线准备并标记 `MANUAL_RUNTIME_REQUIRED`；不得越过 Runtime Proof PASS 实施 Dashboard 或 App 闭环，也不得用离线合同冒充运行结果。

## Runtime Proof 收口指令必须压缩治理而不是继续扩展产品阶段 (2026-07-27)

- Pattern: 产品闭环授权之后，用户进一步明确本轮只做首次 Simulink Runtime Proof，并要求通过或失败后立即停止。若仍保留 Dashboard、参数包、Android 等后续工作为本轮待办，或者继续拆分审计/授权版本，就再次扩大了当前停止条件。
- Rule: Runtime Proof 单任务指令生效后，只保留一个 user-started Desktop 手动入口、一个 run-specific 临时目录和一个临时模型；Gate 必须按运行证据顺序 fail-fast。没有 existing-session 工具时只完成源码与静态测试，并输出一条 `run(...)` 命令；不得启动 MATLAB/MCP、自动重试、promotion、commit 或进入后续产品阶段。

## 最新连续授权可恢复后续阶段但不能解除前置 Runtime Gate (2026-07-27)

- Pattern: Runtime Proof 单任务收口之后，用户再次发送完整产品闭环连续授权，重新要求 PASS 后继续 Dashboard、参数包、等价性、Android 与标定。停止条件以最新授权为准，但前置运行证据并未因此自动成立。
- Rule: 最新授权可以重新激活下游待办，却不能把 `MANUAL_RUNTIME_REQUIRED` 转换成 PASS。只在真实 Build/Compile/Simulation/PCM/Sensitivity/Repeatability/Device Smoke 全部通过后解锁 Phase 1；MATLAB Desktop 或 existing-session 工具缺失时仍停在 Phase 0，不提前写下游代码。

## MATLAB fail-fast stage log 必须从首条记录就具备字段合同 (2026-07-27)

- Pattern: Runtime Proof 用 `struct([])` 初始化 progress，却向其中追加含 `run_id/stage/status/start_time/end_time/artifact/error` 的记录。MATLAB 在真正 operation 抛错后又在错误路径因结构体字段不匹配而失败，导致原始异常被遮蔽、阶段 JSON 未落盘。
- Rule: 所有 MATLAB stage log 都用同字段的 0x0 struct 初始化，并以 RED 测试锁定首条 success/failure record 可追加。发生记录器异常时，不把它归因于 builder 或模型；先修记录器，再只重跑一次以获取原始 Gate 证据。

## MATLAB JSON 原子写入应以 fclose 作为兼容刷新边界 (2026-07-27)

- Pattern: Runtime Proof 的 stage recorder 调用了 R2026a 未定义的 `fflush`。这发生在 operation 已返回之后、`fclose` 之前，既遮蔽下一阶段判断，又使 onCleanup 删除仍打开的 `.tmp` 文件而产生占用警告。
- Rule: MATLAB JSON writer 只使用 `fprintf` 后的 `fclose` 作为 flush/close 边界；用 RED 测试禁止 `fflush`。任何 writer 异常都先视为记录层失败，不能归因于 Simulink block、Compile 或 Audio。

## Runtime Proof JSON 写入必须在替换旧目标前完成关闭、解析与内容校验 (2026-07-27)

- Pattern: 仅删除不兼容的 `fflush` 仍不足以证明 writer 安全：旧实现没有检查真实写入字节数、`fclose` 结果、临时 JSON 可解析性或发布后目标内容，也没有在会话出错后精确回收遗留 file ID。
- Rule: JSON writer 只能在目标目录创建其 own temporary 文件；必须显式关闭 exact file ID、验证临时文件字节数/JSON/SHA、再同目录发布并重读目标 JSON/SHA。异常 cleanup 先关 owned handle 再删 owned temp，绝不使用 `fclose('all')`。会话恢复只可用 `openedFiles` 精确匹配当前 transaction 与 `.s12_playground_json_*.tmp`，不得关闭用户或 MATLAB/Simulink 文件；writer self-test 必须先通过才允许一次 Runtime Proof 续跑。

## MATLAB Java NIO 路径和 varargs 必须通过兼容适配器 (2026-07-27)

- Pattern: atomic JSON writer 先在 `Files.createFile(Paths.get(candidate))` 停止，修正预留后又在 `Files.move(Paths.get(...), Paths.get(...), options)` 停止。R2026a 对 `Paths.get` 以及 `createFile` 的 Java varargs 调度不兼容；吞掉异常会把 API 签名问题伪装成路径、空格或权限问题。
- Rule: 所有 MATLAB Java NIO Path 构造必须经唯一 `java.io.File(...).toPath` helper，不得再调用 `Paths.get`。Java varargs API 必须显式传递空数组（如 `FileAttribute[]`）；只在候选文件确实已存在时重试，其余 Java 异常必须保留原始消息立即 fail-fast，并由最小 RED→GREEN 合同锁定。

## Runtime Proof 修复必须由 Agent 运行整套 MATLAB 测试，不能交给用户代测 (2026-07-27)

- Pattern: 连续的 writer/preflight 修复只做了 Python 静态断言或单文件 MATLAB 测试，遗漏了 SHA char/string、suite path isolation、`validateattributes` R2026a 类型兼容和 stage schema 等实际执行问题，最终让 Jovi 反复承担首错收集。
- Rule: Runtime Proof 相关变更先写 MATLAB regression，再在唯一 existing-session Desktop 中执行汇总 `runtests`（failed=0、incomplete=0）、writer self-test、Code Analyzer、Python static 和 canonical SHA 核验。任何 helper suite 的首错都必须由 Agent 全仓搜索同类模式并自行修复；用户只在真实 device smoke 成功后确认扬声器听感。
- Rule: SHA 全值比较只允许 scalar SHA helper；文本 whole-value 比较只允许 `strcmp`/`isequal` 且动态字段先验证；进度记录从固定 0x0 schema 开始，绝不以 `struct([])` 承接不同字段记录。

## MATLAB Function 脚本文本不得用 sprintf 包含 %#codegen (2026-07-27)

- Pattern: 首轮 Agent Runtime Proof 已通过 atomic writer preflight，却在 `temporary_build` 中把 MATLAB Function 脚本里的 `%#codegen` 交给 `sprintf` 解析，触发 `MATLAB:badformat_mx`。这不是 Simulink Compile 失败，且单纯检查文件存在不会发现。
- Rule: 生成 MATLAB Function 脚本文本必须用 string concatenation 与 `newline`，不要让 `sprintf` 处理包含百分号的源码。每个生成脚本都要有实际 MATLAB unit test，至少验证 scalar 文本、函数声明和 codegen directive；修复后的完整 helper suite 由 Agent 在唯一 shared Desktop 执行，再使用剩余的一次 Runtime Proof。

## Stateflow 根对象访问必须显式调用 sfroot() (2026-07-28)

- Pattern: 第二次受控 Runtime Proof 已通过 JSON preflight 并进入真实 temporary model build，却在 `sfroot.find(...)` 停止。当前 MATLAB 只允许对函数返回值使用 `sfroot().find(...)`，而 Code Analyzer 与普通文本生成测试没有发现此语法兼容性问题。
- Rule: 所有 Stateflow root lookup 都必须通过 `root = sfroot(); root.find(...)` 或 `sfroot().find(...)`，并用真实 MATLAB regression 覆盖 lookup 语法。Runtime Proof 有上限时，先全仓搜索同类 `sfroot.` 调用再使用剩余受控执行；达到上限后只固化证据，不修复或重跑，等待新授权。

## Stateflow 固定尺寸与动态属性必须读取运行后真值 (2026-07-28)

- Pattern: 修复 root lookup 后，R2026a 首先返回 `[18,1]`，暴露出 MATLAB regexp 的双反斜杠错误；修复解析器后，builder 已赋值 `IsDynamic=false` 的 `packed` chart input 仍读回 `true`。静态结构和赋值语句都不能证明 Stateflow 实际保留了接口合同。
- Rule: Stateflow I/O 合同必须测试三层：尺寸文本的真实解析、属性写入、同一运行内的 readback。遇到 readback 不同于写入时，不要直接篡改 expected 值或删掉 gate；先以最小 live chart 复现实例调查 R2026a property/creation sequence，再新增 RED→GREEN 回归。每个 repair cycle 最多两次 Runtime Proof，第二次失败后只保留 transaction 与报告。

## MATLAB Function 输入可变性、Compile Workspace 与敏感性控制必须按运行语义分层 (2026-07-28)

- Pattern: R2026a 的 MATLAB Function 输入变量从连接的 Simulink 信号继承 size variability，因此 `Props.Array.IsDynamic=false` 对 input 可被忽略；同一模型的 output 则可以并必须显式固定。另一个独立缺口是 From Workspace 在 Update Diagram/Active Compile 前尚未收到 Model Workspace 数据。RPM 敏感性 pair 又沿用了会波动的 idle load/throttle，使“非目标控制量必须常量”的合同自行失败。
- Rule: Stateflow input 只校验名称、Scope、尺寸文本和类型，固定性最终由 Signal Specification 与 compiled dimensions 证明；output 继续校验 `IsDynamic=false`。任何含 From Workspace 的模型都必须在每次独立 Update/Compile 打开周期内向该模型自己的 Model Workspace 发布并读回固定尺寸数据。单变量敏感性 pair 必须先把所有非目标控制量冻结，再只改目标行并验证唯一 delta。
- Rule: 共享 Desktop 中修改 `.m` 后，Agent 必须清除相关函数缓存并 `rehash`，再由 Agent 自己运行 RED→GREEN、完整 helper suite 和 Runtime Proof；不得让 Jovi 承担缓存旧代码或首错采集。

## Stateflow chart script 的换行必须由 MATLAB `newline` 生成 (2026-07-29)

- Pattern: v1.0 批量模型创建把 JavaScript JSON 的 `\\n` 传入 MATLAB string；MATLAB 把它保存为反斜杠和字母 n，导致 MATLAB Function chart 解析失败。I3 使用 `newline` 创建的同一脚本可运行，证明问题在脚本传输而不在 excitation/PTR 数学。
- Rule: 任何通过 MCP/evaluate 写入 `Stateflow.EMChart.Script` 的代码都必须在 MATLAB 端以 string concatenation 与 `newline` 组合，禁止把跨语言转义后的 `\\n` 当作真实换行。批量建模后必须逐模型冷加载并 Update，再报告其状态。

## 八车型声纹不能由参数差异或静态距离门限代替参考拟合与听感 (2026-07-30)

- Pattern: v1.1 虽有八套 profile、85/85 static contracts 和 pairwise threshold `0.05`，但 91 个 render 参数中有 60 个相同；共享六阶正弦、firing gain、afterfire kernel 和 source envelope 使人耳仍感到八车接近。
- Rule: 车型真实感只能以可追溯 stock/exterior-rear reference、曲轴角阶次/频带/瞬态派生 target、reference-vs-synthetic distance、跨车检索和 Jovi 盲听共同证明。参数数量、JSON provenance、静态测试、WAV SHA 或普通 FFT 都不能单独证明“像该车型”。
- Rule: 任何 reference 缺少车型/stock/视角或 RPM 证据时，只能标记 R2/R3 qualitative/rejected；不得把它用于数值拟合或提升 OEM source level。所有新增声源、换挡和 afterfire 必须在 PTR 前，并保持 deterministic/no-sample/no-hard-limiter 边界。

## 派生分析的公开自哈希不是来源认证 (2026-07-30)

- Pattern: v1.2 reference analysis 通过了 24 项静态合同，却仍允许用户修改完整 R1 的 make/trim/stock 声明后复用旧 analysis；也允许把 coherent metrics 与其公开 SHA 一起重算。自哈希只能发现无意篡改，无法在无密钥的 JSON 边界证明 PCM 与 reference 的来源关系。
- Rule: 不得把公开 JSON self-hash 写成来源认证。target builder 必须在同次调用内接收完整 R1 manifest 与瞬态 PCM/RPM/event 输入并重新计算分析，分析 binding 必须覆盖整个 canonical manifest。Git 仅保存派生数据；公开录音的真实性依赖可审计 R1 证据与人工审核，不伪装成密码学证明。
- Rule: 媒体隔离须检查 key 和 value。除唯一外部 raw-media-root policy 外，所有 field value 中的 file/data/ftp URI、Windows/Unix/relative path、percent-encoded path traversal、cache 位置和音频文件扩展都必须拒绝；URL path/query 也不可成为绕过口。

## 清理 existing-session MCP 会使当前 Codex stdio 传输不可重建 (2026-07-30)

- Pattern: 为消除重复 existing-session MCP 而终止全部 `matlab-mcp-server.exe`/watchdog 后，MATLAB Desktop 与 MathWorksServiceHost 仍健康，但当前 Codex 会话持有的 stdio transport 已关闭；首次只读健康检查在 MATLAB 执行任何代码前即返回 `Transport closed`，且未自动生成新的 server process。
- Rule: 清理 MCP 前先停止所有会调用 MATLAB 工具的并行 agent；清理后只验证 `MCP=0` 与 MATLAB PID 未变，不在同一个 Codex 会话中重试任何 MATLAB MCP 调用。必须先重建一个新的 Codex transport，再仅建立一个 existing-session MCP，并以一次只读版本/工作目录检查作为首个 gate；出现 `Transport closed` 后 fail-fast，绝不重试、绝不启动第二个 MATLAB。

## 名为 PTR/Radiation 的试听适配器不能等同于完整物理核心 (2026-07-30)

- Pattern: v1.1 模型解析到 canonical `s12_sound_playground_ptr_tuning_step.m`，但该文件明确声明只用于 synthetic visual/audition，绝不调用冻结 PTR/radiation 数值核心。Python `RuntimePtrAdapter` 虽消费已接受 4D-B 二状态边界包并跨帧保持状态，也只构成轻量音频适配层，不等于完整 FVM/PTR 管网。
- Rule: 接口真实性必须从被调用入口逐层追到接受基线、内容 SHA 和数学范围；文件名、模型标签、wrapper 路径或“frozen”字样都不是物理接入证据。报告必须区分完整 FVM/PTR、冻结 radiation package 适配器和 synthetic audition adapter；未接入的层保持明确未完成。

## model_edit 后必须显式保存并冷加载读回 (2026-07-30)

- Pattern: `model_edit` 在已加载的空模型中成功创建结构，但后续脚本执行 `close_system(model,0)`，把尚未写入磁盘的结构全部丢弃；同一会话内的 `model_read` 曾看到块，磁盘冷加载却为空，导致上层 Model Reference 解析为零端口。
- Rule: 每次 `model_edit` 后必须依次执行结构 `model_read`、`model_check`、Update Diagram、`save_system`、关闭、冷加载 `model_read`。任何 Model Reference 建立前都必须以磁盘冷加载确认被引用模型的端口，不得把内存图当作已交付 SLX。
# 声学身份分离不足以代表真实感 (2026-08-02)

- Pattern: v0.15 已证明三套 source 在阶次和相关性指标上可分离，但试听仍约 30% 真实；确定性怠速、固定低频谐振、静态增压正弦和缺少 closed-throttle 瞬态会让独立拓扑听起来仍像程序模板。
- Rule: 后续“真实感”修复必须先建立来源/录音风险与可复算特征合同，再由状态驱动的 cycle variation、pressure/exhaust/body chain、thermal-gated afterfire 和惯性 boost state 进入 pre-PTR source。不得以 RMS、单纯增益、固定 EQ、随机白噪声或更低的 separation 门限替代；自动 PASS 仍不等于人耳 PASS。

## 试听链接必须包含触发目标所需的完整工况 (2026-08-04)

- Pattern: 向 Jovi 交付了 `full_pull.wav` 作为试听入口；该工况持续开节气门，按模型定义不会触发“高转 + 热态 + 收油”的 afterfire。独立 `deceleration.wav` 虽有回火，也不等同于完整驾驶过程。
- Rule: 若试听目标包含回火/减速，默认交付每车一条连续 `idle → acceleration → loaded pull → abrupt closed-throttle lift → coast → idle` WAV，并在 metrics/report 中逐车断言 lift 后 `afterfire_event_count > 0` 和 afterfire energy > 0。不得用已经响度处理的分段 WAV 拼接来代替连续状态渲染，也不得将 `full_pull` 单独作为完整试听链接。

## 数字响度通过不等于实际设备听感通过 (2026-08-04)

- Pattern: Hellcat 完整试听已测得 `-16 LUFS`、`-3.12 dBFS` peak、零削波，且低频轰鸣获得 Jovi 部分认可；但 Jovi 在实际播放时仍明确感到整体音量偏小。数字健康/响度指标没有覆盖 Windows 音量、声卡、耳机/扬声器低频滚降、环境和人耳感知。
- Rule: 后续响度阶段必须把“数字 master 合格”和“设备/人耳合格”分开报告。先以单一全程固定 gain 的小幅 audition-master A/B（例如 Hellcat `-16` 与 `-14 LUFS`，并保持 peak/headroom）诊断播放级别；不得用 RPM 音量耦合、per-clip AGC、削波或盲目增加 50 Hz 低频替代设备与人耳审核。
# 2026-08-09 S12 Stage C integration lessons

- The standalone 60-second prototype is a direction probe, not production evidence: its shift count was false, its 70 Hz boom used the wrong time base, its centroid claims were hard-coded, and it duplicated the formal afterfire layer.
- Python `hash(vehicle_id)` is process-salted; deterministic audio must use explicit stable profile data or fixed integer seeds.
- Track-P path freezing uses substring matching. A Track-S file whose path contains `ptr` can fail the guard, so equalizer naming must avoid that substring without changing governance.

# 2026-08-09 S12 Stage D human listening lessons

- Automatic source/PCM metrics and a closed-set confusion matrix prove implementation health and identity separability; they do not prove that a listener hears Ferrari, Hellcat, or RX-7 as a realistic engine.
- Identity recognition and “candidate sounds more realistic than Stage C” are separate human gates. A candidate may pass one and fail the other, so both results must be recorded independently and no human PASS may be inferred from automated tests.
