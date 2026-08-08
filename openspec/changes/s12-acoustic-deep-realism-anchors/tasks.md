## 1. 基础设施与回归护栏

- [x] 1.1 在本地确认 §4.2 粗调门禁基线：跑 `publish_identity_v02` 三锚点，记录 idle/accel 8/8 PASS 基线指标
- [x] 1.2 建立逐状态谱距与身份分离评估脚本（读取 `realism_reference_manifest.json` 阈值，输出 pairwise 谱距报告）

## 2. 十二个 pytest 回归修复（仅 Track S）

- [x] 2.1 锁定 ferrari `rms_bounded` + `high_freq_grows` 回归：新增 subprocess 锁测试断言两项既有测试 PASS（base 301fed4 已修复，本组只锁定不复修）
- [x] 2.2 锁定 hellcat `blower shaft lobe` 回归：新增锁测试断言既有测试 PASS（base 已修复，本组只锁定）
- [x] 2.3 锁定 rx7 `housing` + `turbo-lift` + `acceleration-stem-balance` + `constant_state` 四项回归：新增锁测试断言既有测试 PASS（base 已修复，本组只锁定）
- [x] 2.4 锁定 5 个 LUFS-RMS 集成子测试（base 已修复，本组只锁定；实际该方法含 6 子测试，整方法锁定覆盖全部）
- [x] 2.5 全量 pytest 跑通：锁测试 8 passed（覆盖 12 回归），新增 assert_track_p_unchanged.py 断言 Track P 零改动且 git diff --check 干净（EXIT=0）

## 3. 三锚点逐状态 deep realism（anchor-deep-realism）

- [x] 3.0 重建 tuning manifest：物理先验推导六态差异化目标 + 录音链低频滚降反演补偿（Jovi 2026-08-07 决策；修复原 manifest 六态塌陷为三态、且 ferrari idle 低频占比仅 0.94% 的录音链失真）
- [ ] 3.1 Ferrari 458 逐状态频谱目标注入（idle / steady / accel / full pull / lift-afterfire / idle return，Track S 源 manifest）
- [ ] 3.2 Hellcat 逐状态频谱目标注入（同上六态，Track S 源 manifest）
- [ ] 3.3 RX-7 逐状态频谱目标注入（同上六态，含 afterfire 瞬态，Track S 源 manifest）
- [ ] 3.4 跨锚点身份分离验证：pairwise 谱距 > manifest 最小分离阈值，无两锚点塌陷
- [ ] 3.5 每个锚点调音后跑 `publish_identity_v02`，确认 §4.2 粗调门禁保持 PASS

## 4. 人耳盲听门禁（human-audition-gate）

- [ ] 4.1 生成密封 opaque-coded 盲听 wav 集 + 盲听表单（身份映射单独密封存储，不进入表单）
- [ ] 4.2 实现混淆矩阵聚合器（逐锚点辨识率 + 最大交叉混淆率，版本化产物）
- [ ] 4.3 实现门禁阈值 / 天花板判定与可复现 PASS/FAIL verdict
- [ ] 4.4 执行盲听（真实受试者或自动感知代理占位），产出混淆矩阵与门禁结论

## 5. AudioParameterPackage 收敛（audio-parameter-package）

- [ ] 5.1 仅当 deep realism + 盲听门禁均 PASS 后，收敛三锚点 Track S 最终参数集
- [ ] 5.2 生成版本化 AudioParameterPackage JSON（含每锚点参数、per-state 目标、afterfire 参数、参考标识、可复现 manifest：source commit + 确定性 seed）
- [ ] 5.3 从 pinned commit + seed 复现渲染，校验指标匹配门禁指标（在声明数值容差内）

## 6. 验收与收尾

- [ ] 6.1 更新 verify JSON 与 Stage B/C 验收报告（标注 deep realism 与盲听结论）
- [ ] 6.2 提交本 change 分支 commit（不 push，待 Jovi 授权）
