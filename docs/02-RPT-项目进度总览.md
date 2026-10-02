# 项目进度总览

更新：2026-10-02 · 主线：P2 · 工作包：P2/P3 GitHub接力：默认关闭的真实PCM接入准备（PR #35）

本文件由 `scripts/update-project-progress.py` 从 `docs/project-ledger.json` 生成，不直接编辑。

进度只计有证据的 DONE 里程碑；阶段内等权，再按阶段权重汇总。它不是工时、声音相似度或测试通过率。部分完成、失败、阻塞和待试听均不计完成；证据被推翻可回退。权重为规划口径，调整必须说明原因。

工程里程碑进度：**23.3%** `████░░░░░░░░░░░░░░░░`。声音产品尚未完成。

| 大阶段 | 权重 | 完成里程碑 | 阶段进度 |
|---|---:|---:|---:|
| P1 工程基础与证据体系 | 10% | 2/2 | 100.0% |
| P2 连续声浪核心 | 25% | 1/3 | 33.3% |
| P3 Android实时运行与交互产品化 | 15% | 1/3 | 33.3% |
| P4 六车型连续声音扩展 | 15% | 0/2 | 0.0% |
| P5 车辆输入与驾驶状态 | 10% | 0/2 | 0.0% |
| P6 真实设备与驾驶验证 | 10% | 0/2 | 0.0% |
| P7 具名试听与产品体验验收 | 10% | 0/2 | 0.0% |
| P8 可发布交付 | 5% | 0/2 | 0.0% |

## 当前阻塞与下一步

- 当前手机默认仍为原六车型声库；HY1 未接入/安装，声音目标 NOT_DONE。
- HY1 单次拟合已冻结：事件校准改善8.1%未达20%；中频最大+1.468dB超过1dB保护门。不能直接安装或再次拟合救分。
- 完整实际 Kotlin 离线资格未结束；新 APK、真机生命周期、物理输出、实车及具名试听均待执行。
- 本轮adb devices无手机；安装、设备生命周期、实车与具名试听未执行。
- Cloud整阶段任务提交仍被账户MFA拦截；已改用音浪新聊天GitHub读写执行接力，未改安全设置。
- PR #35已落实默认关闭的真实AudioEngine PCM调用点，本地220 tests、0失败、25跳过、APK构建通过并远端回审；持续声新源和实际声学仍未完成。

完成 S18/HY1 实际 Kotlin 资格；校准已出现失败门，不允许直接交付

## 六车型新连续算法资格（原声库不等于新算法交付）

| 车型 | 实现 | 声学资格 | 新版手机交付 | 人耳 |
|---|---|---|---|---|
| Hellcat | NOT_STARTED | NOT_RUN | NOT_RUN | PENDING_HUMAN |
| Ferrari 458 | NOT_STARTED | NOT_RUN | NOT_RUN | PENDING_HUMAN |
| LFA | NOT_STARTED | NOT_RUN | NOT_RUN | PENDING_HUMAN |
| GT-R R35 | NOT_STARTED | NOT_RUN | NOT_RUN | PENDING_HUMAN |
| C63 W204 | ACTIVE | NOT_RUN | NOT_RUN | PENDING_HUMAN |
| Supra JZA80 | NOT_STARTED | NOT_RUN | NOT_RUN | PENDING_HUMAN |
