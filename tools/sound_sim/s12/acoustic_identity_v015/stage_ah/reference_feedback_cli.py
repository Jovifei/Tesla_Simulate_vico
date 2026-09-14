"""Run reference-driven fitting through the existing AH two-car audio engine.

No reference media is downloaded or committed. A versioned plan binds external
WAV bytes, source-disjoint splits, coarse state review and candidate windows.
Old B0/C0 packages are never modified. This run compares baseline/tuned C0 with
identical output policy, seed, traces, IR and BASELINE parent denominators.
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile

from .reference_feedback import (
    METRIC, SR, ReferenceCase, Rendered, SearchConfig, audio_sha,
    optimize_reference_feedback, pcm_float, validate_parameters, _validate_cases,
)

PLAN_SCHEMA = "s12.stage_ah.reference_feedback_plan.v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _runtime_identity() -> dict:
    root = Path(__file__).resolve().parents[5]
    scope = "tools/sound_sim/s12/acoustic_identity_v015"
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    if git("status", "--porcelain", "--untracked-files=all", "--", scope):
        raise ValueError("commit/stash scoped source changes before reference fitting")
    paths = git("ls-files", "--", scope).splitlines()
    if not paths:
        raise ValueError("source inventory is empty")
    hashes = {p: _sha(root / p) for p in paths if (root / p).is_file()}
    encoded = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return {"commit": git("rev-parse", "HEAD"), "scope": scope,
            "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
            "source_files": hashes, "source_status": "SOURCE_CLEAN"}


def prepare_plan(baseline_run: Path, destination: Path) -> None:
    """Prepare a reviewable plan from v5 clips; never fabricate state approval."""
    if destination.exists():
        raise FileExistsError(destination)
    bundle = baseline_run.resolve() / "reference_bundle"
    receipt_path = bundle / "reference_clip_receipt.json"
    receipt = _read(receipt_path)
    rows = []
    clips = list(receipt["clips"].values())
    for vehicle in sorted({c["vehicle"] for c in clips}):
        selected = [c for c in clips if c["vehicle"] == vehicle]
        groups = sorted({c["source_video_id"] for c in selected})
        if len(groups) < 2:
            raise ValueError("at least two independent recordings per vehicle required")
        holdout = set(groups[-max(1, len(groups)//3):])
        for c in selected:
            path = bundle / vehicle / c["filename"]
            if _sha(path) != c["sha256"]:
                raise ValueError("reference clip has changed")
            rows.append({
                "case_id": vehicle + "/" + c["scene_id"], "vehicle": vehicle,
                "scene": c["scene_id"], "source_id": c["source_video_id"],
                "source_sha256": c["source_sha256"], "wav_path": str(path),
                "wav_sha256": c["sha256"],
                "split": "validation" if c["source_video_id"] in holdout else "train",
                "candidate_window_s": [0.0, min(4.0, float(c["duration_s"]))],
                "comparable": False,
                "comparability_note": "REVIEW_REQUIRED: verify same coarse RPM/load/event state and candidate window; do not approve by filename alone",
            })
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write(destination, {"schema": PLAN_SCHEMA, "reference_level": "R3_UNSYNCHRONIZED",
                         "baseline_run": str(baseline_run.resolve()),
                         "reference_receipt_sha256": _sha(receipt_path), "cases": rows})


def load_plan(plan_path: Path) -> tuple[dict[str, list[ReferenceCase]], dict]:
    payload = _read(plan_path)
    if payload.get("schema") != PLAN_SCHEMA or payload.get("reference_level") != "R3_UNSYNCHRONIZED":
        raise ValueError("unsupported feedback plan schema/evidence level")
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("reference plan cases required")
    cases: dict[str, list[ReferenceCase]] = {}
    evidence = {"plan_sha256": _sha(plan_path), "reference_files": {}}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("reference case must be an object")
        for key in ("vehicle", "scene", "source_id"):
            if not isinstance(row.get(key), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", row[key]):
                raise ValueError(f"invalid reference identifier: {key}")
        path = Path(row["wav_path"])
        if not path.is_absolute():
            path = plan_path.resolve().parent / path
        path = path.resolve()
        if not path.is_file() or _sha(path) != row["wav_sha256"]:
            raise ValueError(f"reference WAV missing or hash mismatch: {path}")
        sr, audio = wavfile.read(path)
        if sr != SR:
            raise ValueError("reference WAV must already be governed 48000 Hz PCM")
        audio = pcm_float(audio)
        if float(np.mean(np.abs(audio) >= 0.999)) > 0.01:
            raise ValueError("heavily clipped reference must be reviewed/replaced, not fitted")
        case = ReferenceCase(row["case_id"], row["scene"], row["source_id"],
                             row["source_sha256"], row["split"], audio,
                             tuple(row["candidate_window_s"]), row["comparable"],
                             row["comparability_note"])
        cases.setdefault(row["vehicle"], []).append(case)
        evidence["reference_files"][str(path)] = row["wav_sha256"]
    for selected in cases.values():
        _validate_cases(selected)
    return cases, {**evidence, "plan": payload}


def numeric_ok(record: Mapping[str, Any]) -> bool:
    """Missing counters and invalid floats FAIL; they do not default to zero."""
    try:
        n = record["normalization"]
        for raw in (n["post_guard_ceiling_exceedance_samples"], n["emergency_clip_count"],
                    record["identity_layer_clip_count"], record["post_identity_clip_count"]):
            if isinstance(raw, bool) or not isinstance(raw, (int, np.integer)) or raw != 0:
                return False
        for value in (n["emergency_clip_error"], record["identity_layer_clip_error"],
                      record["post_identity_clip_error"]):
            if not np.isfinite(value) or value != 0:
                return False
        return bool(0 < record["final_rms"] <= record["final_peak"] <= 0.94 + 1e-10
                    and np.isfinite(record["peak_estimate_4x"]["peak"])
                    and 0 < record["peak_estimate_4x"]["peak"] <= 1.0)
    except (KeyError, TypeError, ValueError):
        return False


class RemainingFeedbackRenderer:
    """Named parameters enter the actual engine, not a surrogate audio model."""
    def __init__(self, vehicle: str, contexts: Mapping, parents: Mapping, ir: np.ndarray):
        from .remaining_vehicle_pipeline import FEEDBACK_BOUNDS, feedback_parameters
        self.vehicle, self.contexts = vehicle, dict(contexts)
        self.parents, self.ir = dict(parents), np.asarray(ir).copy()
        self.bounds = FEEDBACK_BOUNDS[vehicle]
        defaults = feedback_parameters(vehicle, ())["parameters"]
        self.baseline = {k: defaults[k] for k in self.bounds}
        self.last_records: dict[str, dict] = {}

    def __call__(self, parameters: Mapping[str, float], scene: str) -> Rendered:
        from .remaining_vehicle_pipeline import RemainingVehicleEngine
        from .output_guard import LINKED_SOFT_CEILING_V1
        params = validate_parameters(parameters, self.bounds)
        c = self.contexts[scene]
        engine = RemainingVehicleEngine(self.vehicle, SR, output_policy=LINKED_SOFT_CEILING_V1,
                    parent_peaks=self.parents, ir=self.ir, seed=20260908, scene_ids=(scene,))
        # Keep all non-whitelisted profile values unchanged. No fake human score.
        engine.feedback["parameters"].update(params)
        engine.feedback.update(controller="reference_analysis_by_synthesis_v1",
                               status="REFERENCE_TRIAL", adjustments=[])
        audio = engine.render_track(c["rpm"], c["throttle"], c["duration"],
                    shift_events=c["shift_events"], afterfire_events=c["afterfire_events"],
                    bov_events=c["bov_events"])
        record = copy.deepcopy(engine.reports[-1])
        if record["trace_sha256"] != c["trace_sha256"]:
            raise ValueError("trial trace differs from fixed baseline")
        if record["normalization_denominator"] != self.parents[record["parent_peak_key"]]:
            raise ValueError("trial changed the baseline denominator")
        self.last_records[scene] = record
        return Rendered(audio, numeric_ok(record), record)


def _baseline(vehicle: str, directory: Path):
    from .remaining_vehicle_package import _config, _dashboards, SCENE_IDS
    from .remaining_vehicle_pipeline import RemainingVehicleEngine
    from .output_guard import LINKED_SOFT_CEILING_V1
    cfg = _config(vehicle, directory, 0, "C0")
    engine = RemainingVehicleEngine(vehicle, SR, output_policy=LINKED_SOFT_CEILING_V1,
                                    seed=20260908, scene_ids=SCENE_IDS)
    contexts, records, hashes = {}, {}, {}
    def observe(**data):
        scene = data["scene_id"]
        report = copy.deepcopy(engine.reports[-1])
        if not numeric_ok(report):
            raise ValueError(f"baseline numeric gate failed: {scene}")
        contexts[scene] = {k: data[k] for k in ("rpm", "throttle", "duration",
                             "shift_events", "afterfire_events", "bov_events")}
        contexts[scene]["trace_sha256"] = report["trace_sha256"]
        records[scene], hashes[scene] = report, audio_sha(data["audio"])
    cfg["_render_observer"] = observe
    old = _dashboards.EngineAcoustics
    _dashboards.EngineAcoustics = lambda **kwargs: engine
    try:
        _dashboards.render_vehicle_audio(vehicle, cfg)
    finally:
        _dashboards.EngineAcoustics = old
    cfg.pop("_render_observer")
    return engine, cfg, contexts, records, hashes


def _dashboard(vehicle, cfg, result, reference_rows, group):
    from .remaining_vehicle_package import _dashboards
    cfg["title"] = f"[REFERENCE FEEDBACK / {group}] " + cfg["title"]
    cfg["subtitle"] = "基线与优化使用相同 C0 输出策略；误差是相对频谱形状，不是相似度百分比"
    refs = {}
    for scene in cfg["scenes"]:
        choices = [r for r in reference_rows if r["vehicle"] == vehicle and r["scene"] == scene["id"]]
        if choices:
            row = choices[0]
            source = Path(row["wav_path"])
            shutil.copy2(source, cfg["dir"] / "web_audio" / scene["ref_file"])
            refs[scene["ref_file"]] = {"available": True, "fit_required": False,
                "source_label": f"{row['source_id']} / {row['split']} / R3未同步",
                "sha256": row["wav_sha256"]}
        else:
            scene["ref_file"] = ""
    cfg["_dashboard_contract"] = {
        "schema": "s12.stage_ah.reference_feedback.dashboard.v1", "package_id": "REFERENCE_FEEDBACK",
        "candidate_id": group + "-" + vehicle, "vehicle": vehicle, "seed": 20260908,
        "flags": [], "fit_status": "BASELINE" if group == "BASELINE" else result["status"],
        "fit_metric_status": METRIC, "measurement_status": "R3_RELATIVE_ONLY_UNSYNCHRONIZED",
        "source_status": "SOURCE_CLEAN", "promotable": False,
        "promotion_status": "NOT_PROMOTABLE_R3", "references": refs,
        "human_status": "NOT_EVALUATED", "sample_rate_hz": SR,
        "nav_urls": {}, "parameters": [],
        "candidate_pcm_sha256": {s + ".wav": r["final_pcm_sha256"] for s, r in
            result["baseline_records" if group == "BASELINE" else "selected_records"].items()},
        "reference_sha256": {k: v["sha256"] for k, v in refs.items()},
    }
    old_template = _dashboards.TEMPLATE_PATH
    old_configs = _dashboards.VEHICLE_CONFIGS
    _dashboards.VEHICLE_CONFIGS = {vehicle: cfg}
    _dashboards.TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "stage_ad" / "audition_dashboard_template.html"
    try:
        _dashboards.build_dashboard(vehicle, cfg)
        template = _dashboards.TEMPLATE_PATH.read_text(encoding="utf-8")
        variable = re.search(r"const\s+(\w+)\s*=\s*__AUDIOS_JSON__", template)
        if variable is None:
            raise ValueError("dashboard audio-store contract changed")
        panel = ('<section style="padding:24px"><h2>真实录音驱动的参数闭环 / ' + group + '</h2>'
                 + '<p><a href="../../baseline/' + vehicle + '/index.html">基线 C0</a> | '
                 + '<a href="../../tuned/' + vehicle + '/index.html">优化 C0</a> | '
                 + '<a href="../../summary.json">完整测量、参数和拒绝历史</a></p>'
                 + '<p>相对频谱形状误差（不是相似度百分比）。Reference 未同步；没有 Human PASS。</p>'
                 + '<pre>' + html.escape(json.dumps({k: result[k] for k in
                    ("status", "baseline_train_loss", "selected_train_loss", "parameter_delta",
                     "validation_baseline", "validation_proposed")}, ensure_ascii=False, indent=2))
                 + '</pre></section>')
        for path in (cfg["dir"] / "index.html", cfg["dir"] / "index_standalone.html"):
            text = path.read_text(encoding="utf-8")
            match = re.search(r"const\s+" + re.escape(variable[1]) + r"\s*=\s*", text)
            store = json.JSONDecoder().raw_decode(text[match.end():])[0]
            for scene in cfg["scenes"]:
                for suffix, filename in (("candidate", scene["candidate_file"]), ("ref", scene["ref_file"])):
                    if filename:
                        raw = base64.b64decode(store[scene["id"] + "_" + suffix].split(",", 1)[1], validate=True)
                        if raw != (cfg["dir"] / "web_audio" / filename).read_bytes():
                            raise ValueError("embedded dashboard audio differs from governed WAV")
            # Remove the inert localhost:0 current-car URL; use the relative run navigator.
            text = text.replace('href="http://localhost:0/"', 'href="index.html"')
            path.write_text(text.replace("</header>", "</header>" + panel, 1), encoding="utf-8")
    finally:
        _dashboards.TEMPLATE_PATH = old_template
        _dashboards.VEHICLE_CONFIGS = old_configs


def run_plan(plan_path: Path, output: Path, *, config: SearchConfig = SearchConfig()) -> dict:
    from .remaining_vehicle_package import REMAINING_VEHICLES, SCENE_IDS, _config
    cases, evidence = load_plan(plan_path)
    if not set(cases) <= set(REMAINING_VEHICLES):
        raise ValueError("this adapter supports RX7/Aventador; other cars keep existing qualified paths")
    for selected in cases.values():
        if any(c.scene not in SCENE_IDS for c in selected):
            raise ValueError("unknown canonical scene")
    runtime = _runtime_identity()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / ("." + output.name + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    staging = None
    try:
        if output.exists():
            raise FileExistsError(output)
        staging = Path(tempfile.mkdtemp(prefix="." + output.name + "-", dir=output.parent))
        # Resolve plan paths once; all future reference copies use these bindings.
        for row in evidence["plan"]["cases"]:
            p = Path(row["wav_path"])
            row["wav_path"] = str((p if p.is_absolute() else plan_path.resolve().parent / p).resolve())
        _write(staging / "input_plan.json", evidence["plan"])
        results = {}
        for vehicle, selected in cases.items():
            base_dir, tuned_dir = staging / "baseline" / vehicle, staging / "tuned" / vehicle
            engine, cfg, contexts, records, hashes = _baseline(vehicle, base_dir)
            ir_source_hash = engine.ir_source_sha256
            renderer = RemainingFeedbackRenderer(vehicle, contexts, engine.parent_peaks, engine.ir)
            # Off-switch equivalence against the canonical baseline, all ten scenes.
            for scene in SCENE_IDS:
                if audio_sha(renderer(renderer.baseline, scene).audio) != hashes[scene]:
                    raise ValueError("feedback-disabled PCM differs from canonical baseline")
            result = optimize_reference_feedback(renderer.baseline, renderer.bounds, selected,
                                                   renderer, config=config)
            final_audio, final_records = {}, {}
            for scene in SCENE_IDS:
                r = renderer(result["selected_parameters"], scene)
                final_audio[scene], final_records[scene] = r.audio, r.diagnostics
            if not all(numeric_ok(r) for r in final_records.values()):
                result["status"] = "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK"
                result["selected_parameters"] = dict(renderer.baseline)
                result["parameter_delta"] = {k: 0.0 for k in renderer.baseline}
                result["selected_train_loss"] = result["baseline_train_loss"]
                for scene in SCENE_IDS:
                    r = renderer(renderer.baseline, scene)
                    final_audio[scene], final_records[scene] = r.audio, r.diagnostics
            web = tuned_dir / "web_audio"
            web.mkdir(parents=True)
            for scene, audio in final_audio.items():
                wavfile.write(web / (scene + ".wav"), SR, audio)
                wavfile.write(tuned_dir / (scene + ".wav"), SR, audio)
            result["baseline_records"], result["selected_records"] = records, final_records
            result["baseline_pcm_sha256"] = {s: r["final_pcm_sha256"] for s, r in records.items()}
            result["selected_pcm_sha256"] = {s: r["final_pcm_sha256"] for s, r in final_records.items()}
            if engine.ir_source_sha256 != ir_source_hash:
                raise ValueError("IR source changed during fitting")
            result["ir_source_sha256"] = ir_source_hash
            result["ir_effective_sha256"] = hashlib.sha256(np.asarray(engine.ir, dtype="<f8").tobytes()).hexdigest()
            result["off_switch_pcm_equal_count"] = len(hashes)
            _dashboard(vehicle, cfg, result, evidence["plan"]["cases"], "BASELINE")
            _dashboard(vehicle, _config(vehicle, tuned_dir, 0, "C0"), result,
                       evidence["plan"]["cases"], "TUNED")
            results[vehicle] = result
        for path, expected in evidence["reference_files"].items():
            if _sha(Path(path)) != expected:
                raise ValueError("reference changed during fitting")
        if _runtime_identity() != runtime:
            raise ValueError("source changed during fitting")
        summary = {"schema": "s12.stage_ah.reference_feedback_run.v1", "runtime": runtime,
                   "reference_evidence": evidence, "vehicles": results,
                   "output_policy": "linked_soft_ceiling_v1", "knee": 0.90, "ceiling": 0.94,
                   "comparison": "BASELINE_C0_VS_TUNED_C0_FIXED_BASELINE_DENOMINATORS",
                   "promotable": False, "human_status": "NOT_EVALUATED",
                   "self_contained_status": "AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY"}
        _write(staging / "summary.json", summary)
        links = "".join('<p>' + v + ': <a href="baseline/' + v + '/index.html">基线</a> / '
                         + '<a href="tuned/' + v + '/index.html">优化</a></p>' for v in results)
        (staging / "index.html").write_text('<!doctype html><meta charset="utf-8">'
            + '<title>S12 Reference Feedback</title><h1>真实录音驱动闭环实验</h1>' + links
            + '<p>两组都采用相同 C0 输出保护；不是旧 B0/C0 输出策略对照。'
            + 'R3 未同步；无相似度百分比或 Human PASS。</p><a href="summary.json">测量与完整历史</a>', encoding="utf-8")
        inventory = {p.relative_to(staging).as_posix(): _sha(p)
                     for p in staging.rglob("*") if p.is_file()}
        _write(staging / "ARTIFACTS.json", inventory)
        # Last operation inside the transaction: no rewriting after publication.
        staging.rename(output)
        staging = None
        return summary
    finally:
        if staging is not None:
            shutil.rmtree(staging)
        lock.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--baseline-run", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    fit = commands.add_parser("run")
    fit.add_argument("--plan", type=Path, required=True)
    fit.add_argument("--out", type=Path, required=True)
    fit.add_argument("--max-trials", type=int, default=25)
    fit.add_argument("--allow-r3-unsynchronized", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare_plan(args.baseline_run, args.out)
    else:
        if not args.allow_r3_unsynchronized:
            parser.error("explicit --allow-r3-unsynchronized required for relative-only calibration")
        result = run_plan(args.plan, args.out, config=SearchConfig(max_trials=args.max_trials))
        print(json.dumps({v: r["status"] for v, r in result["vehicles"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
