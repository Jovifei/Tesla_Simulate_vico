# W6 — 可选设备三轴加速度观察（网页实验）

## 范围与动机

此包延续已验收的 Instrument Atelier 界面。原六车音频、声音引擎、DEMO、手动速度、GPS 输入和 VicoFactory/VicoCockpit 仪表均保持原样。

用户之前要求查看加速度。本实现只在**设置 / 诊断**中新增显式按钮「主动授权并读取」和设备坐标轴 X/Y/Z（m/s²），不是车辆纵向/横向加速度，也不参与 PCM、动力总成、事件触发、GPS 速度或声音音量。可能缺乏设备传感器的 Tesla 车机/电脑将按实际环境显示「不可用」或「未收到有效传感器数据」；绝不合成或推导假数据。

## 授权、隔离、有效性

- 页面打开、选车、进入驾驶台、开始声音、切风格/主题或选择 GPS 模式**都不会请求运动传感器权限**。
- 用户点击按钮时才请求 \`DeviceMotionEvent.requestPermission()\`（有该接口时）；无需该接口的浏览器则直接添加 \`devicemotion\` 监听，但仍由用户点击触发。
- 非 HTTPS/安全上下文、浏览器不支持、权限拒绝/异常、三轴含 null/非有限值，均显示未知「—」而非0。
- 优先展示 \`event.acceleration\`（浏览器报告的去重力分量）；仅当没有完整三轴时退回 \`accelerationIncludingGravity\`，并明确标「含重力分量」。不旋转为车辆坐标、不做IMU校准或积分，不从GPS差分计算。
- 最新有效三轴超过2500ms立即清为「—」；自启动超过5000ms没有有效数据，自动解除监听。显示最多每200ms更新一次，不写任何历史缓存。
- 关闭设置、离开车库/切模式、立即停止、页面隐藏、pagehide均移除事件监听并清空读数。迟到的权限应答通过代次拒绝复活。
- 不发送请求、不写本地存储、诊断JSON不加入运动样本；原音频 / GPS 许可入口完全不变。
- 停止监听不是撤销系统或浏览器已经授予的权限。

## 文件

- \`vico_web/src/motion-monitor.mjs\` — 有界、可取消的可选监听；不导入音频/GPS模块。
- \`vico_web/index.html\` — 设置抽屉里三轴数值、来源声明、按钮及状态。
- \`vico_web/style.css\` — 深浅主题下紧凑设置卡；停止键继续独立可达。
- \`vico_web/test/motion-monitor.test.mjs\` — 确定性 Node 测试（纯注入传感器及权限），不冒充设备验证。
- \`vico_web/tools/browser_motion_review.py\` — 本地Chrome/Edge真实AudioWorklet + **注入的**运动事件，验证音频与传感器隔离、运行身份、停止与可达性。不能当作真实IMU证据。

## 复现

从干净 Git SHA 和固定声库父 SHA 构建 release，再执行：

\`\`\`sh
node --test vico_web/test/*.test.mjs
node vico_web/tools/build.mjs --out ABSOLUTE_NEW_EMPTY_DIST
node vico_web/tools/serve.mjs --root ABSOLUTE_NEW_EMPTY_DIST --port 4173
python vico_web/tools/browser_motion_review.py --url http://127.0.0.1:4173/ --out ABSOLUTE_NEW_RECEIPT_DIR --expected-sha FULL_SHA --executable PATH_TO_REAL_CHROME
\`\`\`

全量原 browser_smoke、browser_lifecycle、browser_factory_review、browser_atelier_review 仍必须回归。没有真实浏览器运行结果时标为 NOT_RUN；代码/Node/CI不能替代真实设备、道路GPS、声学或人耳评价。

参考：MDN「Window: devicemotion event」及「DeviceMotionEvent.requestPermission()」，均说明安全上下文、设备数据差异及用户交互授权的限制。
