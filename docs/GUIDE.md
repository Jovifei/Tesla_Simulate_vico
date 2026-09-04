# Documentation Guide

## Canonical Memory Rule

后续 Agent 首先读取：

```text
docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md
docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md
```

证据权重：

- `S12_Handoff_Package_2026-09-03` ≈ 90% 主证据；
- 旧聊天/此前总结 ≈ 10% 补充证据；
- main/PR/CI/SHA 等动态事实以 current GitHub remote 为准；
- 用户当前明确决策优先于旧路线。

当前产品决策：Android App-first；ESP32 = `DEFERRED_FUTURE_OPTION`。

## Documentation Status Rules

- `Implemented`: code exists.
- `Verified`: fresh software/test/CI evidence exists.
- `Verified-on-device`: current target-device evidence exists.
- `Human accepted`: Jovi listening gate passed.
- `R1 qualified`: legal synchronized real-reference gate passed.
- `Blocked`: external input/human/tool is required.
- `Deferred`: intentionally not part of current implementation.

```text
CI green != Human PASS
Human PASS != R1/OEM calibration
historical ESP32 code != current App requirement
```

Historical firmware, old stage reports and raw research remain searchable but must not silently override current App-first project direction.
