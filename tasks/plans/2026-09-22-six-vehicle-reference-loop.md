# AI-8 六车型本地参考闭环

用户已授权 Hellcat、Ferrari 458、LFA、GT-R R35、C63 W204、Supra JZA80 的开发；并行车型审查使用 gpt-6-luna / max，主 agent 负责集成和审核。本次不使用远端 ChatGPT。

基线：53a161d573a8f33959b1e3ef7d510dbfcbb99b70；独立分支 feature/stage-ai8-six-vehicle-20260922。此前 Android 计划不执行。

## 执行清单

- [x] 核对六车已有声源、SHA 与可用 split：现有 SHA 绑定 v3 计划只覆盖 Ferrari (2 train/1 validation) 与 GT-R (3/1)；Hellcat/LFA 不具备合格 split，C63/Supra 缺显式评审计划。
- [x] 复用 fourcar_reference_loop 和 reference_feedback 优化器；为 C63/Supra 补齐一个 source-local 参数的实际渲染适配及 feedback-off 回归。
- [ ] 仅对 Ferrari/GT-R 运行一次有界 R3 相对诊断搜索；不根据验证集反复调搜索范围。
- [x] 实现逐场景数值收据、失败回滚/候选保留和 fail-closed verifier；固定配方不得标为自动合格 B。
- [ ] 运行六车 30 秒 baseline 诊断试听包和独立验证；保持 RX-7/Aventador 既有证据。
- [x] 完成六个 Luna/max 车型只读审查；父 agent 复核其证据并处理字段宣称和 Supra 源 SHA 两项风险。
- [ ] 提交已验证源码和报告；原始音频、参考素材及生成包保留 Git 外。

不更改冻结 Track-P/PTR/Radiation，不放宽峰值与 Reference 门禁，不覆盖既有不可变包。缺少可比性评审或素材时，仍完成可实现的适配和软件验证，逐车明确真实运行阻塞，不伪造资格。人耳接受由 Jovi 给出。

## 分工

- 主 agent：公共资格/包装接口、集成、运行预算和验收。
- 子 agent A：Hellcat/Ferrari/LFA/GTR 已有链路及精确修复。
- 子 agent B：C63/Supra 反馈适配及独立测试。
- 子 agent C：参考输入独立核验，后续验收审查。

每次派发精确文件写入范围；禁止同时编辑公共模块。真实搜索仅使用已有 SHA 绑定计划及受治理输入，保持 R3 私有诊断、禁止再分发；不得从文件名推断可比条件。失败结果同样保留。Hellcat/LFA/C63/Supra 不得在缺少评审计划时进入优化器。
