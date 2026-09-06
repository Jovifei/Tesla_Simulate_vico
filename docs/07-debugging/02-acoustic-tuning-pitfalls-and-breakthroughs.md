# 声浪调试踩坑记录与本轮突破

更新：2026-09-06

## 1. 最大踩坑：为了“架构统一”丢掉已经好听的声音

Stage AE 曾把用户已经试听确认较真实的 `EngineAcoustics` 降级为 teacher，并切回另一 renderer。自动测试很好，但本地实际试听“很差、完全不真实”。

长期规则：**Human A/B 是声学方向门。架构重构不得在没有等价听感证据时替换已验证更好的 renderer。**

因此 Stage AF 直接从 `main=f81d3a3...` 建立，保留原 `EngineAcoustics.render_track()`。

## 2. 旧 closed-loop 的“假接入”

仓库已有 `stage_ad/closed_loop.py`，但它调用 `hellcat_search_parameters()` 和 Stage-X candidate renderer，并没有控制实际好听的 Engine-Sim-inspired renderer。

修复：Stage AF 把 optimizer 包在 `EngineAcoustics` 外层，最终出声函数不变。

## 3. 不要用 raw waveform 对公开视频拟合

公开视频存在时移、mic、AGC、codec、风噪和空间响应差异。sample MSE 会把参数推向错误方向。应优先拟合稳定的频谱比例、阶次/频带、包络和 transient 特征，再由人耳确认。

## 4. 不要把“距离下降”当成真实性通过

R3 只是 diagnostic target。数值更小只说明选定特征更接近；它可能仍然难听。每轮最终必须回到现有 A/B 工作台听。

## 5. 不要一次放开过多参数

当前听感已经达到可用起点，最危险的是大范围搜索把它搜坏。Stage AF 参数范围故意只围绕人工 baseline ±约 10–30%。family 顺序：body → path → induction → afterfire。

## 6. 随机噪声会破坏优化器

原 renderer 部分噪声使用 global `np.random`。相同参数如果每次声音不同，optimizer 会把随机差异误认为参数效果。Stage AF adapter 在每次 render 前固定 seed，并在 render 后恢复调用方 RNG 状态，不改变原代码默认行为。

## 7. IR 路径目前是工程债

当前好声音依赖本机硬编码 Engine-Sim sound-library 路径。它是重要听感来源，但也是 portability / rights 风险。短期不删，因为会破坏好声音；后续要把它变为：IR manifest + SHA + provenance + configurable root。

## 8. 工作台不要重写

现有 8080/8088/8089/8090/8091 服务、双轨 A/B、进度热切换、FFT/波形已经满足试听需求。之前重复新写 dashboard 没有增加声学真实性，还增加维护成本。

Stage AF 只复用它。

## 9. 巨型生成物不要进 Git

旧 Hellcat package 同时提交约 10 个 WAV、reference/web_audio 和 34.5 MB Base64 HTML；四车重复后严重影响 Cograph/clone/index。

正确方式：生成到 `E:\Tesla_speed\review_packages`，Git 只保存生成脚本和轻量入口。

## 10. 当前真正的突破

用户明确判断 `main=f81d3a3...` 的 Engine-Sim-inspired 四车输出已经约 70–80% 相似。说明下列组合值得长期继承：

**blowdown event + firing geometry + bank/path delays + derivative/airflow + IR transfer + vehicle induction/transients + Human A/B**。

下一阶段应该优化这些因果旋钮，不再回到纯 sine/EQ 堆叠。
