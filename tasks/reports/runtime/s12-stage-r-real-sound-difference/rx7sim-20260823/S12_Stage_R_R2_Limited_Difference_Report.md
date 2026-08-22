# S12 Stage R2 有限真实声浪差异报告

状态：`R2_LIMITED_COMPARISON_COMPLETE`

本报告只表示已授权 R2 参考与本地候选在未增益分析信号上的相对数字域差异。没有同步 RPM/state，因此不输出阶次硬门、不输出 OEM 绝对门限，也不生成参数建议。

车型：`rx7_fd`；工况：`full_pull`。

## 差异结果

```json
{
  "band_residual": {
    "1000_4000": {
      "candidate_share": 0.0004570783988811756,
      "delta": -0.019958371653463123,
      "reference_share": 0.020415450052344297,
      "warning": null
    },
    "120_250": {
      "candidate_share": 0.8861440597648235,
      "delta": 0.5587988672797386,
      "reference_share": 0.32734519248508487,
      "warning": null
    },
    "20_60": {
      "candidate_share": 0.002205589251725714,
      "delta": -0.09220058769179239,
      "reference_share": 0.0944061769435181,
      "warning": null
    },
    "250_400": {
      "candidate_share": 0.05089335496320693,
      "delta": -0.025636601418010774,
      "reference_share": 0.0765299563812177,
      "warning": null
    },
    "4000_5500": {
      "candidate_share": 3.7946256672281464e-05,
      "delta": -0.001034562499742164,
      "reference_share": 0.0010725087564144454,
      "warning": null
    },
    "400_1000": {
      "candidate_share": 0.038145662807844885,
      "delta": -0.09504354228349553,
      "reference_share": 0.1331892050913404,
      "warning": null
    },
    "5500_12000": {
      "candidate_share": 6.80782416662496e-05,
      "delta": -0.00139948965150993,
      "reference_share": 0.0014675678931761796,
      "warning": "upstream perceptual compensation; outside validated radiation band; not physical radiation validation"
    },
    "60_120": {
      "candidate_share": 0.021895065827015156,
      "delta": -0.3217166287633229,
      "reference_share": 0.3436116945903381,
      "warning": null
    }
  },
  "human_score": null,
  "loudness_residual": {
    "delta_db": -0.14037828700988975
  },
  "order_residual": {
    "order_continuity": "not_evaluated_without_rpm_trace",
    "ridge_amplitude_error": null,
    "ridge_frequency_error_hz": null,
    "status": "not_evaluated_without_rpm_trace"
  },
  "psychoacoustic_residual": {
    "fluctuation_proxy_delta": 0.06602998819687309,
    "roughness_proxy_delta": -0.00981389785729593,
    "sharpness_proxy_delta": -31.54220504203252,
    "tonality_proxy_delta": -4.478483863592781
  },
  "reference_uncertainty": "R2/no synchronized RPM-state; relative only",
  "scenario": "full_pull",
  "spectral_residual": {
    "centroid_delta_hz": -31.54220504203252,
    "contrast_delta_db": 15.80909782031798,
    "harmonic_percussive_proxy": {
      "candidate_harmonic_share": 0.0,
      "percussive_proxy": 0.3854614747507479,
      "reference_harmonic_share": 0.0
    },
    "log_distance": 0.6624996445293366,
    "rolloff_delta_hz": -173.75884160772264,
    "tristimulus_delta": [
      0.0011543975439848309,
      -0.0010433540664021184,
      -0.00011104347758363616
    ]
  },
  "transient_residual": {
    "candidate": {
      "attack_s": 6.213354166666667,
      "decay_to_10pct_s": 0.0013125,
      "impact_peak": 0.7756311148527264
    },
    "state_window_required_for_shift_or_afterfire": true
  },
  "vehicle_id": "rx7_fd"
}
```

试听必须使用独立的响度匹配副本；本结果中的分析信号没有使用响度匹配副本。R2 结果仍需 Jovi 中文听审后才能进入任何后续判断。
