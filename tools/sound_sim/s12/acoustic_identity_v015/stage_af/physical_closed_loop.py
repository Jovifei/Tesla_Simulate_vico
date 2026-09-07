"""Reference-driven tuning around the successful Stage-AD EngineAcoustics renderer.

Stage AF intentionally does *not* replace ``EngineAcoustics``. It exposes a
small set of physically meaningful controls already present in that renderer,
keeps its successful Engine-Sim-inspired synthesis path, and adds a deterministic
analysis-by-synthesis feedback loop around it.

Evidence boundary: public-video references remain R3/private diagnostic. A low
numerical distance is not Human PASS, R1 calibration or OEM reproduction.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.io import wavfile
from scipy.signal import stft, resample_poly
from scipy.stats import qmc

from ..stage_ad import engine_sim_acoustics as stage_ad_audio
from .package_integrity import dependency_fingerprint, fit_identity_projection
from .spectral_guard import multires_spectral_distance

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


# Ratios stay close to the hand-tuned main=f81d3a3 baseline. The objective is
# refinement of a Human-approved direction, not re-synthesis from scratch.
FAMILY_PARAMETERS: dict[str, tuple[FitParameter, ...]] = {
    "body": (
        FitParameter(
            "exhaust_gain_scale",
            "body",
            0.82,
            1.18,
            1.0,
            "existing combustion/exhaust body contribution",
        ),
        FitParameter(
            "mechanical_resonance_scale",
            "body",
            0.82,
            1.18,
            1.0,
            "existing mechanical/body resonance frequency",
        ),
        FitParameter(
            "df_mix_scale",
            "body",
            0.72,
            1.28,
            1.0,
            "existing acoustic dF/F pressure-velocity contribution",
        ),
    ),
    "path": (
        FitParameter(
            "primary_length_scale",
            "path",
            0.78,
            1.22,
            1.0,
            "all primary runner lengths while preserving cylinder spread",
        ),
        FitParameter(
            "exhaust_length_scale",
            "path",
            0.88,
            1.12,
            1.0,
            "existing tail-pipe propagation length",
        ),
        FitParameter(
            "ir_volume_scale",
            "path",
            0.72,
            1.28,
            1.0,
            "existing exhaust IR/transfer contribution",
        ),
    ),
    "induction": (
        FitParameter(
            "air_noise_scale",
            "induction",
            0.72,
            1.28,
            1.0,
            "existing flow/turbulence contribution around load and induction",
        ),
    ),
    "afterfire": (
        FitParameter(
            "afterfire_scale",
            "afterfire",
            0.35,
            1.20,
            1.0,
            "event energy supplied to the existing afterfire path",
        ),
    ),
}

# Each physical family is judged on scenes where that family is actually
# observable. This avoids an afterfire improvement being hidden by three
# unrelated steady-state scenes.
FAMILY_SCENES: dict[str, tuple[str, ...]] = {
    "body": ("hot_idle", "steady_mid", "full_pull"),
    "path": ("steady_mid", "full_pull"),
    "induction": ("steady_mid", "full_pull"),
    "afterfire": ("afterfire",),
}

FIT_SCENES = ("hot_idle", "steady_mid", "full_pull", "afterfire")
REFERENCE_FILENAMES = {
    "hot_idle": "ref_hot_idle.wav",
    "steady_mid": "ref_steady_mid.wav",
    "full_pull": "ref_full_pull.wav",
    "afterfire": "ref_afterfire.wav",
}
IR_NAMES = {
    "hellcat": "test_engine_16_eq_adjusted_16",
    "ferrari_458": "mild_exhaust_reverb",
    "lfa": "mild_exhaust_reverb",
    "gtr_r35": "test_engine_14_eq_adjusted_16",
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
    numerical_fixes: tuple[str, ...] = ()
    renderer_identity: dict[str, Any] = field(default_factory=dict)
    reference_sources: dict[str, Any] = field(default_factory=dict)
    scene_inputs_sha256: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = "s12.stage_af.physical_fit.v5"
        payload["objective"] = "mean_features_plus_multires_spectrum.v1"
        payload["numerical_fixes"] = sorted(self.numerical_fixes)
        payload["human_status"] = "NOT_EVALUATED_THIS_FIT"
        payload["gain_policy"] = "legacy_per_scene_peak_tanh_preserved"
        payload["state_alignment"] = "SYNTHETIC_SCENE_NOT_SYNCHRONIZED_REAL_RPM"
        payload["trajectory_scope"] = "fit scenes differ from longer dashboard scenes; both require listening"
        payload["scope"] = (
            "R3/R2 diagnostic analysis-by-synthesis; numerical improvement "
            "proposes candidates only; Human A/B remains final gate"
        )
        payload["fit_identity"] = fit_identity_projection(self.renderer_identity)
        return payload


class TunableEngineAcoustics:
    """Thin adapter around the existing good-sounding EngineAcoustics.

    All audio still comes from
    ``stage_ad.engine_sim_acoustics.EngineAcoustics.render_track``.
    """

    def __init__(
        self,
        vehicle_type: str,
        sr: int = SAMPLE_RATE,
        overrides: Mapping[str, float] | None = None,
        seed: int = 20260906,
        numerical_fixes: Sequence[str] = (),
    ) -> None:
        if vehicle_type not in VEHICLE_SPECS:
            raise ValueError(f"unsupported vehicle: {vehicle_type}")
        self.vehicle_type = vehicle_type
        self.sr = int(sr)
        self.seed = int(seed)
        self.overrides = {str(k): float(v) for k, v in (overrides or {}).items()}
        limits = {p.name:p for group in FAMILY_PARAMETERS.values() for p in group}
        for name, value in self.overrides.items():
            if name not in limits or not np.isfinite(value):
                raise ValueError(f"unknown/non-finite physical parameter: {name}")
            if not limits[name].minimum <= value <= limits[name].maximum:
                raise ValueError(f"physical parameter outside approved bounds: {name}")
        self.engine = stage_ad_audio.EngineAcoustics(
            vehicle_type=vehicle_type, sr=sr, numerical_fixes=numerical_fixes
        )
        self._apply_overrides()

    def _apply_overrides(self) -> None:
        e = self.engine
        o = self.overrides
        e.exhaust_gain *= o.get("exhaust_gain_scale", 1.0)
        e.mechanical_resonance_freq *= o.get("mechanical_resonance_scale", 1.0)
        e.dF_F_mix *= o.get("df_mix_scale", 1.0)
        e.air_noise_amount *= o.get("air_noise_scale", 1.0)
        e.ir_volume *= o.get("ir_volume_scale", 1.0)
        e.primary_lengths = np.asarray(e.primary_lengths, dtype=np.float64) * o.get(
            "primary_length_scale", 1.0
        )
        e.exhaust_length = float(e.exhaust_length) * o.get(
            "exhaust_length_scale", 1.0
        )
        # Keep the exact f81d3a3 baseline propagation assumption. Changing the
        # sound-speed model is a separate hypothesis and must earn its own A/B.
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
            scaled_afterfire = [
                (float(event_time), float(intensity) * scale)
                for event_time, intensity in afterfire_events
            ]

        # The baseline renderer has several global np.random calls. Seed only
        # around this render and restore the caller state afterwards. This makes
        # parameter comparisons reproducible without changing the proven source.
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
    return np.linspace(
        start,
        end,
        int(round(duration * sr)),
        endpoint=False,
        dtype=np.float64,
    )


def build_fit_scene(
    vehicle: str,
    scene: str,
    sr: int = SAMPLE_RATE,
) -> tuple[np.ndarray, np.ndarray, float, list | None, list | None, list | None]:
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
        rpm[:split] = np.linspace(
            spec.redline_rpm * 0.70,
            spec.redline_rpm * 0.82,
            split,
            endpoint=False,
        )
        rpm[split:] = np.linspace(
            spec.redline_rpm * 0.82,
            spec.idle_rpm * 1.4,
            n - split,
            endpoint=False,
        )
        throttle = np.ones(n, dtype=np.float64)
        throttle[split:] = 0.04
        events = [(1.10, 0.80), (1.36, 0.46), (1.66, 0.30)]
        return rpm, throttle, duration, None, events, None
    raise ValueError(f"unsupported fit scene: {scene}")


def _to_float_mono(audio: np.ndarray) -> np.ndarray:
    arr = np.asarray(audio)
    if arr.dtype == np.uint8:
        arr = (arr.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(arr.dtype, np.integer):
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
    if peak > 0.0:
        # f81d3a3 normalizes each scene itself. The Stage-AF metric therefore
        # judges timbre/envelope and makes no absolute loudness claim.
        x = x / peak

    frequencies, _, spectrum = stft(
        x,
        fs=sr,
        nperseg=min(2048, x.size),
        noverlap=3 * min(2048, x.size) // 4,
        boundary=None,
        padded=False,
    )
    power = np.abs(spectrum) ** 2 + 1e-12
    mean_power = np.mean(power, axis=1)
    total = float(np.sum(mean_power)) + 1e-12
    bands = (
        (20, 80),
        (80, 160),
        (160, 400),
        (400, 1000),
        (1000, 2500),
        (2500, 5000),
        (5000, 10000),
        (10000, 18000),
    )
    band_log_ratios: list[float] = []
    for low_hz, high_hz in bands:
        mask = (frequencies >= low_hz) & (frequencies < high_hz)
        energy = float(np.sum(mean_power[mask])) if np.any(mask) else 1e-12
        band_log_ratios.append(np.log10(energy / total + 1e-12))

    centroid = float(np.sum(frequencies * mean_power) / total) / (sr * 0.5)

    frame = min(1024, x.size)
    frame_count = max(1, x.size // frame)
    framed = x[: frame_count * frame].reshape(frame_count, frame)
    envelope = np.sqrt(np.mean(np.square(framed), axis=1) + 1e-12)
    envelope_mean = float(np.mean(envelope)) + 1e-12
    envelope_cv = float(np.std(envelope) / envelope_mean)
    envelope_peak = float(np.max(envelope) / envelope_mean)
    positive_flux = (
        float(np.mean(np.maximum(np.diff(np.log(envelope + 1e-9)), 0.0)))
        if envelope.size > 1
        else 0.0
    )
    return np.asarray(
        [*band_log_ratios, centroid, envelope_cv, envelope_peak, positive_flux],
        dtype=np.float64,
    )


def fixed_reference_distance(
    candidate: np.ndarray,
    reference: np.ndarray,
    sr: int = SAMPLE_RATE,
) -> float:
    """V3 diagnostic ruler; old v2 scores/thresholds are NOT comparable.

    Preserve coarse timbre/envelope features but do not let a coordinate median
    discard a pitch error. Add multi-resolution full-spectrum distance.
    Still not an RPM-aligned temporal/order validation or Human realism score.
    """
    candidate_features = _feature_vector(candidate, sr)
    reference_features = _feature_vector(reference, sr)
    scale = np.maximum(np.abs(reference_features), 0.15)
    coarse = float(np.mean(np.abs(candidate_features - reference_features) / scale))
    spectral = multires_spectral_distance(candidate, reference, sr)
    return coarse + spectral


def load_reference_audio(reference_dir: str | Path) -> dict[str, np.ndarray]:
    root = Path(reference_dir)
    found: dict[str, np.ndarray] = {}
    for scene, filename in REFERENCE_FILENAMES.items():
        candidates = (
            root / filename,
            root / "web_audio" / filename,
            root / "references" / filename,
        )
        for path in candidates:
            if not path.is_file():
                continue
            source_sr, audio = wavfile.read(path)
            if int(source_sr) != SAMPLE_RATE:
                values = _to_float_mono(audio)
                divisor = math.gcd(int(source_sr), SAMPLE_RATE)
                audio = resample_poly(values, SAMPLE_RATE // divisor, int(source_sr) // divisor)
            found[scene] = audio
            break
    if not found:
        raise FileNotFoundError(f"no governed reference WAV found under {root}")
    return found


def _select_references(
    references: Mapping[str, np.ndarray],
    scenes: Sequence[str] | None,
) -> dict[str, np.ndarray]:
    if scenes is None:
        return dict(references)
    selected = {scene: references[scene] for scene in scenes if scene in references}
    if not selected:
        raise ValueError(f"no reference scenes available from requested set: {scenes}")
    return selected


def _render_scenes(
    vehicle: str,
    overrides: Mapping[str, float],
    references: Mapping[str, np.ndarray],
    seed: int,
    numerical_fixes: Sequence[str] = (),
) -> dict[str, np.ndarray]:
    renderer = TunableEngineAcoustics(vehicle, overrides=overrides, seed=seed,
                                    numerical_fixes=numerical_fixes)
    rendered: dict[str, np.ndarray] = {}
    for scene in references:
        rpm, throttle, duration, shift, afterfire, bov = build_fit_scene(
            vehicle, scene
        )
        rendered[scene] = renderer.render_track(
            rpm,
            throttle,
            duration,
            shift,
            afterfire,
            bov,
        )
    return rendered


def evaluate_overrides(
    vehicle: str,
    overrides: Mapping[str, float],
    references: Mapping[str, np.ndarray],
    seed: int,
    *,
    scenes: Sequence[str] | None = None,
    numerical_fixes: Sequence[str] = (),
) -> tuple[float, dict[str, float]]:
    selected = _select_references(references, scenes)
    rendered = _render_scenes(vehicle, overrides, selected, seed, numerical_fixes)
    distances = {
        scene: fixed_reference_distance(rendered[scene], selected[scene])
        for scene in selected
    }
    return float(np.mean(list(distances.values()))), distances


def _sample_family(
    parameters: Iterable[FitParameter],
    count: int,
    seed: int,
    center: Mapping[str, float] | None = None,
    shrink: float = 1.0,
) -> list[dict[str, float]]:
    params = list(parameters)
    if not params:
        return [{}]
    wanted = max(1, int(count))
    exponent = max(0, int(math.ceil(math.log2(wanted))))
    unit = qmc.Sobol(d=len(params), scramble=True, seed=seed).random_base2(exponent)
    unit = unit[:wanted]
    samples: list[dict[str, float]] = []
    for row in unit:
        candidate: dict[str, float] = {}
        for parameter, value in zip(params, row):
            if center and parameter.name in center:
                half_width = (
                    0.5
                    * (parameter.maximum - parameter.minimum)
                    * float(shrink)
                )
                low = max(
                    parameter.minimum,
                    float(center[parameter.name]) - half_width,
                )
                high = min(
                    parameter.maximum,
                    float(center[parameter.name]) + half_width,
                )
            else:
                low, high = parameter.minimum, parameter.maximum
            candidate[parameter.name] = float(low + (high - low) * value)
        samples.append(candidate)
    return samples


def _resolve_ir_source(vehicle: str) -> Path:
    library_dir = Path(os.environ.get("S12_ENGINE_SIM_IR_ROOT", stage_ad_audio.SOUND_LIB_DIR))
    name = IR_NAMES[vehicle]
    candidates = (
        library_dir / "new" / f"{name}.wav",
        library_dir / "archive" / f"{name}.wav",
        library_dir / "smooth" / f"{name}.wav",
        library_dir / f"{name}.wav",
    )
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError(f"Could not resolve IR source for {vehicle}: {name} in {library_dir}")


def renderer_identity(vehicle: str, numerical_fixes: Sequence[str] = ()) -> dict[str, Any]:
    renderer = TunableEngineAcoustics(vehicle, numerical_fixes=numerical_fixes)
    ir_source = _resolve_ir_source(vehicle)
    fingerprints = dependency_fingerprint()
    return {
        "vehicle": vehicle,
        "sample_rate": SAMPLE_RATE,
        "renderer": "stage_ad.engine_sim_acoustics.EngineAcoustics",
        "source_sha256": hashlib.sha256(Path(stage_ad_audio.__file__).read_bytes()).hexdigest(),
        "ir_source_path": str(ir_source),
        "ir_source_sha256": hashlib.sha256(ir_source.read_bytes()).hexdigest(),
        "ir_effective_sha256": hashlib.sha256(np.asarray(renderer.engine.ir, dtype="<f8").tobytes()).hexdigest(),
        "ir_provenance": "LOCAL_ASSET_REQUIRES_SEPARATE_RIGHTS_RECEIPT",
        "ir_rights_status": "UNVERIFIED_LOCAL_ASSET",
        "numerical_fixes": sorted(renderer.engine.numerical_fixes),
        "audio_runtime_fingerprint": fingerprints["audio_runtime_fingerprint"],
        "fit_algorithm_fingerprint": fingerprints["fit_algorithm_fingerprint"],
        "package_ui_fingerprint": fingerprints["package_ui_fingerprint"],
    }


def reference_sources(reference_dir: str | Path) -> dict[str, Any]:
    root = Path(reference_dir)
    result = {}
    for scene, name in REFERENCE_FILENAMES.items():
        for path in (root/name, root/"web_audio"/name, root/"references"/name):
            if path.is_file():
                result[scene] = {"path": str(path.resolve()), "filename": name,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                break
    return result


def validate_fit_payload(payload: Mapping[str, Any], vehicle: str,
                         numerical_fixes: Sequence[str], seed: int) -> dict[str, float]:
    if payload.get("schema") != "s12.stage_af.physical_fit.v5":
        raise ValueError("old/unversioned fit cannot be silently reused; refit on current main")
    if payload.get("vehicle") != vehicle or payload.get("seed") != seed:
        raise ValueError("fit vehicle/seed mismatch")
    if sorted(payload.get("numerical_fixes", [])) != sorted(numerical_fixes):
        raise ValueError("fit/render numerical mode mismatch")
    if payload.get("reference_level") not in (
        "R3_PRIVATE_DIAGNOSTIC_ONLY",
        "R2_AUTHORIZED_DIAGNOSTIC",
    ):
        raise ValueError("unsupported reference evidence level")
    recorded_references = payload.get("reference_sources")
    if not isinstance(recorded_references, Mapping):
        raise ValueError("fit reference sources missing")
    missing_scenes = [scene for scene in FIT_SCENES if scene not in recorded_references]
    if missing_scenes:
        raise ValueError(f"fit reference missing: {','.join(missing_scenes)}")
    canonical = dict(payload)
    checksum = canonical.pop("fit_sha256", None)
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    if checksum != hashlib.sha256(encoded).hexdigest():
        raise ValueError("fit checksum mismatch")
    recorded_identity = payload.get("renderer_identity")
    if not isinstance(recorded_identity, Mapping):
        raise ValueError("fit renderer identity missing")
    recorded_fit_identity = payload.get("fit_identity")
    if recorded_fit_identity != fit_identity_projection(recorded_identity):
        raise ValueError("fit identity projection missing or inconsistent")
    if fit_identity_projection(recorded_identity) != fit_identity_projection(
        renderer_identity(vehicle, numerical_fixes)
    ):
        raise ValueError("audio runtime/fit algorithm or IR changed; refit rather than fallback")
    return {str(k): float(v) for k, v in payload["overrides"].items()}


def per_scene_guard(candidate: Mapping[str, float], anchor: Mapping[str, float],
                    fraction: float, tolerance: float = 1e-10) -> bool:
    return candidate.keys() == anchor.keys() and all(
        np.isfinite(v) and v <= anchor[k] * (1.0 + fraction) + tolerance
        for k, v in candidate.items()
    )


def fit_vehicle(
    vehicle: str, reference_dir: str | Path, *,
    families: Iterable[str] = ("body", "path", "induction", "afterfire"),
    base_overrides: Mapping[str, float] | None = None,
    candidates_per_round: int = 8, max_rounds: int = 2,
    plateau_fraction: float = 0.01, max_global_regression_fraction: float = 0.03,
    seed: int = 20260906, reference_level: str = "R3_PRIVATE_DIAGNOSTIC_ONLY",
    numerical_fixes: Sequence[str] = (),
) -> PhysicalFitResult:
    if vehicle not in VEHICLE_SPECS:
        raise ValueError(f"unsupported vehicle: {vehicle}")
    if reference_level not in ("R3_PRIVATE_DIAGNOSTIC_ONLY", "R2_AUTHORIZED_DIAGNOSTIC"):
        raise ValueError("only explicit diagnostic evidence levels accepted; no inferred R1")
    if candidates_per_round < 1 or max_rounds < 1:
        raise ValueError("candidate and round budgets must be positive")
    if not 0 <= max_global_regression_fraction <= 0.1 or not 0 <= plateau_fraction < 1:
        raise ValueError("invalid bounded stopping/guard policy")
    identity = renderer_identity(vehicle, numerical_fixes)
    flags = tuple(identity["numerical_fixes"])
    references = load_reference_audio(reference_dir)
    sources = reference_sources(reference_dir)
    missing_scenes = [scene for scene in FIT_SCENES if scene not in sources]
    if missing_scenes:
        raise FileNotFoundError(
            f"missing required fit reference scenes: {','.join(missing_scenes)}"
        )
    selected_families = list(dict.fromkeys(families))
    if any(f not in FAMILY_PARAMETERS for f in selected_families):
        raise ValueError("unknown parameter family")
    if not VEHICLE_SPECS[vehicle].has_induction:
        selected_families = [f for f in selected_families if f != "induction"]
    current = {str(k): float(v) for k,v in (base_overrides or {}).items()}

    def score(overrides):
        return evaluate_overrides(vehicle, overrides, references, seed, numerical_fixes=flags)

    baseline_distance, baseline_scenes = score(current)
    rounds = [{"stage":"baseline", "distance":baseline_distance,
               "scene_distances":baseline_scenes, "overrides":dict(current)}]
    current_scenes = dict(baseline_scenes)
    for family_index, family in enumerate(selected_families):
        target_scenes = tuple(s for s in FAMILY_SCENES[family] if s in references)
        if not target_scenes:
            rounds.append({"stage":family,"status":"SKIPPED_NO_TARGET_REFERENCE"})
            continue
        params = FAMILY_PARAMETERS[family]
        start_target = float(np.mean([current_scenes[s] for s in target_scenes]))
        accepted_target = start_target
        for round_index in range(max_rounds):
            center = {p.name:current.get(p.name,p.baseline) for p in params}
            proposals = [center] + _sample_family(params,candidates_per_round,
                seed+100*family_index+round_index,center,0.45**round_index)
            candidates = []
            accepted = []
            for proposal in proposals:
                merged = dict(current); merged.update(proposal)
                overall, by_scene = score(merged)
                target = float(np.mean([by_scene[s] for s in target_scenes]))
                ok = per_scene_guard(by_scene, baseline_scenes, max_global_regression_fraction)
                item = {"target_distance":target,"overall_distance":overall,
                        "scene_distances":by_scene,"overrides":merged,"guard_pass":ok}
                candidates.append(item)
                if ok: accepted.append(item)
            # Never select an unguarded proposal, even when all candidates fail.
            winner = min(accepted,key=lambda r:(r["target_distance"],r["overall_distance"])) if accepted else None
            previous = accepted_target
            changed = winner is not None and winner["target_distance"] < accepted_target - 1e-12
            if changed:
                current = dict(winner["overrides"])
                current_scenes = dict(winner["scene_distances"])
                accepted_target = winner["target_distance"]
            improvement = (previous-accepted_target)/max(previous,1e-9)
            rounds.append({"stage":family,"round":round_index,"objective_scenes":list(target_scenes),
                "status":"ACCEPTED_PROPOSAL" if changed else "KEEP_PREVIOUS",
                "relative_target_improvement":improvement,"candidates":candidates,
                "guard_anchor":"INITIAL_BASELINE_EACH_SCENE","overrides":dict(current)})
            if improvement < plateau_fraction: break
        rounds.append({"stage":family,"status":"ACCEPTED" if accepted_target < start_target else "NO_IMPROVEMENT_KEEP_BASELINE",
                       "start_target_distance":start_target,"accepted_target_distance":accepted_target,
                       "overrides":dict(current)})
    final_distance, final_scenes = score(current)
    if not per_scene_guard(final_scenes, baseline_scenes, max_global_regression_fraction):
        raise RuntimeError("final candidate violates initial per-scene anchor")
    if renderer_identity(vehicle,flags) != identity or reference_sources(reference_dir) != sources:
        raise RuntimeError("renderer/IR/reference changed during fit; result not publishable")
    trace_hashes = {}
    for scene in references:
        rpm, throttle, duration, shift, afterfire, bov = build_fit_scene(vehicle,scene)
        data = np.asarray(rpm,dtype="<f8").tobytes()+np.asarray(throttle,dtype="<f8").tobytes()
        data += json.dumps([duration,shift,afterfire,bov],sort_keys=True).encode()
        trace_hashes[scene]=hashlib.sha256(data).hexdigest()
    return PhysicalFitResult(vehicle,reference_level,tuple(selected_families),current,
        baseline_distance,final_distance,rounds,seed,flags,identity,sources,trace_hashes)


def write_fit_result(
    result: PhysicalFitResult,
    output_dir: str | Path,
) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    canonical_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["fit_sha256"] = hashlib.sha256(canonical_bytes).hexdigest()
    path = root / "final_r3_diagnostic_fit.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "fit_history.json").write_text(
        json.dumps(result.rounds, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
