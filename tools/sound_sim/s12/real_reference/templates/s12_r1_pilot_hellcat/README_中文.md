# Hellcat R1 试点模板

把真实交付目录放在：

```text
E:\Claude_allow\Download\s12-r1-pilot\<recording_id>\
```

建议目录：

```text
<recording_id>/
├─ raw/raw_audio.wav 或 raw_audio.flac
├─ state/rpm.csv
├─ state/load_throttle.csv
├─ state/gear_shift.csv
├─ spec.json
├─ rights.json 或 rights.pdf
└─ sha256.txt
```

当前模板是空 fixture，不代表真实数据，也不包含任何猜测的 RPM、负载、油门或挡位。请复制字段后填写真实值，不要把 `REPLACE_WITH_*` 留在交付包中。

`rights.json` 必须逐项确认本地分析、派生特征、Comparator、中文人耳 A/B 和有界调音；普通商业 SFX 许可不能自动通过。`rights.pdf` 只能作为人工审查证据，若没有机器可读 scope，预检会停在 `MANUAL_REVIEW_REQUIRED`。

文件完成后运行项目的 `r1_pilot` 预检。预检通过前不会复制媒体、运行 MATLAB 阶次、生成参数或修改声源。
