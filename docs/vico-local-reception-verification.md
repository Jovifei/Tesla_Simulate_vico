# GitHub接力本地接收验证 · 2026-10-02

远端PR #35分支codex-remote-p2-p3-audit-20261002，接收SHA83d6267a71e05117026836b8720dfbca2621c8f0。独立本地工作树remote-p2-p3-validation-20261002；不覆盖Owner App或研究main。

远端完成隔离资格、注册表、诊断、实际event-on/off PCM输出和基础测试。当前PARTIAL，不等于持续声新算法或Android生产接入已完成。

本地修复：注册ID必须匹配qualification.candidateId；冻结C63_HY1及所有C63_HY1_派生ID均禁止启用。两项回归修复前真实失败、修复后通过。

本地补验证：空轨迹无证据；T/S/E/SE各自event-on/off真实PCM逐样本与直接renderer一致、峰值/身份/长度对应；环形诊断淘汰早期失败后仍保留全程失败与最大峰值。测试使用合成HybridTestProfiles，不是冻结拟合参数声学资格。

命令：在vico_app/Project/android运行gradlew.bat :app:testDebugUnitTest :app:assembleDebug --offline --console=plain。

结果：BUILD SUCCESSFUL；208 tests，0 failures，0 errors，25 skipped。跳过资格用例不算通过。git diff --check PASS。

Debug APK SHA256：3904b01ebad5ee7e9dd5927d9ea6bc0e39b7abeb25180b650055188612b5e9d3。

adb devices无连接设备，设备安装/生命周期NOT_RUN；声学NOT_RUN，人耳PENDING_HUMAN。HY1历史失败和生产默认旧声库保持。APK未安装、未提交。

下一步：将本地修复推回PR35给远端审核；远端继续完成P2/P3主要工程，真实参考与手机门由本地补证。不得把已有模块构建成功转换为声学或产品完成。
