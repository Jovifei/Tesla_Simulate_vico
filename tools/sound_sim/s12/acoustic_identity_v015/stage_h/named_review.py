"""Named Stage-H engineering audition package builder.

This package is intentionally not a blind package: it exposes vehicle names so
Jovi can locate Hellcat-specific defects before a later anonymous qualification
round.  No Stage-G sealed key is read.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np

from ..acoustic_analysis import compute_engine_identity_metrics, compute_order_map, write_order_map, write_spectrogram
from ..contracts import SourceRender, VehicleStateTrace
from ..loudness_manager import manage_bundle_loudness, measure_loudness
from ..render_drive_cycle_v10 import build_drive_cycle_trace
from ..render_identity_v02 import _apply_frozen_ptr, _edge_fade, _health, _read_pcm24_wav, _write_pcm24_wav
from ..stage_d.scenarios import build_stage_d_scenario_trace
from ..stage_g.candidate_profiles import load_stage_g_candidate
from ..stage_g.render_candidate import render_stage_g_candidate
from .candidate_profiles import load_stage_h_candidate
from .perceptual_metrics import compute_hellcat_perceptual_metrics
from .render_candidate import render_stage_h_candidate


_SAMPLE_RATE_HZ = 48000
_VEHICLES = ("ferrari_458", "hellcat", "rx7_fd")
_STAGE_G_FILENAMES = {"ferrari_458": "Ferrari_candidate_v4.json", "hellcat": "Hellcat_candidate_v4.json", "rx7_fd": "RX7_candidate_v4.json"}
_PIPELINE = (
    "independent_source", "idle_dynamics", "deterministic_afterfire", "low_frequency_body",
    "exhaust_rumble", "shift_dynamics", "transient_peak_shaping", "pre_ptr_equalization",
    "frozen_ptr", "edge_fade", "fixed_whole_cycle_gain", "pcm24",
)


def build_stage_h_named_review(
    output_root: str | Path,
    *,
    stage_h_candidate_path: str | Path | None = None,
    stage_g_candidate_root: str | Path | None = None,
    duration_s: float = 60.0,
) -> dict[str, object]:
    """Render named Stage-G/H comparison evidence and stop before human input."""
    if not np.isfinite(duration_s) or duration_s < 2.0:
        raise ValueError("duration_s must be finite and >= 2.0")
    root = Path(output_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"named Stage-H output must be a new directory: {root}")
    for relative in ("01_Hellcat", "02_Anchor_Mapping", "03_Metrics", "04_Feedback"):
        (root / relative).mkdir(parents=True, exist_ok=True)

    package_root = Path(__file__).resolve().parents[1]
    stage_g_root = Path(stage_g_candidate_root) if stage_g_candidate_root else package_root / "targets" / "stage_g_candidates"
    stage_h_path = Path(stage_h_candidate_path) if stage_h_candidate_path else package_root / "targets" / "stage_h_candidates" / "Hellcat_candidate_v5.json"
    stage_g = {vehicle: load_stage_g_candidate(stage_g_root / filename) for vehicle, filename in _STAGE_G_FILENAMES.items()}
    stage_h = load_stage_h_candidate(stage_h_path)
    candidates_dir = root / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    for vehicle, filename in _STAGE_G_FILENAMES.items():
        _copy(stage_g_root / filename, candidates_dir / f"{vehicle}_StageG_candidate_v4.json")
    _copy(stage_h_path, candidates_dir / "hellcat_StageH_candidate_v5.json")

    evidence_dir = root / "source_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _copy(package_root / "targets" / "hellcat_supercharger_target_v1.json", evidence_dir / "hellcat_supercharger_target_v1.json")
    _copy(package_root / "reference_database" / "Hellcat_Supercharger_Acoustic_Study_v1.md", evidence_dir / "Hellcat_Supercharger_Acoustic_Study_v1.md")
    (evidence_dir / "online_reference_matrix.json").write_text(json.dumps({
        "official_hardware": [
            "https://blog.stellantisnorthamerica.com/2015/11/10/can-you-name-that-engine-day-ii/",
            "https://blog.stellantisnorthamerica.com/2022/08/15/the-cat-is-back-2023-dodge-durango-srt-hellcat-most-powerful-suv-ever-returns-to-dodge-lineup/",
        ],
        "listening_context": ["https://www.dodgegarage.com/news/article/video/2022/05/driving-every-modern-dodge-performance-vehicle-on-the-road-and-track-part-ii"],
        "sae_context": ["https://saemobilus.sae.org/articles/nvh-integration-twin-charger-direct-injected-gasoline-engine-2014-01-2087"],
        "provenance": "A hardware facts; B/R2 relative listening context; C synthetic candidate assumptions",
    }, indent=2) + "\n", encoding="utf-8", newline="\n")

    full_cycle: dict[str, dict[str, object]] = {}
    for vehicle in _VEHICLES:
        trace = build_drive_cycle_trace(vehicle, duration_s=duration_s)
        g_source = render_stage_g_candidate(vehicle, trace, stage_g[vehicle])
        h_source = render_stage_h_candidate(vehicle, trace, stage_h) if vehicle == "hellcat" else g_source
        g_audio, g_info = _write_final(root / "01_Hellcat" if vehicle == "hellcat" else root / "02_Anchor_Mapping", _named_filename(vehicle, "StageG_Baseline" if vehicle == "hellcat" else "StageG_Unchanged"), g_source, trace)
        h_audio, h_info = _write_final(root / "01_Hellcat" if vehicle == "hellcat" else root / "02_Anchor_Mapping", _named_filename(vehicle, "StageH_Candidate" if vehicle == "hellcat" else "StageG_Unchanged"), h_source, trace)
        full_cycle[vehicle] = {
            "stage_g": {**g_info, "source_metrics": compute_engine_identity_metrics(vehicle, g_source, trace)},
            "stage_h": {**h_info, "source_metrics": compute_engine_identity_metrics(vehicle, h_source, trace)},
            "trace": {"duration_s": float(trace.time_s[-1]), "rpm_start": float(trace.rpm[0]), "rpm_end": float(trace.rpm[-1]), "pipeline": list(_PIPELINE)},
        }
        if vehicle == "hellcat":
            full_cycle[vehicle]["stage_g"]["hellcat_perceptual_metrics"] = _legacy_hellcat_metrics(g_source, trace)
            full_cycle[vehicle]["stage_h"]["hellcat_perceptual_metrics"] = compute_hellcat_perceptual_metrics(h_source, trace)

    # Hellcat diagnostic acceleration stems are intentionally named and are not
    # used as product audio or anonymous identity evidence.
    acceleration_trace = build_stage_d_scenario_trace("hellcat", "acceleration", duration_s=8.0)
    g_acc = render_stage_g_candidate("hellcat", acceleration_trace, stage_g["hellcat"])
    h_acc = render_stage_h_candidate("hellcat", acceleration_trace, stage_h)
    _write_named_stem(root / "01_Hellcat" / "03_Hellcat_StageG_BlowerOnly_Acceleration.wav", g_acc, "blower", acceleration_trace)
    _write_named_stem(root / "01_Hellcat" / "04_Hellcat_StageH_BlowerOnly_Acceleration.wav", h_acc, "blower", acceleration_trace)
    _write_named_stem(root / "01_Hellcat" / "05_Hellcat_StageH_ExhaustOnly_Acceleration.wav", h_acc, "exhaust", acceleration_trace)

    metrics = {"scope": "C/synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction", "vehicle": "hellcat", "stage_g": full_cycle["hellcat"]["stage_g"], "stage_h": full_cycle["hellcat"]["stage_h"], "duration_s": duration_s, "pipeline": list(_PIPELINE), "status": "WAITING_FOR_JOVI_NAMED_CALIBRATION"}
    (root / "03_Metrics" / "hellcat_before_after_metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    candidate_audio = _read_pcm24_wav(root / "01_Hellcat" / "02_Hellcat_StageH_Candidate_60s.wav")
    trace = build_drive_cycle_trace("hellcat", duration_s=duration_s)
    write_spectrogram(root / "03_Metrics" / "spectrogram.png", candidate_audio, _SAMPLE_RATE_HZ)
    write_order_map(root / "03_Metrics" / "blower_order_map.png", compute_order_map(candidate_audio, trace, _SAMPLE_RATE_HZ))
    (root / "03_Metrics" / "stem_energy_map.png").write_bytes(_render_stem_energy_png(metrics))

    feedback_path = root / "04_Feedback" / "Jovi_Stage_H_Named_Feedback.csv"
    _write_feedback_template(feedback_path)
    (root / "00_OPEN_ME_FIRST.md").write_text(_open_me_first(root), encoding="utf-8", newline="\n")
    (root / "artifact_manifest.json").write_text(json.dumps({"package_id": "S12_Stage_H_Named_Review_v1", "status": "WAITING_FOR_JOVI_NAMED_CALIBRATION", "source_sha256": {"stage_g": {v: _sha256(stage_g_root / f) for v, f in _STAGE_G_FILENAMES.items()}, "stage_h": _sha256(stage_h_path)}, "provenance": "synthetic; uncalibrated; Hellcat-inspired; not OEM reproduction", "sealed_key_read": False}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    zip_path = root / "S12_Stage_H_Named_Review.zip"
    _zip_tree(zip_path, root, exclude={zip_path.name, "SHA256SUMS.txt"})
    _write_sha256sums(root)
    return {"package_id": "S12_Stage_H_Named_Review_v1", "output_root": str(root), "status": "WAITING_FOR_JOVI_NAMED_CALIBRATION", "core_wavs": [str(path) for path in sorted((root / "01_Hellcat").glob("*.wav"))], "zip": str(zip_path), "metrics": metrics}


def _source_for_stem(render: SourceRender, stem: str) -> np.ndarray:
    if stem not in render.stems:
        return np.zeros_like(render.pressure)
    return np.asarray(render.stems[stem], dtype=np.float64)


def _write_final(directory: Path, filename: str, source: SourceRender, trace: VehicleStateTrace) -> tuple[np.ndarray, dict[str, object]]:
    ptr = _edge_fade(_apply_frozen_ptr(source.pressure))
    managed = manage_bundle_loudness({"cycle": ptr}, _SAMPLE_RATE_HZ, target_lufs=-16.0, peak_limit_dbfs=-1.5)
    path = _write_pcm24_wav(directory / filename, managed.segments["cycle"])
    reopened = _read_pcm24_wav(path)
    health = _health(reopened)
    if float(health["peak_dbfs"]) > -1.5 + 1e-6 or int(health["clipping_count"]) != 0:
        raise ValueError(f"named WAV health gate failed: {path}")
    return reopened, {"path": str(path), "sha256": _sha256(path), "loudness": _loudness(measure_loudness(reopened)), "gain_db": managed.gain_db, "headroom_limited": managed.headroom_limited, "health": health}


def _write_named_stem(path: Path, source: SourceRender, stem: str, trace: VehicleStateTrace) -> None:
    raw = _edge_fade(_apply_frozen_ptr(_source_for_stem(source, stem)))
    managed = manage_bundle_loudness({"stem": raw}, _SAMPLE_RATE_HZ, target_lufs=-20.0, peak_limit_dbfs=-1.5)
    _write_pcm24_wav(path, managed.segments["stem"])


def _legacy_hellcat_metrics(source: SourceRender, trace: VehicleStateTrace) -> dict[str, object]:
    return dict(compute_engine_identity_metrics("hellcat", source, trace).get("hellcat", {}))


def _loudness(metrics) -> dict[str, object]:
    return {"integrated_lufs": float(metrics.integrated_lufs), "rms_dbfs": float(metrics.rms_dbfs), "peak_dbfs": float(metrics.peak_dbfs), "crest_factor_db": float(metrics.crest_factor_db), "clipping_count": int(metrics.clipping_count)}


def _named_filename(vehicle: str, role: str) -> str:
    if vehicle == "hellcat":
        return f"{1 if role == 'StageG_Baseline' else 2:02d}_Hellcat_{role}_60s.wav"
    names = {"ferrari_458": "Ferrari_458", "rx7_fd": "RX7_FD"}
    return f"{names[vehicle]}_{role}_60s.wav"


def _open_me_first(root: Path) -> str:
    files = sorted((root / "01_Hellcat").glob("*.wav"))
    lines = ["# S12 Stage H - Open Me First", "", "Status: `WAITING_FOR_JOVI_NAMED_CALIBRATION`", "", "This is a named engineering package. It is not the Stage G anonymous blind package and no sealed key was read.", "", "## Listen in this order", "", f"1. `{root / '01_Hellcat' / '01_Hellcat_StageG_Baseline_60s.wav'}` - Stage G baseline.", f"2. `{root / '01_Hellcat' / '02_Hellcat_StageH_Candidate_60s.wav'}` - Stage H candidate; listen for the load-dependent '滋滋哟' whine while the low V8 body remains primary.", f"3. `{root / '01_Hellcat' / '03_Hellcat_StageG_BlowerOnly_Acceleration.wav'}` and `{root / '01_Hellcat' / '04_Hellcat_StageH_BlowerOnly_Acceleration.wav'}` - engineering isolation only.", f"4. `{root / '01_Hellcat' / '05_Hellcat_StageH_ExhaustOnly_Acceleration.wav'}` - confirms exhaust remains the anchor.", "", "## Timeline", "", "0-8 s idle; 8-26 s acceleration with 3 shifts; 26-36 s full pull; 36-46 s lift/afterfire/bypass; 46-52 s coast; 52-60 s idle return.", "", "Then listen to the named Ferrari/RX-7 files in `02_Anchor_Mapping` to identify which earlier anonymous clip was harsh and which was strong. Do not infer their mapping from the sealed Stage G package.", "", "All outputs are synthetic, uncalibrated, Hellcat-inspired and not OEM reproduction.", ""]
    return "\n".join(lines)


def _write_feedback_template(path: Path) -> None:
    fields = ("file_id", "vehicle_id", "hellcat_likeness_1_5", "whine_presence_1_5", "whine_naturalness_1_5", "low_frequency_weight_1_5", "high_frequency_harshness_1_5", "artifact_freedom_1_5", "keep_or_change", "notes")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for file_id, vehicle in (("01_Hellcat_StageG_Baseline_60s", "hellcat"), ("02_Hellcat_StageH_Candidate_60s", "hellcat"), ("03_Hellcat_StageG_BlowerOnly_Acceleration", "hellcat"), ("04_Hellcat_StageH_BlowerOnly_Acceleration", "hellcat"), ("05_Hellcat_StageH_ExhaustOnly_Acceleration", "hellcat"), ("Ferrari_458_StageG_Unchanged_60s", "ferrari_458"), ("RX7_FD_StageG_Unchanged_60s", "rx7_fd")):
            writer.writerow({"file_id": file_id, "vehicle_id": vehicle, "keep_or_change": ""})


def _render_stem_energy_png(metrics: Mapping[str, object]) -> bytes:
    # Keep package generation usable on headless machines; the chart itself is
    # a compact SVG-like text image only when matplotlib is unavailable.
    try:
        import matplotlib.pyplot as plt
        import io
        hellcat = metrics["stage_h"]["hellcat_perceptual_metrics"]  # type: ignore[index]
        figure, axis = plt.subplots(figsize=(7, 3))
        axis.bar(("blower", "exhaust", "rumble"), [hellcat.get("blower_energy", 0.0), hellcat.get("exhaust_energy", 0.0), hellcat.get("rumble_energy", 0.0)])
        axis.set_title("Stage H Hellcat stem energy (synthetic)")
        axis.set_ylabel("energy")
        buffer = io.BytesIO(); figure.tight_layout(); figure.savefig(buffer, format="png", dpi=120); plt.close(figure)
        return buffer.getvalue()
    except Exception:
        return b"Stage H stem energy chart unavailable; see JSON metrics.\n"


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _zip_tree(output: Path, root: Path, exclude: set[str]) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name in exclude:
                continue
            info = zipfile.ZipInfo(path.relative_to(root).as_posix()); info.date_time = (2020, 1, 1, 0, 0, 0); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _write_sha256sums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(f"{_sha256(path)}  {path.relative_to(root).as_posix()}\n")
    (root / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8", newline="\n")


__all__ = ("build_stage_h_named_review",)
