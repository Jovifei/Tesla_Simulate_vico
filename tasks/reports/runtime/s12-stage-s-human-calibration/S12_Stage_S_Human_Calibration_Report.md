# S12 Stage S 反馈驱动调音报告

状态：`R2_AB_PACKAGE_READY` / `WAITING_FOR_JOVI_HUMAN_FEEDBACK`

Stage Q 已有三条可审计 CC/CC0 R2 参考（Ferrari 458、Hellcat、Supra），Stage R 已完成有限数字域比较。本轮已生成仓库外的中文 A/B 包：

`E:\\Claude_allow\\Download\\s12-stage-s-human-ab-r2-20260822`

其 `study_manifest.json` SHA-256 为 `9471784e875c98beb2e2ea91081f1ffa87f851ff461bd8e405d414d3447411e6`。包内只有响度匹配试听副本；原始分析 WAV 仍由 Stage Q 外部路径和 SHA 绑定，试听副本不能用于指标计算。RX-7 FD 当前只有 R3 旋转机械演示，因此没有进入正式 R2 A/B。

Jovi 需要按 README_中文.md 播放 A/B，并在 `feedback_template.csv` 中绑定听者、设备、系统音量、输出端点、系统音效、case ID、参考 SHA、候选 SHA 和全部中文评分维度。空模板不是反馈，任何 fixture 结果也不算真实听审。

一次只允许修改一个车型、一个场景问题和一个参数组；自动指标改善且人耳不退步后，才能进入下一轮。所有调音都必须在独立 sound-fix 分支进行，当前分支不修改车型 source。

中文评分维度已写入 `stage_s_chinese_listening_contract.json`；本轮 A/B 包的可见文案为中文，不依赖英文浏览器页面。一次只允许修改一个车型、一个场景问题和一个参数组；自动指标改善且人耳不退步后，才能进入下一轮。所有调音都必须在独立 sound-fix 分支进行，当前分支不修改车型 source。
