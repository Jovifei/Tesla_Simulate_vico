# 连续混合渲染器设计

## 目标

在不依赖用户自采、也不修改默认声库的条件下，减少现有短循环声的固定重复、跨块相位重置、层间硬切和事件突变。公开真实录音只作为研究纹理输入，不自动升级为目标车型声源。

## 设计

- `ContinuousTextureReader` 持有唯一连续 phase；RPM 只改变 phase 增量，不改变读头位置。
- `ContinuousHybridRenderer` 将 base、纹理层和事件层相加，并用平滑包络控制动态。
- 事件使用 raised-cosine attack/release，末帧归零，避免 click。
- 输出每帧执行有限值和 `[-1,1]` 限制；长 PCM 统计采用线性扫描，不把样本展开到函数调用栈。
- 研究 harness 写出来源 SHA、输出 SHA、peak、最大跳变和 `INSUFFICIENT_EVIDENCE` 状态。

## 明确不做

- 不改 `core.mjs`、默认 bank、Android、APK、MATLAB、设备或公网；
- 不从音频推断 RPM、负载、挡位或 720° phase；
- 不将公开 Honda/Ferrari/BMW 等录音改名为 Hellcat、Ferrari 458 或其他目标车型；
- 不把研究 PCM 标为产品候选。

## 验收

聚焦测试覆盖跨块分割、RPM 改变不 seek、包络平滑、事件攻击/释放、纹理缺失和长 PCM；完整 Web 回归必须保持全绿。
