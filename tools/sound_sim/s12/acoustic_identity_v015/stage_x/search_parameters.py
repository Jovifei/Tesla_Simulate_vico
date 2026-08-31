"""Stage X Hellcat parameter definitions and reachability harness.

Each search parameter maps to an event-domain config mutation. A parameter
is REACHABLE only when the renderer consumes it (diagnostics/parameter
consumption), the rendered WAV changes (SHA), a target metric moves, and
non-target movement stays bounded. Unreachable parameters are excluded
from the search and reported as PARAMETER_NOT_REACHABLE.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from ..event_domain.config_schema import load_config, parameter, unwrap
from ..stage_v.io import write_json
from .multi_reference_comparator import raw_dynamic_metrics, timbre_metrics
from ..stage_y.harmonic_map_fit import MAP_PATH, configure_committed_fixture_timbre_map

REACHABILITY_SCHEMA = "s12.stage_x.parameter_reachability.v1"
PARAMETER_NOT_REACHABLE = "PARAMETER_NOT_REACHABLE"
PARAMETER_REACHABLE = "PARAMETER_REACHABLE"


@dataclass(frozen=True)
class SearchParameter:
    name: str
    baseline: float
    delta: float
    apply: Callable[[dict[str, Any], float], None]
    target_metrics: tuple[str, ...]
    guard_metrics: tuple[str, ...] = ()
    unit: str = "normalized"
    note: str = ""
    architecture: str = "P2H"
    scenes: tuple[tuple[str, float], ...] = (("hot_idle_20s", 2.0), ("full_load_acceleration", 2.0))
    stem: str = "post_ptr"
    probe_mode: str = "engine"


def _set_parameter(config: dict[str, Any], path: str, value: Any) -> None:
    """Set an existing parameter node's value, preserving provenance keys."""
    node: Any = config
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]]["value"] = value


def _scale_spread(config: dict[str, Any], key: str, spread: float) -> None:
    values = np.asarray(unwrap(config, key), dtype=np.float64)
    mean = float(np.mean(values))
    if np.allclose(values, mean):
        pattern = np.array([1.0 if index % 2 == 0 else -1.0 for index in range(values.size)], dtype=np.float64)
        values = mean * (1.0 + 0.22 * pattern)
    _set_parameter(config, key, list(mean + (values - mean) * spread))


def _band_120_400(audio: np.ndarray, sample_rate: int) -> float:
    metrics = timbre_metrics(audio, sample_rate)
    shares = metrics["fine_band_shares"]
    return shares[2] + shares[3]  # 120-250 + 250-400


def _low_band(audio: np.ndarray, sample_rate: int) -> float:
    return timbre_metrics(audio, sample_rate)["fine_band_shares"][0] + timbre_metrics(audio, sample_rate)["fine_band_shares"][1]


def _mid_band(audio: np.ndarray, sample_rate: int) -> float:
    return timbre_metrics(audio, sample_rate)["fine_band_shares"][4] + timbre_metrics(audio, sample_rate)["fine_band_shares"][5]


def _high_band(audio: np.ndarray, sample_rate: int) -> float:
    return timbre_metrics(audio, sample_rate)["fine_band_shares"][6] + timbre_metrics(audio, sample_rate)["fine_band_shares"][7]


def _window_energy_share(audio: np.ndarray, start: float, end: float) -> float:
    samples = np.asarray(audio, dtype=np.float64).reshape(-1)
    lower = int(np.clip(round(start * samples.size), 0, samples.size))
    upper = int(np.clip(round(end * samples.size), lower + 1, samples.size))
    energy = np.square(samples)
    return float(np.sum(energy[lower:upper]) / max(float(np.sum(energy)), 1.0e-12))


def _window_rms(audio: np.ndarray, start: float, end: float) -> float:
    """RMS in a declared dynamic-probe window (not a whole-scene proxy)."""
    samples = np.asarray(audio, dtype=np.float64).reshape(-1)
    lower = int(np.clip(round(start * samples.size), 0, samples.size))
    upper = int(np.clip(round(end * samples.size), lower + 1, samples.size))
    return float(np.sqrt(np.mean(np.square(samples[lower:upper]))))


def _window_high_band_share(audio: np.ndarray, sample_rate: int, start: float, end: float) -> float:
    samples = np.asarray(audio, dtype=np.float64).reshape(-1)
    lower = int(np.clip(round(start * samples.size), 0, samples.size))
    upper = int(np.clip(round(end * samples.size), lower + 1, samples.size))
    return _high_band(samples[lower:upper], sample_rate)


def _post_ptr_narrowband_energy_share(
    audio: np.ndarray,
    sample_rate: int,
    centers_hz: float | tuple[float, ...] | list[float] | np.ndarray,
    half_width_hz: float = 2.0,
) -> float:
    """Return non-DC Hann-windowed energy in the declared narrow bands."""
    samples = np.asarray(audio, dtype=np.float64)
    if samples.ndim == 2:
        if samples.shape[1] == 0:
            return 0.0
        samples = samples.mean(axis=1)
    elif samples.ndim != 1:
        raise ValueError("narrowband metric expects mono or channel-major PCM")
    if samples.size == 0:
        return 0.0
    samples = samples[-int(sample_rate):]
    if not np.all(np.isfinite(samples)):
        return 0.0
    centers = np.atleast_1d(np.asarray(centers_hz, dtype=np.float64))
    if centers.size == 0 or not np.all(np.isfinite(centers)) or half_width_hz < 0.0:
        return 0.0
    windowed = samples * np.hanning(samples.size)
    power = np.square(np.abs(np.fft.rfft(windowed)))
    frequencies = np.fft.rfftfreq(samples.size, d=1.0 / float(sample_rate))
    denominator = float(np.sum(power[1:]))
    if denominator <= 0.0 or not np.isfinite(denominator):
        return 0.0
    target_bins = np.any(
        np.abs(frequencies[:, np.newaxis] - centers[np.newaxis, :]) <= float(half_width_hz),
        axis=1,
    )
    target_bins[0] = False
    numerator = float(np.sum(power[target_bins]))
    return float(numerator / denominator)


_BLOWER_SPECTRUM_RPM = 3000.0


def _blower_sideband_narrowband_share(audio: np.ndarray, sample_rate: int) -> float:
    crank_hz = _BLOWER_SPECTRUM_RPM / 60.0
    ratio = float(unwrap(load_config("hellcat_v1"), "forced_induction.ratio"))
    return _post_ptr_narrowband_energy_share(audio, sample_rate, (ratio * crank_hz,))


def _blower_broadband_narrowband_share(audio: np.ndarray, sample_rate: int) -> float:
    crank_hz = _BLOWER_SPECTRUM_RPM / 60.0
    centers = (
        float(sample_rate) * 0.017 / (2.0 * np.pi) + 0.31 * crank_hz,
        float(sample_rate) * 0.041 / (2.0 * np.pi) + 0.73 * crank_hz,
        float(sample_rate) * 0.097 / (2.0 * np.pi),
    )
    return _post_ptr_narrowband_energy_share(audio, sample_rate, centers)


def _blower_casing_narrowband_share(audio: np.ndarray, sample_rate: int) -> float:
    crank_hz = _BLOWER_SPECTRUM_RPM / 60.0
    return _post_ptr_narrowband_energy_share(audio, sample_rate, (4.7 * crank_hz, 9.3 * crank_hz))


def _afterfire_residual_window(audio: np.ndarray, sample_rate: int) -> tuple[np.ndarray, int, int, int]:
    """Locate one residual afterfire packet relative to the declared 40% lift.

    Inputs are always actual post-PTR PCM minus the same render with only
    ``afterfire.gain`` set to zero.  This removes combustion before selecting a
    short event-local analysis window; it is not a whole-scene loudness proxy.
    """
    stereo = np.asarray(audio, dtype=np.float64)
    if stereo.ndim != 2 or stereo.shape[1] != 2 or stereo.shape[0] == 0:
        return np.zeros((1, 2), dtype=np.float64), 0, 0, 0
    lift_start = int(round(0.40 * stereo.shape[0]))
    energy = np.sum(np.square(stereo), axis=1)
    smoothing = max(1, int(round(0.001 * sample_rate)))
    envelope = np.convolve(energy, np.ones(smoothing, dtype=np.float64) / smoothing, mode="same")
    post_lift = envelope[lift_start:]
    if post_lift.size == 0 or float(np.max(post_lift)) <= 1.0e-18:
        return np.zeros((1, 2), dtype=np.float64), lift_start, lift_start, lift_start
    peak = lift_start + int(np.argmax(post_lift))
    threshold = max(float(envelope[peak]) * 0.02, 1.0e-18)
    onset = peak
    while onset > lift_start and envelope[onset - 1] >= threshold:
        onset -= 1
    window_end = min(stereo.shape[0], onset + max(1, int(round(0.055 * sample_rate))))
    return stereo[onset:window_end], onset, peak, lift_start


def _afterfire_residual_energy_envelope(audio: np.ndarray, sample_rate: int) -> float:
    window, _, _, _ = _afterfire_residual_window(audio, sample_rate)
    return float(np.sqrt(np.mean(np.square(window))))


def _afterfire_residual_onset(audio: np.ndarray, sample_rate: int) -> float:
    _, onset, _, lift_start = _afterfire_residual_window(audio, sample_rate)
    return float((onset - lift_start) / sample_rate)


def _afterfire_residual_peak_offset(audio: np.ndarray, sample_rate: int) -> float:
    _, _, peak, lift_start = _afterfire_residual_window(audio, sample_rate)
    return float((peak - lift_start) / sample_rate)


def _afterfire_residual_path_balance(audio: np.ndarray, sample_rate: int) -> float:
    window, _, _, _ = _afterfire_residual_window(audio, sample_rate)
    energy = np.sum(np.square(window), axis=0)
    return float((energy[0] - energy[1]) / max(float(np.sum(energy)), 1.0e-12))


def _afterfire_residual_crest(audio: np.ndarray, sample_rate: int) -> float:
    window, _, _, _ = _afterfire_residual_window(audio, sample_rate)
    rms = float(np.sqrt(np.mean(np.square(window))))
    return float(np.max(np.abs(window)) / max(rms, 1.0e-12))


def _early_path_balance(audio: np.ndarray, sample_rate: int) -> float:
    """Relative left/right energy in the early post-PTR path-arrival window."""
    del sample_rate
    stereo = np.asarray(audio, dtype=np.float64)
    if stereo.ndim != 2 or stereo.shape[1] != 2:
        return 0.0
    early = stereo[: int(round(0.20 * stereo.shape[0]))]
    energy = np.mean(np.square(early), axis=0)
    return float((energy[0] - energy[1]) / max(float(np.sum(energy)), 1.0e-12))


METRIC_FUNCS: dict[str, Callable[[np.ndarray, int], float]] = {
    "low_band_share": _low_band,
    "band_120_400": _band_120_400,
    "mid_band_share": _mid_band,
    "high_band_share": _high_band,
    "tonality": lambda audio, sr: timbre_metrics(audio, sr)["tonality_proxy"],
    "sharpness": lambda audio, sr: timbre_metrics(audio, sr)["sharpness_proxy"],
    "roughness": lambda audio, sr: timbre_metrics(audio, sr)["roughness_proxy"],
    "flux": lambda audio, sr: timbre_metrics(audio, sr)["spectral_flux"],
    "centroid": lambda audio, sr: timbre_metrics(audio, sr)["spectral_centroid_hz"],
    "crest": lambda audio, sr: raw_dynamic_metrics(audio, sr)["crest_db"],
    "dynamic_range": lambda audio, sr: raw_dynamic_metrics(audio, sr)["dynamic_range_db"],
    "transient_density": lambda audio, sr: raw_dynamic_metrics(audio, sr)["transient_event_density_per_s"],
    "early_energy_share": lambda audio, sr: _window_energy_share(audio, 0.00, 0.35),
    "transition_energy_share": lambda audio, sr: _window_energy_share(audio, 0.35, 0.60),
    "late_energy_share": lambda audio, sr: _window_energy_share(audio, 0.65, 1.00),
    "afterfire_residual_energy_envelope": _afterfire_residual_energy_envelope,
    "afterfire_residual_onset": _afterfire_residual_onset,
    "afterfire_residual_peak_offset": _afterfire_residual_peak_offset,
    "afterfire_residual_path_balance": _afterfire_residual_path_balance,
    "afterfire_residual_crest": _afterfire_residual_crest,
    "early_path_balance": _early_path_balance,
    "high_slew_high_band_share": lambda audio, sr: _window_high_band_share(audio, sr, 0.30, 0.40),
    "idle_recovery_window_rms": lambda audio, sr: _window_rms(audio, 0.775, 0.80),
    "path_window_rms": lambda audio, sr: _window_rms(audio, 0.15, 0.45),
    "blower_window_rms": lambda audio, sr: _window_rms(audio, 0.35, 0.70),
    "blower_sideband_narrowband_share": _blower_sideband_narrowband_share,
    "blower_broadband_narrowband_share": _blower_broadband_narrowband_share,
    "blower_casing_narrowband_share": _blower_casing_narrowband_share,
    "boost_attack_envelope_rms": lambda audio, sr: _window_rms(audio, 0.40, 0.425),
    "boost_release_envelope_rms": lambda audio, sr: _window_rms(audio, 0.5875, 0.6125),
    "bypass_sweep_window_rms": lambda audio, sr: _window_rms(audio, 0.2625, 0.2875),
    "blower_component_high_band_share": lambda audio, sr: _window_high_band_share(audio, sr, 0.30, 0.40),
    "monitor_attack_envelope_rms": lambda audio, sr: _window_rms(audio, 0.05, 0.30),
    "monitor_release_envelope_rms": lambda audio, sr: _window_rms(audio, 0.65, 0.95),
    "monitor_makeup_envelope_rms": lambda audio, sr: _window_rms(audio, 0.45, 0.55),
}


def _fixed(value: float, unit: str, source: str) -> dict[str, Any]:
    return parameter(value, unit, "search_override", source=source, verification_state="synthetic_assumption")


def hellcat_search_parameters() -> list[SearchParameter]:
    """The 27 contract parameters mapped onto event-domain config mutations."""
    return [
        SearchParameter("combustion_event_energy", 0.60, 0.18, lambda c, v: _set_parameter(c, "combustion_event.event_energy", v), ("crest", "transient_density", "low_band_share"), ("centroid",), unit="normalized_pressure", note="per-event pressure energy"),
        SearchParameter("combustion_rise_time", 0.0035, 0.0012, lambda c, v: _set_parameter(c, "combustion_event.rise_time_s", v), ("band_120_400", "sharpness"), ("low_band_share",), unit="s"),
        SearchParameter("combustion_decay_time", 0.030, 0.008, lambda c, v: _set_parameter(c, "combustion_event.decay_time_s", v), ("low_band_share", "dynamic_range"), ("tonality",), unit="s"),
        SearchParameter("cycle_variation", 0.08, 0.03, lambda c, v: _set_parameter(c, "cycle_variation", v), ("roughness", "flux"), ("centroid",), unit="normalized"),
        SearchParameter("crank_inertia", 0.34, 0.10, lambda c, v: _set_parameter(c, "crank_inertia", v), ("high_slew_high_band_share",), (), unit="kg_m2", scenes=(("throttle_tip_in", 2.5),)),

        SearchParameter("idle_governor", 0.22, 0.07, lambda c, v: _set_parameter(c, "idle_governor", v), ("idle_recovery_window_rms",), (), unit="normalized_torque", scenes=(("y1_idle_dip_recovery", 1.6),)),

        SearchParameter("primary_length_spread", 1.0, 0.25, lambda c, v: _scale_spread(c, "per_path_primary_length_m", v), ("band_120_400", "roughness"), (), unit="spread_scale"),
        SearchParameter("primary_attenuation_spread", 1.0, 0.28, lambda c, v: _scale_spread(c, "per_path_attenuation", v), ("early_path_balance",), (), unit="spread_scale", scenes=(("full_load_acceleration", 1.6),)),
        SearchParameter("waveguide_reflection", 1.0, 1.0, lambda c, v: c.setdefault("exhaust_waveguide", {}).update({"reflection_mode": _fixed("open" if v < 1.0 else "closed", "label", "stage x search reflection mode")}), ("band_120_400", "dynamic_range"), (), unit="mode_scale", note="open vs closed junction reflection", architecture="P2H", scenes=(("full_load_acceleration", 2.0), ("gear_shift", 1.5))),
        SearchParameter("waveguide_loss", 0.08, 0.03, lambda c, v: c.setdefault("exhaust_waveguide", {}).update({"loss_per_meter": _fixed(v, "ratio", "stage x search waveguide loss")}), ("high_band_share", "mid_band_share"), (), unit="per_m"),
        SearchParameter("collector_loss", 0.92, 0.06, lambda c, v: _set_parameter(c, "collector_loss", v), ("mid_band_share", "high_band_share"), (), unit="ratio"),
        SearchParameter("attack_mix_120_400", 0.0, 0.20, lambda c, v: c.setdefault("attack_shaping", {}).update({"band_120_400_mix": _fixed(v, "gain", "stage x attack shaping")}), ("band_120_400",), ("low_band_share",), unit="gain"),
        SearchParameter("timbre_map_order_weights", 1.0, 0.30, lambda c, v: c.setdefault("timbre_mixes", {}).update({"order_weights": _fixed([v, v, 1.0, 1.0], "vector", "stage x order weights")}), ("sharpness", "tonality"), (), unit="vector_scale", architecture="P3", scenes=(("full_load_acceleration", 2.0), ("throttle_tip_in", 2.0))),

        SearchParameter("blower_sideband_mix", 1.0, 0.30, lambda c, v: c.setdefault("timbre_mixes", {}).update({"sideband_mix": _fixed(v, "gain", "stage x sideband mix")}), ("blower_sideband_narrowband_share",), ("low_band_share",), unit="gain", architecture="P3", scenes=(("y1_blower_spectrum", 2.5),)),

        SearchParameter("blower_broadband_mix", 1.0, 0.30, lambda c, v: c.setdefault("timbre_mixes", {}).update({"broadband_mix": _fixed(v, "gain", "stage x broadband mix")}), ("blower_broadband_narrowband_share",), ("tonality",), unit="gain", architecture="P3", scenes=(("y1_blower_spectrum", 2.5),)),

        SearchParameter("blower_casing_mix", 1.0, 0.40, lambda c, v: c.setdefault("timbre_mixes", {}).update({"casing_mix": _fixed(v, "gain", "stage x casing mix")}), ("blower_casing_narrowband_share",), ("low_band_share",), unit="gain", architecture="P3", scenes=(("y1_blower_spectrum", 2.5),)),

        SearchParameter("intake_mix", 0.18, 0.06, lambda c, v: _set_parameter(c, "intake_model", v), ("mid_band_share", "flux"), (), unit="normalized_gain"),
        SearchParameter("boost_attack", 0.08, 0.07, lambda c, v: c.setdefault("timbre_mixes", {}).update({"boost_attack_s": _fixed(v, "s", "stage x boost attack")}), ("boost_attack_envelope_rms",), (), unit="s", architecture="P3", scenes=(("y1_boost_attack", 1.6),)),

        SearchParameter("boost_release", 0.25, 0.24, lambda c, v: c.setdefault("timbre_mixes", {}).update({"boost_release_s": _fixed(v, "s", "stage x boost release")}), ("boost_release_envelope_rms",), (), unit="s", architecture="P3", scenes=(("y1_precharged_boost_release", 1.6),)),

        SearchParameter("bypass_threshold", 0.20, 0.08, lambda c, v: c.setdefault("timbre_mixes", {}).update({"bypass_threshold": _fixed(v, "throttle", "stage x bypass threshold")}), ("bypass_sweep_window_rms",), (), unit="throttle", architecture="P3", scenes=(("y1_bypass_threshold_sweep", 1.6),)),

        SearchParameter("afterfire_reservoir_rate", 0.72, 0.20, lambda c, v: c["afterfire"].update({"fuel_reservoir_rate": _fixed(v, "normalized", "stage x reservoir rate")}), ("afterfire_residual_energy_envelope",), (), unit="normalized", architecture="P3", scenes=(("afterfire_eligible", 2.5),), probe_mode="afterfire_residual"),

        SearchParameter("afterfire_ignition_delay", 0.004, 0.0015, lambda c, v: _set_parameter(c, "afterfire.ignition_delay_s", v), ("afterfire_residual_onset", "afterfire_residual_peak_offset"), (), unit="s", architecture="P3", scenes=(("afterfire_eligible", 2.5),), probe_mode="afterfire_residual"),

        SearchParameter("afterfire_location_mix", 0.0, 1.0, lambda c, v: _set_parameter(c, "afterfire.event_location", "central_collector" if v < 0.0 else "bank_collector"), ("afterfire_residual_path_balance", "afterfire_residual_peak_offset"), (), unit="mode", note="baseline primary, low central collector, high bank collector routing", architecture="P3", scenes=(("afterfire_eligible", 2.5),), probe_mode="afterfire_residual"),

        SearchParameter("afterfire_energy", 0.06, 0.02, lambda c, v: _set_parameter(c, "afterfire.gain", v), ("afterfire_residual_energy_envelope", "afterfire_residual_crest"), (), unit="normalized_gain", architecture="P3", scenes=(("afterfire_eligible", 2.5),), probe_mode="afterfire_residual"),

        SearchParameter("monitor_attack", 0.12, 0.05, lambda c, v: c.setdefault("monitor_policy", {}).update({"attack_s": _fixed(v, "s", "stage x monitor attack")}), ("monitor_attack_envelope_rms",), (), unit="s", stem="monitor", probe_mode="monitor_step"),

        SearchParameter("monitor_release", 1.20, 0.40, lambda c, v: c.setdefault("monitor_policy", {}).update({"release_s": _fixed(v, "s", "stage x monitor release")}), ("monitor_release_envelope_rms",), (), unit="s", stem="monitor", probe_mode="monitor_step"),

        SearchParameter("monitor_max_makeup", 9.0, 3.0, lambda c, v: c.setdefault("monitor_policy", {}).update({"max_makeup_db": _fixed(v, "dB", "stage x monitor makeup")}), ("monitor_makeup_envelope_rms",), (), unit="dB", stem="monitor", probe_mode="monitor_step"),

    ]


def apply_parameters(base_config: dict[str, Any], overrides: dict[str, float], parameters: list[SearchParameter]) -> dict[str, Any]:
    """Deep-copy the base config and apply named search overrides."""
    config = copy.deepcopy(base_config)
    by_name = {item.name: item for item in parameters}
    for name, value in overrides.items():
        if name not in by_name:
            raise KeyError(f"unknown search parameter: {name}")
        by_name[name].apply(config, float(value))
    return config


def _engine_settings(architecture: str) -> dict[str, str]:
    return {
        "P2": {"path_model": "delay_lpf_v1", "forced_induction_model": "harmonic_v1"},
        "P2H": {"path_model": "waveguide_v1", "forced_induction_model": "harmonic_v1"},
        "P3": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"},
        "P5": {"path_model": "waveguide_v1", "forced_induction_model": "timbre_map_v1"},
    }[architecture]


def _render_config_pcm(config: dict[str, Any], architecture: str, traces: list[Any]) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Render post-PTR and engine-monitor stems for each trace (P1 falls back)."""
    from ..stage_w.bakeoff import _render_architecture, build_hellcat_bakeoff_trace  # noqa: F401
    from ..stage_w.persistent_engine import PersistentEventDomainEngine

    settings = _engine_settings(architecture)
    if settings["forced_induction_model"] == "timbre_map_v1":
        configure_committed_fixture_timbre_map(config)
    blocks: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for trace in traces:
        engine = PersistentEventDomainEngine(copy.deepcopy(config), 48000, 960, ptr_enabled=True, **settings)
        result = engine.process_with_trace({"rpm": trace.rpm, "load": trace.load, "throttle": trace.throttle, "acceleration_mps2": trace.acceleration_mps2})
        post = result.post_ptr_raw if result.post_ptr_raw is not None else result.raw_pcm
        blocks.append((result.raw_pcm, post, result.monitor_pcm))
    return blocks


def _render_monitor_step_pcm(config: dict[str, Any], architecture: str) -> tuple[list[tuple[np.ndarray, np.ndarray, np.ndarray]], dict[str, float]]:
    """Exercise the stateful monitor with a deterministic attack-to-release input.

    The ordinary engine probe remains the default.  This renderer is intentionally
    limited to monitor-policy controls: low-RMS blocks first raise makeup gain, then
    higher-RMS blocks make desired gain lower than the held state and enter release.
    """
    from ..stage_w.persistent_engine import PersistentEventDomainEngine

    engine = PersistentEventDomainEngine(copy.deepcopy(config), 48000, 960, ptr_enabled=True, **_engine_settings(architecture))
    sample_rate = engine.sample_rate_hz
    block_size = engine.block_size
    sample_index = np.arange(block_size, dtype=np.float64)

    def tone_block(rms: float, block_index: int) -> np.ndarray:
        time_s = (block_index * block_size + sample_index) / sample_rate
        mono = rms * np.sqrt(2.0) * np.sin(2.0 * np.pi * 233.0 * time_s)
        return np.column_stack((mono, mono))

    raw_blocks: list[np.ndarray] = []
    for index in range(60):
        raw_blocks.append(tone_block(0.02, index))
    for index in range(60, 100):
        raw_blocks.append(tone_block(0.15, index))
    diagnostic = engine.monitor_diagnostic_trace(raw_blocks)
    raw_pcm = np.concatenate(raw_blocks, axis=0)
    evidence = {
        "attack_gain_start_db": float(diagnostic.gain_trace_db[0]),
        "attack_gain_end_db": float(diagnostic.gain_trace_db[59]),
        "release_desired_gain_db": float(diagnostic.desired_gain_trace_db[60]),
        "release_gain_end_db": float(diagnostic.gain_trace_db[-1]),
    }
    return [(raw_pcm, raw_pcm, diagnostic.monitor_pcm)], evidence


def _render_parameter_probe(
    item: SearchParameter, config: dict[str, Any], traces: list[Any]
) -> tuple[list[tuple[np.ndarray, np.ndarray, np.ndarray]], dict[str, float]]:
    if item.probe_mode in {"engine", "afterfire_residual"}:
        blocks = _render_config_pcm(config, item.architecture, traces)
        if _engine_settings(item.architecture)["forced_induction_model"] == "timbre_map_v1":
            fitted_map = config["fitted_timbre_map"]
            return blocks, {
                "fitted_timbre_map_schema": fitted_map["schema"],
                "fitted_timbre_map_fixture_sha256": fitted_map["fixture_sha256"],
                "fitted_timbre_map_file_sha256": hashlib.sha256(MAP_PATH.read_bytes()).hexdigest(),
                "require_fitted_timbre_map": bool(config["require_fitted_timbre_map"]),
            }
        return blocks, {}
    if item.probe_mode == "monitor_step":
        return _render_monitor_step_pcm(config, item.architecture)
    raise ValueError(f"unsupported probe mode: {item.probe_mode}")


def _build_parameter_probe_trace(scene: str, duration_s: float) -> Any:
    """Build short, parameter-specific traces without changing bake-off scenes."""
    from ..contracts import VehicleStateTrace
    from ..stage_w.bakeoff import build_hellcat_bakeoff_trace

    if not scene.startswith("y1_"):
        return build_hellcat_bakeoff_trace(scene, duration_s)
    count = max(12, int(round(duration_s * 50.0)))
    time_s = np.arange(count, dtype=np.float64) / 50.0
    phase = np.linspace(0.0, 1.0, count, dtype=np.float64)
    if scene == "y1_blower_spectrum":
        rpm = np.full(count, 3000.0)
        load = np.full(count, 0.8)
        throttle = np.full(count, 0.8)
        acceleration = np.zeros(count, dtype=np.float64)
        return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()
    if scene == "y1_high_slew_tip_in":
        rpm = np.where(phase < 0.35, 1100.0, 4300.0)
        load = np.where(phase < 0.35, 0.12, 0.92)
        throttle = np.where(phase < 0.35, 0.10, 0.96)
    elif scene == "y1_idle_dip_recovery":
        rpm = np.interp(phase, (0.0, 0.24, 0.38, 0.68, 1.0), (980.0, 980.0, 650.0, 880.0, 860.0))
        load = np.full(count, 0.12)
        throttle = np.full(count, 0.03)
    elif scene == "y1_boost_attack":
        rpm = np.where(phase < 0.35, 2100.0, 4700.0)
        load = np.where(phase < 0.35, 0.15, 0.95)
        throttle = np.where(phase < 0.35, 0.12, 0.98)
    elif scene == "y1_precharged_boost_release":
        rpm = np.where(phase < 0.38, 4800.0, 4400.0)
        load = np.where(phase < 0.38, 0.95, 0.35)
        throttle = np.where(phase < 0.38, 0.98, 0.35)
    elif scene == "y1_bypass_threshold_sweep":
        rpm = np.full(count, 3200.0)
        throttle = np.interp(phase, (0.0, 0.24, 0.50, 0.76, 1.0), (0.08, 0.16, 0.24, 0.32, 0.18))
        load = 0.12 + 0.76 * throttle
    elif scene == "y1_monitor_descending_gain":
        rpm = np.where(phase < 0.35, 900.0, 4600.0)
        load = np.where(phase < 0.35, 0.15, 0.94)
        throttle = np.where(phase < 0.35, 0.12, 0.96)
    else:
        raise ValueError(f"unsupported Y1 probe scene: {scene}")
    acceleration = np.gradient(rpm / 60.0, time_s)
    return VehicleStateTrace(time_s, rpm, load, throttle, acceleration).validate()


def run_parameter_reachability(
    output_root,
    traces: list[Any],
    metric_stem: str = "post_ptr",
    *,
    architecture: str = "P2H",
    tolerance: float = 0.02,
    parameter_names: tuple[str, ...] | list[str] | None = None,
    write_artifact: bool = True,
) -> dict[str, Any]:
    """Render baseline and +/- delta per parameter; classify reachability.

    A parameter is reachable when: both directions render finite audio, the
    post-PCM WAV-equivalent bytes differ from baseline, at least one target
    metric moves by more than tolerance, and guard metrics stay within a
    bounded factor (5x the target movement). Consumption is proven by the
    config actually mutating the render, not by a declared flag.
    """
    from ..stage_w.bakeoff import _render_architecture  # local import avoids cycles in docs

    root = output_root
    if write_artifact:
        root.mkdir(parents=True, exist_ok=True)
    base_config = load_config("hellcat_v1")
    parameters = hellcat_search_parameters()
    if parameter_names is not None:
        requested = tuple(parameter_names)
        available = {item.name for item in parameters}
        unknown = [name for name in requested if name not in available]
        if unknown:
            raise KeyError(f"unknown selected search parameters: {unknown}")
        selected = set(requested)
        parameters = [item for item in parameters if item.name in selected]

    def _stem_blocks(blocks: list[tuple[np.ndarray, np.ndarray, np.ndarray]], stem: str) -> list[np.ndarray]:
        index = {"raw": 0, "post_ptr": 1, "monitor": 2}[stem]
        return [block[index] for block in blocks]

    def _render_reachability_probe(
        item: SearchParameter, config: dict[str, Any], item_traces: list[Any]
    ) -> tuple[list[np.ndarray], list[np.ndarray], dict[str, Any]]:
        """Return selected-stem PCM for SHA and metric PCM for the declared probe.

        Afterfire uses actual selected post-PTR PCM for the byte-level acceptance
        gate, but subtracts an otherwise identical zero-afterfire-gain render for
        metric evaluation.  Other probes use the selected stem for both.
        """
        blocks, evidence = _render_parameter_probe(item, config, item_traces)
        selected_stem = _stem_blocks(blocks, item.stem)
        if item.probe_mode != "afterfire_residual":
            return selected_stem, selected_stem, evidence
        control_config = copy.deepcopy(config)
        _set_parameter(control_config, "afterfire.gain", 0.0)
        control_blocks = _render_config_pcm(control_config, item.architecture, item_traces)
        control_stem = _stem_blocks(control_blocks, item.stem)
        if len(selected_stem) != len(control_stem) or any(actual.shape != control.shape for actual, control in zip(selected_stem, control_stem)):
            raise ValueError("afterfire residual control shape differs from selected post-PTR PCM")
        residual = [actual - control for actual, control in zip(selected_stem, control_stem)]
        return selected_stem, residual, evidence | {
            "afterfire_gain_zero_control": True,
            "afterfire_residual_domain": "selected_post_ptr_minus_identical_gain_zero_control",
        }

    results = []
    for item in parameters:
        record: dict[str, Any] = {
            "parameter": item.name,
            "baseline": item.baseline,
            "delta": item.delta,
            "unit": item.unit,
            "target_metrics": list(item.target_metrics),
            "note": item.note,
            "probe_architecture": item.architecture,
            "probe_scenes": [scene for scene, _ in item.scenes],
            "probe_stem": item.stem,
            "probe_mode": item.probe_mode,
        }
        movement: dict[str, float] = {}
        direction_evidence: dict[str, dict[str, Any]] = {}
        item_traces = [_build_parameter_probe_trace(scene, duration) for scene, duration in item.scenes]
        item_baseline, item_baseline_metrics_pcm, probe_evidence = _render_reachability_probe(item, base_config, item_traces)
        if probe_evidence:
            record["probe_evidence"] = probe_evidence
        baseline_bytes = b"".join(block.tobytes() for block in item_baseline)
        item_baseline_metrics = _pcm_metrics(item_baseline_metrics_pcm)
        for direction, sign in (("minus", -1.0), ("plus", 1.0)):
            value = item.baseline + sign * item.delta
            config = copy.deepcopy(base_config)
            item.apply(config, value)
            try:
                pcm_blocks, metric_pcm_blocks, _ = _render_reachability_probe(item, config, item_traces)
            except Exception as error:  # noqa: BLE001 - reachability must classify, not crash
                direction_evidence[direction] = {
                    "value": float(value),
                    "finite": False,
                    "sha_changed": False,
                    "target_movement": 0.0,
                    "error": str(error),
                }
                continue
            if not all(np.all(np.isfinite(block)) for block in pcm_blocks):
                direction_evidence[direction] = {
                    "value": float(value),
                    "finite": False,
                    "sha_changed": False,
                    "target_movement": 0.0,
                    "error": "non-finite selected-stem PCM",
                }
                continue
            variant_bytes = b"".join(block.tobytes() for block in pcm_blocks)
            sha_changed = hashlib.sha256(variant_bytes).hexdigest() != hashlib.sha256(baseline_bytes).hexdigest()
            variant_metrics = _pcm_metrics(metric_pcm_blocks)
            direction_movement: dict[str, float] = {}
            for metric, value_pair in variant_metrics.items():
                base_value = item_baseline_metrics[metric]
                change = abs(value_pair - base_value) / max(abs(base_value), 1e-9)
                direction_movement[metric] = float(change)
                movement[metric] = max(movement.get(metric, 0.0), change)
            direction_evidence[direction] = {
                "value": float(value),
                "finite": True,
                "sha_changed": sha_changed,
                "target_movement": float(max((direction_movement.get(name, 0.0) for name in item.target_metrics), default=0.0)),
                "metric_movement": {name: float(metric_value) for name, metric_value in sorted(direction_movement.items())},
            }
        target_movement = max((movement.get(name, 0.0) for name in item.target_metrics), default=0.0)
        directional_ok = all(
            direction_evidence.get(direction, {}).get("finite")
            and direction_evidence[direction]["sha_changed"]
            and direction_evidence[direction]["target_movement"] > tolerance
            for direction in ("minus", "plus")
        )
        guard_violation = any(
            movement.get(name, 0.0) > max(5.0 * target_movement, 0.5) for name in item.guard_metrics
        )
        if not directional_ok:
            status = PARAMETER_NOT_REACHABLE
            reason = "both perturbation directions must be finite, change selected-stem PCM, and exceed tolerance"
        elif guard_violation:
            status = PARAMETER_NOT_REACHABLE
            reason = "guard metric moved out of bounds"
        else:
            status = PARAMETER_REACHABLE
            reason = f"target movement {target_movement:.4f}"
        record.update({
            "status": status,
            "reason": reason,
            "metric_movement": {name: float(value) for name, value in sorted(movement.items())},
            "directions": direction_evidence,
        })
        results.append(record)
    summary = {
        "schema": REACHABILITY_SCHEMA,
        "architecture": architecture,
        "protocol": "per-parameter targeted probe: architecture + scenes + stem declared on each SearchParameter",
        "metric_stem": metric_stem,
        "selected_parameter_names": list(parameter_names) if parameter_names is not None else None,
        "parameter_count": len(results),
        "reachable_count": sum(1 for item in results if item["status"] == PARAMETER_REACHABLE),
        "unreachable": [item["parameter"] for item in results if item["status"] != PARAMETER_REACHABLE],
        "results": results,
        "scope": "synthetic; uncalibrated; vehicle-inspired; not OEM reproduction",
    }
    if write_artifact:
        write_json(root / "parameter_reachability.json", summary)
    return summary


def _pcm_metrics(blocks: list[np.ndarray]) -> dict[str, float]:
    """Metric vector over the concatenated scene set (post-PCM domain)."""
    stereo = np.concatenate(blocks, axis=0) if blocks else np.zeros((1, 2))
    concat = stereo.mean(axis=1)
    sample_rate = 48000
    metrics = raw_dynamic_metrics(concat, sample_rate)
    timbre = timbre_metrics(concat, sample_rate)
    return {
        "crest": metrics["crest_db"],
        "dynamic_range": metrics["dynamic_range_db"],
        "transient_density": metrics["transient_event_density_per_s"],
        "low_band_share": timbre["fine_band_shares"][0] + timbre["fine_band_shares"][1],
        "band_120_400": timbre["fine_band_shares"][2] + timbre["fine_band_shares"][3],
        "mid_band_share": timbre["fine_band_shares"][4] + timbre["fine_band_shares"][5],
        "high_band_share": timbre["fine_band_shares"][6] + timbre["fine_band_shares"][7],
        "tonality": timbre["tonality_proxy"],
        "sharpness": timbre["sharpness_proxy"],
        "roughness": timbre["roughness_proxy"],
        "flux": timbre["spectral_flux"],
        "centroid": timbre["spectral_centroid_hz"],
        "early_energy_share": _window_energy_share(concat, 0.00, 0.35),
        "transition_energy_share": _window_energy_share(concat, 0.35, 0.60),
        "late_energy_share": _window_energy_share(concat, 0.65, 1.00),
        "afterfire_residual_energy_envelope": _afterfire_residual_energy_envelope(stereo, sample_rate),
        "afterfire_residual_onset": _afterfire_residual_onset(stereo, sample_rate),
        "afterfire_residual_peak_offset": _afterfire_residual_peak_offset(stereo, sample_rate),
        "afterfire_residual_path_balance": _afterfire_residual_path_balance(stereo, sample_rate),
        "afterfire_residual_crest": _afterfire_residual_crest(stereo, sample_rate),
        "early_path_balance": _early_path_balance(stereo, sample_rate),
        "high_slew_high_band_share": _window_high_band_share(concat, sample_rate, 0.30, 0.40),
        "idle_recovery_window_rms": _window_rms(concat, 0.775, 0.80),
        "path_window_rms": _window_rms(concat, 0.15, 0.45),
        "blower_window_rms": _window_rms(concat, 0.35, 0.70),
        "blower_sideband_narrowband_share": _blower_sideband_narrowband_share(concat, sample_rate),
        "blower_broadband_narrowband_share": _blower_broadband_narrowband_share(concat, sample_rate),
        "blower_casing_narrowband_share": _blower_casing_narrowband_share(concat, sample_rate),
        "boost_attack_envelope_rms": _window_rms(concat, 0.40, 0.425),
        "boost_release_envelope_rms": _window_rms(concat, 0.5875, 0.6125),
        "bypass_sweep_window_rms": _window_rms(concat, 0.2625, 0.2875),
        "blower_component_high_band_share": _window_high_band_share(concat, sample_rate, 0.30, 0.40),
        "monitor_attack_envelope_rms": _window_rms(concat, 0.05, 0.30),
        "monitor_release_envelope_rms": _window_rms(concat, 0.65, 0.95),
        "monitor_makeup_envelope_rms": _window_rms(concat, 0.45, 0.55),
    }


__all__ = [
    "METRIC_FUNCS",
    "PARAMETER_NOT_REACHABLE",
    "PARAMETER_REACHABLE",
    "REACHABILITY_SCHEMA",
    "SearchParameter",
    "apply_parameters",
    "hellcat_search_parameters",
    "run_parameter_reachability",
]
