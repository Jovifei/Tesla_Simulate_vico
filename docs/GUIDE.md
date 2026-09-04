# Documentation Guide

## Canonical project memory

后续 Agent 首先读取：

```text
docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md
docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md
```

证据权重：

- `S12_Handoff_Package_2026-09-03` ≈ 90%；
- 旧聊天/此前总结 ≈ 10%；
- 动态 GitHub 事实现场复核；
- 用户当前明确产品决策优先。

当前方向：Android App-first；ESP32 = `DEFERRED_FUTURE_OPTION`。

## Evidence status vocabulary

- `Implemented`: code exists.
- `Verified`: fresh software/test/CI evidence.
- `Human accepted`: Jovi listening passed.
- `R1 qualified`: legal synchronized real-reference passed.
- `Blocked`: external dependency.
- `Deferred`: intentionally outside current scope.

```text
CI green != Human PASS
Human PASS != R1/OEM calibration
historical ESP32 code != current App requirement
```

Historical firmware, old stage reports and raw research remain searchable but must not override the active App-first direction.
