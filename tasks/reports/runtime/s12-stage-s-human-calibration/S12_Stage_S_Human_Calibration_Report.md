# S12 Stage S 反馈驱动调音报告

状态：`WAITING_FOR_REAL_REFERENCE_DATA` / `WAITING_FOR_JOVI_HUMAN_FEEDBACK`

已建立中文听审合同，但没有生成占位音频，也没有把 Stage P fixture 结果当作真实反馈。正式 webMUSHRA/A-B 包必须绑定 Stage Q 的合法真实参考、Stage R 的候选 SHA 和完整播放元数据。

一次只允许修改一个车型、一个场景问题和一个参数组；自动指标改善且人耳不退步后，才能进入下一轮。所有调音都必须在独立 sound-fix 分支进行，当前分支不修改车型 source。

中文评分维度已写入 `stage_s_chinese_listening_contract.json`。上游 webMUSHRA 的固定按钮若要完全中文，还需要维护本地化前端覆盖；不能只翻译配置文本就声称全中文。
