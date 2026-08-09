# S12 Track-P Baseline v3

> 状态：生效中（取代 Baseline v2）
> 建立日期：2026-08-09
> 边界：`synthetic; uncalibrated; not OEM reproduction`

## 变更原因

`main` 与 `agent/s12-acoustic-realism-review-optimization` 从 `2d8c58a` 分叉后分别前进。统一合并提交 `ea586bc53d8e115324db586035823cbc4f605c8c` 同时保留：

- `main` 的 HY3 独有成果；
- 声学分支的八车型、深度真实感、Android 与验证链；
- 42 个 AST 语义相同的 Python 冲突采用 Baseline v2 字节版本，避免无意义改写 Track-P；
- HY3 恢复的 synthetic visual/audition PTR 适配器 `s12_sound_playground_ptr_tuning_step.m`；该文件不等同于完整 FVM/PTR 物理核心。

冻结 radiation JSON 的 Git blob 是 LF，而既有合同锁定 CRLF 字节 SHA。合并提交新增精确 `.gitattributes` 规则，使新工作树稳定检出合同字节；未修改 radiation JSON、PTR 数学或 FVM。

## 基线标识

| 项 | 值 |
|---|---|
| Baseline commit | `ea586bc53d8e115324db586035823cbc4f605c8c` |
| Parents | `b7579747854e8fa6d4fca1ebba6f34242ee571c5`, `b96bb452f49ef695fe08146c0c501c6fa427641a` |
| 冻结文件数 | `180` |
| 冻结清单 SHA-256 | `94281467e14a66780232fb6ae04bd01917a58a3332721967a80c41f4d6217a8a` |
| 冻结符号数 | `2` |
| 冻结符号 SHA-256 | `e1fbda0a64d7232a8c17712a0c63d9ae3e0f95ae9bf9236c55d049b9b5bd9f7d` |
| Accepted radiation bytes SHA-256 | `0f4b2ca494cd44f79d05968513759578d04e6ab38b1ee37f7621158abb0d2d6f` |

## 验证要求

```powershell
python tools/sound_sim/s12/acoustic_identity_v015/scripts/assert_track_p_unchanged.py
python -m pytest tools/sound_sim/s12/acoustic_identity_v015/tests/test_s12_track_p_guard.py -q
```

守卫 PASS 只证明冻结边界与本基线一致，不替代 MATLAB/Simulink Runtime Proof 或人工听感验收。
