# Tesla Vico 声浪 - Android WebView 壳工程

本目录是 Tesla Vico 声浪 App 的**安卓原生壳工程**。App 的全部界面由 Stitch 设计
「Tesla Vico Sound Simulator（简约白）」导出的 HTML 提供，安卓层只负责提供一个
全屏 WebView 容器、底部导航桥接与返回键处理。**1:1 复刻 Stitch 设计**。

## 架构

```
Stitch HTML (Tailwind + Material Symbols + Inter, 离线本地化)
        │  file:///android_asset/screens/*.html
        ▼
   WebView (AppCompatActivity)
        │  window.AndroidBridge.navigate(route)   ← bridge.js 注入
        ▼
   VicoBridge (@JavascriptInterface) → webView.loadUrl(对应屏)
```

4 个屏幕（中文优先，来自 Stitch 项目 `16876534166380289626`）：

| 路由 | 资产文件 | Stitch 源屏 |
| --- | --- | --- |
| dashboard | `screens/dashboard.html` | Vico Dashboard - Chinese Version |
| library | `screens/library.html` | Vico Library - Luxury Car Profiles（声浪库） |
| settings | `screens/settings.html` | Vico Settings - Chinese Version |
| calibration | `screens/calibration.html` | Vico Calibration - Optimized Guidance |

底部 3 标签导航（仪表盘 / 声音库 / 设置）由 HTML 自身渲染，`bridge.js` 绑定其点击
→ `AndroidBridge.navigate()`；校准页由仪表盘「校准」按钮进入。

## 目录结构

```
android/
├── settings.gradle.kts
├── build.gradle.kts                 # 根工程，声明插件版本
├── gradle.properties
├── gradle/wrapper/                  # gradle-wrapper.jar + properties (Gradle 8.9)
├── gradlew / gradlew.bat
└── app/
    ├── build.gradle.kts             # AGP 8.5.2, Kotlin 1.9.24, minSdk 24
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml
        ├── java/com/vico/simulator/
        │   ├── MainActivity.kt      # WebView 宿主 + 返回键 + 状态恢复
        │   └── web/VicoBridge.kt    # @JavascriptInterface navigate(route)
        ├── assets/
        │   ├── screens/{dashboard,library,settings,calibration}.html
        │   ├── vendor/tailwind.js          # Tailwind Play CDN 本地化（含 forms/container-queries 插件）
        │   ├── fonts/{material-symbols,inter}.css + *.woff2   # Google Fonts 本地化
        │   └── bridge.js                    # 底部导航 + 校准按钮 → AndroidBridge
        └── res/
            ├── layout/activity_main.xml
            ├── drawable/ic_launcher.xml     # 矢量占位图标
            └── values/{strings,themes,colors}.xml
```

## 环境要求

- **JDK 21**：使用 Android Studio 自带 JBR
  `D:\Program Files\Android\Android Studio\jbr`
- **Android SDK 34** + Build-Tools 34.x：`C:\Users\Admin\AppData\Local\Android\Sdk`
- Gradle 8.9（wrapper 已自带，首次自动下载，本机已缓存）

## 命令行构建

Windows / Git Bash：

```bash
cd Project/android
export JAVA_HOME="D:/Program Files/Android/Android Studio/jbr"
export ANDROID_HOME="C:/Users/Admin/AppData/Local/Android/Sdk"
export PATH="$JAVA_HOME/bin:$PATH"
./gradlew assembleDebug
```

产物：`app/build/outputs/apk/debug/app-debug.apk`

安装到已连接设备（USB 调试）：

```bash
./gradlew installDebug
```

## 在 Android Studio 中打开

1. Android Studio → **Open** → 选择 `Project/android` 目录（非仓库根目录）
2. 首次打开自动下载 AGP/Kotlin/AndroidX 依赖，耐心等待
3. 选 `app` 配置 → Run

## 关键配置

| 项 | 值 |
| --- | --- |
| applicationId | `com.vico.simulator` |
| minSdk / targetSdk / compileSdk | 24 / 34 / 34 |
| Kotlin | 1.9.24 |
| AGP | 8.5.2 |
| Gradle | 8.9 |
| JVM Target | 1.8 |
| App 中文名 | Vico 声浪模拟器 |

## WebView 关键设置（`MainActivity.kt`）

- `javaScriptEnabled = true`
- `domStorageEnabled = true`（localStorage）
- `allowFileAccess` / `allowContentAccess = true`（加载 `file:///android_asset/`）
- `mediaPlaybackRequiresUserGesture = false`（Web Audio 自动播放，声浪无需先点击）
- `cacheMode = LOAD_NO_CACHE`（开发期避免旧 HTML 缓存）

## JS 桥（`bridge.js` ↔ `VicoBridge.kt`）

HTML 侧（`bridge.js` 自动注入到每屏）：

```js
window.AndroidBridge.navigate('dashboard' | 'library' | 'settings' | 'calibration');
```

Kotlin 侧（`VicoBridge.kt`）映射到对应 `screens/*.html` 并 `loadUrl`。新增原生能力
（传感器、GPS、音频等）时，在 `VicoBridge.kt` 增加 `@JavascriptInterface` 方法即可。

## 当前 S12 声库

当前产品六车型声库位于 `app/src/main/assets/s12_v10/`，由
`E:\Tesla_speed\prj\tools\sound_sim\s12\acoustic_identity_v015` 的当前六车型
renderer 导出为 `vico.s12.soundbank.v1`：每车 16 个 RPM/load 循环和 1 个收油片段，
48 kHz mono IEEE-float，并额外包含 3 个 S12 换挡事件与 common RPM/load trace。Android 播放链保留持久相位、状态平滑、bank 插值、换挡/回火事件和低频 pressure 层；旧
`assets/matlab_v6/` 仅作为历史 MATLAB V6 bank 兼容路径。当前六车型缺 bank 时不会
静默回退到旧通用 Kotlin 合成器。

电脑参考与手机基线使用同一声道/采样率/固定车辆增益契约：一次 arithmetic-mean
stereo→mono downmix、`-16 LUFS` 目标、`-1.5 dBFS` 峰值上限；若某车因 bank 峰值
触发 headroom，manifest 会如实记录 `headroom_limited`，不通过逐片段 AGC 或手机主音量掩盖。

声库边界仍为 synthetic / uncalibrated / not OEM reproduction；移动端声库生成器见
`tools/python/export_s12_android_sound_banks.py`。算法来源留在 `E:\Tesla_speed`，
不复制大型参考仓库。

## 离线 1:1 说明

所有 CDN 资源（Tailwind Play CDN、Material Symbols、Inter）已下载到 `assets/vendor/`
与 `assets/fonts/`，HTML 中的 CDN 引用已重写为 `file:///android_asset/...` 本地路径。
**App 完全离线运行**，无需联网即可 1:1 渲染 Stitch 设计（车内无网场景友好）。

> 注：Tailwind Play CDN 为运行时编译（~419KB JS），首屏渲染略慢；1:1 保真优先。
> 后续如需优化可换为预编译 CSS。
