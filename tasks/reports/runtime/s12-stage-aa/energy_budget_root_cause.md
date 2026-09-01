# S12 Stage AA 能量账本与根因

- main head: `209378bcb9a0c1a352ffd56ca1c765ecce01f81d`
- scope: `Hellcat synthetic source-domain layer taps; OUTPUT_SCALE applied uniformly for published-level comparison`
- 本账本只记录诊断 layer taps；未修改 master gain、PTR、Radiation 或 Track-P。

## 最大逐层变化（dB RMS）

| Scene | Layer | Gain vs previous | Ratio |
| --- | --- | ---: | ---: |
| full_load | transients → dp_dc | -25.476 dB | 0.0532324 |
| lift | transients → dp_dc | -24.268 dB | 0.0611807 |
| afterfire | transients → dp_dc | -24.268 dB | 0.0611807 |
| gear_shift | transients → dp_dc | -24.162 dB | 0.0619276 |
| idle_return | pre_ptr → post_ptr_raw | -22.733 dB | 0.0730032 |
| tip_in | pre_ptr → post_ptr_raw | -22.450 dB | 0.0754242 |
| steady_2000 | pre_ptr → post_ptr_raw | -22.381 dB | 0.0760201 |
| idle_return | transients → dp_dc | -22.345 dB | 0.0763368 |
| lift | pre_ptr → post_ptr_raw | -22.231 dB | 0.0773516 |
| afterfire | pre_ptr → post_ptr_raw | -22.231 dB | 0.0773516 |
| hot_idle | pre_ptr → post_ptr_raw | -21.915 dB | 0.0802151 |
| steady_3000 | pre_ptr → post_ptr_raw | -21.891 dB | 0.0804387 |

## 结论

最严重的逐层能量变化出现在 `full_load` 的 `dp_dc`，相对前一音频层为 `-25.476 dB`。这只是定位线索，不等于可直接调参。
`full_load` 中 pre-transients 的 DC 均值为 `0.187067`、AC RMS 为 `0.094866`；经过 dP/DC 后 DC 均值为 `0.001509`、RMS 为 `0.009289`。因此主要异常是绝对压力基线占主导、dP/DC 高通后只剩小幅波动，而非单纯的播放增益问题。
逐层账本必须先用于确认 event/path/collector/waveguide/transient/dP/pre-PTR/post-PTR/monitor 哪一层承担主要损失；任何候选修复都必须回到该层并同时验证低频 body、动态范围、click、afterfire 和 blower guard。
当前结论仍为诊断性：没有使用全局增益补偿，也没有 R1 同步参考，不能从能量恢复本身推出声学质量提升。
