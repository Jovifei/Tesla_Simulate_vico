# S12 Stage T Profile Candidate 交接

状态：`BLOCKED_PROFILE_CANDIDATE_NOT_READY`

当前不生成任何 `approved_profile_candidate/` 文件，不写入 `APPROVED_PROFILE`、`PROFILE_FREEZE` 或 `PRODUCT_READY`。只有三个锚点车型完成 R1 真实参考、客观 hard gates 和真实 Jovi 听审后，才能建立候选参数包。

本分支也不修改 Simulink、Runtime、Android、ESP32 或 CAN；产品交接保持关闭。
