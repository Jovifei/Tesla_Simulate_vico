"""Real-reference fitting through the existing AH engines and rich workbench.

prepare -> review coarse-state windows -> run -> verify/serve. No new renderer,
no downloads, no fake human scores, no peak/loudness matching of exported audio.
Only RX7/Aventador are wired in v1. Existing other-vehicle adapters stay intact.
"""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile

from .reference_feedback import (
    METRIC, SR, ReferenceCase, Rendered, SearchConfig, audio_sha,
    optimize_reference_feedback, pcm_float, validate_parameters, _validate_cases,
)

PLAN_SCHEMA = "s12.stage_ah.reference_feedback_plan.v1"
RUN_SCHEMA = "s12.stage_ah.reference_feedback_run.v1"
ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class BaselineNumericGateError(ValueError):
    """A vehicle baseline is unsafe; the other vehicle may still be audited."""

    def __init__(self, vehicle: str, scene: str, record: Mapping[str, Any], captured_scenes=()):
        self.vehicle = vehicle
        self.scene = scene
        self.record = copy.deepcopy(record)
        self.captured_scenes = tuple(captured_scenes)
        super().__init__(f"baseline numeric gate failed: {vehicle}/{scene}")


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


def _sealed(path: Path) -> dict:
    from ..stage_af.package_integrity import canonical_json_bytes
    obj = _read(path)
    body = dict(obj)
    key = "manifest_sha256" if "manifest_sha256" in body else "contract_sha256"
    digest = body.pop(key, None)
    if digest is None or digest != hashlib.sha256(canonical_json_bytes(body)).hexdigest():
        raise ValueError(f"receipt checksum missing/mismatch: {path}")
    return obj


def _runtime_identity() -> dict:
    root = Path(__file__).resolve().parents[5]
    scope = "tools/sound_sim/s12/acoustic_identity_v015"
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    if git("status", "--porcelain", "--untracked-files=all", "--", scope):
        raise ValueError("commit scoped source changes before reference fitting")
    paths = git("ls-files", "--", scope).splitlines()
    if not paths:
        raise ValueError("source inventory is empty")
    hashes = {p: _sha(root / p) for p in paths if (root / p).is_file()}
    encoded = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return {"commit": git("rev-parse", "HEAD"), "scope": scope,
            "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
            "source_files": hashes, "source_status": "SOURCE_CLEAN"}


def prepare_plan(baseline_run: Path, destination: Path) -> None:
    """Propose disjoint recording splits. State labels require actual review."""
    if destination.exists():
        raise FileExistsError(destination)
    bundle = baseline_run.resolve() / "reference_bundle"
    path = bundle / "reference_clip_receipt.json"
    receipt = _sealed(path)
    rows = []
    clips = list(receipt["clips"].values())
    for vehicle in sorted({c["vehicle"] for c in clips}):
        selected = [c for c in clips if c["vehicle"] == vehicle]
        sources = sorted({c["source_video_id"] for c in selected})
        if len(sources) < 2:
            raise ValueError("independent recordings required")
        holdout = set(sources[-max(1, len(sources)//3):])
        for c in selected:
            wav = bundle / vehicle / c["filename"]
            if _sha(wav) != c["sha256"]:
                raise ValueError("reference clip changed")
            rows.append({"case_id": vehicle + "/" + c["scene_id"], "vehicle": vehicle,
                "scene": c["scene_id"], "source_id": c["source_video_id"],
                "source_sha256": c["source_sha256"], "wav_path": str(wav),
                "wav_sha256": c["sha256"], "receipt_key": vehicle + "/" + c["filename"],
                "split": "validation" if c["source_video_id"] in holdout else "train",
                "candidate_window_s": [0.0, min(4.0, float(c["duration_s"]))],
                "comparable": False,
                "comparability_note": "REVIEW_REQUIRED: same coarse RPM/load/event state; filename alone is not evidence"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write(destination, {"schema": PLAN_SCHEMA, "reference_level": "R3_UNSYNCHRONIZED",
        "baseline_run": str(baseline_run.resolve()), "reference_receipt_sha256": _sha(path),
        "cases": rows})


def load_plan(plan_path: Path) -> tuple[dict[str, list[ReferenceCase]], dict]:
    payload = _read(plan_path)
    if payload.get("schema") != PLAN_SCHEMA or payload.get("reference_level") != "R3_UNSYNCHRONIZED":
        raise ValueError("unsupported plan/evidence level")
    root = Path(payload["baseline_run"])
    root = (root if root.is_absolute() else plan_path.resolve().parent / root).resolve()
    receipt_path = root / "reference_bundle" / "reference_clip_receipt.json"
    if _sha(receipt_path) != payload["reference_receipt_sha256"]:
        raise ValueError("reference receipt changed")
    receipt = _sealed(receipt_path)
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty plan cases required")
    cases, files = {}, {}
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not ID.fullmatch(row[k])
                                          for k in ("vehicle", "scene", "source_id")):
            raise ValueError("invalid reference identity")
        ref = receipt["clips"].get(row["receipt_key"])
        if not isinstance(ref, dict) or any(ref[k] != row[r] for k, r in
                (("vehicle", "vehicle"), ("source_video_id", "source_id"),
                 ("source_sha256", "source_sha256"), ("sha256", "wav_sha256"))):
            raise ValueError("case is not bound to the original reference receipt")
        p = Path(row["wav_path"])
        p = (p if p.is_absolute() else plan_path.resolve().parent / p).resolve()
        if not p.is_file() or _sha(p) != row["wav_sha256"]:
            raise ValueError(f"reference missing/hash mismatch: {p}")
        sr, audio = wavfile.read(p)
        if sr != SR:
            raise ValueError("governed reference must already be 48000 Hz")
        audio = pcm_float(audio)
        if float(np.mean(np.abs(audio) >= .999)) > .01:
            raise ValueError("heavily clipped reference requires review")
        if not row["comparability_note"].strip() or "REVIEW_REQUIRED" in row["comparability_note"]:
            raise ValueError("reference operating-state review is incomplete")
        case = ReferenceCase(row["case_id"], row["scene"], row["source_id"], row["source_sha256"],
                row["split"], audio, tuple(row["candidate_window_s"]), row["comparable"], row["comparability_note"])
        cases.setdefault(row["vehicle"], []).append(case)
        files[str(p)] = row["wav_sha256"]
        row["wav_path"] = str(p)
    for group in cases.values():
        _validate_cases(group)
    return cases, {"plan_sha256": _sha(plan_path), "reference_files": files,
                   "reference_receipt_path": str(receipt_path),
                   "reference_receipt_sha256": _sha(receipt_path), "plan": payload}


def numeric_ok(record: Mapping[str, Any]) -> bool:
    """Missing data, hard clips and non-finite results fail closed."""
    try:
        n = record["normalization"]
        for value in (n["post_guard_ceiling_exceedance_samples"], n["emergency_clip_count"],
                      record["identity_layer_clip_count"], record["post_identity_clip_count"]):
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value != 0:
                return False
        for value in (n["emergency_clip_error"], record["identity_layer_clip_error"],
                      record["post_identity_clip_error"]):
            if not np.isfinite(value) or value != 0:
                return False
        return bool(0 < record["final_rms"] <= record["final_peak"] <= .94 + 1e-10
                    and np.isfinite(record["peak_estimate_4x"]["peak"])
                    and 0 < record["peak_estimate_4x"]["peak"] <= 1.0
                    and np.isfinite(record["normalization_denominator"])
                    and record["normalization_denominator"] > 0)
    except (KeyError, TypeError, ValueError):
        return False


class RemainingFeedbackRenderer:
    """Whitelisted values enter existing named sources, with no fake scores."""
    def __init__(self, vehicle: str, contexts: Mapping, parents: Mapping, ir: np.ndarray):
        from .remaining_vehicle_pipeline import FEEDBACK_BOUNDS, feedback_parameters
        self.vehicle, self.contexts = vehicle, dict(contexts)
        self.parents, self.ir = dict(parents), np.asarray(ir).copy()
        self.bounds = FEEDBACK_BOUNDS[vehicle]
        defaults = feedback_parameters(vehicle, ())["parameters"]
        self.baseline = {k: defaults[k] for k in self.bounds}
        self.last_records = {}

    def __call__(self, parameters: Mapping[str, float], scene: str) -> Rendered:
        from .remaining_vehicle_pipeline import RemainingVehicleEngine
        from .output_guard import LINKED_SOFT_CEILING_V1
        params = validate_parameters(parameters, self.bounds)
        c = self.contexts[scene]
        engine = RemainingVehicleEngine(self.vehicle, SR, output_policy=LINKED_SOFT_CEILING_V1,
                    parent_peaks=self.parents, ir=self.ir, seed=20260908, scene_ids=(scene,))
        engine.feedback["parameters"].update(params)
        engine.feedback.update(controller="reference_analysis_by_synthesis_v1", status="REFERENCE_TRIAL", adjustments=[])
        audio = engine.render_track(c["rpm"], c["throttle"], c["duration"],
            shift_events=c["shift_events"], afterfire_events=c["afterfire_events"], bov_events=c["bov_events"])
        record = copy.deepcopy(engine.reports[-1])
        if record["trace_sha256"] != c["trace_sha256"]:
            raise ValueError("trial trace differs from baseline")
        if record["normalization_denominator"] != self.parents[record["parent_peak_key"]]:
            raise ValueError("trial changed parent denominator")
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
            raise BaselineNumericGateError(vehicle, scene, report, sorted(records))
        contexts[scene] = {k: data[k] for k in ("rpm", "throttle", "duration", "shift_events", "afterfire_events", "bov_events")}
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
    if set(records) != set(SCENE_IDS):
        raise ValueError("baseline must capture ten distinct canonical scenes")
    return engine, cfg, contexts, records, hashes


def _embedded(text: str, name: str):
    match = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*", text)
    if not match:
        raise ValueError(f"missing embedded {name}")
    return json.JSONDecoder().raw_decode(text[match.end():])[0]


def _dashboard(vehicle, cfg, result, reference_rows, group, run_id, all_vehicles):
    from .remaining_vehicle_package import _dashboards
    from ..stage_af.package_integrity import seal_payload
    cfg["title"] = f"[REFERENCE FEEDBACK / {group}] " + cfg["title"]
    cfg["subtitle"] = "同一 C0 输出保护：频谱误差驱动参数闭环，R3未同步，不是相似度百分比"
    refs = {}
    for scene in cfg["scenes"]:
        choices = [r for r in reference_rows if r["vehicle"] == vehicle and r["scene"] == scene["id"]]
        if choices:
            row = choices[0]
            source = Path(row["wav_path"])
            target = cfg["dir"] / "web_audio" / scene["ref_file"]
            shutil.copy2(source, target)
            if _sha(target) != row["wav_sha256"]:
                raise ValueError("reference copy drift")
            refs[scene["ref_file"]] = {"available": True, "fit_required": False,
                "source_label": f"{row['source_id']} / {row['split']} / R3未同步", "sha256": row["wav_sha256"]}
        else:
            scene["ref_file"] = ""
    selected_records = result["baseline_records" if group == "BASELINE" else "selected_records"]
    wav_hashes = {s + ".wav": _sha(cfg["dir"] / "web_audio" / (s + ".wav")) for s in selected_records}
    contract = seal_payload({
        "package_id": run_id + "-" + group.lower(), "candidate_id": group + "-" + vehicle,
        "vehicle": vehicle, "seed": 20260908, "flags": [], "source_status": "SOURCE_CLEAN",
        "fit_status": "BASELINE" if group == "BASELINE" else result["status"],
        "fit_metric_status": METRIC, "measurement_status": "R3_RELATIVE_ONLY_UNSYNCHRONIZED",
        "promotable": False, "promotion_status": "NOT_PROMOTABLE_R3", "references": refs,
        "human_status": "NOT_EVALUATED", "sample_rate_hz": SR, "nav_urls": {},
        "parameters": result["baseline_parameters" if group == "BASELINE" else "selected_parameters"],
        "output_policy": "linked_soft_ceiling_v1", "knee": .90, "ceiling": .94,
        "reference_feedback": {"controller": "reference_analysis_by_synthesis_v1", "status": result["status"]},
        # The old template's candidate_pcm_sha256 means WAV-file SHA. Retain its
        # API meaning and separately expose the true decoded PCM identities.
        "candidate_pcm_sha256": wav_hashes, "candidate_wav_sha256": wav_hashes,
        "decoded_pcm_sha256": {s + ".wav": r["final_pcm_sha256"] for s, r in selected_records.items()},
        "reference_sha256": {k: v["sha256"] for k, v in refs.items()},
    }, "s12.stage_ah.reference_feedback.dashboard.v1")
    cfg["_dashboard_contract"], cfg["_dashboard_params"] = contract, []
    _write(cfg["dir"] / "dashboard_contract.json", contract)
    old_template, old_configs = _dashboards.TEMPLATE_PATH, _dashboards.VEHICLE_CONFIGS
    _dashboards.VEHICLE_CONFIGS = {vehicle: cfg}
    _dashboards.TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "stage_ad" / "audition_dashboard_template.html"
    try:
        _dashboards.build_dashboard(vehicle, cfg)
        nav = " | ".join('<a href="../../' + g + '/' + v + '/index.html">' + v + ' ' + g + '</a>'
                         for v in all_vehicles for g in ("baseline", "tuned"))
        fields = ("status", "baseline_train_loss", "selected_train_loss", "parameter_delta", "validation_baseline", "validation_proposed")
        panel = ('<section style="padding:24px"><h2>真实录音驱动参数闭环 / ' + group + '</h2>'
                 + '<p>' + nav + '</p><p><a href="../../summary.json">完整试验历史</a></p>'
                 + '<p>误差不是相似度百分比；不是 OEM/Human PASS。声音仍是程序合成，不播放参考冒充候选。</p><pre>'
                 + html.escape(json.dumps({k: result[k] for k in fields}, ensure_ascii=False, indent=2)) + '</pre></section>')
        for path in (cfg["dir"] / "index.html", cfg["dir"] / "index_standalone.html"):
            text = path.read_text(encoding="utf-8").replace('href="http://localhost:0/"', 'href="index.html"')
            path.write_text(text.replace("</header>", "</header>" + panel, 1), encoding="utf-8")
            _verify_html(path, contract, cfg["scenes"])
    finally:
        _dashboards.TEMPLATE_PATH, _dashboards.VEHICLE_CONFIGS = old_template, old_configs


def _verify_html(path, contract, scenes):
    text = path.read_text(encoding="utf-8")
    if _embedded(text, "DASHBOARD_CONTRACT") != contract or _embedded(text, "SCENES") != scenes:
        raise ValueError("embedded contract/scene mismatch")
    store = _embedded(text, "AUDIO_STORE")
    for scene in scenes:
        for role, field, hashes in (("candidate", "candidate_file", contract["candidate_wav_sha256"]),
                                   ("ref", "ref_file", contract["reference_sha256"])):
            filename = scene[field]
            if filename:
                raw = base64.b64decode(store[scene["id"] + "_" + role].split(",", 1)[1], validate=True)
                file = path.parent / "web_audio" / filename
                if raw != file.read_bytes() or hashlib.sha256(raw).hexdigest() != hashes[filename]:
                    raise ValueError("embedded audio != on-disk governed WAV")


def verify_run(root: Path, expected_manifest_sha256: str | None = None) -> dict:
    root = root.resolve()
    path = root / "ARTIFACTS.json"
    if expected_manifest_sha256 is not None and _sha(path) != expected_manifest_sha256:
        raise ValueError("run inventory file SHA mismatch")
    manifest = _sealed(path)
    files = manifest["files"]
    if not files:
        raise ValueError("empty run inventory")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p != path}
    if actual != set(files):
        raise ValueError("run inventory missing/unexpected files")
    for relative, digest in files.items():
        p = root / relative
        if p.is_symlink() or not p.resolve().is_relative_to(root) or _sha(p) != digest:
            raise ValueError(f"artifact drift: {relative}")
    summary = _read(root / "summary.json")
    if summary.get("schema") != RUN_SCHEMA or summary.get("promotable") is not False:
        raise ValueError("wrong run contract")
    for vehicle, result in summary["vehicles"].items():
        if result.get("status") == "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK":
            relative = result.get("failure_receipt")
            if not isinstance(relative, str):
                raise ValueError("blocked vehicle is missing failure receipt")
            receipt_path = (root / relative).resolve()
            if not receipt_path.is_relative_to(root):
                raise ValueError("blocked vehicle receipt escapes run")
            receipt = _sealed(receipt_path)
            if receipt.get("vehicle") != vehicle or receipt.get("status") != result["status"]:
                raise ValueError("blocked vehicle receipt mismatch")
            continue
        for group in ("baseline", "tuned"):
            folder = root / group / vehicle
            contract = _sealed(folder / "dashboard_contract.json")
            for filename in ("index.html", "index_standalone.html"):
                page = folder / filename
                _verify_html(page, contract, _embedded(page.read_text(encoding="utf-8"), "SCENES"))
    return summary


def run_plan(plan_path: Path, output: Path, *, config: SearchConfig = SearchConfig()) -> dict:
    from .remaining_vehicle_package import REMAINING_VEHICLES, SCENE_IDS, _config
    from ..stage_af.package_integrity import seal_payload
    config.validate()
    cases, evidence = load_plan(plan_path)
    if not set(cases) <= set(REMAINING_VEHICLES) or any(c.scene not in SCENE_IDS for rows in cases.values() for c in rows):
        raise ValueError("unsupported vehicle/scene adapter")
    runtime = _runtime_identity()
    output = output.resolve()
    if not ID.fullmatch(output.name):
        raise ValueError("output directory name must be a safe run identifier")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / ("." + output.name + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    staging = None
    try:
        if output.exists():
            raise FileExistsError(output)
        staging = Path(tempfile.mkdtemp(prefix="." + output.name + "-", dir=output.parent))
        _write(staging / "input_plan.json", evidence["plan"])
        results = {}
        for vehicle, selected in cases.items():
            base_dir, tuned_dir = staging / "baseline" / vehicle, staging / "tuned" / vehicle
            try:
                engine, cfg, contexts, records, hashes = _baseline(vehicle, base_dir)
            except BaselineNumericGateError as error:
                relative = f"diagnostics/{vehicle}-baseline-numeric-failure.json"
                (staging / "diagnostics").mkdir(parents=True, exist_ok=True)
                receipt = seal_payload({
                    "schema": "s12.stage_ah.reference_feedback.baseline_failure.v1",
                    "run_id": output.name,
                    "vehicle": error.vehicle,
                    "scene": error.scene,
                    "status": "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK",
                    "reason": "baseline numeric gate failed; vehicle held out",
                    "record": error.record,
                    "captured_scenes": list(error.captured_scenes),
                    "runtime_commit": runtime["commit"],
                }, "s12.stage_ah.reference_feedback.baseline_failure.v1")
                _write(staging / relative, receipt)
                results[vehicle] = {
                    "status": "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK",
                    "promotable": False,
                    "human_status": "NOT_EVALUATED",
                    "failure_receipt": relative,
                    "failure_scene": error.scene,
                    "captured_scene_count": len(error.captured_scenes),
                }
                continue
            ir_source_hash = engine.ir_source_sha256
            renderer = RemainingFeedbackRenderer(vehicle, contexts, engine.parent_peaks, engine.ir)
            for scene in SCENE_IDS:
                if audio_sha(renderer(renderer.baseline, scene).audio) != hashes[scene]:
                    raise ValueError("feedback-disabled PCM differs from canonical baseline")
            result = optimize_reference_feedback(renderer.baseline, renderer.bounds, selected, renderer, config=config)
            final_audio, final_records = {}, {}
            def render_all(params):
                for scene in SCENE_IDS:
                    r = renderer(params, scene)
                    final_audio[scene], final_records[scene] = r.audio, r.diagnostics
            render_all(result["selected_parameters"])
            if not all(numeric_ok(r) for r in final_records.values()):
                result["status"] = "ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK"
                result["selected_parameters"] = dict(renderer.baseline)
                result["parameter_delta"] = {k: 0.0 for k in renderer.baseline}
                result["selected_train_loss"] = result["baseline_train_loss"]
                render_all(renderer.baseline)
            if not all(numeric_ok(r) for r in final_records.values()):
                raise ValueError("baseline rollback failed numeric verification")
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
            _dashboard(vehicle, cfg, result, evidence["plan"]["cases"], "BASELINE", output.name, sorted(cases))
            _dashboard(vehicle, _config(vehicle, tuned_dir, 0, "C0"), result, evidence["plan"]["cases"],
                       "TUNED", output.name, sorted(cases))
            results[vehicle] = result
        if _sha(plan_path) != evidence["plan_sha256"] or _sha(Path(evidence["reference_receipt_path"])) != evidence["reference_receipt_sha256"]:
            raise ValueError("input plan/receipt changed during fitting")
        if any(_sha(Path(p)) != digest for p, digest in evidence["reference_files"].items()):
            raise ValueError("reference changed during fitting")
        if _runtime_identity() != runtime:
            raise ValueError("source changed during fitting")
        summary = {"schema": RUN_SCHEMA, "run_id": output.name, "runtime": runtime,
            "reference_evidence": evidence, "vehicles": results, "output_policy": "linked_soft_ceiling_v1",
            "knee": .90, "ceiling": .94, "comparison": "BASELINE_C0_VS_TUNED_C0_FIXED_BASELINE_DENOMINATORS",
            "promotable": False, "human_status": "NOT_EVALUATED",
            "self_contained_status": "AUDIO_SELF_CONTAINED / STYLE_NETWORK_DEPENDENCY"}
        _write(staging / "summary.json", summary)
        links = "".join(
            ('<p>' + v + ': BLOCKED — <a href="' + row["failure_receipt"] + '">基线失败收据</a></p>'
             if row.get("failure_receipt") else
             '<p>' + v + ': <a href="baseline/' + v + '/index.html">基线 C0</a> / '
             + '<a href="tuned/' + v + '/index.html">优化 C0</a></p>')
            for v, row in results.items())
        (staging / "index.html").write_text('<!doctype html><meta charset="utf-8">'
            + '<title>S12 Reference Feedback</title><h1>真实录音驱动闭环实验</h1>' + links
            + '<p>此页仅导航。车型页保持原富交互 A/B；B为真实录音，不是基线合成音。'
            + '未宣称OEM或机器相似度。</p><a href="summary.json">完整历史</a>', encoding="utf-8")
        files = {p.relative_to(staging).as_posix(): _sha(p) for p in staging.rglob("*") if p.is_file()}
        _write(staging / "ARTIFACTS.json", seal_payload({"files": files}, "s12.stage_ah.reference_feedback.artifacts.v1"))
        verify_run(staging)
        staging.rename(output)  # all final metadata was sealed before this operation
        staging = None
        return summary
    finally:
        if staging is not None:
            shutil.rmtree(staging)
        lock.unlink(missing_ok=True)


def serve_run(root: Path, port: int, expected_sha: str, preflight_only: bool = False) -> None:
    from ..stage_ag.serve_r1_review_strict import _make_server
    verify_run(root, expected_sha)
    if preflight_only:
        print("Reference-feedback package preflight PASS")
        return
    server = _make_server(root.resolve(), port)
    try:
        print(f"http://localhost:{port}/ — original rich vehicle pages; no historical portal")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # serve_forever runs in this thread. shutdown() here would deadlock.
        server.server_close()


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
    serve = commands.add_parser("serve")
    serve.add_argument("--run", type=Path, required=True)
    serve.add_argument("--manifest-sha256", required=True)
    serve.add_argument("--port", type=int, default=29380)
    serve.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare_plan(args.baseline_run, args.out)
    elif args.command == "run":
        if not args.allow_r3_unsynchronized:
            parser.error("explicit --allow-r3-unsynchronized required")
        result = run_plan(args.plan, args.out, config=SearchConfig(max_trials=args.max_trials))
        print(json.dumps({v: r["status"] for v, r in result["vehicles"].items()}, ensure_ascii=False))
    else:
        if not 1024 <= args.port <= 65535:
            parser.error("port must be in [1024,65535]")
        serve_run(args.run, args.port, args.manifest_sha256, args.preflight_only)


if __name__ == "__main__":
    main()
