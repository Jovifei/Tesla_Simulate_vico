# Stage AE 当前交接 — 2026-09-05

## Why

Stage AD 的四车 A/B 实验说明 blowdown/event + runner/path + transfer response 的方向听感有效，但实现一度分叉成第二套 `EngineAcoustics` renderer，并引入 per-scene normalize、comparator-side gain 和未治理 IR。

Stage AE 的任务是把**有效经验收回唯一 S12 主链**。

## Current architecture

```text
VehicleState
→ PersistentEventDomainEngine
→ event / fractional path / waveguide / collector
→ optional governed IR
→ Frozen PTR/Radiation
→ RAW comparator PCM
→ one package-wide MONITOR attenuation
→ Human A/B
```

`EngineAcoustics = TEACHER_DIAGNOSTIC_ONLY`。

## New reusable capabilities

- Hellcat/Ferrari/LFA/GTR 使用同一 config schema + renderer；
- LFA/GTR 不再依赖独立硬编码 renderer；
- IR 必须有 SHA/rights/source manifest；
- Python partitioned convolution 为未来 C++ Golden equivalence reference；
- 四车共享 `body → path → induction → afterfire` diagnostic family fit；
- 负反馈 comparator 不接 monitor/master gain；
- audition 一车只使用一个 attenuation-only package gain；
- standalone A/B 页面不依赖公网 CSS/JS。

## Open source absorbed

- FFTConvolver `non-uniform@f2cdeb...`：partitioned convolution architecture，MIT；
- engine-sim-unity-audio `main@77080ca...`：整包 gain、manifest/pin/NOTICE discipline，MIT；
- Oboe `main@2a45aa2...`：未来 Android low-latency interface，Apache-2.0；
- BitResonant EV sonification：telemetry interpolation 方法论，CC BY-NC-SA，因此 method-only；
- DiffMoog/DDSP：未来 warm-start proposal，不替代 S12 truth。

## Local AI entry

唯一执行入口：

`docs/05-execution/03-stage-ae-local-ai-handoff.md`

本地 AI 的终点：生成四车 WAV + A/B 页面，然后 STOP 等待 Jovi；不继续做 App/ESP32，不自动 Profile Freeze。
