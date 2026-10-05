# Vico 速度/加速度输入时序修复（2026-10-03）

状态：**软件回归通过；Android 构建、本次真机输入测量、GNSS 真实精度验收待完成。**

## 范围与身份

- 基线：`4f51f11c50ac6c8b9a4b761d90560b65ffef5687`，现有 PR37 分支。
- 真正 App：`vico_app/Project/android`，`com.vico.simulator`。根目录历史 Android demo、ESP32/CAN 并非当前 App 输入。
- 2026-10-03 本地盘点的六个核心源文件与此基线逐字节 SHA-256 一致：SensorProvider、LocationSpeedState、SensorSourceState、CalibrationAccumulator、MatlabV6SoundBankEngine、MatlabPowertrainController。
- 已安装 GM1910 APK 的 SHA-256 为 `debfa840e22f0556f96439d51ef623648a2147e44490f1fad5c43e36dba5098f`（versionName 1.0 / versionCode 1 / debug）；安装包与历史接收回执一致，**不等于已从干净提交重现其构建**。
- 本次不改声音源、车型参数、音量、阈值、N2 默认开关或历史声学资格。

## 实际调用链

`LocationManager.GPS_PROVIDER` → `LocationSpeedState`（Android m/s × 3.6 → km/h）

`TYPE_LINEAR_ACCELERATION` → `CalibrationAccumulator`（静止三轴偏置）→ **手机 Y 轴**（m/s²）

两路 → `SensorProvider` 主线程输出 → `MainActivity.onSensorSample` → `DrivePoint` → `AudioEngine.mapPoint` → `MatlabV6SoundBankEngine` → `MatlabPowertrainController` → `SoundState` → `AudioEngine.pushState` → `MatlabStatefulBankRenderer` / 输出。

- README 的 VirtualEngineState 是概念名称，生产类名为上述 DrivePoint / SoundState。
- 当前速度没有低通或速度微分；加速度不是通过相邻 GPS 速度计算。没有新增预测速度或 GPS 衍生加速度。
- MainActivity 从加速度推导 throttle/brake；控制器按 km/h→m/s→轮速映射 RPM，并在换挡时处理 dt。音频 renderer 另有 RPM/load 平滑。它们全部保持原样，不能把音频状态平滑误当成 GPS 滤波。
- DEMO、试听、S13/S14 参考回放可以代替真实输入；不能用其结果当实车采样验收。

## 已证明问题与修复

1. **旧/重复 GPS 时间戳覆盖新测量**：原实现只看 fix 是否在 3 秒以内。20 m/s 的新测量（72 km/h）后到达较旧的 10 m/s 测量，可错误退回 36 km/h。现按 elapsedRealtimeNanos 严格递增接收，重复/倒序不覆盖。
2. **非有限速度穿透**：原实现接受 NaN / 正无穷。现拒绝非有限、负值及换算溢出；保留正常 km/h 单位转换。
3. **额外固定输出等待**：原 GPS 回调只写值，等待下一个 50 ms tick。现新有效 fix 在下一主循环输出，多个回调合并；批量回调只取最新可用 fix。更晚的缺速度/NaN/未来时间 fix 不遮蔽同批有效测量。
4. **IMU 不过期**：原实现忽略 SensorEvent.timestamp，旧加速度可以无限保留。现拒绝重复/倒序/非有限/超过 250 ms 的事件，并在每次 tick 过期检查；无有效测量归零，不对无效零值应用校准偏置。250 ms 是软件停更保护，不是传感器真实精度保证。
5. **生命周期与 DEMO 污染**：暂停/重启清空实际输入；拒绝启动前的排队事件。DEMO 中仍过期检查真实输入；退出 DEMO 前刷新真实状态，防止先发布旧缓存。权限刷新不在 Activity 停止时重新采样。
6. **墙钟跳变影响运动时间**：App DrivePoint、DEMO dt、试听期限统一使用 elapsedRealtime；文件名和记录日期仍可使用墙钟。
7. GPS 最小请求间隔由 500 ms 改为 100 ms；这是请求值，**不保证设备按 10 Hz 产生 GNSS fix**，也不保证更精准。IMU 显式 maxReportLatency=0 与旧重载的默认语义一致，不把这一项计为已证实性能提升。

GPS 3 秒 freshness 上限保持不变；不把 20 Hz UI 更新误称 20 Hz GPS。主线程阻塞、操作系统/芯片 fix 频率、GNSS 误差、安装朝向仍须设备证据。

## 软件证据

- 将新原状态测试先放到原生产代码：13 个 sensor 测试运行，8 通过、5 明确失败。失败为倒序覆盖、重复覆盖、非有限接收、错误接收旧 fix、单调时钟无效时未清理。
- 修复后 sensor JVM：21/21，通过；0 skip、0 ignore。包括时间戳 ramp、launch/cruise/brake、批次有无效尾部、过期边界、数组防别名。
- Android 源码接线检查：6/6，通过；原基线相同接线检查失败。此类检查不是设备运行证明。
- 既有 S14 生命周期/试听接线：3/3，通过。
- Linux N2 回归：46 JVM 通过、2 预期 opt-in 未运行；81 Python 通过、0 skip。数字声学导出仍是 synthetic software checks，不是声学/试听合格。
- 独立 Android adapter 模拟：另附可重复 fixture 和执行日志；使用假时钟/handler，仅模拟调度与生命周期，不能替代 Android SDK 编译或设备传感器测试。

复验命令（从仓库根运行）：

```sh
python vico_app/tools/python/run_sensor_jvm_tests.py --deps /path/to/pinned-jars --build-dir /new/output
python -m unittest discover -s vico_app/tools/python -p 'test_sensor_input_wiring.py' -v
python vico_app/tools/python/run_n2_ci.py --platform linux --deps /path/to/pinned-jars --output /new/n2-output
```

依赖从现有 `vico_app/tools/jvm/dependencies.json` 校验 SHA-256；脚本不自动下载或安装。CI 已将 sensor/MainActivity 路径纳入触发，并在 Linux 阶段运行输入回归。

## Android/设备复验边界

隔离目录使用现有 Android SDK/JDK，先验证源文件清单与补丁 SHA，再运行 Android 编译、sensor 单测、lint、assembleDebug。不得覆盖 Owner 脏工作区，不自动安装/启动、不改变 ADB、设备权限、网络/安全设置。构建回执要记录源身份、命令结果、APK SHA 和明确的未运行项。

后续设备输入确认须先明确用户遇到问题的设备、版本，以及 DEMO/试听/参考回放是否关闭。需要分别记录 fix 源时间、接收时间、输出时间、更新频率、速度精度字段（存在/不存在）、停车/起步/减速和丢信号恢复；设备缺 speed accuracy 时不得凭空写 0 或声称精准。真实误差需独立参考，合成 fixture 不能证明 GNSS truth accuracy。

**剩余加速度限制**：现有静止归零只能去偏置，不能证明手机 Y 与车身纵向一致。代码要求手机顶部对齐车辆前方；现 UI 未完成可靠的安装朝向/投影校准。任意手机朝向下准确纵向加速度、GPS 衍生加速度 fallback 不属于此次已完成项；应独立设计和验证，不能通过本次去延迟修复宣称已解决。

## 回退

撤销本次输入补丁即可恢复原请求间隔、状态与调度。不要回退或覆盖既有 N2/声库资格修复；不得把旧有 stale/NaN 行为描述为通过。


## 托管 Android CI 候选验证

本地材料交接未完成，云端工作区也未安装 Android SDK，因此候选发布时 Android compile/lint/APK 明确为 NOT_RUN。授权使用原仓库既有 draft 分支的托管 CI 验证原源码；并非改道传输构建包。

新增 exact-head `android-input-build`：只使用 GitHub `ubuntu-24.04` 预装的 SDK34/build-tools34；在缺少任一必需工具或既有 license 文件时直接失败。所有 Gradle 命令显式 `-Pandroid.builder.sdkDownload=false`；没有 sdkmanager、协议接受或手机安装步骤。使用既有 pinned checkout/setup-java action，权限仍为 contents:read。

执行完整 Android 主源码和单测源码编译、sensor 包单测（至少21例且零 skip）、lintDebug、assembleDebug，并记录精确源哈希、结果与 APK 身份；历史外部参考材料单测不混算为已运行。需实际 CI 结果通过后才能更新 Android 构建状态。GitHub 官方预装清单：https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md#android 。禁止 SDK 自动下载的官方说明：https://developer.android.com/studio/intro/update#download-with-gradle 。
