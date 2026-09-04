# Tesla Simulate Vico Documentation

当前文档主入口服务于 **S12 声音真实性 + 车内 Android App 实时声浪**。

项目长期记忆优先读：

1. `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`
2. `knowledge/obsidian/S12/Engine-Audio-Ecosystem/Research-Sources-And-Adoption-History.md`
3. `04-planning/03-current-app-product-direction.md`
4. `01-architecture/01-project-system-architecture.md`
5. `04-planning/02-project-master-roadmap.md`
6. `08-reports/10-project-status-20260904.md`
7. `09-backlog/02-project-master-backlog.md`

证据规则：handoff package ≈90%，旧聊天/此前总结 ≈10%；动态 GitHub 事实现场复核；用户当前明确决策优先。

当前产品：

```text
Android App
→ speed + acceleration
→ VirtualEngineState
→ vehicle profile
→ S12 realtime sound
→ playback
```

当前 nearest gate：`AC8 → Jovi V3 audition → AA-C3 accept/ONE Round2 → Engineering Profile → App productization`。

边界：

```text
R1 = MISSING
HUMAN_PASS = false
ESP32 = DEFERRED_FUTURE_OPTION
```

历史 ESP32 文档仅作 future reference，不覆盖当前 App-first 主线。