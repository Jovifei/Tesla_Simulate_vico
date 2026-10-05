# REAL 虚拟需求与巡航策略候选

基线：c7789afe8dd287980e7a8fba052b133ca3cc35ac。状态：本地工程候选，尚未发布、安装或通过实听。本批只改变REAL输入的虚拟控制策略及相关安全身份，Python S12声学权威、全部WAV、固定gain、齿比、renderer DSP、S13/reference和DEMO/PREVIEW/QUALIFICATION旧控制路径不变。

## 触发问题与已复现根因

原updateMeasured调用旧update：升降挡依赖加速度符号。50Hz IMU与1Hz GPS保持回放中，GPS首次报75时加速度已变0，会错过升挡，巡航留一挡7200rpm；70也会留一挡约6919rpm。原throttle=a/3在匀速时必为0，素材查表被压在load下沿。加速度由正回0还能触发一次release，不能据此判断真实收油。

这与速度显示的mph换算、GPS陈旧、手机方向、源数据真实性是不同问题。本批不改变显示速度/单位，也不把IMU积分作为车速，不宣称解决了道路测量准确性。

## 三个量分开

- virtualDemand是前进行驶、平路无风假设下的归一化牵引需求估计。默认d=clip((低通纵向加速度+.13+.00028×v²)/3)，v为m/s；不是实测油门、发动机负载或制动力
- bankLoad=.32+.60d是当前六套S12素材的查表坐标。d=0仍使用.32素材，不能声称已有真实idle/coast/unloaded素材；查表越界计数归零只是坐标范围保证
- shiftGain独立传递给原renderer。虚拟换挡包络不再写回需求或查表坐标

常数是公开工程候选。[MathWorks通用纵向模型](https://www.mathworks.com/help/sdl/ref/longitudinalvehicle.html)的行业平均示例换算后A/m约.1275/.1334/.1373 m/s²、C/m约.000348/.000241/.000257 1/m；仅支持量级和量纲，不是当前车辆标定。坡度、风、倒车方向、真实踏板和制动意图不可由这两个输入独立确定。

加速度低通tau=.12s只作用于虚拟需求，原测量/显示/日志加速度不改。只有新原始IMU时间推进低通和驻留；GPS-only可更新路阻，不推进IMU时长。重复时间戳必须保持同一数值和GPS精度元数据，乱序/非法/缺源拒绝后恢复以当前有效值重锚。

停车需v<=.30m/s、|a|<=.10m/s²持续.60s；正加速起步即使GPS暂为0也立即退出停车。负向候选a<=−.20m/s²，驻留.15s后才有release资格，再经原.08s释放驻留。阈值仍需真实静止噪声验证。平巡低需求会消费旧arm，不能几秒后借老峰伪造释放。

## 巡航与速度不确定性

名义U(d)=idle+(shiftRPM−idle)×(.4+.6d)。每对齿比使用同一U：上界U/K_g，下界hU/K_g，h沿原profile。后续挡怠速下限1.4idle、低挡红线检查.98redline；方向驻留.4s、换挡间隔至少max(.8s,原包络时长)，每次最多一挡。恢复隔离窗内静默选择保持挡位，不制造补发事件。

需求噪声±.1的非重叠约束用分段函数精确临界点验证，不使用101点采样冒充代数证明。测试发现过noise=.105、h=.8027漏检并已加入回归。

新增GPS实验曾发现：真值约29、1Hz读数22↔36km/h，30秒29次猎挡。现在传递原reported speed uncertainty u；升挡及升后idle检查用max(0,v−3.6u)，降挡及低挡红线检查用v+3.6u，速度/RPM/需求仍使用原v。只有null使用2m/s策略缓冲；显式负数、NaN、Infinity拒绝，不转成null来fallback。u和GPS样本绑定，同gpsNs改u会拒绝。

[Android定义](https://developer.android.com/reference/android/location/Location#getSpeedAccuracyMetersPerSecond())是68%置信估计，不是硬误差界，也未保证高斯标准差。2m/s fallback不升级UNVERIFIED为已验证精度。无猎挡保证只限于测试假设“实际误差不超过buffer且需求在声明范围”；低估误差的provider仍可能造成摆动，原RPM也仍跟随GPS波动。

缓冲的代价明确保留：C63满需求名义70.82km/h升挡，u2时观测门槛约78.02，可能先触及虚拟红线。在144km/h/12s、GPS1Hz回放中，首次升挡由观测72延后至84，出现短暂7200钳位；不使用临时forced-up绕过缓冲。精度较差时，保守挡位不一定是理想听感。

## 连续性与日志

上游epoch保持原值；模型每进入新可信REAL段递增modelContinuityRevision，并在整个段持续携带。即使latest-state mailbox漏掉invalid和首个恢复包，writer仍能识别新段、清除旧afterfire/shift，并屏蔽整个首个收到的恢复snapshot。重复IMU、GPS-only、隔离窗静默重锚不递增；synthetic/reference保留0。

MatlabV6SoundBankEngine调用同一纯映射函数，测试覆盖实际controller→映射→AudioInputGate→原renderer，而不是只测新policy。原AudioEngine已有owner线程evaluate→clear→禁事件→render顺序，无需改其DSP或写入循环。

普通日志profile追加real_virtual_drive_v1，表示本build的REAL策略版本；每行source/drive mode决定是否实际使用。DEMO等仍为旧synthetic策略，不能用DEMO成功来证明新REAL策略已实机通过。MODEL的throttle列是虚拟需求proxy，load列是bank坐标；raw/selected速度与加速度保持原义，schema未改。

## 验证和风险

最终便携套件185项通过（无skip），另有真实源路由静态检查；Android外壳完整编译仍需精确提交CI。

同一c778正常声库、同gain、实际Kotlin controller/renderer，6车型×6条40s轨迹×reported u0/u2，共138,240,000 frames。使用零测量噪声、1Hz采样保持GPS和50Hz IMU；并不等于实车采样。原preClip/hardClip/nonfinite预算逐case检查，全部通过。跨邮箱丢失、普通stop和watchdog用实际renderer确认旧事件清掉、有限尾音归零。

C63精确fixture巡航：20仍1挡，40为2挡，70/75为3挡约3033/3250rpm，100/144为3挡。u2会更保守，不能混同u0结果。原C63仅3个齿比，144仍约6239rpm；Hellcat最高挡约6074接近6200红线。这些是现有虚拟车型数据的限制，不添加未经依据的新齿比。

重要听感/音量边界：70巡航避开原6919掉幅区后，同gain RMS提高约9.96dB。这不是“更真实”评分，也不是简单增大音量；原高转共振/相消问题仍在。任何后续试听必须低音量、同输出保护，单独检查启停/恢复/换挡和人耳反馈。没有新手机安装或道路验收。

[可复现包](../review_packages/vico-real-drive-20261004/README.md)保存case指标、源码/资产身份、旧测试期望更改依据及运行入口。失败的GPS猎挡、旧峰延迟释放、101点guard漏检和中间invalid被吞的例子都保留为回归，不删掉来换取绿灯。
