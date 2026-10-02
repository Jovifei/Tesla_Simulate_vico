# 受控Debug验证与生产门分离 · 2026-10-02

本地接收发现验证顺序死锁：默认关闭的Debug qualification route原先要求DEVICE/HUMAN已通过，才能在设备上采集DEVICE/HUMAN证据。

修复仅改变资格顺序，不开启候选：

- isDeviceValidationEligible：要求有效身份/三个hash格式、非空有限诊断，以及DIGITAL/STATE/CONTINUITY/ACOUSTIC明确通过。
- isRuntimeEligible：仍要求全部门（包括DEVICE/HUMAN）通过。
- internal Debug AudioEngine hook使用设备验证资格；release/运行期间不能准备新provider，默认旧声库不变。
- 冻结HY1及所有派生ID仍拒绝；声学未通过仍拒绝。当前没有合格N2 provider或UI/JS启用入口。
- 同时修正provider注释，使其准确描述已存在的Debug调用点。

新增测试证明离线全门通过、DEVICE/HUMAN待验证时可以受控Debug准备，但不能作为生产资格；ACOUSTIC失败时继续拒绝。

本地完整build/test：223 tests，0 failures/errors，27 skipped；另有两项冻结HY1 opt-in验证已单独执行，不把skip当PASS。此APK尚未替换手机上已验证的c455e72版本；新source未过门前不启用。
