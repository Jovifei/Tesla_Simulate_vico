# Vico 输入 声浪与循环点击问题经验记录

更新：2026-10-04。证据类别：`CURRENT_STATUS` + `EXECUTION_RUNBOOK`。

本记录说明本轮改了什么、为什么改、失败了什么，以及哪些结论尚未成立。工程测试不等于道路准确，也不等于人耳通过。以下发布状态按明确的源码和产物身份区分；不得把研究候选写成已安装版本。

## 一 当前已交付与未交付

- 已发布输入质量及日志版本：PR37 `7bf34080c358cc8b2eb4407266f008773c3efb6a`，仍为 Draft。精确 CI run `37181105256` 三门成功；Android 144/144，lint 0 errors / 8 warnings。
- 已安装的是独立 main-compatible 组合，不是上述 CI APK：main `6e4cf1437972caf383baab3f987de0ebf2db373d` 加已审改动，tree `c38fdc1a095391293ce99d414307e171342d7db4`，5203 文件，13 个 main 集成文件保留。APK SHA256 `232da58988159315c231e9333ac6453a0610aa33245856583e0ac14a632f0f44`。本机 Android 150/150、JS 25/25、lint 0/6；同签名升级保留设置、权限、首次安装身份与 mph 偏好。
- 静态日志：3 个 COMPLETE session，278/272/267 行，共817行；CONFIG 首行、必需字段与解析通过。一次有1个 queue drop、4个 startup gap，不是无损记录。导出文本与 normalized-LF hash 一致，本机 CRLF 转换导致磁盘 byte hash 不同，不称逐字节一致。
- 静态时 GPS unavailable、安装方向未确认，真实声正确暂停，audio peak=0。129条UI_ACK是MPH/null。校准、六向未确认选择、重复启停、停止保存、后台flush已验；有实际车前向参照的确认/信任失效、道路、物理音频及人耳尚未验。
- SESSION_START 缺口已独立提交 `3e76f0d702db85f4f82d048e2cdc474a11a6e73e` 并更新原分支，尚未安装。精确 CI 单独跟踪；已建 Git tree 不等于已有 commit、ref 更新或 CI，发布需分别读回验证。接缝改动作为后续独立提交，保留该日志修复。
- 本文后述循环修复、虚拟需求策略均为研究/候选；产品准入与安装记录必须单独补证，不自动升级为交付。

## 二 速度与加速度的定位方法

### 70 显示 43 先核单位 不责怪用户

原生速度换算 m/s×3.6 正确；保留 mph 设置时70 km/h约为43.5 mph，软件页面回归可复现。静态实机见到 mph，只能证明该时刻设置，不能反推发生道路投诉时的设置。修复是显著显示单位、日志同时区分标准速度与实际展示数值，不强改用户偏好。

### unknown 不等于停车

旧逻辑曾接受约2.8秒前的42 km/h，超时后输出0，再恢复70，造成假停车与假恢复。100ms只是位置请求间隔，不保证真实GNSS更新率。GPS源时间、接收时间、年龄、speed accuracy及是否有speed必须独立保留；缺失精度为UNVERIFIED，不能冒充已证高质量。

实际声音入口是 SensorProvider → MainActivity → AudioEngine → MatlabV6SoundBankEngine → MatlabPowertrainController。不要只修未被当前路由使用的另一个 SoundModel。质量必须进真实模型；音频线程有独立deadline watchdog，即使主线程停发也不能无限播放旧可信状态。短暂失效可能被latest-only邮箱覆盖，因此还需跨帧epoch清理待播放瞬态。

### 静止校准不能推断车前向

校准只估三轴偏置，设备Y轴不是任意安装下的车辆纵向。当前六向合同限定自然竖屏物理轴，停车明确确认；已存选项和本次信任分开。后台、校准/input session改变、手动移动失效；普通页面切换不随便逼用户重设。没有自动检测所有倾斜/偏航的能力。

## 三 声音事件与动力策略

- 旧真实控制器在40 km/h、加速度1.4↔0.2、50ms切换的30秒回放中产生300次afterfire、0次真实换挡。听到反复变化不能直接称“换了300挡”。
- REAL afterfire已改为原始IMU来源去重、arm/release驻留、冷却及恢复重锚。重复发布不推进episode；真实shift有独立exact-once通道。恢复要同时清renderer队列、差分基线和episode，不只首帧关事件。
- 仍存在结构局限：throttle=clamp(a/3)，匀速需求必为0；70匀速曾一直一挡约6919RPM，升挡又要求正加速度。声库最低load是0.32，模型0被夹到下沿。这是虚拟策略和素材覆盖问题，不是证明实际油门为0。
- 新虚拟需求/巡航方案必须区分实测speed/accel、virtualDemand、bank坐标、shiftGain。滚阻/风阻项是平路工程假设，坡度、风、踏板和制动意图不可观测；bank下沿不代表真实无载素材。成对升降阈值需来自同一需求函数，不能新升挡阈值配旧固定7000RPM降挡表，否则会猎挡。旧reference update保留。

## 四 音色掉幅不能一律归为相消

真实loader优先 `s12_v10`，不是旧 `matlab_v6`。默认C63的当前bank自己标明 synthetic / uncalibrated / not OEM。

原Kotlin与现bank55组、1404万frames回放中，51组拆分路径可逐sample重建最终PCM，误差0。5500→6800高load端点RMS下降约15.86dB；端点没有RPM混音，不能归因于层间相消。

原recipe重建C63 16/16 loop与仓库float32逐样本一致。旧bark的1100Hz窄共振在5500RPM的第三点火谐波被击中，source先掉约13.48dB，冻结PTR的频率选择性把最终差异扩大到约15.86dB。2秒持续源仍存在，排除短片起动/裁剪为主因。6150RPM又会击中820Hz共振，稀疏bank锚点遗漏该峰，因此不能用单调增益斜坡或逐loop等响归一化修饰结果。

7000RPM低load另有相消：两路相关约−0.650，除线性中点约3.01dB损失，还多约3.72dB；6150额外相消约0。必须分开 source、loop、mix、output 与扬声器链路。

## 五 周期点声与循环边界

用户描述约每0.5–0.6秒“点点点”。工作假设是重复间隔，不是0.5–0.6Hz频段，也不是已获得现场录音。

六车型26组10秒定RPM/load、零shift/afterfire的实际renderer回放证实多个loop边界的数值锐边。原生低RPM周期0.36s；重采样后每层周期为 loopSamples/sampleRate × anchorRPM/targetRPM。C63 910RPM存在约0.277/0.554s、Supra980约0.294/0.588s、Hellcat910约0.297/0.593s候选周期。多个边界可能重合；不能独归某一层，更不能说已确认用户听到的就是它。1/333/960/997分块的同一C63 PCM逐字节相等，排除了该离线case的20ms分块造周期。

旧 `_loop` 把开头8ms替为尾8ms到头8ms的混合，却保留尾部原样；loop第一点变成原倒数384点，前一点仍是原最后一点，wrap有回跳。真正的修复应核两个拼接点和全局极端差分，而不是只在旧wrap附近取样。

### 已证失败的修复尝试

- 直接trim overlap或改整数engine-cycle长度可降锐边，但改变周期/混合相位。910/980实际混音RMS下降0.62–1.27dB并增加相消；不能因点击指标改善就采纳。
- 保持0.36s和主体相位的pre-roll补尾方法在6组低RPM探索中副作用较少。但全55组的7000低/中load和下降扫频仍有局部相消退化；70 km/h轨迹某100ms窗输出RMS下降约1.01dB。整体指标或两个全局最小值通过，不能覆盖逐同窗口反例。
- Supra800/.92固定gain下peak由.84139514变.84489739，超过−1.5dB预算约.03608dB。超峰在未改主体，是去DC均值改变造成，仍必须拒绝；不因此放宽门、clip或降gain救分。
- 当前选择只研究C63 700/1400双load四loop的版本化窄候选，保2200+、其他车型及旧reference资产不变。须重新验新旧层边界与全轨迹。它最多叫低转接缝改善候选，不叫全域/全车型问题解决。

## 六 必须保留的验收与复现

已发表输入基线：

```bash
# 使用工作流SHA固定的依赖，不临时升级依赖后混用旧证据。
python vico_app/tools/python/run_sensor_jvm_tests.py --deps "$PINNED_JVM_DEPS" --build-dir "$NEW_EMPTY_TEST_DIR"
node --test vico_app/tools/js/test_*.cjs
python -m unittest discover -s vico_app/tools/python -p 'test*input*wiring.py' -v
python -m unittest discover -s vico_app/tools/python -p 'test_summarize_session.py' -v
```

本轮已将固定源码/原20WAV身份与55场景重放入口归档至 `review_packages/vico-input-loop-20261004/replay/`；命令见[窄候选复现](../vico-c63-low-rpm-loop-variant-20261004.md)。每个后续候选发布时仍必须随源码归档：原recipe/manifest/PCM身份、未修改原bank hash、新旧loop长度和gain、实际Kotlin回放harness、逐窗口AB CSV、原失败候选、原始preClipPeak/hardClip/nonFinite，而非仅已clamp输出峰值。研究脚本或命令若仍只在临时目录，不得宣称已形成可复用项目交接。

最低重复验证顺序：
1. 冻结源码head、全部资产hash、输入轨迹、采样率、增益及门槛；标探索后筛查和未见持出。
2. 原source→层→PTR→loop逐级定位；原recipe对原资产复现误差单列，微小float32残差也不写成bitexact。
3. 零事件≥10秒恒定及升降速，按实际新长度重算wrap；检查新crossfade入口、全时域d1/d2、HF和同窗RMS/相消，防止移峰或整体变轻骗过指标。
4. 含真实controller shift/afterfire的同轨迹，controls完全一致，事件文件hash不变；读取renderer preclip统计。
5. 版本化live bank与reference显式分开。S13ReviewSession不能悄悄拿新的selectedBank；旧PCM身份仍需独立复核。
6. 精确commit CI后，再验证main-compatible完整manifest、签名和保数据安装。静态日志、有效GPS道路输入、物理输出与人耳分开记录。

不得删除失败证据或用新口径重算旧分数把失败改成通过。

## 七 尚未关闭

SESSION_START精确CI/设备复验；安装方向实际确认与道路输入；虚拟需求/巡航策略；窄接缝候选全轨迹与新旧层边界、产品路由/手机/试听；Supra峰预算；高转source共振与RPM相消；其他车型同等级验收；正式参考及人耳结论。
