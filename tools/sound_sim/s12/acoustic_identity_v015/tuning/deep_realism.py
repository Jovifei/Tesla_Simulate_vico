# tools/sound_sim/s12/acoustic_identity_v015/tuning/deep_realism.py
"""逐状态 deep realism 注入（Track S only，ratio-invariant）。

ratio-invariant 契约
--------------------
本模块对 pre-PTR 的 `pressure` 与**全部** stems 施加同一条时变增益包络
g(t)：同一时刻所有 stem 乘同一个标量。因此任意两个 stem 之间、以及任意
两个频段之间的能量比值在每一时刻都保持不变，`integer_order_concentration`、
turbo/turbine-vs-rotary 频段比值等身份指标不会被破坏。

由此得到一个必须明确记录的**数学结论**：`band_energy_shares` 以总能量归一，
故其对幅度缩放严格不变。在单一状态的分析窗内，本模块的注入
**无法**改变 band shares（实测 delta ~1e-16）。它能改变的只有
(a) 状态段之间的相对响度配比，以及 (b) 整体电平。任何真正改变某一状态
频段占比的操作都属于"重分配频段能量 / 对单个 stem 单独加权"，是被
ratio-invariant 红线禁止的。

增益包络经过短时平滑，避免状态切换处的阶跃产生咔哒声与宽带频谱溅射
（后者本身就会污染身份指标）。

本模块与车型无关：一切车型相关参数都从 manifest 读取，供 Ferrari 458 /
Hellcat / RX-7 FD 三个锚点车复用。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import numpy as np

from ..contracts import SourceRender, VehicleStateTrace

_V015 = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _V015 / "targets" / "deep_realism_tuning_manifest.json"

STATE_KEYS = (
    "idle",
    "steady_cruise",
    "acceleration",
    "full_pull",
    "lift_afterfire",
    "idle_return",
)

# 每个状态的代表性稳态工况点 (rpm, load, throttle)。
# `classify_state` 对每一项都必须回判出同名状态；`test_s12_deep_realism_anchors.py`
# 的 ClassifyStateTests 守这条不变量。目标重建（reference_reconstruction）与逐状态
# 验收测试共用此表，避免工况点在项目里分叉。
STATE_OPERATING_POINTS = {
    "idle": (1100.0, 0.12, 0.12),
    "idle_return": (1800.0, 0.12, 0.12),
    "steady_cruise": (3600.0, 0.42, 0.45),
    "acceleration": (4200.0, 0.80, 0.88),
    "full_pull": (7200.0, 0.94, 0.96),
    "lift_afterfire": (6000.0, 0.10, 0.05),
}

# 状态切换处的增益平滑时长；足够长以把 level_scale 阶跃摊成听不见的斜坡。
_GAIN_SMOOTHING_S = 0.05


def load_tuning_manifest(path: Path | None = None) -> dict:
    """读取 deep realism 调音 manifest。"""
    return json.loads(Path(path or _MANIFEST_PATH).read_text(encoding="utf-8"))


def classify_state(rpm: np.ndarray, load: np.ndarray, throttle: np.ndarray) -> np.ndarray:
    """逐样本状态分类，返回与 rpm 等长、元素取自 STATE_KEYS 的 object 数组。

    `lift_afterfire` 采用**持续 overrun** 判据（高转速 + 收油），而非仅看
    油门导数的瞬时跌落：真实的 lift-off / 爆鸣是一段拖曳工况，只有一个
    采样点的导数事件无法用于逐状态频谱度量。瞬时跌落仍保留为附加触发。
    """
    rpm = np.asarray(rpm, dtype=np.float64)
    load = np.asarray(load, dtype=np.float64)
    throttle = np.asarray(throttle, dtype=np.float64)
    if not (rpm.shape == load.shape == throttle.shape):
        raise ValueError("rpm, load and throttle must have equal shapes")

    out = np.array(["steady_cruise"] * rpm.size, dtype=object)
    out[rpm < 1300.0] = "idle"
    out[(rpm >= 1300.0) & (rpm < 2400.0) & (throttle < 0.30)] = "idle_return"
    out[(rpm >= 2400.0) & (rpm < 5000.0) & (throttle >= 0.30) & (throttle < 0.80)] = "steady_cruise"
    out[(rpm >= 2400.0) & (rpm < 5000.0) & (throttle >= 0.80)] = "acceleration"
    out[rpm >= 5000.0] = "full_pull"
    # lift-afterfire：高转速下的收油拖曳（持续 overrun），或瞬时骤降油门。
    drop = np.r_[False, np.diff(throttle) < -0.10]
    out[(rpm >= 4000.0) & ((throttle < 0.15) | drop)] = "lift_afterfire"
    return out


def apply_deep_realism(
    render: SourceRender,
    vehicle_id: str,
    trace: VehicleStateTrace,
    manifest: dict | None = None,
    sample_rate_hz: int = 48000,
) -> SourceRender:
    """在源层注入 per-state 电平配比（ratio-invariant）。

    返回一个新的 `SourceRender`；`pressure` 与每个 stem 都乘以同一条增益
    包络。原 render 不被修改。
    """
    manifest = manifest or load_tuning_manifest()
    try:
        vehicle = manifest["vehicles"][vehicle_id]
    except KeyError as error:
        raise KeyError(f"deep realism manifest has no vehicle {vehicle_id!r}") from error
    states: Mapping[str, Mapping[str, object]] = vehicle["states"]

    count = int(np.asarray(render.pressure).shape[0])
    labels = _labels_on_render_grid(trace, count, sample_rate_hz)

    uniform = float(vehicle.get("uniform_ratio_scale", 1.0))
    per_state = np.empty(count, dtype=np.float64)
    for state in np.unique(labels):
        if state not in states:
            raise KeyError(f"deep realism manifest for {vehicle_id!r} has no state {state!r}")
        per_state[labels == state] = float(states[state]["level_scale"])

    gain = _smooth(uniform * per_state, int(round(_GAIN_SMOOTHING_S * sample_rate_hz)))
    envelope = gain[:, np.newaxis]

    pressure = np.asarray(render.pressure, dtype=np.float64) * envelope
    stems = {name: np.asarray(stem, dtype=np.float64) * envelope for name, stem in render.stems.items()}

    unique, counts = np.unique(labels, return_counts=True)
    diagnostics = dict(render.diagnostics)
    diagnostics.update(
        {
            "deep_realism_applied": True,
            "deep_realism_vehicle_id": vehicle_id,
            "deep_realism_uniform_ratio_scale": uniform,
            "deep_realism_state_fractions": {
                str(state): float(n) / float(count) for state, n in zip(unique, counts)
            },
            "deep_realism_gain_min": float(gain.min()),
            "deep_realism_gain_max": float(gain.max()),
            "deep_realism_invariant": "single time-varying scalar applied to pressure and every stem",
        }
    )
    return SourceRender(pressure=pressure, stems=stems, diagnostics=diagnostics).validate()


def _labels_on_render_grid(trace: VehicleStateTrace, count: int, sample_rate_hz: int) -> np.ndarray:
    """把 trace 的状态分类重采样到渲染的样本栅格上。

    trace 的时间分辨率不一定等于渲染采样率，直接把 trace 长度的数组乘到
    `[N, 2]` 的 pressure 上会广播失败（brief 骨架的隐患）。这里按渲染器
    相同的方式重建时间栅格并插值。
    """
    time_s = trace.time_s[0] + np.arange(count, dtype=np.float64) / sample_rate_hz
    rpm = np.interp(time_s, trace.time_s, trace.rpm)
    load = np.interp(time_s, trace.time_s, trace.load)
    throttle = np.interp(time_s, trace.time_s, trace.throttle)
    return classify_state(rpm, load, throttle)


def _smooth(values: np.ndarray, window: int) -> np.ndarray:
    """边缘保持的移动平均；把 per-state 阶跃摊成连续斜坡。"""
    if window <= 1 or values.size <= 1:
        return values
    window = min(window, values.size)
    pad = window // 2
    padded = np.pad(values, (pad, window - 1 - pad), mode="edge")
    kernel = np.full(window, 1.0 / window)
    return np.convolve(padded, kernel, mode="valid")
