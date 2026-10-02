# 本轮手机接收验证 · 2026-10-02

## 设备与安装

当前GM1910（OnePlus 7 Pro，Android 11）已连接既有ADB服务15037。此前只检查默认5037导致误判；未重启既有服务。后续命令明确使用-P 15037及所选设备。

Debug包com.vico.simulator、versionCode=1。安装前比对当前已安装APK与新APK签名证书SHA256一致：9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774。仅install -r，无卸载、清数据或改系统配置。首次安装时间保持2026-07-10 11:43:13；更新后的最后安装时间2026-10-02 18:09:46（设备时钟）。

本轮验证APK SHA256：debfa840e22f0556f96439d51ef623648a2147e44490f1fad5c43e36dba5098f。含MainActivity准备失败日志补充，数值声源未改变。构建与220tests/0fail/25skip通过。

冷启动成功，随后HOME/恢复为HOT启动成功，进程存活；本轮PID范围日志未见FATAL EXCEPTION或目标App ANR。不是长期设备资格结论。

## 20秒既有AH基线诊断

App原已选C63，诊断结束恢复先前DEMO模式/场景与默认声库。执行现有debug vico_s15_smoke，scope=GM1910_DEMO_LAUNCH_DECEL_NOT_ORIGINAL_TRACE；candidate=C63_AH_V1。

- intended duration：20000ms；1021 blocks / 980160 frames（含停止收尾）。
- AudioTrack accepted frames=980160；underrun 0→0；audio_error=null。
- PCM实算finite=true，peak=0.7270747423，SHA256=218749ac0021fd6a2617e8d2e9fb8a8bbe07bd0bea44c56529f876f93910ccfc，与收据匹配。
- compute deadline misses=0；最大compute约4.49ms；写入最长约170.66ms，保留原测量，不将阻塞写耗时当计算耗时。
- capture为POST_ENVELOPES_PRE_AUDIOTRACK_ACCEPTED，input_binding=UNBOUND，comparison_status=NOT_EVALUATED。
- capture full_window=false：目标30秒，本轮20秒；不把此收据当30秒完整窗口或原始trace资格。
- human_acceptance=NOT_RUN；不声称实际扬声器频响或具名试听通过。

本轮首次诊断未立即看到新收据，未证实准备失败。补充失败日志后冷启动诊断正常完成，未出现该日志；不宣称日志补充修复了数值声源。

原始本地收据/合成PCM只保留E:/Claude_allow/Download/vico-device-reception-20261002/smoke-1790935809632.*，不提交到GitHub；仅此派生摘要用于远端审核。

## 当前边界与循环下一步

Debug升级、冷/热启动、既有AH基线短诊断有真实设备证据。新的P2声源实现及声学资格尚未完成；HY1仍失败，不安装/启用失败新候选。远端继续实现整包，本地接收运行真实参考计算、编译、设备验证和必要修复，再回推审核。无需重复代码授权；确需停止必须给出现时阻塞与用户具体必要操作。
