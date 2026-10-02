# 路线图与进度体系验证

2026-10-02，本地 Codex 落地原音浪聊天给出的八阶段规划。

- 唯一账本：docs/project-ledger.json；权重合计100，完成按有证据 DONE 计算。
- `python -B -m unittest discover -s scripts -p test_project_progress.py -v`：6 tests，OK。验证缺证据、无效权重、缺失证据、依赖环、部分状态不计完成及失败回退。
- `python scripts/update-project-progress.py --check`：两视图与账本一致。
- 不采用远端建议的无逐项计算22%；初始工程进度由本地里程碑生成。
- P5现有输入链路盘点为 PARTIAL，不把缺实车资格写成完全无实现；六车矩阵仅指新连续算法资格，不抹掉原有声库。
- HY1仍执行中；此次只交付路线图工具，不代表声学/手机/人耳完成。
- 本次为计划与项目状态视图，Obsidian：NO_MEMORY_UPDATE。未宣称知识库已同步。

维护：每次代码、测试、审核、设备或试听交付，同批更新账本并重新生成、检查。文件存在仅是工具校验，人仍须审查证据适用的源码/配置/APK身份。
