# Vico Web Lab：六车型网页版本执行计划

## 0. 身份、目标和授权边界

- 仓库：`Jovifei/Tesla_Simulate_vico`，仅此仓库。
- 父分支：`codex-remote-stage-20261011-integration`（PR38）。
- 本阶段固定起点：`477913e7500bb3ff13c3b72cf5b1a3cac1b28145`。它在 `8496346` 接缝修复之上加入 normal 有限慢包络抑制；不能误把旧 SHA 当最新。
- 网页独立分支：`codex-web-vico-lab-20261015`。Draft PR 的 base 是上述 PR38 分支，不是 main。
- 新代码仅放 `vico_web/` 和独立网页 CI；不修改 Android 生产/测试、原 WAV、manifest、固定 gain、S13/S14 reference、Owner 或 V4。
- 源拟合 count/budget 保持 0；本阶段是算法平台移植，不做 MATLAB、拟合、随机种子搜索或素材生成。
- 目标：使用 Jovi 现有六车型与算法，提供可部署到自有 HTTPS 域名的原创网页驾驶/试听站。功能参考同类产品；不复制 tslbox 的代码、图片、音频、商标素材或登录系统。
- 不将网站移植称为声音已修复。父版本对慢包络仅有限改善，完整重复纹理问题保留。

## 1. 最终用户体验

打开自己的 HTTPS 站点先进入六车型车库，选择 C63 W204、Hellcat、Ferrari 458、LFA、GT-R R35 或 Supra JZA80 后，进入独立驾驶台。特斯拉横屏优先呈现实际虚拟 km/h、RPM、挡位、负载和输入状态；显眼的开始/立即停止按钮始终可见。选车、进入驾驶台或切换页面都不自动播放或申请定位。只有点击开始才创建/恢复音频；更换车型、浏览器后退、隐藏页面和停止都会先取消旧声音与 GPS。手机竖屏提供可用回退。

车库与驾驶台是同一页面的互斥视图，使用 `#/garage` 与 `#/drive/<vehicle-id>` hash 路由，服务器无需 `/drive` 重写。有效车型直链进入待启动驾驶台；未知车型回车库并显示错误。演示、手动目标速度和实验 GPS 是明确的输入模式，跨模式切换先停止旧会话，GPS 只有点击授权按钮才调用定位。演示踏板只控制演示场景，不冒充手动节气门。

GPS 是独立、显式开启的实验输入：只使用浏览器已报告的 speed，不保存/上传坐标；缺速、陈旧、权限拒绝时失效/静音，不把未知解释成零速。它不是 Android `updateMeasured` + IMU + QualifiedAfterfire 的等价移植，页面与诊断须写 `WEB_GPS_ESTIMATED`；禁用自动回火/换挡音效。完整 REAL 等价属于后续 W4，未经本地验证不标 PASS。停车/由乘客操作，驾驶员不得调试。

## 2. 技术选型

采用原生 ES modules、Web Audio AudioWorklet、Node 22 内置 test runner，无运行期 CDN/npm 依赖、无后端账号、无第三方统计、无 Service Worker 缓存。这样服务器仅托管静态目录，旧版本回退不涉及数据库或手机数据。

核心不是播放器循环一个 mp3，而是移植现有 Kotlin 的：canonical engineCycles、RPM/load 双线性插值、35ms 状态平滑、H=8 局部斜率修正、50/600ms 能量 EMA 与 5ms/0.97–1.03 有限包络、原 shift/afterfire PCM。使用 Math.fround 明确模拟 Kotlin Float 运算。默认 `NORMAL_SEAM_ENVELOPE_V1`，保留 `LEGACY_LOCKED`、`NORMAL_CANONICAL_SEAM_V1` 数字对照。

模型内部固定使用声库采样率；浏览器实际 AudioContext 采样率必须记录。不同采样率用明确的流式重采样，不能把 48k PCM 当 44.1k 播放。原速率纯核对照与设备重采样分别验收。

AudioWorklet 按实际输出数组长度处理，不假定永远 128 帧。控制积分固定音频采样时钟 20ms；UI 只发布目标，不在 requestAnimationFrame 中生成 PCM。该 DEMO 时钟与 Android UI elapsed-time 不同，必须用相同输入轨迹做跨平台比较，而非比较两次不同交互。

## 3. 文件与职责

- `src/core.mjs`：纯算法、F32 WAV 解码、powertrain/DEMO、normal renderer、时钟及输入失效。
- `src/worklet.mjs`：实际音频处理器、有限消息、心跳失效与统计；无文件/网络/FFT。
- `src/session.mjs`：同源资源 SHA 校验、加载取消、AudioContext 所有权、停止/失败恢复。
- `src/app.mjs`、`index.html`、`style.css`：六车型 UI、演示/手动/实验 GPS、响应式仪表盘。
- `tools/build.mjs`：从固定 Git 源复制原资产到新 dist；核对原文件 Git blob，生成 SHA-256 清单及清理后的网页 manifest。原 manifest 的本地绝对路径不会进入发布目录。
- `tools/serve.mjs`：仅本机开发服务器，不承担生产 TLS。
- `tools/render.mjs`：调用实际网页算法导出 F32LE 与身份/峰值回执，不写原素材。
- `tools/kotlin_reference.py`：本地用固定依赖编译真实 Kotlin 核，生成同条件参考供网页数字复核；缺依赖标 NOT_RUN，禁止用 JS 自比自冒充 Kotlin 对照。
- `test/`：解析信号/真实入口所有权/资源身份/重采样/失效与取消回归。
- `deploy/`：独立站点服务器配置样例；没有任何自动登录、DNS、证书或现有站点修改。
- `LOCAL_CODEX_PROMPT.md`：固定 SHA 隔离接收与完整本地执行指令。

## 4. 分阶段执行与否决门

### W0：固定来源与隔离（本回合执行）

读取 PR38 最新 head，从精确 SHA 创建新分支。正文计划先入库，再提交真实代码。所有证据记录父 SHA、网页提交、工具版本、命令退出码和文件哈希。local Tesla connector 本回合连接失败，不声称已核实当前本地树；GitHub 的已发布源为本轮执行依据。

验收：新分支存在；最终比较中只有网页目录/网页 CI 的新增 diff；main 与 PR38 ref 未移动。不得用 reset/clean/stash/强推来接收。

### W1：六车型资产与真实数字核（本回合实施）

完整读取现有 normal/source 接口；移植 renderer、normal envelope、DEMO 和 synthetic powertrain。构建器读取六个原 manifest 的完整动力参数，不统一齿比/红线。C63 normal 使用已存在四 WAV overlay，并验证 properties 的原/候选 hash；其他五车使用原 bank。原 WAV 字节不改，不复制生成新候选。

验收：manifest/PCM/hash 反例、有限值、采样率、帧数、短/错误 WAV、H8 支持区外不变、有限包络、事件 exact-once、分块一致。真实六车正常构建不能以 synthetic fixtures 替代。Kotlin/JS 先用固定输入逐点检查；48个恒定状态、完整 DEMO、REAL 留存反例只在有实际返回后记录通过。原 ±0.5dB 门槛不松，S13 原 Kotlin参考不重写。

### W2：浏览器生产链（本回合实施，本地接收验收）

接通 UI -> source target -> worklet -> actual core -> destination，不能 helper-only。音频手势启动、有限音量、停止淡出、失焦/隐藏停止、过期心跳静音、重复开始/车型切换取消、加载失败可恢复。资源加载只在主线程，声音计算在 worklet；并发下载和内存有界。

验收：真实 Chromium 页面从车库选车后开始/停止、后退/前进、切车、加载取消、错误 hash/恢复、模式切换及迟到踏板释放、GPS 失效、隐藏页面；实际 AudioWorklet 必须建立并产生非空计数。横屏驾驶台在 1440×900、1280×720、1280×600、1024×600 和 1920×1080 测试 viewport 中不依赖页面滚动即可看见开始/停止及主要仪表，停止按钮不得被设置抽屉遮挡；390×844 竖屏无横向溢出。截图用 viewport 而非超长整页，并记录 viewport、DPR、浏览器、路由和网页 SHA。这些尺寸不是 Tesla 真机证据。UI mock 通过不能冒充声音设备通过。44.1/48/96k 的重采样单列，跨浏览器不预先宣称 bitexact。

### W3：网页数字等价与桌面/手机兼容（本地执行）

固定 Node/JDK/依赖，建立同输入 Kotlin与JS原速率导出。比较逐采样最大误差、RMS误差、事件帧、峰值、100ms同窗差和1.6–2.1Hz绝对包络功率；浮点超越函数差异如实记录，不自动抬高容差。

桌面 Chrome/Edge、Android Chrome、iOS Safari、实际 Tesla 浏览器分别记录支持/失败/NOT_RUN。HTTPS、用户手势、AudioWorklet、GPS权限各有真实状态。手机音频路由、蓝牙、后台、来电中断、真车都不是桌面测试的推论。

### W4：自有域名测试部署（本地执行，部署前确认目标）

先构建新的版本化 dist，仅把静态构建目录上传到新的测试子域名/目录。优先既有反向代理；Caddyfile 只是独立新站点样例，不覆盖服务器配置。核对域名/DNS/TLS/目录权限、CSP、MIME、禁止目录遍历/清单浏览、错误资源返回404、不回退HTML冒充JS。

确认服务器上的 catalog 和静态文件 SHA 与本地构建一致，点击手势试听；随后才考虑正式域名指向。切换采用版本目录/软链接，保留旧 release；回滚切回旧目录，不删数据。服务日志可能保留IP，不能声称服务器零日志。

### W5：完整 REAL/持续纹理（后续，不混入移植验收）

Android REAL 的 IMU、freshness、uncertainty、epoch、虚拟需求和合格事件须逐项移植再验收，不能用浏览器差分速度称为等价。慢纹理修复属于新算法工程；网页版本应忠实暴露现存问题而不是加随机声音掩盖。新声源或 gain 政策需要精确新授权。

## 5. 本地标准入口

在独立 worktree 仓库根运行：

```sh
node --version
node --test vico_web/test/*.test.mjs
node vico_web/tools/build.mjs --out /absolute/new/empty/vico-web-release
node vico_web/tools/serve.mjs --root /absolute/new/empty/vico-web-release --port 4173
```

Windows 用新的 `E:/Tesla_speed/reports/web-<SHA>/dist` 路径；脚本拒绝覆盖已有输出。浏览器访问 `http://localhost:4173`，不是双击 file://。远程手机通过正式 HTTPS 测试域名访问，不能关闭浏览器安全策略。

Kotlin参考、浏览器smoke与数字导出见脚本 `--help` 和本地 prompt。仅命令退出0、预期计数非零、输出完整且 hash绑定时才记录 PASS。缺工具/跳过/空日志均不是 PASS。

## 6. 保留与交付定义

交付包括：计划、实际网页代码、测试、版本化构建、服务器模板、真实 GitHub SHA/Draft PR、本地接收 prompt。网页部署地址、手机声音、道路、人耳及新声学资格不预先宣称完成。不将同类网站可见前端当成开源，不复制其付费资产。

验收分层：SOURCE_IMPLEMENTED / REMOTE_UNIT_TESTED / LOCAL_REAL_BANK_VALIDATED / KOTLIN_PARITY / BROWSER_WORKLET / SERVER_HTTPS / DEVICE / ROAD / HUMAN。每层独立记录。

## 7. 官方实现资料（设计依据，不是竞品取证）

- Web Audio / AudioWorklet: https://www.w3.org/TR/webaudio/ ; https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet
- Geolocation speed可以为null、单位m/s: https://www.w3.org/TR/geolocation/
- Node内置测试: https://nodejs.org/api/test.html
- Caddy静态站点与HTTPS: https://caddyserver.com/docs/quick-starts/static-files

本文件定义执行方向；实际运行结果写入 `verification/`，不得把计划中的验收项写成已通过。

## Instrument Atelier 显示接回（2026-10-20）

本地接回的正式显示层、冻结范围和真实浏览器检查见 [ATELIER_RECEPTION_20261020.md](docs/ATELIER_RECEPTION_20261020.md)。单文件设计预览不进入正式运行链路；播放仍由原AudioSession/AudioWorklet驱动。
