# S12 Stage R2 有限真实声浪差异报告

状态：`R2_LIMITED_COMPARISON_COMPLETE`

本报告只表示已授权 R2 参考与本地候选在未增益分析信号上的相对数字域差异。没有同步 RPM/state，因此不输出阶次硬门、不输出 OEM 绝对门限，也不生成参数建议。

车型：`hellcat`；工况：`launch`。

## 差异结果

```json
{
  "band_residual": {
    "1000_4000": {
      "candidate_share": 0.013997393763085876,
      "delta": -0.04050268923358238,
      "reference_share": 0.05450008299666825,
      "warning": null
    },
    "120_250": {
      "candidate_share": 0.25071510806777303,
      "delta": -0.1652860029477961,
      "reference_share": 0.41600111101556914,
      "warning": null
    },
    "20_60": {
      "candidate_share": 0.051286473024059615,
      "delta": 0.0416591315112527,
      "reference_share": 0.009627341512806913,
      "warning": null
    },
    "250_400": {
      "candidate_share": 0.14361470703342666,
      "delta": -0.06356188303487267,
      "reference_share": 0.20717659006829933,
      "warning": null
    },
    "4000_5500": {
      "candidate_share": 0.006718145539871198,
      "delta": 0.004743650594182825,
      "reference_share": 0.0019744949456883738,
      "warning": null
    },
    "400_1000": {
      "candidate_share": 0.24399825648415102,
      "delta": 0.13958997606186563,
      "reference_share": 0.1044082804222854,
      "warning": null
    },
    "5500_12000": {
      "candidate_share": 0.008827633101505843,
      "delta": 0.00615900433858977,
      "reference_share": 0.0026686287629160733,
      "warning": "upstream perceptual compensation; outside validated radiation band; not physical radiation validation"
    },
    "60_120": {
      "candidate_share": 0.2788933906997339,
      "delta": 0.07552929340612996,
      "reference_share": 0.20336409729360394,
      "warning": null
    }
  },
  "human_score": null,
  "loudness_residual": {
    "delta_db": 0.45302822727763115
  },
  "order_residual": {
    "order_continuity": "not_evaluated_without_rpm_trace",
    "ridge_amplitude_error": null,
    "ridge_frequency_error_hz": null,
    "status": "not_evaluated_without_rpm_trace"
  },
  "psychoacoustic_residual": {
    "fluctuation_proxy_delta": -0.003276788076522097,
    "roughness_proxy_delta": 0.0046716290314620015,
    "sharpness_proxy_delta": 37.60439982059165,
    "tonality_proxy_delta": -0.23080611459562306
  },
  "reference_uncertainty": "R2/no synchronized RPM-state; relative only",
  "scenario": "launch",
  "spectral_residual": {
    "centroid_delta_hz": 37.60439982059165,
    "contrast_delta_db": -17.71646747817244,
    "harmonic_percussive_proxy": {
      "candidate_harmonic_share": 0.0,
      "percussive_proxy": -1.5247847759785085,
      "reference_harmonic_share": 0.0
    },
    "log_distance": 0.503287490395887,
    "rolloff_delta_hz": 65.91952167240515,
    "tristimulus_delta": [
      0.00021710339011771218,
      -0.00022884139278429904,
      1.1738002666442327e-05
    ]
  },
  "transient_residual": {
    "candidate": {
      "attack_s": 3.697278911564626,
      "decay_to_10pct_s": 0.0009523809523809524,
      "impact_peak": 0.8021097519588841
    },
    "state_window_required_for_shift_or_afterfire": true
  },
  "vehicle_id": "hellcat"
}
```

试听必须使用独立的响度匹配副本；本结果中的分析信号没有使用响度匹配副本。R2 结果仍需 Jovi 中文听审后才能进入任何后续判断。
