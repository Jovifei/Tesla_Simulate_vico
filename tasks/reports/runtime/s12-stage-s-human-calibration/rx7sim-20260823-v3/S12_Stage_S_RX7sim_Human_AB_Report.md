# S12 Stage S：RX-7sim 中文人耳 A/B 交接（v3）

状态：`R2_LIMITED_COMPARISON_ONLY` / `WAITING_FOR_JOVI_HUMAN_FEEDBACK`

本次只交付一个语义匹配案例：RX-7 FD、`full_pull`、`rx7sim_exhaust_revLong01`。外部试听包位于：

`E:\\Claude_allow\\Download\\s12-rx7sim-human-ab-zh-20260823-v3\\package\\index.html`

页面为中文离线页面，绑定 `test_id=s12-stage-s-r2-ab-20260822` 和研究清单 SHA-256 `2BF26029B68DCAC80C7A9896DC570C18BC3D9F52B5F07C500F38C9A865CE501C`，并固定绑定参考/候选源 SHA 与两份试听副本 SHA。页面脚本已通过 Node 语法检查；试听 WAV 头部可完整打开。页面只导出听审反馈，不自动调音、不更新 Profile，也不把试听副本重新用于 Comparator 指标。

## Jovi 操作

1. 双击外部 `index.html`，先听 A（参考），再听 B（本地候选）。
2. 使用同一播放设备和系统音量，填写监听人、设备、音量、输出端点、系统音效及全部中文评分。
3. 点击导出反馈 JSON，并把导出的文件交回；未绑定 `test_id`、研究清单 SHA、案例 ID、参考/候选 SHA 的文件不会导入。

## 导入门禁

可用以下命令生成规范化收据；命令只校验绑定，不授予自动调音或 Profile 权限：

`python -m tools.sound_sim.s12.real_reference.feedback_import --feedback <反馈.json> --study <study_manifest.json> --binding <feedback_binding.json> --output <收据.json>`

- 真实原始版权音频只保存在批准的仓库外目录；Git 只保留路径别名、SHA、provenance 和本收据。
- 这是 R2 相对比较，不是原厂身份或真实度百分比证明。
- 在收到 Jovi 的完整绑定反馈前，Stage S 调音轮次为 0，参数修改为 0，Profile Candidate 不生成。
- 其余四条 RX-7sim 录音因没有语义匹配的本地候选，没有进入本次 A/B；禁止跨工况复用代理。

机器收据见同目录 `r2_human_ab_receipt_v1.json`。
