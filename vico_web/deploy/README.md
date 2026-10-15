# 自有服务器/域名部署与回滚

这是一套静态站点：服务器分发页面、模块、校验清单和原始音频素材；声音在访客浏览器生成。无需 Node 后端、数据库、账户、Tesla账号、支付、第三方CDN或云合成服务。Node只用于构建/测试，本机 serve.mjs 不是生产服务器。

## 1. 先确定目标，不能自动改现有站点

本回合未提供实际域名、服务器系统或站点目录。首次部署前由 Jovi 确认测试子域名（例如 sound-test.自己的域名）、已经使用的反向代理、全新 release 目录、TLS管理方式和回滚指向。服务器凭据不写进仓库/聊天。优先复用已有 Nginx/Caddy/面板，不能停用现有服务抢占80/443，也不能整体覆盖默认站点配置。

本地 Codex 先完成真实素材构建、Kotlin/JS对照、浏览器验证；部署信息不足仅阻断部署，不阻断前面的代码修复与验证。禁止从连接错误推测账户密码失效或更改防火墙/安全配置。

## 2. 生成单一可追溯 release

在固定提交的隔离 worktree 根执行，输出目录必须不存在：

```powershell
node --test vico_web/test/*.test.mjs
node vico_web/tools/build.mjs --out E:/Tesla_speed/reports/web-RECEIVE_SHA/dist
```

记录完整 `git rev-parse HEAD`、构建器退出码、`catalog.json` 和 `build-manifest.json` SHA；必须 `testOnly=false`、车型6个、sourceCommit等于477913e7500bb3ff13c3b72cf5b1a3cac1b28145。每个bank.json及WAV有真实SHA，原始gain已经写在原WAV，不得再次乘fixedVehicleGain。不要把整个仓库、.git、Android源码、日志、诊断PCM或任何私有文件上传。

初次发布推荐独立测试域名根目录，避免既有站点的SPA fallback、Service Worker、跨域缓存和权限策略干扰。需要子路径时，先验证所有相对模块与assets URL；不要添加HTML catch-all去掩盖404。

## 3. 上传新目录，不覆盖旧 release

经确认后，本地执行者将构建目录复制到服务器的全新版本目录，例如 `/srv/vico-web/releases/<WEB_SHA>/`；这里只是目录示例。验证服务器每个文件SHA与本地build-manifest一致。保留只读素材权限，目录内不要创建指向私有目录的软链接。

`Caddyfile` 是新虚拟主机模板，不是自动安装脚本。`VICO_DOMAIN`为确认后的真实域名，`VICO_ROOT`指向上述版本目录或独立current链接。只有管理员批准后才做语法验证、加入现有配置和无中断reload。Caddy可以管理HTTPS，但DNS和外网可达性需实际核对。已有Nginx环境照搬响应策略即可，不必更换服务。

配置合同：HTML/JS/catalog保守no-cache；正确`.mjs` MIME；同源脚本、模块和WAV；CSP不使用unsafe-eval；不启用目录浏览；未知模块404；默认不请求定位/麦克风；GPS由用户主动授权。不得关闭浏览器安全策略使HTTP外网音频或GPS工作。

## 4. 上线前检查表

| 检查 | 证据与通过条件 |
|---|---|
| 身份 | 远端catalog.webCommit、sourceCommit与本地预期一致，所有发布文件hash匹配 |
| TLS/MIME | 页面HTTPS正常，所有mjs为JavaScript MIME，无混合内容，错误URL返回404 |
| 资源 | 6车型能按需加载，篡改任一测试副本WAV后明确拒绝播放，不回退假素材 |
| 无自动播放 | 初次加载没有声音，用户点击后context运行；不允许站点强制播放 |
| 生命周期 | 快速重复开始/停止/切车型、加载取消、页面隐藏后不残留旧播放 |
| 页面 | 桌面与390px窄屏可操作、无水平溢出、km/h正确，不复制竞品标识 |
| 数据 | network日志无坐标/音频遥测上传；诊断仅用户主动下载；服务器访问日志可能记录IP |
| 输出 | 源采样率与context采样率均记录；浏览器计数不叫AudioTrack underrun |
| 物理 | 实际手机、Tesla浏览器、蓝牙、道路、人耳分别记录，未做就是NOT_RUN |

数字口径：网页端与Kotlin是跨语言移植。最大逐采样误差阈值2e-6用于移植检查，不是对旧音质门槛的放松；±0.5dB和原峰值合同仍必须保留。当前qualify.mjs输出固定、不重叠100ms窗口，逐采样stride窗口/动态轨迹由本地补充同一参考比较，不得把一种窗口统计写成另一种。

## 5. 发布和回滚

测试域名验收后，Jovi明确批准才切正式入口。保存旧release路径、旧config和两版build-manifest。切换独立current指向或站点root后重复身份/加载检查。异常时切回旧release并reload，不能删原目录或用户数据，不强推main。

本版没有Service Worker；仍需要刷新旧页以使用新JS。浏览器已打开的旧上下文要停止后再重新加载。服务端代码不可自动改变用户已打开页面的声学状态。

## 6. 公开发布前的预期说明

使用可下载原始WAV的纯前端架构，意味着访问者可以下载所分发的素材和JS；混淆不提供保密保证。只分发你有权使用的项目素材。车型名用于风格描述，不宣称原厂授权/真实OEM复刻，不加对方网站图标、商标图或录音。

功能交付为Vico网页版本，不是竞品源码复制。当前普通声源及有限包络处理保留原慢纹理局限，网页化本身不构成新的声音通过结论。

官方部署文档： https://caddyserver.com/docs/caddyfile/directives/root 、 https://caddyserver.com/docs/caddyfile/directives/file_server 、 https://caddyserver.com/docs/caddyfile/directives/header 。以实际安装版本验证配置，不根据模板声称服务器已部署。
