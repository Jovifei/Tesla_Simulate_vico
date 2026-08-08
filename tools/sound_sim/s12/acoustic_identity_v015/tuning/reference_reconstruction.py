# tools/sound_sim/s12/acoustic_identity_v015/tuning/reference_reconstruction.py
"""从发动机物理先验重建 per-state band 目标，并检验录音链滚降补偿是否可用。

为什么需要本模块
----------------
Task 1.2 手写的 deep-realism manifest 直接照抄参考库的 3 段录音特征
（idle / acceleration / afterfire），把 3 组数值填进 6 个状态，产生两个致命缺陷：

1. **六态塌陷成三态** —— `steady_cruise == acceleration == full_pull`，
   隐含"高频占比不随 rpm 变化"，与身份套件
   `test_ferrari_high_frequency_energy_grows_with_rpm_without_normalization`
   要求的 >=1.35 直接互斥。
2. **目标带着录音链的低频滚降** —— `ferrari_458.idle` 的 20-250 Hz 只占 0.94%，
   而 V8 怠速点火基频只有 ~73 Hz，低频不可能不占主导。

本模块给出的解法：用一个可复现、可审计的**正演物理模型**产生六态目标形状，
并把参考录音的可用性交给一个**真的会失败的检验**去判定，而不是假定它可用。

模型口径
--------
- 频率轴上的离散阶次分量 + 三个宽带项（排气脉冲/管道共振、排气流噪声、涡轮窄带），
  积分到 `acoustic_analysis/spectral_targets.py::BAND_EDGES` 的四个 band。
- 阶次定义为"每转曲轴（转子机为偏心轴）的循环数"，`f = rpm/60 * order`。
- 关键性质：阶次级数随 rpm 线性上移而 band 边界固定，因此高频占比必然随 rpm 增长。
  这条性质天然修复缺陷 1，且不依赖任何为通过断言而选的系数。

排气脉冲/管道共振项（Task 3.1 补入）
-----------------------------------
Task 3.0 的模型只有阶次级数 + 流噪声 + 涡轮窄带，缺了真实排气噪声在高负荷下
**能量占绝对多数**的那一项：排气门开启瞬间的 blowdown 压力脉冲。该脉冲宽带、
幅度随缸压（∝ 进气充量 ∝ load）上升，在排气管的基频驻波模态上被谐振放大后由
尾管开口辐射。它的缺失使模型在高负荷段把低频压得过低——`acceleration` 的
20-250 Hz 只有 5%，而 §4.2 参考录音同段是 36%，趋势系统性相反。

本项的三个参数各有独立依据，不是为拟合而设的自由度：

- `exhaust_resonance_hz`：管道基模 `f = c/(2L)`。排气气体热态声速
  `c = sqrt(gamma*R*T)`，取 gamma≈1.35、R≈287 J/(kg*K)、T≈800 K，得 c≈557 m/s
  （远高于常温 343 m/s）。L 取各车集气管到尾管口的实际管长量级。
- Q（`_EXHAUST_RESONANCE_Q`）：开口端辐射损耗 + 热气粘性损耗 + 消声器吸声共同
  限制品质因数，实测排气管道模态落在 Q≈2~4，取中值。
- 负荷指数（`_PULSE_LOAD_EXPONENT`）：缸压 ∝ 充量 ∝ load，声能 ∝ 压力^2，故
  能量 ∝ load^2。与既有流噪声项的 load^2 口径一致，不是另设的拟合指数。

注意本项**不会**把怠速低频占比拉低：load^2 在 idle（load=0.12）只有 0.0144，
脉冲项在怠速几乎不出力。怠速仍由点火基频（V8 1100 rpm 时仅 73 Hz）主导 20-250 Hz，
这正是 `test_idle_low_band_share_is_physically_plausible` 守的物理事实。参考录音
idle 段 20-250 Hz 只占 0.94%、1-4 kHz 却占 46.7%，是消费级录音的高通 + AGC 抬噪
产物，不是发动机的频谱——详见下节的自洽性检验。

录音链补偿的自洽性检验
----------------------
brief 建议"用 idle 段拟合 (fc, n)，再套用到同车所有段"，其依据是"同一条录音
=> 同一条录音链"。本模块**实现了这个方法，同时检验它**：`fit_recording_chain`
在 idle 段上拟合（in-sample），再在该车全部参考段上评估同一组参数
（out-of-sample）。若 out-of-sample 残差相对 in-sample 显著恶化，说明该录音链
不能用单一 LTI 高通描述（消费级录音的降噪/AGC 是随电平变化的非线性处理），
此时补偿结果不可信，目标退回纯物理推导。判据是预先声明的常量，见
`_CHAIN_GENERALISATION_RATIO_MAX` / `_CHAIN_RESIDUAL_MAX`。

所有先验都是**估计值**，不是实测标定。项目声明纪律始终是
`synthetic; uncalibrated; not OEM reproduction`。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..acoustic_analysis.spectral_targets import BAND_EDGES
from .deep_realism import STATE_KEYS, STATE_OPERATING_POINTS

_V015 = Path(__file__).resolve().parents[1]
_REFERENCE_DIR = _V015 / "reference_database"
_REGISTRY_PATH = _REFERENCE_DIR / "realism_reference_manifest.json"

VEHICLE_IDS = ("ferrari_458", "hellcat", "rx7_fd")
PROVENANCE_VALUES = ("compensated_reference", "physics_derived", "hybrid")

_DB_PER_OCTAVE = 20.0 * math.log10(2.0)
_ANALYSIS_MIN_HZ = BAND_EDGES[0][0]
_ANALYSIS_MAX_HZ = BAND_EDGES[-1][1]
_BAND_QUADRATURE_POINTS = 129

# 排气流噪声的 Strouhal 锚点：流速 ~ rpm*load，故峰值频率按 rpm*load 线性缩放。
# 锚点值本身是先验估计（量级依据：小口径排气管高负荷下的宽带"咆哮"集中在 1 kHz 附近）。
_FLOW_NOISE_PEAK_HZ_AT_ANCHOR = 1200.0
_FLOW_NOISE_ANCHOR_RPM_LOAD = 7200.0
# 排气脉冲激发的管道基模品质因数。开口端辐射损耗（60 mm 管在 100 Hz 处已相当可观）、
# 热气粘性损耗与消声器吸声共同限制 Q，实测排气管道模态在 2~4，取中值 2.5。
# 三车共用：Q 由损耗机理决定，各车差别远小于 f_res 的差别，不值得再开一个自由度。
_EXHAUST_RESONANCE_Q = 2.5
# 脉冲项能量的负荷指数。缸压 ∝ 进气充量 ∝ load，声能 ∝ 压力^2 => 能量 ∝ load^2。
# 与 flow-noise 项共用同一口径，不是独立拟合出来的指数。
_PULSE_LOAD_EXPONENT = 2.0

# 涡轮窄带（对数频率上的高斯包），中心随 rpm*load 上移。
_TURBO_CENTRE_BASE_HZ = 2500.0
_TURBO_CENTRE_SPAN_HZ = 4000.0
_TURBO_LOG_WIDTH = 0.18

# 录音链拟合的搜索栅格（固定、无随机，保证可复现）。
_FC_GRID_HZ = (15.0, 2500.0, 90)
_ORDER_GRID = (0.5, 5.0, 37)
# 残差加权下限：参考占比低于此值的 band 其相对误差不可信，不让它主导拟合。
_RESIDUAL_WEIGHT_FLOOR = 1e-3
# 预先声明的自洽性判据。out/in > 3 表示拟合不外推；out > 0.35（约 2.2 倍能量误差）
# 表示即便外推也没有可用精度。
_CHAIN_GENERALISATION_RATIO_MAX = 3.0
_CHAIN_RESIDUAL_MAX = 0.35

# 参考库分段 -> 该段的名义工况点 (rpm, load)。参考库没有记录 rpm（所有段
# `rpm_confidence: "none"`），这里给的是与段语义相符的估计值，属于假设。
REFERENCE_SEGMENT_OPERATING_POINTS = {
    "idle": (1100.0, 0.12),
    "acceleration": (5000.0, 0.85),
    "afterfire": (4000.0, 0.10),
}
# 六态 -> 参考库分段。只有语义确实对应的状态才挂参考段；
# `steady_cruise` / `full_pull` / `idle_return` 在参考库里没有对应录音段，
# 把 acceleration 段同时塞给它们正是缺陷 1 的成因。
REFERENCE_SEGMENT_FOR_STATE = {
    "idle": "idle",
    "acceleration": "acceleration",
    "lift_afterfire": "afterfire",
}
# 参考库分段 -> registry(`realism_reference_manifest.json`) 中的同义段名。
_REGISTRY_SEGMENT_ALIAS = {"idle": "idle", "acceleration": "acceleration", "afterfire": "deceleration"}
# registry 的 `intent` 含这些措辞即表示该段尚不可用作目标。
_REGISTRY_UNAVAILABLE_MARKERS = ("not available", "required", "pending")


@dataclass(frozen=True)
class EnginePrior:
    """单车的发动机声学先验。所有数值都是先验估计，不是实测标定。"""

    firing_order: float
    """主序阶次：每转曲轴（转子机为偏心轴）的燃烧次数。"""
    sub_order_weight: float
    """整数非主序分量的幅度权重（缸间/转子间充量差异）。"""
    half_order_weight: float
    """半阶分量的幅度权重；只有十字曲轴 V8 非零。"""
    harmonic_rolloff_db_per_octave: float
    """主序之上的谐波包络滚降（幅度，dB/oct）。"""
    flow_noise_fraction: float
    """满负荷时宽带排气流噪声占阶次能量的比例。"""
    pulse_fraction: float
    """满负荷时排气 blowdown 脉冲激发的管道共振占阶次能量的比例。

    量级依据：WOT 下尾管口噪声（exhaust orifice noise）是整车排气噪声的主导通道，
    比其余通道高约 6~10 dB，故该项与整条阶次级数同量级（fraction ~1）。各车的差别
    来自脉冲在到达尾管前被削掉多少——见各自的 `basis`。
    """
    exhaust_resonance_hz: float
    """排气管基频驻波模态 `c/(2L)`，c≈557 m/s（热态排气气体）。"""
    turbo_weight: float
    """满负荷时涡轮窄带占阶次能量的比例；自然吸气车为 0。"""
    basis: str
    """该组先验的依据说明，写进 manifest 供审计。"""


ENGINE_PRIORS: dict[str, EnginePrior] = {
    "ferrari_458": EnginePrior(
        firing_order=4.0,
        sub_order_weight=0.18,
        half_order_weight=0.0,
        harmonic_rolloff_db_per_octave=6.0,
        flow_noise_fraction=0.25,
        pulse_fraction=1.00,
        exhaust_resonance_hz=110.0,
        turbo_weight=0.0,
        basis=(
            "flat-plane crank V8, 8 cylinders 4-stroke => 4 events per crank revolution; "
            "even 180-degree bank firing suppresses half-order content; free-flowing NA "
            "exhaust modelled with a shallow 6 dB/oct harmonic envelope. "
            "Exhaust blowdown pulse: mid-engine layout gives a short collector-to-tip run "
            "of about 2.5 m, so the open-open pipe fundamental is c/(2L) = 557/5.0 = 111 Hz "
            "(rounded to 110 Hz) with hot-gas c = sqrt(1.35*287*800). The NA low-restriction "
            "rear-exit system barely attenuates the pulse, so essentially all of the blowdown "
            "energy reaches the tailpipe: pulse_fraction 1.00, the reference level for the "
            "other two vehicles"
        ),
    ),
    "hellcat": EnginePrior(
        firing_order=4.0,
        sub_order_weight=0.18,
        half_order_weight=0.50,
        harmonic_rolloff_db_per_octave=8.5,
        flow_noise_fraction=0.25,
        pulse_fraction=0.85,
        exhaust_resonance_hz=85.0,
        turbo_weight=0.0,
        basis=(
            "cross-plane crank V8, 8 cylinders 4-stroke => 4 events per crank revolution; "
            "uneven per-bank firing repeats over 720 degrees and radiates a strong "
            "half-order series (the audible lope); large-volume muffler modelled with a "
            "steeper 8.5 dB/oct envelope. "
            "Exhaust blowdown pulse: front-engine sedan routing gives the longest run of the "
            "three, about 3.3 m, so the pipe fundamental drops to c/(2L) = 557/6.6 = 84 Hz "
            "(rounded to 85 Hz) -- the lowest of the three and the reason the rumble sits "
            "deeper. The same large-volume absorptive mufflers that motivate the steeper "
            "harmonic envelope also absorb part of the pulse, so pulse_fraction is set "
            "slightly below the free-flowing Ferrari at 0.85"
        ),
    ),
    "rx7_fd": EnginePrior(
        firing_order=2.0,
        sub_order_weight=0.18,
        half_order_weight=0.0,
        harmonic_rolloff_db_per_octave=6.0,
        flow_noise_fraction=0.25,
        pulse_fraction=0.60,
        exhaust_resonance_hz=95.0,
        turbo_weight=0.04,
        basis=(
            "13B two-rotor Wankel: each rotor fires once per eccentric-shaft revolution, "
            "two rotors => 2nd order main series (NOT the 4th order of a 4-stroke V8); "
            "rotor-to-rotor variation feeds the odd integer orders; sequential turbo adds "
            "a load-gated narrowband component. "
            "Exhaust blowdown pulse: compact coupe routing gives about 2.9 m, so the pipe "
            "fundamental is c/(2L) = 557/5.8 = 96 Hz (rounded to 95 Hz), between the Ferrari "
            "and the Hellcat. pulse_fraction is the lowest of the three at 0.60 because the "
            "sequential turbines sit IN the exhaust stream and extract/scatter a large share "
            "of the blowdown energy before it reaches the pipe -- the standard reason a "
            "turbocharged engine is quieter at the tailpipe than an NA one of equal output"
        ),
    ),
}


@dataclass(frozen=True)
class ChainFit:
    """录音链高通滚降的拟合结果与其自洽性检验。"""

    vehicle_id: str
    fc_hz: float
    order_n: float
    in_sample_residual: float
    out_of_sample_residual: float
    single_chain_consistent: bool
    fitted_on: str
    validated_on: tuple[str, ...] = field(default_factory=tuple)


def firing_frequency_hz(vehicle_id: str, rpm: float) -> float:
    """主序点火频率：`rpm/60 * firing_order`。"""
    return rpm / 60.0 * ENGINE_PRIORS[vehicle_id].firing_order


def order_components(vehicle_id: str, rpm: float, load: float) -> list[tuple[float, float, float]]:
    """返回 `(order, frequency_hz, energy)` 的离散阶次分量列表。

    包络在主序点火频率以下取平坦（幅度不超过主序），以上按
    `harmonic_rolloff_db_per_octave` 滚降；这避免了"用频率比的负幂次外推到
    低阶次"会把 1 阶、2 阶抬到荒谬幅度的问题。
    """
    prior = ENGINE_PRIORS[vehicle_id]
    if rpm <= 0.0:
        raise ValueError("rpm must be positive")
    f_fire = firing_frequency_hz(vehicle_id, rpm)
    exponent = prior.harmonic_rolloff_db_per_octave / _DB_PER_OCTAVE
    step = 0.5 if prior.half_order_weight > 0.0 else 1.0

    components: list[tuple[float, float, float]] = []
    index = 1
    while True:
        order = step * index
        frequency = rpm / 60.0 * order
        if frequency > _ANALYSIS_MAX_HZ:
            break
        index += 1
        weight = _series_weight(prior, order)
        if weight <= 0.0 or frequency < _ANALYSIS_MIN_HZ:
            continue
        amplitude = weight * min(1.0, (frequency / f_fire) ** -exponent)
        components.append((order, frequency, amplitude * amplitude))
    return components


def physics_band_shares(vehicle_id: str, rpm: float, load: float) -> list[float]:
    """物理先验推导的四个 band 能量占比（和为 1）。"""
    energies = _band_energies(vehicle_id, rpm, load)
    total = float(energies.sum())
    return [float(value) for value in energies / total]


def fit_recording_chain(vehicle_id: str, reference: dict | None = None) -> ChainFit:
    """按 brief 的方法在 idle 段拟合高通 `(fc, n)`，并在其余段上检验它是否成立。"""
    reference = reference or load_reference_targets(vehicle_id)
    segments = available_reference_segments(reference)
    if "idle" not in segments:
        raise ValueError(f"{vehicle_id}: reference has no idle segment to fit the chain on")

    grid = [
        (fc, order)
        for fc in np.geomspace(*_FC_GRID_HZ[:2], int(_FC_GRID_HZ[2]))
        for order in np.linspace(*_ORDER_GRID[:2], int(_ORDER_GRID[2]))
    ]
    fc_hz, order_n = min(
        grid, key=lambda pair: _chain_residual(vehicle_id, reference, ("idle",), pair[0], pair[1])
    )
    in_sample = _chain_residual(vehicle_id, reference, ("idle",), fc_hz, order_n)
    out_of_sample = _chain_residual(vehicle_id, reference, segments, fc_hz, order_n)
    consistent = (
        out_of_sample <= _CHAIN_GENERALISATION_RATIO_MAX * in_sample
        and out_of_sample <= _CHAIN_RESIDUAL_MAX
    )
    return ChainFit(
        vehicle_id=vehicle_id,
        fc_hz=float(fc_hz),
        order_n=float(order_n),
        in_sample_residual=float(in_sample),
        out_of_sample_residual=float(out_of_sample),
        single_chain_consistent=bool(consistent),
        fitted_on="idle",
        validated_on=segments,
    )


def compensated_reference_shares(
    vehicle_id: str, segment: str, fit: ChainFit, reference: dict | None = None
) -> list[float]:
    """对参考段反演补偿录音链滚降后的 band 占比。

    每个 band 的链增益取"物理谱在该 band 内的能量加权平均"，因为同一 band 内
    能量集中在哪个频率会显著改变有效衰减量。
    """
    reference = reference or load_reference_targets(vehicle_id)
    measured = np.asarray(reference["stock_median"][f"{segment}_band_shares"], dtype=np.float64)
    rpm, load = REFERENCE_SEGMENT_OPERATING_POINTS[segment]
    gains = _band_chain_gains(vehicle_id, rpm, load, fit.fc_hz, fit.order_n)
    restored = measured / np.maximum(gains, 1e-12)
    return [float(value) for value in restored / restored.sum()]


def state_targets(vehicle_id: str) -> dict[str, dict]:
    """组装该车六态的 band 目标与逐态 provenance。"""
    reference = load_reference_targets(vehicle_id)
    fit = fit_recording_chain(vehicle_id, reference)
    usable = usable_reference_segments(vehicle_id, reference, fit)

    targets: dict[str, dict] = {}
    for state in STATE_KEYS:
        rpm, load, _throttle = STATE_OPERATING_POINTS[state]
        physics = np.asarray(physics_band_shares(vehicle_id, rpm, load), dtype=np.float64)
        segment = REFERENCE_SEGMENT_FOR_STATE.get(state)
        if segment is not None and segment in usable:
            compensated = np.asarray(
                compensated_reference_shares(vehicle_id, segment, fit, reference), dtype=np.float64
            )
            blended = np.sqrt(physics * compensated)
            shares = blended / blended.sum()
            entry = {
                "band_shares_target": _rounded_unit_sum(shares),
                "provenance": "hybrid",
                "reference_segment": segment,
                "basis": "geometric blend of the physics prior and the roll-off compensated reference segment",
            }
        else:
            entry = {
                "band_shares_target": _rounded_unit_sum(physics),
                "provenance": "physics_derived",
                "reference_segment": None,
                "basis": _physics_only_basis(vehicle_id, state, segment, fit),
            }
        entry["operating_point"] = {"rpm": rpm, "load": load}
        targets[state] = entry
    return targets


def load_reference_targets(vehicle_id: str) -> dict:
    path = _REFERENCE_DIR / f"{vehicle_id}_reference_targets.json"
    return json.loads(path.read_text(encoding="utf-8"))


def available_reference_segments(reference: dict) -> tuple[str, ...]:
    """参考库里真的带 band 特征的分段。"""
    median = reference["stock_median"]
    return tuple(
        segment
        for segment in REFERENCE_SEGMENT_OPERATING_POINTS
        if f"{segment}_band_shares" in median
    )


def registry_corroborated_segments(vehicle_id: str) -> tuple[str, ...]:
    """`realism_reference_manifest.json` 未声明"不可用/待人工标注"的分段。

    参考库的 `*_reference_targets.json` 与 registry 记录的其实是**不同的录音**
    （video_id 不一致），registry 才是带风险声明与提取状态的权威登记。凡 registry
    明说该段不可用的，其 band 特征就不得当作目标依据。
    """
    registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    entry = registry["vehicles"][vehicle_id]
    status = entry.get("feature_extraction", {}).get("status", "").lower()
    idle_only = "idle only" in status

    corroborated = []
    for segment, alias in _REGISTRY_SEGMENT_ALIAS.items():
        if idle_only and segment != "idle":
            continue
        intent = entry["segments"].get(alias, {}).get("intent", "").lower()
        if any(marker in intent for marker in _REGISTRY_UNAVAILABLE_MARKERS):
            continue
        corroborated.append(segment)
    return tuple(corroborated)


def usable_reference_segments(
    vehicle_id: str, reference: dict, fit: ChainFit
) -> tuple[str, ...]:
    """可作为调音目标依据的参考段：registry 认可 **且** 录音链补偿检验通过。"""
    if not fit.single_chain_consistent:
        return ()
    corroborated = set(registry_corroborated_segments(vehicle_id))
    return tuple(s for s in available_reference_segments(reference) if s in corroborated)


def _series_weight(prior: EnginePrior, order: float) -> float:
    ratio = order / prior.firing_order
    if abs(ratio - round(ratio)) < 1e-9 and round(ratio) >= 1:
        return 1.0
    if abs(order - round(order)) < 1e-9:
        return prior.sub_order_weight
    return prior.half_order_weight


def _band_energies(
    vehicle_id: str, rpm: float, load: float, chain: tuple[float, float] | None = None
) -> np.ndarray:
    """四个 band 的能量（未归一）。`chain` 给出 (fc, n) 时叠加录音链高通。"""
    prior = ENGINE_PRIORS[vehicle_id]
    energies = np.zeros(len(BAND_EDGES), dtype=np.float64)
    harmonic_total = 0.0
    for _order, frequency, energy in order_components(vehicle_id, rpm, load):
        harmonic_total += energy
        gain = _highpass_power(frequency, chain) if chain else 1.0
        for index, (low, high) in enumerate(BAND_EDGES):
            if low <= frequency <= high:
                energies[index] += energy * gain
                break

    flow_peak = _FLOW_NOISE_PEAK_HZ_AT_ANCHOR * max(rpm * load, 1.0) / _FLOW_NOISE_ANCHOR_RPM_LOAD
    turbo_centre = _TURBO_CENTRE_BASE_HZ + _TURBO_CENTRE_SPAN_HZ * min(rpm * load / 8000.0, 1.0)
    if prior.pulse_fraction > 0.0:
        energies += (
            harmonic_total
            * prior.pulse_fraction
            * load**_PULSE_LOAD_EXPONENT
            * _broadband_band_shares(
                lambda f: _exhaust_pulse_shape(f, prior.exhaust_resonance_hz), chain
            )
        )
    energies += harmonic_total * prior.flow_noise_fraction * load**2 * _broadband_band_shares(
        lambda f: _flow_noise_shape(f, flow_peak), chain
    )
    if prior.turbo_weight > 0.0:
        energies += harmonic_total * prior.turbo_weight * load**2 * _broadband_band_shares(
            lambda f: _turbo_shape(f, turbo_centre), chain
        )
    return energies


def _broadband_band_shares(shape, chain: tuple[float, float] | None) -> np.ndarray:
    """把一个宽带谱形状积分到各 band，并按**未经录音链**的总量归一。

    归一用未滤波总量，使得"宽带项占阶次能量的比例"这一先验在加不加录音链时
    含义一致；录音链只改变它在各 band 之间的分布与总量。
    """
    raw = np.zeros(len(BAND_EDGES), dtype=np.float64)
    filtered = np.zeros(len(BAND_EDGES), dtype=np.float64)
    for index, (low, high) in enumerate(BAND_EDGES):
        grid = np.geomspace(low, high, _BAND_QUADRATURE_POINTS)
        values = np.array([shape(f) for f in grid], dtype=np.float64)
        raw[index] = float(np.trapezoid(values, grid))
        if chain:
            gains = np.array([_highpass_power(f, chain) for f in grid], dtype=np.float64)
            filtered[index] = float(np.trapezoid(values * gains, grid))
    total = float(raw.sum())
    if total <= 0.0:
        return raw
    return (filtered if chain else raw) / total


def _exhaust_pulse_shape(frequency: float, resonance_hz: float) -> float:
    """排气 blowdown 脉冲激发的管道基模：二阶带通谐振器的功率响应。

    ``|H(f)|^2 = x^2 / ((1 - x^2)^2 + (x/Q)^2)``，``x = f / f_res``。

    - 分子 ``x^2``：尾管开口端的单极子辐射效率 ∝ f^2。稳态排气流（DC）不辐射声，
      所以响应在 DC 处必须为零——这是本项与 `_flow_noise_shape` 共有的低频行为。
    - 分母的极点对：排气管的基频驻波模态，峰值在 f_res，品质因数
      `_EXHAUST_RESONANCE_Q`。
    - f_res 之上按 f^-2 衰减，故 ~250 Hz 以上迅速失去能量：f_res≈100 Hz、Q=2.5 时
      约 87% 的项能量落在 band0 (20-250 Hz)，约 10% 落在 band1，其余可忽略。
    """
    x = frequency / resonance_hz
    return x * x / ((1.0 - x * x) ** 2 + (x / _EXHAUST_RESONANCE_Q) ** 2)


def _flow_noise_shape(frequency: float, peak_hz: float) -> float:
    """湍流排气流噪声：峰值以下 ~f^2 上升，以上 ~f^-2 衰减。"""
    x = frequency / peak_hz
    return x**2 / (1.0 + x**4)


def _turbo_shape(frequency: float, centre_hz: float) -> float:
    return math.exp(-0.5 * (math.log(frequency / centre_hz) / _TURBO_LOG_WIDTH) ** 2)


def _highpass_power(frequency: float, chain: tuple[float, float]) -> float:
    fc_hz, order_n = chain
    ratio = (frequency / fc_hz) ** (2.0 * order_n)
    return ratio / (1.0 + ratio)


def _band_chain_gains(
    vehicle_id: str, rpm: float, load: float, fc_hz: float, order_n: float
) -> np.ndarray:
    unfiltered = _band_energies(vehicle_id, rpm, load)
    filtered = _band_energies(vehicle_id, rpm, load, chain=(fc_hz, order_n))
    return filtered / np.maximum(unfiltered, 1e-30)


def _chain_residual(
    vehicle_id: str, reference: dict, segments: tuple[str, ...], fc_hz: float, order_n: float
) -> float:
    """加权 RMS log10 band 残差：物理谱经录音链后 vs 实测参考。"""
    total = 0.0
    weight_sum = 0.0
    for segment in segments:
        rpm, load = REFERENCE_SEGMENT_OPERATING_POINTS[segment]
        energies = _band_energies(vehicle_id, rpm, load, chain=(fc_hz, order_n))
        predicted = energies / max(float(energies.sum()), 1e-30)
        measured = np.asarray(
            reference["stock_median"][f"{segment}_band_shares"], dtype=np.float64
        )
        weights = np.maximum(measured, _RESIDUAL_WEIGHT_FLOOR)
        errors = np.log10(np.maximum(predicted, 1e-6)) - np.log10(np.maximum(measured, 1e-6))
        total += float(np.sum(weights * errors**2))
        weight_sum += float(weights.sum())
    return math.sqrt(total / weight_sum)


def _physics_only_basis(vehicle_id: str, state: str, segment: str | None, fit: ChainFit) -> str:
    if segment is None:
        return "no reference segment corresponds to this operating state; derived from the physics prior"
    if not fit.single_chain_consistent:
        return (
            "reference segment discarded: the single recording-chain roll-off fitted on idle "
            f"does not generalise (out-of-sample residual {fit.out_of_sample_residual:.3f} vs "
            f"in-sample {fit.in_sample_residual:.3f}); derived from the physics prior"
        )
    return (
        "reference segment not corroborated by realism_reference_manifest.json; "
        "derived from the physics prior"
    )


def _rounded_unit_sum(shares: np.ndarray, digits: int = 6) -> list[float]:
    """四舍五入到固定位数后把舍入残差并入最大项，保证和精确为 1。"""
    rounded = [round(float(value), digits) for value in shares]
    index = int(np.argmax(rounded))
    rounded[index] = round(rounded[index] + (1.0 - math.fsum(rounded)), digits + 3)
    return rounded
