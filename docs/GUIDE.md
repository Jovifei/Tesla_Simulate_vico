# Documentation Guide

## Directory Structure

```text
docs/
  README.md
  GUIDE.md
  00-reference/
  01-architecture/
  02-requirements/
  03-protocols/
  04-planning/
  05-execution/
  06-testing/
  07-debugging/
  08-reports/
  09-backlog/
  10-learning/
  knowledge/
  superpowers/
```

## Canonical Memory Rule

后续 Agent 首先读取：

```text
docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md
docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md
```

用户明确指定项目历史知识的证据权重：

- `S12_Handoff_Package_2026-09-03` ≈ 90% 主证据；
- 旧聊天/此前总结 ≈ 10% 补充证据；
- 对 main/branch/PR/CI/SHA 等可变化事实，current GitHub remote truth 始终优先；
- 用户当前明确产品决策优先于旧路线。

当前产品决策：Android App-first；ESP32 = `DEFERRED_FUTURE_OPTION`。

## Naming Rules

- Use ASCII paths where practical.
- Use Chinese, English, or bilingual titles inside Markdown files.
- Use `00-guide.md` as the category guide inside numbered public directories.
- Keep old/speculative material outside the primary read path unless reviewed.

## Documentation Status Rules

Every project-facing document must make its evidence boundary clear：

- `Implemented`: code exists.
- `Verified`: fresh software/test/CI evidence exists.
- `Verified-on-device`: current target-device evidence exists.
- `Human accepted`: Jovi listening gate passed.
- `R1 qualified`: legal synchronized real-reference gate passed.
- `Blocked`: external input/human/tool is required.
- `Deferred`: intentionally not part of current implementation.

Never promote one evidence class into another：

```text
CI green != Human PASS
Human PASS != R1/OEM calibration
historical ESP32 code != current App requirement
```

## Promotion Rule

The public read path should point to the active App-first roadmap and the canonical long-term memory. Historical firmware, old stage reports and raw research remain searchable but must not silently override current project direction.
