"""Reference-driven tuning around the successful Stage-AD EngineAcoustics renderer.

Stage AF intentionally does *not* replace ``EngineAcoustics``.  It exposes a
small set of physically meaningful controls already present in that renderer,
keeps its successful Engine-Sim-inspired synthesis path, and adds a deterministic
analysis-by-synthesis feedback loop around it.

Evidence boundary: public-video references remain R3/private diagnostic.  A low
numerical distance is not Human PASS, R1 calibration or OEM reproduction.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
from scipy.stats import qmc

from ..stage_ad import engine_sim_acoustics as stage_ad_audio

SAMPLE_RATE = 48_000


@dataclass(frozen=True)
class VehicleFitSpec:
    idle_rpm: float
    redline_rpm: float
    pull_start_rpm: float
    pull_end_rpm: float
    has_induction: bool


VEHICLE_SPECS: dict[str, VehicleFitSpec] = {
    "hellcat": VehicleFitSpec(720.0, 6500.0, 1500.0, 6200.0, True),
    "ferrari_458": VehicleFitSpec(1050.0, 9000.0, 2200.0, 8800.0, False),
    "lfa": VehicleFitSpec(850.0, 9500.0, 2200.0, 9300.0, False),
    "gtr_r35": VehicleFitSpec(700.0, 7200.0, 1600.0, 6900.0, True),
}


@dataclass(frozen=True)
class FitParameter:
    name: str
    family: str
    minimum: float
    maximum: float
    baseline: float
    description: str


# Ratios deliberately stay near the hand-tuned main=f81d3a3 baseline.  The goal
# is refinement, not re-synthesis from scratch.
FAMILY_PARAMETERS: dict[str, tuple[FitParameter, ...]] = {
    "body": (
        FitParameter("exhaust_gain_scale", "body", 0.82, 1.18, 1.0, "combustion/exhaust body scale before existing renderer normalization"),
        FitParameter("mechanical_resonance_scale", "body", 0.82, 1.18, 1.0, "existing mechanical/body resonance frequency scale"),
        FitParameter("df_mix_scale", "body", 0.72, 1.28, 1.0, "existing acoustic dF/F pressure-velocity contribution"),
    ),
    "path": (
        FitParameter("primary_length_scale", "path", 0.78, 1.22, 1.0, "all primary runner lengths; preserves per-cylinder spread"),
        FitParameter("exhaust_length_scale", "path", 0.88, 1.12, 1.0, "tail-pipe propagation length"),
        FitParameter("ir_volume_scale", "path", 0.72, 1.28, 1.0, "existing exhaust transfer/IR contribution"),
    ),
    "induction": (
        FitParameter("air_noise_scale", "induction", 0.72, 1.28, 1.0, "existing flow/turbulence contribution"),
        FitParameter("df_mix_scale", "induction", 0.82, 1.18, 1.0, "pressure derivative contribution around induction transitions"),
    ),
    "afterfire": (
        FitParameter("afterfire_scale", "afterfire", 0.35, 1.20, 1.0, "event energy supplied to the existing afterfire path"),
    ),
}

FIT_SCENES = ("hot_idle", "steady_mid", "full_pull", "afterfire")
REFERENCE_FILENAMES = {
    "hot_idle": "ref_hot_idle.wav",
    "steady_mid": "ref_steady_mid.wav",
    "full_pull": "ref_full_pull.wav",
    "afterfire": "ref_afterfire.wav",
}


@dataclass(frozen=True)
class PhysicalFitResult:
    vehicle: str
    reference_level: str
    families: tuple[str, ...]
    overrides: dict[str, float]
    baseline_distance: float
    final_distance: float
    rounds: list[dict[str, Any]]
    seed: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = "s12.stage_af.physical_fit.v1"
        payload["scope"] = "R3/R2 diagnostic analysis-by-synthesis; Human A/B remains final gate"
        return payload


class TunableEngineAcoustics:
    """Thin adapter around the *existing* good-sounding EngineAcoustics.

    It intentionally avoids a second synthesis path.  All audio still comes from
    ``stage_ad.engine_sim_acoustics.EngineAcoustics.render_track``.
    """

    def __init__(
        self,
        vehicle_type: str,
        sr: int = SAMPLE_RATE,
        overrides: Mapping[str, float] | None = None,
        seed: int = 20260906,
    ) -> None:
        if vehicle_type not in VEHICLE_SPECS:
            raise ValueError(f"unsupported vehicle: {vehicle_type}")
        self.vehicle_type = vehicle_type
        self.sr = int(sr)
        self.seed = int(seed)
        self.overrides = {str(k): float(v) for k, v in (overrides or {}).items()}
        self.engine = stage_ad_audio.EngineAcoustics(vehicle_type=vehicle_type, sr=sr)
        self._apply_overrides()

    def _apply_overrides(self) -> None:
        e = self.engine
        o = self.overrides
        e.exhaust_gain *= o.get("exhaust_gain_scale", 1.0)
        e.mechanical_resonance_freq *= o.get("mechanical_resonance_scale", 1.0)
        e.dF_F_mix *= o.get("df_mix_scale", 1.0)
        e.air_noise_amount *= o.get("air_noise_scale", 1.0)
        e.ir_volume *= o.get("ir_volume_scale", 1.0)
        e.primary_lengths = np.asarray(e.primary_lengths, dtype=np.float64) * o.get("primary_length_scale", 1.0)
        e.exhaust_length = float(e.exhaust_length) * o.get("exhaust_length_scale", 1.0)
        # Preserve the exact baseline model's 343 m/s assumption.  A later stage
        # may make temperature stateful only after A/B evidence proves it helps.
        e.delays_sec = (e.primary_lengths + e.exhaust_length) / 343.0

    def render_track(
        self,
        rpm_curve: np.ndarray,
        throttle_curve: np.ndarray,
        duration: float,
        shift_events: list | None = None,
        afterfire_events: list | None = None,
        bov_events: list | None = None,
    ) -> np.ndarray:
        scaled_afterfire = afterfire_events
        scale = self.overrides.get("afterfire_scale", 1.0)
        if afterfire_events:
            scaled_afterfire = [(float(t), float(v) * scale) for t, v in afterfire_events]
        # The baseline renderer uses a few global numpy random calls.  Seed only
        # for this render and restore caller state afterwards so candidate search
        # is repeatable without contaminating the rest of the process.
        state = np.random.get_state()
        np.random.seed(self.seed)
        try:
            return self.engine.render_track(
                rpm_curve,
                throttle_curve,
                duration,
                shift_events=shift_events,
                afterfire_events=scaled_afterfire,
                bov_events=bov_events,
            )
        finally:
            np.random.set_state(state)


def _curve(start: float, end: float, duration: float, sr: int) -> np.ndarray:
    return np.linspace(start, end, int(round(duration * sr)), endpoint=False, dtype=np.float64)


def build_fit_scene(vehicle: str, scene: str, sr: int = SAMPLE_RATE) -> tuple[np.ndarray, np.ndarray, float, list | None, list | None, list | None]:
    spec = VEHICLE_SPECS[vehicle]
    if scene == "hot_idle":
        duration = 2.4
        rpm = np.full(int(sr * duration), spec.idle_rpm, dtype=np.float64)
        throttle = np.full_like(rpm, 0.10)
        return rpm, throttle, duration, None, None, None
    if scene == "steady_mid":
        duration = 2.4
        target = min(spec.redline_rpm * 0.48, 4200.0)
        rpm = np.full(int(sr * duration), target, dtype=np.float64)
        throttle = np.full_like(rpm, 0.34)
        return rpm, throttle, duration, None, None, None
    if scene == "full_pull":
        duration = 3.6
        rpm = _curve(spec.pull_start_rpm, spec.pull_end_rpm, duration, sr)
        throttle = np.ones_like(rpm)
        return rpm, throttle, duration, None, None, None
    if scene == "afterfire":
        duration = 3.0
        n = int(sr * duration)
        split = int(1.05 * sr)
        rpm = np.empty(n, dtype=np.float64)
        rpm[:split] = np.linspace(spec.redline_rpm * 0.70, spec.redline_rpm * 0.82, split, endpoint=False)
        rpm[split:] = np.linspace(spec.redline_rpm * 0.82, spec.idle_rpm * 1.4, n - split, endpoint=False)
        throttle = np.ones(n, dtype=np.float64)
        throttle[split:] = 0.04
        events = [(1.10, 0.80), (1.36, 0.46), (1.66, 0.30)]
        return rpm, throttle, duration, None, events, None
    raise ValueError(f"unsupported fit scene: {scene}")


def _to_float_mono(audio: np.ndarray) -> np.ndarray:
    arr = np.asarray(audio)
    if np.issubdtype(arr.dtype, np.integer):
        info = np.iinfo(arr.dtype)
        arr = arr.astype(np.float64) / max(abs(info.min), info.max)
    else:
        arr = arr.astype(np.float64)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    if arr.ndim != 1 or arr.size < 32 or not np.all(np.isfinite(arr)):
        raise ValueError("audio must be finite non-empty mono/stereo PCM")
    return arr


def _feature_vector(audio: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    x = _to_float_mono(audio)
    peak = float(np.max(np.abs(x)))
    if peak > 0:
        x = x / peak  # base EngineAcoustics already scene-normalizes; compare timbre/envelope, not loudness claims.
    f, _, z = stft(x, fs=sr, nperseg=2048, noverlap=1536, boundary=None, padded=False)
    p = np.abs(z) ** 2 + 1e-12
    mean_p = np.mean(p, axis=1)
    bands = ((20,80),(80,160),(160,400),(400,1000),(1000,2500),(2500,5000),(5000,10000),(10000,18000))
    band_db = []
    total = float(np.sum(mean_p)) + 1e-12
    for lo, hi in bands:
        mask = (f >= lo) & (f < hi)
        energy = float(np.sum(mean_p[mask])) if np.any(mask) else 1e-12
        band_db.append(np.log10(energy / total + 1e-12))
    centroid = float(np.sum(f * mean_p) / total) / (sr * 0.5)
    # Envelope shape / transient density.  This helps afterfire and shift-like scenes
    # without letting raw sample alignment dominate the fit.
    frame = 1024
    count = max(1, x.size // frame)
    env = np.sqrt(np.mean(np.square(x[: count * frame].reshape(count, frame)), axis=1) + 1e-12)
    env_mean = float(np.mean(env)) + 1e-12
    env_cv = float(np.std(env) / env_mean)
    env_peak = float(np.max(env) / env_mean)
    flux = float(np.mean(np.maximum(np.diff(np.log(env + 1e-9)), 0.0))) if env.size > 1 else 0.0
    return np.asarray([*band_db, centroid, env_cv, env_peak, flux], dtype=np.float64)


def fixed_reference_distance(candidate: np.ndarray, reference: np.ndarray, sr: int = SAMPLE_RATE) -> float:
    """A fixed, scene-independent ruler for analysis-by-synthesis ranking."""
    a = _feature_vector(candidate, sr)
    b = _feature_vector(reference, sr)
    scale = np.maximum(np.abs(b), 0.15)
    return float(np.median(np.abs(a - b) / scale))


def load_reference_audio(reference_dir: str | Path) -> dict[str, np.ndarray]:
    root = Path(reference_dir)
    found: dict[str, np.ndarray] = {}
    for scene, filename in REFERENCE_FILENAMES.items():
        candidates = (root / filename, root / "web_audio" / filename, root / "references" / filename)
        for path in candidates:
            if path.is_file():
                sr, audio = wavfile.read(path)
                if int(sr) != SAMPLE_RATE:
                    # Linear resampling is sufficient for diagnostic metric binding;
                    # final A/B source bytes remain untouched by this function.
                    values = _to_float_mono(audio)
                    target_n = max(32, int(round(values.size * SAMPLE_RATE / int(sr))))
                    audio = np.interp(
                        np.linspace(0, 1, target_n, endpoint=False),
                        np.linspace(0, 1, values.size, endpoint=False),
                        values,
                    )
                found[scene] = audio
                break
    if not found:
        raise FileNotFoundError(f"no governed reference WAV found under {root}")
    return found


def _render_scenes(vehicle: str, overrides: Mapping[str, float], references: Mapping[str, np.ndarray], seed: int) -> dict[str, np.ndarray]:
    renderer = TunableEngineAcoustics(vehicle, overrides=overrides, seed=seed)
    rendered: dict[str, np.ndarray] = {}
    for scene in references:
        rpm, throttle, duration, shift, afterfire, bov = build_fit_scene(vehicle, scene)
        rendered[scene] = renderer.render_track(rpm, throttle, duration, shift, afterfire, bov)
    return rendered


def evaluate_overrides(vehicle: str, overrides: Mapping[str, float], references: Mapping[str, np.ndarray], seed: int) -> tuple[float, dict[str, float]]:
    rendered = _render_scenes(vehicle, overrides, references, seed)
    distances = {scene: fixed_reference_distance(rendered[scene], references[scene]) for scene in references}
    return float(np.median(list(distances.values()))), distances


def _sample_family(parameters: Iterable[FitParameter], count: int, seed: int, center: Mapping[str, float] | None = None, shrink: float = 1.0) -> list[dict[str, float]]:
    params = list(parameters)
    sampler = qmc.Sobol(d=len(params), scramble=True, seed=seed)
    unit = sampler.random(max(1, count))
    samples: list[dict[str, float]] = []
    for row in unit:
        candidate: dict[str, float] = {}
        for p, u in zip(params, row):
            if center and p.name in center:
                half = 0.5 * (p.maximum - p.minimum) * shrink
                lo = max(p.minimum, float(center[p.name]) - half)
                hi = min(p.maximum, float(center[p.name]) + half)
            else:
                lo, hi = p.minimum, p.maximum
            candidate[p.name] = float(lo + (hi - lo) * u)
        samples.append(candidate)
    return samples


def fit_vehicle(
    vehicle: str,
    reference_dir: str | Path,
    *,
    families: Iterable[str] = ("body", "path", "induction", "afterfire"),
    base_overrides: Mapping[str, float] | None = None,
    candidates_per_round: int = 12,
    max_rounds: int = 3,
    plateau_fraction: float = 0.01,
    seed: int = 20260906,
    reference_level: str = "R3_PRIVATE_DIAGNOSTIC_ONLY",
) -> PhysicalFitResult:
    if vehicle not in VEHICLE_SPECS:
        raise ValueError(vehicle)
    references = load_reference_audio(reference_dir)
    selected_families = [f for f in families if f in FAMILY_PARAMETERS]
    if not VEHICLE_SPECS[vehicle].has_induction:
        selected_families = [f for f in selected_families if f != "induction"]
    current = {str(k): float(v) for k, v in (base_overrides or {}).items()}
    baseline_distance, baseline_scenes = evaluate_overrides(vehicle, current, references, seed)
    best_distance = baseline_distance
    rounds: list[dict[str, Any]] = [{"stage":"baseline","distance":baseline_distance,"scene_distances":baseline_scenes,"overrides":dict(current)}]

    for family_index, family in enumerate(selected_families):
        params = FAMILY_PARAMETERS[family]
        family_center = {p.name: current.get(p.name, p.baseline) for p in params}
        previous_family_best = best_distance
        for round_index in range(max_rounds):
            shrink = 1.0 if round_index == 0 else 0.45 ** round_index
            candidates = _sample_family(params, candidates_per_round, seed + family_index * 100 + round_index, family_center, shrink)
            candidates.insert(0, dict(family_center))
            scored: list[tuple[float, dict[str,float], dict[str,float]]] = []
            for candidate_family in candidates:
                merged = dict(current)
                merged.update(candidate_family)
                distance, scene_distances = evaluate_overrides(vehicle, merged, references, seed)
                scored.append((distance, candidate_family, scene_distances))
            scored.sort(key=lambda item: item[0])
            distance, family_center, scene_distances = scored[0]
            merged_best = dict(current); merged_best.update(family_center)
            rounds.append({
                "stage": family,
                "round": round_index,
                "distance": distance,
                "scene_distances": scene_distances,
                "family_overrides": dict(family_center),
                "overrides": merged_best,
                "candidate_count": len(scored),
            })
            improvement = (best_distance - distance) / max(best_distance, 1e-9)
            if distance < best_distance:
                best_distance = distance
            if round_index > 0 and improvement < plateau_fraction:
                break
        current.update(family_center)
        # Never keep a family if it made the fixed ruler worse.
        final_family_distance, _ = evaluate_overrides(vehicle, current, references, seed)
        if final_family_distance > previous_family_best:
            for p in params:
                if p.name in current:
                    current[p.name] = p.baseline if p.name not in (base_overrides or {}) else float(base_overrides[p.name])
            best_distance, _ = evaluate_overrides(vehicle, current, references, seed)
        else:
            best_distance = final_family_distance

    return PhysicalFitResult(
        vehicle=vehicle,
        reference_level=reference_level,
        families=tuple(selected_families),
        overrides=current,
        baseline_distance=baseline_distance,
        final_distance=best_distance,
        rounds=rounds,
        seed=seed,
    )


def write_fit_result(result: PhysicalFitResult, output_dir: str | Path) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    config_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["fit_sha256"] = hashlib.sha256(config_bytes).hexdigest()
    path = root / "final_r3_diagnostic_fit.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (root / "fit_history.json").write_text(json.dumps(result.rounds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
