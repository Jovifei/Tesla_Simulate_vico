# N2 Profile/binary 本地接收修复 · 2026-10-02

接收a61cb1d：测试编译失败（bandEdgesHz被移除）；Profile改写还删除了coefficient范围/非零验证、late-tail约束及identity内的seeds/fractions/dimensions/budgets。

本地恢复5330f68完整Profile实现，仅保留必要的新接口：finite source/event scales<100、calibratedCopy及calibrated初始化工厂。原bank生成法/coefficients/种子不变，单位Profile身份恢复98dec5a954e836a0105241a04e920b8209f239441a51d039a46eb6b4f8e287c0，实际测量sourceScale13.728409855272066是评分前初始化，不是失败后调gain。

Binary reader按固定557310字节读取，提前拒绝截断/超长数据、错误identity格式；读取完整参数及arrays后构造真实Profile并重算identity。补齐noise arrays、seeds、fractions的bit-exact roundtrip和身份变化测试，保留trailing/tamper拒绝。

本地build/test：243 tests、0 failures/errors、27 skipped，APK构建成功，源码diff-check通过。未进行N2 objective/held-out评估，也未安装此N2候选；手机仍为已验证的AH默认路径。

N2UnitCalibrationTest为本地验证新增opt-in工具：16稳态3秒、取[1,3)s的旧bark与单位新源中位RMS；无参考/held-out/目标评分，输出不得覆盖旧run。该focused测量已实际运行。RootUnitReceipt位于本地受控下载目录，不上传原始PCM。

仍需远端完成：事件额外.25和正交/能量校准、真正事务restore、全部参考轨迹/stem/hash导出、actual reference/fit driver、锁定预约验证与630已知/new-state回归。此接收修复不是大阶段完成。
