# W7 R1 · 低高度仪表与设备运动竞态返修（2026-10-24）

**唯一仓库**：Jovifei/Tesla_Simulate_vico；**PR39** \`codex-web-vico-lab-20261015\`，base \`codex-remote-stage-20261011-integration\`，不合 main。返修基线 \`122438be1da5336c257c22438aa4e94b6d543c05\`。最终提交以 PR39 远端 head 和其同 SHA CI 回执为准。

## 1. 原始本地 RED（保留，不重置，不掩盖）

本地工作区 \`E:/Tesla_speed/reports/vico-w7-122438be/LOCAL-W7-FAILURE.md\` 及其原始 \`receipt.json\`：

- Chrome/Edge W7 驾驶台各 exit1：Mercedes 1280×600 有效巡航速度字形 **63.3056px < 固定64px**（挡位45.64px）。
- 原 1345 显示检查 Chrome **167 FAIL**、Edge **166 FAIL**，包括 C63/Supra 数字与 km/h 重叠、LFA/GT-R 低高度数值、GT-R挡位约39.01px；Ferrari/LFA/Supra 右侧负载/红线贴底。
- Chrome 运动监测第一次第2次授权后 Z=-3.00立即断言失败，同 SHA 单独重跑 PASS，Edge首次PASS。属**浏览器注入竞态待消除**，不能叫真实IMU错误。
- 原音频六车、Node86、33生命周期与smoke通过项只保留原 SHA 的证据，不自动移植到返修版。

## 2. 源码修复

限定 \`vico_web/**\`：
- \`src/factory-display.js\` 保留完整物理刻度与原车型红线；调优 C63中央半表轴心和速度/readout/单位分区、Hellcat/BMW挡位字号、GT-R速度/挡位的垂直间隔、Supra速度数值与右屏底部、LFA单环的左右附屏及红线迁移、Ferrari黄底转速与右侧红线、Audi中央速度/挡位字形、VW端点刻度位置、Honda标题不盖刻度；数字简洁页的负载说明收回外壳内。**不隐藏刻度、单位或红线。**
- \`test/cockpit.test.mjs\` / \`test/factory-display.test.mjs\` 对应新机械轴心和表盘坐标，仍严格验证针角、超量程、偏好、无音频副作用和字形。
- \`tools/browser_atelier_review.py\` 把元数据 \`.r5-meta\`、单位、标题、刻度、动态数字全部纳入碰撞检查，保留原 **1345项、64/44px、对比度和停止命中阈值**。
- \`tools/browser_w7_instruments.py\` 检查内罩边界和元数据互压；只接受当前模型 Worklet 的实际runId、银行SHA、帧增长和停止。
- \`tools/browser_motion_review.py\` 将注入的 \`devicemotion\` 包标记为测试专有，由代理只向观察器转发注入包以阻止原生无效传感器事件覆盖测试值；保留真实监听/解除、权限、实际Worklet和按钮点击。另测无效包立即清空、有效包恢复，以及**实体按下Escape**释放监听。**这种浏览器注入不等于真传感器验收。**

无 \`app.mjs\`、\`session.mjs\`、\`core.mjs\`、\`worklet.mjs\`、\`appearance.js\`、Android、原 WAV/manifest/fixed-gain/114个银行文件改动。

## 3. 本次远端验证与边界

使用旧 \`122438be\` CI 实际静态六车包逐文件SHA匹配后，在禁止 \`localhost\` 的当前容器中，以 \`Playwright.page.set_content\` + 原版 HTML/CSS + 修改后的实际 \`factory-display.js\` 做**离线 Chromium SVG几何检查**，不是播放测试：

- 六自动车型 + C63五个独立显示预设，双主题 × 车型/数字布局 × 六尺寸（1440×900、1280×720、1280×600、1024×600、1010×1270、390×844）× 五个边界输入，共 **1320/1320几何检查通过**。
- 检查速度/挡位字形、负载/红线/单位/装饰标题/刻度/针轴不碰撞，非移动端元数据不越出内罩，横屏无页面溢出，STOP始终可达；数值异常保持未知，且主要刻度不被隐藏。
- 真实GitHub CI只验证 Node / Python语法 / 固定六车构建。**远端此处没有真实 AudioWorklet、GPS、设备 IMU、Tesla触控、声学或人耳通过回执**。如CI中断/跳过，不能记PASS。

## 4. 本地接收与发布否决门

在新隔离 worktree 从**最终 PR39 head SHA**接收，禁止覆盖本地声学脏树、清理或推送 main。真实六车从固定父Git源构建到新目录并验资产SHA。然后在实际 Chrome **和** Edge各运行：

\`\`\`sh
node --test vico_web/test/*.test.mjs
node vico_web/tools/build.mjs --out ABS_NEW_EMPTY_DIST
node vico_web/tools/serve.mjs --root ABS_NEW_EMPTY_DIST --port 4173
python vico_web/tools/browser_w7_instruments.py --url http://127.0.0.1:4173/ --out ABS_NEW_W7_RECEIPT --expected-sha FULL_HEAD_SHA --executable PATH_TO_BROWSER
python vico_web/tools/browser_motion_review.py --url http://127.0.0.1:4173/ --out ABS_NEW_MOTION_RECEIPT --expected-sha FULL_HEAD_SHA --executable PATH_TO_BROWSER
python vico_web/tools/browser_atelier_review.py --url http://127.0.0.1:4173/ --out ABS_NEW_GEOMETRY_RECEIPT --expected-sha FULL_HEAD_SHA --executable PATH_TO_BROWSER
\`\`\`

此外新 SHA 的 factory11/112张图片、smoke六车、lifecycle33各独立复归；特别保存 1280×600 的 C63/LFA/GT-R/Supra 和 1440×900 Ferrari 图片。失败=退出码非0/未跑/空回执，不能拿前一 SHA 的证据代替。

原线上 \`0822de48\` 保留，**未自动上线**。新SHA达到真实浏览器、哈希、生命周期资格后才走既有独立 release 流程。Tesla真机、设备IMU、道路GPS、蓝牙/扬声器、慢纹理声学和具名试听仍 NOT_RUN/NOT_EVALUATED；项目路线图P2–P8声学/设备/Human门不因本网页修复升级。
