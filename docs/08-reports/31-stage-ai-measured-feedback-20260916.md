# Stage AI — 真实误差反馈接入四车与 A/B/C 证据分离

## 当前阶段与基点

2026-09-16 新授权：继续工程、分步提交，完成一阶段后交本地 Codex 验证。
基点为 `feature/stage-ah-three-way-audition-20260915@c52d5011c80528f564bba650b98efbd3c82f80f8`，它包含 `676478952f18c671fe2863e198e25dff91db32a8` 的两车闭环/失败隔离。主线仍是 `d98a6238c091187595e71c0c88e8fa0e718548c2`。本阶段不合并 main，不改历史分支、音色默认、IR、Reference 或旧包。

新分支：`feature/stage-ai-measured-feedback-20260916`。所有动态 SHA 和 CI 必须现场读取。

## 审核结论（来源边界）

用户本地报告：Aventador 已执行 25 次试探，训练 0.7782814707→0.7758840044，validation 0.6338016382→0.6281315657。它们是既定频谱形状误差，不是60–80%的相似度证据。RX7 基线 09_steady_mid 的4×插值峰值1.031113…使其没有获得可用B。

远端可见代码：四车 B 是固定源参数修改；Supra B 是固定 overlay；仅因为文件不同或名为feedback，不能叫同一种自动闭环。当前 three_way_audition.py 将这些统一命名反馈，可能使用户误解。此外切到缺失B/C场景时直接return可能残留旧场景播放；新页面包装器予以修复。

## 分阶段实现

AI-1 `feedback_evidence.py`：自动B资格要求真实fit schema、接受过的参数、完整trial与独立来源validation；固定recipe或伪成功标签不合格。加入sequence/previous SHA的JSONL日志，每个render开始/结束flush+fsync。日志是可追溯收据，不是防篡改认证系统。

AI-2 `fourcar_reference_loop.py`：复用现有 `reference_feedback.optimize_reference_feedback`，将参数传入实际 `FourCarRealReferenceEngine` 命名声源。不是写第二个模拟器，也不套混音EQ。四车每车只搜既有一个参数；范围为本阶段工程边界而非OEM标定范围。25组参数默认预算、同seed/trace/flags、C0输出保护和scene+trace父分母不变。训练源码来源不跨validation；每次最终验收后不以validation结果继续自动搜索。旧四场景/车相对Reference +3%诊断继续保留。无改善/验证退化/数值失败回退基线，不强行给一个不同声音。

AI-3 `qualified_three_way.py`：保留原八车十场景富交互模板，A/C逐字节复制旧三路包。B只能来自经验证的自动fit，并核对其baseline与页面A相同、十场景数值/轨迹/输出策略、PCM/WAV。页面提供日志入口，列出A/B相同场景，禁用无合格B。C63/Supra仍可A/C，旧fixed recipe继续留在旧包。RX7继续阻塞；Aventador可导入已有合格fit。没有伪造其它车已执行真实搜参。

## 本地唯一执行闭环

1. 拉取新分支；建干净worktree；核实本阶段CI。
2. 定位已有四车C0父包，从原experiment/c0_report独立核对manifest文件SHA。
3. `python -m tools.sound_sim.s12.acoustic_identity_v015.stage_ah.fourcar_reference_loop prepare --baseline-package <C0> --manifest-sha256 <SHA> --out <fresh-plan.json>`。
4. 本地审核既有五来源的粗RPM/负荷/事件工况、viewpoint与窗口，不直接把所有comparable改true。同来源不能跨组；缺少合适validation则报告缺口，不拿驶过低转和全负荷比较。
5. `...fourcar_reference_loop run --plan <approved-plan> --out <fresh-run> --max-trials 25 --allow-r3-unsynchronized`。
6. `...qualified_three_way build --old-run <old-ABC-v5> --old-sha <SHA> --fourcar-run <new-fourcar-fit> --fourcar-sha <SHA> --two-run <existing-Aventador-loop> --two-sha <SHA> --out <fresh-ABC>`。
7. `...qualified_three_way serve --run <fresh-ABC> --sha <ARTIFACTS-file-SHA> --port 29580`；先preflight-only，再实际浏览器A/B/C切换与八车导航。A/C不改，只有有据可依的B启用。

新报告逐车包含history、parameter_delta、source分组、baseline/selected losses、旧Reference guard、全场景数值记录；日志在diagnostics/<vehicle>/，页面内有独立证据入口。基础数据或来源漂移阻止发布。失败保留诊断、不冒充完整包。

## 数值/声学边界与后续

RX7 的样本峰值<1不意味着4×重建峰值<1。本轮保留原阈值，不降gain、不删除门禁、不对clipCount写0。下一阶段需在本机相同IR做峰值位置/频带/非线性重建诊断，再决定源带限或过采样输出方案；当前没有足够实物证据直接定唯一原因。

Aventador结果虽有改善但幅度不大；现有目标函数是时间汇总相对频谱功率，不识别所有瞬态顺序或精确转速/麦克风链。完成当前四车回路后才考虑工况/阶次分辨目标函数，不将多次搜参到边界伪装为20%相似度消除。参数触顶仅作为诊断，不能据此自动扩大范围。

阶段完成=代码及隔离测试资格+本地接手路径，不代表真实素材已在远端拟合。无Human PASS、无OEM、无Profile Freeze。没有新素材下载、开源代码/权重复制或第三方音频进入Git。没有必要声称又集成了多个完整开源引擎；本轮是在现有工程中真正调用此前缺失的反馈路径。
