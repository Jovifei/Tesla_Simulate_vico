# 本地 Codex：Vico Web 整阶段接收、验证和测试发布

请完整执行，不逐个文件派工。Jovi 已授权本阶段网页代码、测试、必要最小修复和该网页分支的普通提交。仅仓库 `Jovifei/Tesla_Simulate_vico`。不使用 Work，不重做已完成的 PR38 Android 修复，不合 main，不强推，不 reset/clean/stash Owner 工作树。

## 身份

- 新分支：`codex-web-vico-lab-20261015`。
- 源算法/原声库固定父 SHA：`477913e7500bb3ff13c3b72cf5b1a3cac1b28145`。
- 接收 SHA：使用远端最后答复给出的完整 40 位 SHA，设为 `$ReceiveSha`。不要把跟随移动的分支名当作已核定提交。
- 范围：`vico_web/**` 与 `.github/workflows/vico-web.yml`。原 Android/WAV/manifest/fixed gain/S13/S14/Owner/V4/main/data 禁止改动。源拟合 count/budget0，无 MATLAB。
- 当前 remote：31 个 Node 测试通过（明确 synthetic fixtures + worklet host shim），不是实际六车型/Kotlin/浏览器/设备通过。远端浏览器访问被沙箱策略阻止，未绕过。远端本地Tesla connector连接失败，代码来自GitHub固定源。

## A. 新隔离 worktree，不能覆盖旧接收树

读取现有 repo/worktree 信息自行找到正确 `.git` 仓库，不把 E:/Tesla_speed 的 isRepo=false 当阻塞。保留所有现有工作树脏内容。以下为命令结构，`$Repo` 用实际仓库路径：

```powershell
$Branch = 'codex-web-vico-lab-20261015'
$ReceiveSha = '<远端最终提供的40位SHA>'
$Worktree = "E:/Tesla_speed/worktrees/vico-web-$($ReceiveSha.Substring(0,8))"
$Evidence = "E:/Tesla_speed/reports/vico-web-$($ReceiveSha.Substring(0,8))"
git -C $Repo fetch origin $Branch
git -C $Repo cat-file -e "$ReceiveSha^{commit}"
git -C $Repo merge-base --is-ancestor 477913e7500bb3ff13c3b72cf5b1a3cac1b28145 $ReceiveSha
git -C $Repo worktree add -b "local-vico-web-$($ReceiveSha.Substring(0,8))" $Worktree $ReceiveSha
Set-Location $Worktree
git rev-parse HEAD
git diff --name-only 477913e7500bb3ff13c3b72cf5b1a3cac1b28145 HEAD
```

每步检查退出码。输出路径已存在时新选唯一目录，不能清空旧目录。确认 diff 不包含 Android、WAV 或父分支修改，再继续。后续本地修复也只在本 worktree。

先读 `vico_web/README.md`、`deploy/README.md`、`verification/remote-stage.json` 和所有实际生产函数。不要只读 README 就写 PASS。

## B. 真实构建与快速回归

使用现有 Node22，记录版本；无 npm install 必要。

```powershell
node --version
node --test vico_web/test/*.test.mjs
node vico_web/tools/build.mjs --out "$Evidence/dist"
node vico_web/tools/render.mjs --dist "$Evidence/dist" --vehicle c63_w204_v6 --rpm 910 --load .32 --out "$Evidence/web-c63-910"
```

测试至少31项，零失败、零跳过；实际数以 XML/TAP/退出码为准。构建必须六车型且testOnly=false；清单包含固定父SHA和当前网页SHA。核验每个WAV与父Git原字节相同（C63四个normal overlay为同一父树的既有合法替代），不再次乘fixed gain。确认发布JSON不含本机绝对源路径、账户、私有原始日志。

构建/解析失败先最小修复网页代码，不复制test fixture作为真实资源，也不静默回退声库。新生成的PCM、jar、dist放Evidence，不提交大型原始文件。

## C. 实际 Kotlin ↔ 网页算法对照

找到已存在的 SHA-pinned JVM dependency目录。可复用过去N2/test返回里的依赖缓存，但必须逐项与父 `vico_app/tools/jvm/dependencies.json` hash对齐。缺失时明确NOT_RUN并按既有正常下载授权补齐，不关校验。

```powershell
python vico_web/tools/kotlin_reference.py --repo . --deps $PinnedDeps --java $Jdk21Java --out "$Evidence/kotlin-envelope" --mode NORMAL_SEAM_ENVELOPE_V1
node vico_web/tools/qualify.mjs --dist "$Evidence/dist" --reference "$Evidence/kotlin-envelope" --out "$Evidence/web-parity-envelope"
```

同样对LEGACY_LOCKED和NORMAL_CANONICAL_SEAM_V1各生成独立新目录和48case对照。Kotlin runner须真正编译/运行，其银行DTO抽取边界已说明，不删核心函数去过编译。此处源模型来自固定477 SHA，不是Android APK字节的设备验证。

maxAbsError<=2e-6是跨语言数值精度门，不代表任何声学放宽；每个100ms原±.5dB及peak<=.8413951416451951/finite均保留。浮点Math.exp/cos差异要量化，不能只看相关系数。当前qualify脚本检查非重叠100ms窗口；本地完整回审还要扩展已有sample-stride滑动窗口、1.6–2.1Hz绝对包络功率及完整动态轨迹。不要把非重叠窗口表述成每采样滑窗。

补充一次生成状态/事件、两侧共享的完整DEMO序列（overspeed→decel→stop）及80km/h控制序列：对照actualKotlin.synthetic Powertrain与JS，检查RPM/挡位/load/torque、事件时刻、PCM。网页DEMO使用音频采样时钟，不与另一轮UI wall-clock轨迹混比。浏览器GPS适配器不作为Android updateMeasured等价，必须保持WEB_GPS_ESTIMATED及关闭事件，不能擅自改称REAL通过。

关键反例：C63910慢纹理、GTR高转低load、Supra高转高load、层切换/零速/非有限值、重复事件、所有权取消、已过期GPS加载后恢复。移植不是新的源拟合，不能改原WAV、gain、种子或现有参数追分。

## D. 实际浏览器与界面

```powershell
node vico_web/tools/serve.mjs --root "$Evidence/dist" --port 4173
```

在另一个本地进程运行（使用已装Playwright/浏览器）：

```powershell
python vico_web/tools/browser_smoke.py --url http://localhost:4173 --out "$Evidence/browser"
```

依赖/浏览器缺失需按工具安装原授权处理；不能关闭安全设置或把Node host shim当浏览器执行。脚本会真正创建AudioWorklet、点击开始产生PCM统计、快速切车取消、390px检查并截图。审阅截图和console/network，不只看脚本退出0。

额外人工/可自动化场景：首次加载无自动声；六车逐一开始/停止；加载期间改速度采用最新输入；停止/快速切换不存在旧context复活；隐藏页面和context suspended后不自动重启；坏SHA明确失败；返回重试恢复；GPS拒绝/速度null/stale静音且无坐标上传；输出率44.1/48/96k分别记录。当前线性重采样不是频谱无损证明，先验收48k路径，其他率需单列高频/alias与音高检查。

Chrome桌面、Android Chrome、iOS Safari、Tesla浏览器分开记录。没有真实设备就NOT_RUN，不替用户安装APK、不动ADB、不用旧Android成绩替代网页结果。网页页面必须保留“非原车录音/未声学验收/仅停车操作”等范围提示。

## E. 提交与服务器测试发布

所有可完成的软件工作持续完成，必要bug修复必须有RED/GREEN。不以某一步通过就停止。修改仅网页白名单。比较当前远端新分支head是否仍为ReceiveSha；若有人并行更新先读差异协调，不强推覆盖。

有修复时普通提交后：

```powershell
git push origin HEAD:codex-web-vico-lab-20261015
```

如为非快进拒绝，停止push并给出双方SHA；不能force。没有修复则不造空提交。

服务器阶段按deploy/README执行。Jovi未指定实际域名/目录/现有服务时，先完成软件验收并给出静态dist与部署参数表；只在这个人类信息门询问目标，不阻断A-D。确认后只新建独立测试release/虚拟主机，TLS、MIME、hash、响应策略实际核验，保留回滚。不要改账号安全、整个Nginx/Caddy配置、DNS或正式站点指向而不告知。未给真实可用部署渠道时不声称已部署。

## F. 返回同一聊天复审

返回固定最终40位SHA、Draft PR、diff范围、本地命令/退出码、31+ Node测试、真实六车asset/build hash、3模式Kotlin48case与动态对照、全部失败/skip、浏览器截图及AudioWorklet日志、dist hash与部署结果（或精确未完成门）。代码/日志放workspace路径让远端读取，不粘贴大段日志、不上传Project源码。原Owner/V4/frozen摘要保持。

状态严格分层：SOURCE / NODE_FIXTURE / ACTUAL_BANK_BUILD / KOTLIN_PARITY / DYNAMIC_PARITY / BROWSER / HTTPS_HOST / DEVICE / ROAD / HUMAN。空日志、缺输出、fixture伪素材和跳过都不能写PASS。只有真实经过前面门的静态包才可交公开试听；未过时保留工程包并明确缺口，不能叫完整复刻完成。
