---
title: Stage AI-8 Six-Vehicle Reference Loop
project: Tesla-Speed-Sound
stage: Stage-AI-8
type: engineering_status
status: ENGINEERING_DIAGNOSTICS_COMPLETE_HUMAN_REVIEW_PENDING
updated: 2026-09-23
---

# Stage AI-8：六车型扩展

Stage AI-8 在独立 `feature/stage-ai8-six-vehicle-20260922` 分支补上四车型独立数值资格、C63/Supra 单一 source-local 参数反馈适配、六车 baseline 诊断预览与参考 readiness。

## 已验证

- Ferrari 458 与 GT-R R35 使用既有 SHA 绑定 v3 计划做了一轮 bounded R3 relative diagnostic；各自留出 validation 改善，且反馈关闭十场景 PCM 与 baseline 一致。
- Hellcat、LFA、C63 W204、Supra JZA80 没有足以启动搜索的当前评审计划；保持不搜索，不人为放宽样本门禁。
- 六车均有 30 秒 baseline 音频及数值收据，可进入 Jovi 人耳试听；这不是 B 资格、Human PASS、OEM 标定、实车验证或商业分发授权。
- R3 权利/同步信息未核实的资料只用于该受限本地相对诊断，不随 Git/输出包再分发。六车试听的四车事件 tuple 适配明确标作 synthetic preview-only。

## 精确产物

- readiness：`E:\Tesla_speed\review_packages\s12-ai8-readiness-20260923-v2.json`，SHA-256 `2fe26b7789770f712147e23a98b63ce3a2130e96e0dbe54be2083b4efd626bc4`。
- six-car preview：`E:\Tesla_speed\review_packages\s12-ai8-six-vehicle-preview-20260923-v2`，manifest SHA-256 `d53352b5a96f1ca5c741a7c9ecc1f54893bbf6e7f14fa183c6555ae342ba58d7`，verifier `VERIFIED`。
- Ferrari/GT-R run：`E:\Tesla_speed\review_packages\s12-ai8-fourcar-reference-loop-20260923-v1`，ARTIFACTS SHA-256 `8db412ec9a7e5a78138a5f461c166fb2eaf5906d724d9375fadcd167f00a5dbd`，verifier `verified`。
- 源码提交：`531e097`, `db35e1d`, `b9ab654`；Track-P 未变；相关回归 `199 passed, 1 skipped`，预览回归 `25 passed`。

## 待办门禁

等待 Jovi 具名试听/反馈；四个 reference-blocked 车型需要独立的 SHA 绑定评审窗口、split 和 rights/use 决定。在这些门禁到达前，不写入 Human PASS、B-ready、OEM、Profile Freeze 或校准完成。

## GitHub 发布状态

初始预发布检查（2026-09-23）：只读 GitHub API 显示 AI-7 PR #31 为 open/draft，AI-8 远端分支与 PR 尚不存在；本地 Git 传输到 `github.com:443` 经当前 `127.0.0.1` 路径失败。此为当时的时间戳状态快照，后续执行前应查询 live PR/branch 状态。没有更改 VPN、代理、DNS 或网络进程。本轮没有使用远端 ChatGPT 网页。
