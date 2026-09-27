# APP-2 PR #33 状态转换审查修复计划

状态：远端 `c2c_7d2f / iteration 1` 返回 `CHANGES_REQUIRED`，限定 F1–F3。本计划在既有 `feature/stage-app1-android-runtime-20260924` 上执行，不合并 main。

## 基线与边界

- 起点 `a059ea4d4011cfd74a8c644f2c522d6e0644ca87`；PR #33 为 open/draft，base `main@29b50961d9628f835e7172b797380ccb36a7f38d`，本地与远端 head 一致。
- 原候选 APK SHA-256 `464EAC5D3FE35D7BC84E9A4749DAA3FD10EFBEEBFEEB95E40BEB2B08A403B487` 已复制到 `E:/Tesla_speed/review_packages/s12-app2-transition-c2c_7d2f-i2-v1/`；完整基线 patch 和 name-status 同处保存。
- 允许修改实时核心 profile 切换、Android 播放服务／原生桥／控件与定向测试、任务和报告。两份实验 profile 声源参数、Python Golden、受保护声学模型、旧 `:app`、PR #31/#32 和 main 保持原状。

## 增量与证据

1. F1 静音启动与普通停止：先写 VolumeRamp 首样本精确零、有限帧起停包络及原生 stop 完成测试，记录 RED。音量 0 在打开 Oboe 前固定为静音；正常停止 960 帧内到精确零，再由控制线程关闭。断流/错误关闭有控制线程有限超时和 ERROR_HARD_STOP 诊断。实时回调不等待锁、不调用 JNI 或删除对象。
2. F2 profile：先写重复选择与不切换逐样本一致、A→B→A 快速请求、跨分块输出一致和峰值上界测试，记录 RED。相同稳定 profile 为 no-op；淡化过程中仅保留最新一个待切换请求，当前混音完整结束再启动下一次 100ms 淡化。线性交叉权重非负且和为 1；音频回调每次最多消费固定数目命令。
3. F3 输入过期与会话代次：新建小型、无 Android 依赖的 `DriveSessionState` 和 JVM 假时钟测试，覆盖等待首样本、250ms IMU 超时、恢复、Replay↔Drive、Stop→Start 与旧回调。服务每 50ms 检查是否过期，仅在有效→无效转换时将无效状态交给 native；UI 从同一不可变快照读取质量和速度，过期显示不可用。保留原 500ms native 兜底，不把旧测量时间重写为新有效样本。
4. 验证：逐项 GREEN，再运行原生 runtime_tests、VolumeRamp 主机测试、全部 player JVM、Python/C++ 12 项、`:app:assembleDebug :player:testDebugUnitTest :player:lintDebug :player:assembleDebug`、Track-P guard、`git diff --check`。模拟器验证新版 APK 的静音启动、切换、后台停止和快速重开；不以模拟器代替真机。
5. 发布交接：保留原候选；新 APK、原始命令/输出、测试源码对应 commit、模拟器记录、base→final 与 start→final 差异、PR live base/head 存入包外收据。提交并正常推送同一 APP 分支，使 PR #33 更新；向原“音浪”聊天提交 `EXECUTED` 请求复审。没有人耳/权利/OEM/产品放行提升。

若需要修改声源参数、旧 Golden、受保护模型或发生分支身份冲突，停止并保留现场，不扩大本轮范围。
