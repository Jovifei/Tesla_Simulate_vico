# S12 Stage R2 有限真实声浪差异报告

状态：`R2_LIMITED_COMPARISON_COMPLETE`

本报告只表示已授权 R2 参考与本地候选在未增益分析信号上的相对数字域差异。没有同步 RPM/state，因此不输出阶次硬门、不输出 OEM 绝对门限，也不生成参数建议。

车型：`supra_jza80`；工况：`full_pull`。

## 差异结果

```json
{
  "band_residual": {
    "1000_4000": {
      "candidate_share": 0.0012160071065793264,
      "delta": -0.05289987057088915,
      "reference_share": 0.05411587767746848,
      "warning": null
    },
    "120_250": {
      "candidate_share": 0.42863114536994035,
      "delta": -0.04453300046506087,
      "reference_share": 0.4731641458350012,
      "warning": null
    },
    "20_60": {
      "candidate_share": 0.04004472015925908,
      "delta": 0.032883922655056935,
      "reference_share": 0.0071607975042021444,
      "warning": null
    },
    "250_400": {
      "candidate_share": 0.06782232748243217,
      "delta": -0.012122778708605217,
      "reference_share": 0.07994510619103738,
      "warning": null
    },
    "4000_5500": {
      "candidate_share": 2.8927847692541473e-06,
      "delta": -0.0002036945765259334,
      "reference_share": 0.00020658736129518753,
      "warning": null
    },
    "400_1000": {
      "candidate_share": 0.0044073754247155915,
      "delta": -0.10341327328176005,
      "reference_share": 0.10782064870647563,
      "warning": null
    },
    "5500_12000": {
      "candidate_share": 2.888986101550977e-06,
      "delta": -0.0005943061593138985,
      "reference_share": 0.0005971951454154494,
      "warning": "upstream perceptual compensation; outside validated radiation band; not physical radiation validation"
    },
    "60_120": {
      "candidate_share": 0.44836716640983276,
      "delta": 0.17186983172411335,
      "reference_share": 0.2764973346857194,
      "warning": null
    }
  },
  "human_score": null,
  "loudness_residual": {
    "delta_db": -6.474682332118416
  },
  "order_residual": {
    "order_continuity": "not_evaluated_without_rpm_trace",
    "ridge_amplitude_error": null,
    "ridge_frequency_error_hz": null,
    "status": "not_evaluated_without_rpm_trace"
  },
  "psychoacoustic_residual": {
    "fluctuation_proxy_delta": -0.023648523944064814,
    "roughness_proxy_delta": -0.01305811675465429,
    "sharpness_proxy_delta": -167.1217437424749,
    "tonality_proxy_delta": 17.2101086443108
  },
  "reference_uncertainty": "R2/no synchronized RPM-state; relative only",
  "scenario": "full_pull",
  "spectral_residual": {
    "centroid_delta_hz": -167.1217437424749,
    "contrast_delta_db": -26.438546313142176,
    "harmonic_percussive_proxy": {
      "candidate_harmonic_share": 0.0,
      "percussive_proxy": 2.7987473551756796,
      "reference_harmonic_share": 0.0
    },
    "log_distance": 0.8546569494652856,
    "rolloff_delta_hz": -250.7183285444764,
    "tristimulus_delta": [
      0.0005818792771717929,
      -0.0005160795415753714,
      -6.579973559661765e-05
    ]
  },
  "transient_residual": {
    "candidate": {
      "attack_s": 3.295125,
      "decay_to_10pct_s": 0.0012291666666666666,
      "impact_peak": 0.6684351888994192
    },
    "state_window_required_for_shift_or_afterfire": true
  },
  "vehicle_id": "supra_jza80"
}
```

试听必须使用独立的响度匹配副本；本结果中的分析信号没有使用响度匹配副本。R2 结果仍需 Jovi 中文听审后才能进入任何后续判断。
