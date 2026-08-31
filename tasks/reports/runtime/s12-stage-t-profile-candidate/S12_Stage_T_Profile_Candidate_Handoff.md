# S12 Stage T Profile Candidate 交接

状态：`BLOCKED_PROFILE_CANDIDATE_NOT_READY`

当前不生成任何 `approved_profile_candidate/` 文件，不写入 `APPROVED_PROFILE`、`PROFILE_FREEZE` 或 `PRODUCT_READY`。Ferrari/Hellcat/Supra 的 R2 A/B 包已在仓库外生成，但 RX-7 FD 仍为 R3，且三个锚点均没有真实 Jovi 听审 receipt；R2 不能替代 R1，也不能满足 Profile Candidate 门。

本分支也不修改 Simulink、Runtime、Android、ESP32 或 CAN；产品交接保持关闭。
