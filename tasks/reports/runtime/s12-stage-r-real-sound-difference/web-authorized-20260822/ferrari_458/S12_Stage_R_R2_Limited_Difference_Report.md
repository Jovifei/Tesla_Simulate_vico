# S12 Stage R2 有限真实声浪差异报告

状态：`R2_LIMITED_COMPARISON_COMPLETE`

本报告只表示已授权 R2 参考与本地候选在未增益分析信号上的相对数字域差异。没有同步 RPM/state，因此不输出阶次硬门、不输出 OEM 绝对门限，也不生成参数建议。

车型：`ferrari_458`；工况：`acceleration`。

## 差异结果

```json
{
  "band_residual": {
    "1000_4000": {
      "candidate_share": 0.17642499547368812,
      "delta": 0.013782581954993878,
      "reference_share": 0.16264241351869424,
      "warning": null
    },
    "120_250": {
      "candidate_share": 0.10849595268451978,
      "delta": -0.018346565290071226,
      "reference_share": 0.126842517974591,
      "warning": null
    },
    "20_60": {
      "candidate_share": 0.000288305382619016,
      "delta": -0.0006457517860815333,
      "reference_share": 0.0009340571687005493,
      "warning": null
    },
    "250_400": {
      "candidate_share": 0.14767841286918854,
      "delta": -0.057391620227961626,
      "reference_share": 0.20507003309715016,
      "warning": null
    },
    "4000_5500": {
      "candidate_share": 0.00021972283624343436,
      "delta": -0.008564170563324256,
      "reference_share": 0.00878389339956769,
      "warning": null
    },
    "400_1000": {
      "candidate_share": 0.5662510806219305,
      "delta": 0.07530977868627187,
      "reference_share": 0.49094130193565866,
      "warning": null
    },
    "5500_12000": {
      "candidate_share": 4.097490397728146e-05,
      "delta": -0.003020053350931284,
      "reference_share": 0.0030610282549085655,
      "warning": "upstream perceptual compensation; outside validated radiation band; not physical radiation validation"
    },
    "60_120": {
      "candidate_share": 0.00045090178252843666,
      "delta": -0.001187876890330065,
      "reference_share": 0.0016387786728585016,
      "warning": null
    }
  },
  "human_score": null,
  "loudness_residual": {
    "delta_db": 2.700104499766379
  },
  "order_residual": {
    "order_continuity": "not_evaluated_without_rpm_trace",
    "ridge_amplitude_error": null,
    "ridge_frequency_error_hz": null,
    "status": "not_evaluated_without_rpm_trace"
  },
  "psychoacoustic_residual": {
    "fluctuation_proxy_delta": -0.0077395186543948655,
    "roughness_proxy_delta": 0.0027260103484704687,
    "sharpness_proxy_delta": -18.85342910855195,
    "tonality_proxy_delta": 1.258820656173988
  },
  "reference_uncertainty": "R2/no synchronized RPM-state; relative only",
  "scenario": "acceleration",
  "spectral_residual": {
    "centroid_delta_hz": -18.85342910855195,
    "contrast_delta_db": -25.33167156254123,
    "harmonic_percussive_proxy": {
      "candidate_harmonic_share": 0.0,
      "percussive_proxy": -2.3358397008215075,
      "reference_harmonic_share": 0.0
    },
    "log_distance": 0.5747750117910693,
    "rolloff_delta_hz": -162.2388227568416,
    "tristimulus_delta": [
      0.0008234991142910264,
      -0.0008162768724649753,
      -7.222241826090418e-06
    ]
  },
  "transient_residual": {
    "candidate": {
      "attack_s": 6.2470068027210885,
      "decay_to_10pct_s": 0.00015873015873015873,
      "impact_peak": 0.8527857824103802
    },
    "state_window_required_for_shift_or_afterfire": true
  },
  "vehicle_id": "ferrari_458"
}
```

试听必须使用独立的响度匹配副本；本结果中的分析信号没有使用响度匹配副本。R2 结果仍需 Jovi 中文听审后才能进入任何后续判断。
