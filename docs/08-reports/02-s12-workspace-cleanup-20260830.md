# S12 Workspace Cleanup — 2026-08-30

Date: 2026-08-30
Branch: `agent/s12-stage-x-r2-engineering-selection`
Scope: local workspace hygiene only. No firmware, Track-P, Runtime, or selection-gate change.

## Why

The Tesla Speed workspace accumulated dated pytest sandboxes, EasyEDA one-off
dumps, Simulink `.slxc` caches, Python `__pycache__`, and unregistered
worktree leftovers. Those files were process artifacts, not source of truth.

## What was removed

| Class | Examples |
|---|---|
| Dated pytest sandboxes | `_stage_l_*`, `_r2_*`, `_pytest_tmp`, `_task10_*` |
| EasyEDA one-off scripts | root `wire_*.js` / `fix_*.js` / `verify_*.js` |
| Simulink scratch | `slprj/`, `prj/*.slxc`, `mcp_minimal_acceptance.slx` |
| Python caches | `__pycache__/`, `.pytest_cache/`, worktree `.task*` / `_agent_tmp` |
| EDA process dumps | `outputs/easyeda_hd_put_*`, `outputs/easyeda_hd_wire_*` |
| Agent diagnostic dumps | `reports/child-claude-s12-*` |
| Historical audit copies | `audit_packages/S12_Simulink_Sound_Playground_v09_audit*` |
| Unregistered clones | `audit-worktrees/s12-pp-source-2d8c58a`, `worktrees/s12-v11`, `worktrees/_task-3-0-backup-s12-v12` |
| Firmware build | `prj/build/` |

Locked `_stage_l_*` directories required an elevated `takeown`/`icacls` pass
because they were owned by a sandbox SID at Medium integrity.

## What was kept

- Registered git worktrees (Stage C–X and `s12-v12`)
- `hardware/`, `hardware_lc/`, `hardware_kicad/`
- `prj/` source (ESP-IDF)
- `review_packages/` including `s12-stage-x-r2-engineering-selection-v1`
- `tasks/` runtime evidence
- `docs/`, `research/`
- `node_modules/` (reinstall with `npm install`)

## Ignore contract

The same patterns are now in `.gitignore` so dated pytest sandboxes, EDA
dumps, and audit extract folders cannot re-enter Git.

## Relation to Stage X

This cleanup does not change engineering preselection or formal R1 status:

- `selection_outcome`: `NO_MEASURABLE_IMPROVEMENT_AFTER_REDESIGN`
- `formal_selection`: `FORMAL_R1_REFERENCE_MISSING`
- Review package remains at `E:\Tesla_speed\review_packages\s12-stage-x-r2-engineering-selection-v1`

Knowledge-base note: `docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/13-Workspace-Cleanup-20260830.md`
