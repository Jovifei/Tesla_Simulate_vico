# P3 接入补丁本地接收修复 · 2026-10-02

远端交付至5b02d827；两版hook补丁分别因格式混用、hunk计数错误不能应用。本地基于远端设计完成真实调用点和接口修复，保留默认旧声库。

- AudioEngine增加internal、debug-only、非运行期间的资格provider准备入口，默认没有provider。没有UI或JS启用入口，没有合格新候选自动注册。
- 正常播放PCM点先渲染旧声库，保持回退时旧模型状态连续；资格provider可用才覆盖PCM。历史prototype、参考与review路径保持原有生成器。
- 实际route绑定candidate/profile/source身份与格式明确的报告；每个block重新检查资格。未知hash、空诊断、冻结HY1及派生ID拒绝。
- PCM错误长度、非finite、越出[-1,1]、renderer异常、输入失效、非48k均清除provider，回退旧路径。无有效声音输入按现有包络输出静音。
- stop、setVehicle和playLoop finally清除候选。MainActivity现有生命周期调用stop，所以不会自动恢复未经重新准备的候选。
- provider PCM复制后再交给AudioEngine混音，防止原buffer被音量处理覆盖。报告hash为声明的产物引用，不声称签名认证或真实声学证明。
- adapter prepare拒绝时清除先前artifact，并拒绝未知hash格式。

验证：gradlew.bat :app:testDebugUnitTest :app:assembleDebug --offline --console=plain，BUILD SUCCESSFUL。220 tests，0 failures/errors，25 skipped；包括真实四模式event-on/off的合成PCM一致性、provider异常/无资格/撤销/输入错误/越界/清理、artifact身份与先前候选清理。源码git diff --check PASS；重新生成patch后，patch自身的空白context行产生尾空白提示，这是标准diff上下文，不删除。git apply --reverse --check通过。

Debug APK SHA256：595e212486b11c9a7df0923ec4428771a598848be5e7ab98a1af4e78b655379d。

设备安装、AudioTrack实测、声学与人耳均未执行；adb无设备。持续声新源没有完成，HY1仍失败，P2/P3整体PARTIAL。本段是未来合格候选的实际接入准备，不是新声浪交付。

tools/patches/vico-p3-audio-engine-hook.patch已由本地生成器重建为准确代码diff，基线5b02d827；实现已包含在本提交，不应再次apply。可用git apply --reverse --check验证格式与当前实现对应。

下一步由远端独立审核回推代码，再负责新候选/实际声学资格的大阶段方案与实现；本地承担参考计算、编译及手机补验。缺少合格新源不得开启生产候选路线。
