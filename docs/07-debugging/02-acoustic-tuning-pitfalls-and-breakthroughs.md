# 声浪调试踩坑与突破

## 已确认的坑

- **250 Hz 以下激进低切**：会直接削掉 40–150 Hz exhaust/body，导致塑料感。DC blocking 应只处理真正 DC/超低频漂移。
- **低转速关闭燃烧、靠 ring/sine 冒充 idle**：短期好听，动态与车型身份会崩。
- **固定 5.6/8.4 kHz 等人工纯音**：容易产生电子蜂鸣；身份应由 shaft/order/sideband/path 共同产生。
- **per-scene peak normalization**：所有场景都“响”，但 idle/WOT 相对能量被洗掉。
- **comparator 前 master gain / peak clamp**：可能制造假的 reference-distance 改善。
- **第二套 renderer**：实验代码若不回收主链，会让不同车型无法进入同一 C++/Android runtime。
- **公网音频直接叫 calibrated**：视频 R3 有 AGC、麦克风、改装状态和同步状态未知，只能 diagnostic/Human A/B。
- **无 provenance 的 IR**：即使上游代码是 MIT，也不能自动推断所有录音资产可产品分发。

## 本轮突破

- blowdown/event-domain 方向经 A/B 试听被用户判断“已经比较相像”；
- runner/path delay + transfer response 能显著减少纯 synthesizer 感；
- 同屏 A/B 能快速暴露 body、induction、shift、afterfire 的差异；
- Stage AE 将成功方法统一回 PersistentEventDomainEngine，并增加 package-wide gain 与 governed IR。
