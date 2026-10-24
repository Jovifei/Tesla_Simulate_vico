# W7 · Vico Web 仪表完整接力与设备输入安全闭环（2026-10-24）

**交付仓库**：仅 \`Jovifei/Tesla_Simulate_vico\` 的 \`vico_web/**\`；Draft PR39，base为 \`codex-remote-stage-20261011-integration\`，不合main，不更改线上服务器。基线Web SHA \`22cadf391773eac13d8c146a05d5a1b36f2725f6\`，源资产冻结父 \`477913e7500bb3ff13c3b72cf5b1a3cac1b28145\`。本阶段的GitHub最终SHA/实际CI以PR head实时读回为准。

## 阶段选择与原路线图边界

已读工作区唯一 \`prj/docs/01-ARC-项目总体路线图.md\`、\`02-RPT-项目进度总览.md\` 与 \`project-ledger.json\`（生成视图截至2026-10-02；不擅自改动或宣布里程碑DONE）。主Android P2连续声浪、P3实时与P4逐车声学、P5实输入、P6设备和P7人耳尚有硬门；另一个本地声学工作树有未提交内容，因此不在此时做Android/PCM/硬件改动。

选择**单一完整可执行Web阶段 W7**：先关住设备运动状态机的已实测Esc监听泄漏和陈旧/无效读数窗口，再把本地未提交的六车型真实仪表候选纳入正式网页，人工限定范围调整Ferrari/LFA/GT-R/Supra读数层级、C63机械三筒，保持五种独立显示预设，完成本地可复验的数值和真实Worklet浏览器测试入口，提交可审GitHub代码。

此W7为网页产品子阶段，**不计P1–P8 Android主线DONE权重**。下游实体Tesla浏览器、实际IMU、道路GPS、扬声器/蓝牙、人耳和慢纹理声学仍为 NOT_RUN/NOT_EVALUATED。Jovi最终美术接受是人审，不靠绿色CI代签。

## 1. 输入与生命期（先修真实RED）

- 旧 \`22cadf3\` 下实际Chrome Esc关闭设置后 \`devicemotion\` listener仍留1个、X值仍1.00；原应用Esc路径不产生设置按钮点击。现在 \`motion-monitor.mjs\` 独立监听Escape，代次取消且清空轴向数值，晚到的权限授予不得重启。
- 旧运动读取以**最早 startedAt**计算没有数据的5秒窗口；长时有效流一旦收到null帧可能被立即停掉。新实现按最近有效帧/首次无效窗口计时；首次接收5秒无有效则停止；有效帧后2.5秒过期显示未知，连续缺失超过5秒再解除监听；有效恢复重置窗口。异常帧不延长期限。停止/隐藏/页面切换仍清理监听。
- 先以正常GitHub update_file写RED测试并运行，保留Fail/Skip，再写真正修复并重跑，不删失败断言；音频核心、GPS输入、PCM和真实模型完全不依赖此观察器。

## 2. 六车仪表统一绘制（本阶段实改）

正式声音ID不变：C63 W204、Hellcat、Ferrari 458、LFA、GT-R R35、Supra JZA80。外观自动映射与Mercedes/BMW/Audi/VW/Honda显示选择互相独立，不新增声音车、不改合成/采样/音量/增益/默认算法。

- W204：三筒同一遮光罩，速度居中，左挡位，右转速；速度数字与单位移入表内留白。
- Hellcat / BMW：双圆和中央数字分区保持。
- Ferrari 458：中央黄底机械转速；左大速度和负载、右挡位重排在同一面板内，防止下缘越界；黄底数值保持深色文字。
- LFA：单主转速环内的挡位主视觉，两侧数字进入明确的副屏，不再漂浮。
- GT-R：左小速度/中央偏置转速/右大速度和挡位信息屏，重新分配RPM、红线、负载的下缘。
- Supra：左半圆速度、中央大转速、右辅助圆角屏，向内收起转速单位、速度单位与红线。
- Audi双完整圆、VW中央短弧、Honda半圆细分段均沿用候选；选车及换肤时数据仍经旧 \`VicoCockpit.prepare/update\` 和 \`VicoFactory\`，没有第二个播放器。

所有刻度、红区、机械轴心/旋转读数仍是单一SVG坐标，物理RPM刻度每100、主要每1000、速度10/40不变。图形超量程饱和，但数值不能被显示量程截断。对不支持的燃油/温度/增压/胎压/电量一律不作假读数。资产为自主设计SVG，未复制任何OEM照片、徽标或第三方美术文件。

### 版权与开源许可证

仓库根已有JoviF 2026 **MIT** 许可证，原声明保留；本包没有安装新的依赖、加入字体或引入外部源/热链，不从开源汽车仪表库复制代码，无新增第三方许可证义务。厂方车型仪表/竞品页面只作外形组织参考，不复制其素材；Web Audio与DeviceMotion参考MDN规范中的功能合同而不复制库代码。实际素材/声音许可及Android整体发布审计仍按路线图P4/P8办理，不能被这一网页UI源许可判断取代。

## 3. 最小文件职责与回归

- \`vico_web/src/motion-monitor.mjs\`、\`test/motion-monitor.test.mjs\`：Esc/权限代次/缺帧过期与恢复RED/GREEN。
- \`src/factory-display.js\`、\`style.css\`、\`index.html\`：本次R7视觉源，延续W6运动显示而不覆盖它。
- \`test/cockpit.test.mjs\`、\`test/factory-display.test.mjs\`：真实显示适配、完整物理刻度、三筒、Honda半圆/五种预设/新增读数边界。
- \`tools/browser_w7_instruments.py\`：用**原生真实浏览器+AudioWorklet**复核六车、明暗、1280×600等，自动截图及检查hood边界、字形、STOP、声音会话身份；没有真实浏览器运行的回执时列 NOT_RUN。
- \`tools/browser_motion_review.py\`：真实Worklet + **注入**运动输入，不能称实设备传感器通过。
- 旧 \`browser_atelier_review.py\`（1345场景）、\`browser_factory_review.py\`（11场景）、\`browser_lifecycle.py\`（33案例/采样率）、\`browser_smoke.py\`仍必须真实回归。

Windows在独立新worktree用精确远端SHA接收，先保留Owner及其他声学脏树，构建到**新空目录**，检查真实六车126/新清单哈希，后运行：

\`\`\`sh
node --test vico_web/test/*.test.mjs
node vico_web/tools/build.mjs --out ABS_NEW_EMPTY_DIST
node vico_web/tools/serve.mjs --root ABS_NEW_EMPTY_DIST --port 4173
python vico_web/tools/browser_w7_instruments.py --url http://127.0.0.1:4173/ --out ABS_NEW_W7_RESULT_DIR --expected-sha FULL_SHA --executable PATH_CHROME
python vico_web/tools/browser_motion_review.py --url http://127.0.0.1:4173/ --out ABS_NEW_MOTION_RESULT_DIR --expected-sha FULL_SHA --executable PATH_CHROME
\`\`\`

另用Edge重复，完成已有1345/11/33+smoke复归。入口检查实际源/静态资源哈希绑定；保留所有fail/skip及截图。若受执行策略阻断Browser，不以远端CI、模拟/静态、已旧SHA回执冒充新版本通过。

## 4. 退出门与交付

远端门：正常非强推PR39 head、仅Web白名单，Node全套真实PASS、无skip，CI真实六车Git固定资产构建并提供新SHA/真实artifact；手工源码复审不混合设备/声学。禁止网络策略改变、安全检查关闭、服务部署或main合并。

本地接收门：真实六车资源新SHA哈希、真实Chrome+Edge W7/运动注入/旧浏览器矩阵和截图、无法通过的精确错误与必要本地修复后普通GitHub反馈。远端审计回归通过后，才由已授权的本地发布流程考虑另一个独立release；**当前公网旧版保持原状**。设备、车内、道路和人耳仍需真人独立采集及Jovi批准。

本阶段不回写主 \`prj/docs/project-ledger.json\` 和生成路线图，因为W7不计Android主线、现场Git根有用户自有变更且远端Repo仅授权网页范围；将可证事实保存在此SHA绑定的网页阶段文档即可。
