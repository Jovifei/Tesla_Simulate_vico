# N2 event restore 本地回归修复 · 2026-10-02

接收d71fd2f后，实际回归N2EventAtomicRegressionTest证明：future occurrence有效、nested queue cursor非法时，restore虽抛异常但已改写live occurrence counters/scalars。

修复：将response构造提取为共用factory；同profile的disposable occurrence与response先执行各自真实restore校验，通过后再写live state。没有改变发生机会、种子或响应波形，也没有编辑冻结s17/s18核心。

回归先RED后GREEN；完整244 tests、0 failure/error、27 skipped，APK构建成功。非法恢复后live occurrence counters/scalars及response RNG保持原值。

N2仍未objective/held-out评分、未安装；恢复修复不等于声学接受。此修复交回远端审核，其继续完成Source/Renderer的同类事务接线与完整参考工具。
