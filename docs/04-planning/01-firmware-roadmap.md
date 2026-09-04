# Tesla Simulate Vico ESP32 固件子路线图（Deferred / Historical）

> `DEFERRED_FUTURE_OPTION`。当前主线：S12 声音真实性 → Human Gate → Android App。

历史 ESP32 代码资产保留，但当前不执行 board bring-up、BLE/WiFi/MQTT/OTA、IRAM、CAN analyser、advanced sound port 或 vehicle pilot。

只有 App 已 Human accepted、speed+acceleration 多车型 realtime 稳定、AudioParameterPackage/C++ 稳定，且用户明确重新开启独立硬件需求时才恢复。

当前权威文档：
- `03-current-app-product-direction.md`
- `02-project-master-roadmap.md`
- `../knowledge/obsidian/S12/Engine-Audio-Ecosystem/Project-Long-Term-Memory.md`
