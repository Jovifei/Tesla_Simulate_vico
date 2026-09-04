# Tesla Simulate Vico

## 当前项目方向（2026-09-04）

`Tesla Simulate Vico` 当前处于**声音算法真实性 + 车内 App 实时播放**阶段。

当前产品主线不是 ESP32。仓库里虽然保留了早期 ESP32-S3 固件、CAN/BLE/SD/WiFi/OTA/I2S 等资产，但这些内容现在属于**历史资产 / Future Deferred**，不作为当前 blocker、验收门或实施优先级。

### 项目长期记忆 / 证据规则

后续 Agent 不应重新依赖超长聊天恢复上下文。优先阅读：

- [项目长期记忆](docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md)
- [研究论文/开源项目/方法吸收历史](docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md)

用户明确指定：`S12_Handoff_Package_2026-09-03` 作为约 **90% 主证据**，旧聊天/此前总结约 **10% 补充证据**；SHA/PR/CI 等会变化的事实始终以当前 GitHub 远端为准。

当前目标是做一个放在车内运行的 App：

```text
App 获得车辆速度 speed
+ App 获得/计算车辆加速度 acceleration
                ↓
        VehicleState / VirtualEngineState
                ├─ virtual RPM
                ├─ virtual load / throttle proxy
                ├─ virtual gear / shift
                ├─ lift / overrun
                └─ transient state
                ↓
        用户选择 Vehicle Profile
       Hellcat / Ferrari / RX-7 / ...
                ↓
          S12 实时声浪算法
                ↓
             App 播放
```

当前最小实时输入是 **speed + acceleration**。RPM、load、gear、shift 等可以由 App 内部虚拟发动机状态模型推导。未来如果加入 CAN/OBD 或其他车辆接口，它们只是更高精度的 `VehicleState` input adapter，不是当前算法阶段必须先完成的前置条件。

## 当前项目状态

| 范围 | 状态 | 说明 |
|---|---|---|
| S12 声音架构 | Verified in software | Stage V→AC persistent source / comparator / Track-P guard / CI 已建立 |
| Hellcat AA-C3 | Engineering candidate | 自动指标改善，尚未 Human accepted |
| PR #5 hardening | Merged | exact-head run `33703659821` SUCCESS；current `main=82c7cb77...` |
| Stage-AC AC8 | Pending | post-merge pre-human smoke/receipt 尚需闭合 |
| V3 blind audition | Package verified | 等待 Jovi 试听 |
| R1 | Missing | 不得称 OEM calibration / Profile Freeze |
| Vehicle profile architecture | Partially ready | Hellcat 先闭环，Ferrari/RX-7 后续迁移 |
| AudioParameterPackage | Not started | Human Engineering Profile 后冻结合同 |
| Portable C++ / Android realtime | Not started | 当前 App 产品化主路线 |
| App speed/acceleration state adapter | Not started | 当前产品化必做 |
| App vehicle selector / realtime playback | Not started | 当前产品化必做 |
| ESP32 simplified runtime | Deferred | 后期可选，不是当前 blocker |

## 当前最近关卡

```text
Stage-AC post-merge AC8 closeout
→ WAITING_FOR_JOVI_AUDITION
→ Jovi Hellcat V3 blind audition
→ feedback SHA + blind binding
→ accept AA-C3 OR ONE source-causal Round2
→ Hellcat Engineering Profile
```

V3 package：

`E:\Tesla_speed\review_packages\s12-stage-aa-hellcat-quality-v3`

manifest SHA-256：

`b1ea99d36179229ff7d31f30f4790b6b84d8af587c14d44398e8e595f5f0964f`

## Human PASS 后的当前产品化路线

```text
Hellcat Engineering Profile
→ Ferrari 458 / RX-7 profile migration
→ AudioParameterPackage
→ Golden VehicleState / Golden PCM
→ portable C++ realtime core
→ Python ↔ C++ equivalence
→ Android App realtime engine
→ speed/acceleration input adapter
→ virtual RPM/load/gear model
→ vehicle profile selector
→ realtime audio playback
→ 车内 CPU / memory / latency / underrun / lifecycle 验收
```

App 是当前产品载体，不是临时测试工具。

## 当前声音系统心智模型

```text
speed + acceleration
        ↓
VirtualEngineState
        ↓
PersistentEventDomainEngine
  ├─ crank / phase
  ├─ combustion events
  ├─ exhaust/path/bank/collector
  ├─ forced induction
  ├─ mechanical texture
  ├─ shift/lift/transients
  └─ state-gated afterfire
        ↓
PressureAudioChain
        ↓
Frozen PTR / Radiation boundary
        ↓
Realtime PCM
        ↓
App audio output
```

## 当前硬规则

- 反馈前不修改 AA-C3、不提前揭盲；
- Round2 只允许一次、最多 3 个 source-causal hypotheses；
- 禁止 whole-mix / master / broad pre-PTR gain 修复；
- CI green ≠ Human PASS；
- Human PASS ≠ R1/OEM calibration；
- Track-P / PTR / Radiation 不因听感偏好随意修改；
- 当前不把 ESP32 工作加入主计划或阻塞 App/声音算法；
- 不要求 App 当前必须先接 Tesla CAN 才能运行。

## 文档入口

- [项目长期记忆](docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md)
- [研究来源与方法吸收历史](docs/knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md)
- [当前 App-first 产品方向](docs/04-planning/03-current-app-product-direction.md)
- [当前系统架构](docs/01-architecture/01-project-system-architecture.md)
- [项目总路线图](docs/04-planning/02-project-master-roadmap.md)
- [项目整体状态](docs/08-reports/10-project-status-20260904.md)
- [项目总 Backlog](docs/09-backlog/02-project-master-backlog.md)
- [S12 Stage AA Hellcat 报告](docs/08-reports/09-s12-stage-aa-acoustic-quality-closure.md)

## ESP32 说明

仓库中的 ESP32 代码和旧固件文档不删除，因为它们是已有工程资产。但当前统一状态是：

`ESP32 = DEFERRED_FUTURE_OPTION`

只有 App 版本的声音真实性、实时性和车内体验稳定后，才重新评估是否需要做嵌入式简化版。