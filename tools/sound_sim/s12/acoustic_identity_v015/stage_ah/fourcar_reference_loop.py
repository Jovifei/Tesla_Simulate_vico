"""AI-2: four-car measured parameter search, reusing the qualified AH renderer.

One named parameter per car; no new oscillator, output gain, IR or metric.
The original reference_feedback optimizer performs the search/validation.
Real recordings remain local. Catalog windows are suggestions, not RPM labels.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
from typing import Mapping

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from .feedback_evidence import Journal, SCENES, canonical, fit_eligibility, sha_file, write_json
from .reference_feedback import ReferenceCase, Rendered, SearchConfig, audio_sha, pcm_float, optimize_reference_feedback, validate_parameters, _validate_cases
from .reference_feedback_cli import _runtime_identity, numeric_ok
from .fourcar_pipeline import (FOURCAR_VEHICLES, FOURCAR_TARGET_PATH, REAL_REFERENCE_BASE_PATHS,
    REAL_REFERENCE_CHANGED_PARAMETERS, FourCarRealReferenceEngine, load_real_reference_profile,
    scene_trace_key, peak_estimate_4x, _resolve_ir_path, IR_NAMES)
from .fourcar_package import _import_dashboards, _vehicle_directory, _read_sealed
from .engine import RemediationEngine, input_sha
from .output_guard import LINKED_SOFT_CEILING_V1
from .qualification import (QUALIFICATION_FILENAME, build_qualification_receipt,
                            verify_qualification_receipt)
from .reconstruction_peak import reconstructed_peak_receipt
from ..stage_af.package_integrity import seal_payload, validate_artifacts
from ..stage_af.physical_closed_loop import fixed_reference_distance

PLAN_SCHEMA = "s12.stage_ai.fourcar_reference_plan.v1"
RUN_SCHEMA = "s12.stage_ai.fourcar_reference_run.v1"
# Bounded experiments, NOT measured OEM parameter ranges.
BOUNDS = {"hellcat": (0.90, 1.35), "ferrari_458": (0.90, 1.40),
          "lfa": (0.90, 1.40), "gtr_r35": (0.12, 0.26)}
LOCK = threading.RLock()  # original dashboard generator uses module globals
ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
RELATIVE_SCENES = {"01_afterfire": "ref_afterfire.wav", "02_full_pull": "ref_full_pull.wav",
                   "03_hot_idle": "ref_hot_idle.wav", "09_steady_mid": "ref_steady_mid.wav"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _bind_qualification_record(report: dict, pcm: np.ndarray, scene: str, trace: str) -> None:
    """Bind fields independently required to qualify the final decoded artifact."""
    artifact = np.ascontiguousarray(pcm, dtype='<i2')
    report.update(
        parent_peak_key=scene_trace_key(scene, trace),
        sample_rate_hz=48000,
        sample_count=int(len(artifact)),
        reconstruction_peak=reconstructed_peak_receipt(artifact.astype(np.float64)/32767.0),
    )


def _safe(root, relative):
    p = root / relative
    if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):
        raise ValueError("artifact path escapes package")
    return p


def verify_parent(root: Path, expected_sha: str):
    path = root / "audition_manifest.json"
    if sha_file(path) != expected_sha:
        raise ValueError("parent manifest file digest mismatch")
    m = _read_sealed(path)
    if (m.get("group") != "C0" or m.get("output_policy") != LINKED_SOFT_CEILING_V1
            or m.get("identity_mode") != "vehicle_identity_v1r1"):
        raise ValueError("parent must be the existing four-car C0, not REALREF or legacy B0")
    if m.get("numeric_gate", {}).get("status") != "PASS":
        raise ValueError("parent numeric gate not qualified")
    rows = m.get("vehicles", [])
    if len(rows) != 4 or {r["vehicle"] for r in rows} != set(FOURCAR_VEHICLES):
        raise ValueError("four unique parent vehicles required")
    if not m.get("artifacts"):
        raise ValueError("parent artifact inventory missing")
    validate_artifacts(m["artifacts"], root)
    for row in rows:
        folder = _safe(root, row["directory"])
        if set(row["candidate_sha256"]) != {s + ".wav" for s in SCENES}:
            raise ValueError("parent must bind all ten WAVs")
        for role in ("candidate_sha256", "reference_sha256"):
            for name, digest in row[role].items():
                if sha_file(_safe(folder / "web_audio", name)) != digest:
                    raise ValueError("parent WAV identity drift")
    return m


def prepare(parent: Path, parent_sha: str, out: Path, *, catalog: Path = FOURCAR_TARGET_PATH):
    verify_parent(parent, parent_sha)
    db = read(catalog)
    cases = []
    for vehicle in FOURCAR_VEHICLES:
        sources = sorted(db["vehicles"][vehicle]["sources"], key=lambda s: s["id"])
        for index, source in enumerate(sources):
            cases.append({"vehicle": vehicle, "case_id": vehicle + "/" + source["id"],
                "source_id": source["id"], "wav_path": source["external_wav_path"],
                "source_window_s": source["analysis_window_s"],
                "scene": "02_full_pull", "candidate_window_s": [0.0, 4.0],
                "split": "validation" if index == len(sources)-1 else "train",
                "comparable": False, "comparability_note": "REVIEW_REQUIRED: " + source.get("scenario", "unknown"),
                "viewpoint": "REVIEW_REQUIRED", "state_family": "REVIEW_REQUIRED"})
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, {"schema": PLAN_SCHEMA, "parent_package": str(parent.resolve()),
        "parent_manifest_sha256": parent_sha, "catalog_path": str(catalog.resolve()),
        "catalog_sha256": sha_file(catalog), "evidence_level": "R3_UNSYNCHRONIZED",
        "cases": cases, "excluded_sources": [],
        "rules": ["Do not approve windows from filenames alone", "Freeze source split before fitting",
                  "Do not use validation to choose windows, ranges, metric or iteration budget"]})


def load_plan(path):
    p = read(path)
    if p.get("schema") != PLAN_SCHEMA or p.get("evidence_level") != "R3_UNSYNCHRONIZED":
        raise ValueError("wrong plan schema/evidence level")
    catalog = Path(p["catalog_path"])
    if sha_file(catalog) != p["catalog_sha256"]:
        raise ValueError("reference catalog drift")
    db, cases, evidence, frozen_files = read(catalog), {}, [], {str(catalog): sha_file(catalog)}
    for row in p["cases"]:
        v = row["vehicle"]
        if v not in FOURCAR_VEHICLES or row["scene"] not in SCENES:
            raise ValueError("unknown vehicle/scene")
        source = next((s for s in db["vehicles"][v]["sources"] if s["id"] == row["source_id"]), None)
        if source is None:
            raise ValueError("reference not present in governed catalog")
        for key in ("comparability_note", "viewpoint", "state_family"):
            if not str(row.get(key, "")).strip() or "REVIEW_REQUIRED" in str(row[key]):
                raise ValueError("reference state/viewpoint review is incomplete")
        wav = Path(row["wav_path"])
        if not wav.is_absolute():
            wav = path.resolve().parent / wav
        if sha_file(wav) != source["wav_sha256"]:
            raise ValueError("real source WAV changed; do not silently rehash it")
        sr, raw = wavfile.read(wav)
        if sr < 8000 or sr > 192000:
            raise ValueError("unsupported reference sample rate")
        start, end = map(float, row["source_window_s"])
        if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end or end-start > 30:
            raise ValueError("invalid/far too long source window")
        i, j = round(start*sr), round(end*sr)
        if not 0 <= i < j <= len(raw):
            raise ValueError("source window outside recording")
        clip = pcm_float(raw[i:j])
        if np.mean(np.abs(clip) >= .999) > .01:
            raise ValueError("heavily clipped reference needs review")
        if sr != 48000:
            factor = math.gcd(int(sr), 48000)
            clip = resample_poly(clip, 48000//factor, int(sr)//factor, axis=0)
        ref = ReferenceCase(row["case_id"], row["scene"], source["source_url"], source["wav_sha256"],
            row["split"], clip, tuple(row["candidate_window_s"]), row["comparable"], row["comparability_note"])
        cases.setdefault(v, []).append(ref)
        frozen_files[str(wav.resolve())] = source["wav_sha256"]
        evidence.append({**row, "wav_path": str(wav.resolve()), "wav_sha256": source["wav_sha256"],
            "source_url": source["source_url"], "source_sample_rate": int(sr),
            "analysis_resampling": "none" if sr == 48000 else "polyphase_kaiser5_to_48000_no_gain",
            "rights_status": source.get("rights_status", "UNVERIFIED"),
            "decoded_window_sha256": audio_sha(clip)})
    for v, refs in cases.items():
        _validate_cases(refs)
        if len({c.source_sha256 for c in refs if c.split == 'train'}) < 2:
            raise ValueError("at least two independent training recordings per vehicle required")
        # Prevent training on exterior and claiming onboard validation by accident.
        rows = [e for e in evidence if e['vehicle'] == v]
        train_strata = {(e['viewpoint'], e['state_family']) for e in rows if e['split'] == 'train'}
        if any((e['viewpoint'], e['state_family']) not in train_strata for e in rows if e['split'] == 'validation'):
            raise ValueError("validation has an unmatched viewpoint/state stratum")
    if not cases:
        raise ValueError("empty reference plan")
    return p, cases, evidence, frozen_files


def capture_baseline(vehicle: str, directory: Path, entry: Mapping, parent: Path):
    """Real ten-scene renderer, capture immediately after each scene (not last_report x10)."""
    dash = _import_dashboards()
    engine = RemediationEngine(vehicle, variant="r1_baseline", seed=20260908,
                               output_policy=LINKED_SOFT_CEILING_V1)
    cfg = copy.deepcopy(dash.VEHICLE_CONFIGS[vehicle])
    cfg['dir'] = directory
    directory.mkdir(parents=True)
    contexts, records, peaks = {}, {}, {}
    def observe(**data):
        scene = data['scene_id']
        report = copy.deepcopy(engine.last_report)
        wav = directory / 'web_audio' / (scene + '.wav')
        if sha_file(wav) != entry['candidate_sha256'][scene + '.wav']:
            raise ValueError(f"baseline differs from accepted C0: {vehicle}/{scene}")
        trace = input_sha(data['rpm'], data['throttle'], data['duration'],
                         [data['shift_events'], data['afterfire_events'], data['bov_events']])
        if report['trace_sha256'] != trace or scene in contexts:
            raise ValueError("duplicate or mismatched baseline scene trace")
        pcm = np.asarray(data['audio'])
        report.update(scene_id=scene, final_pcm_sha256=hashlib.sha256(np.ascontiguousarray(pcm, dtype='<i2')).hexdigest(),
            final_peak=float(np.max(np.abs(pcm.astype(float)))/32767),
            final_rms=float(np.sqrt(np.mean((pcm.astype(float)/32767)**2))),
            peak_estimate_4x=peak_estimate_4x(pcm.astype(float)/32767),
            normalization_denominator=report['parent_peak'])
        _bind_qualification_record(report, pcm, scene, trace)
        if not numeric_ok(report):
            raise ValueError(f"baseline numeric gate: {vehicle}/{scene}")
        contexts[scene] = {k: data[k] for k in ('rpm','throttle','duration','shift_events','afterfire_events','bov_events')}
        contexts[scene]['trace_sha256'] = trace
        peaks[scene_trace_key(scene, trace)] = report['parent_peak']
        records[scene] = report
    old = dash.EngineAcoustics
    cfg['_render_observer'] = observe
    dash.EngineAcoustics = lambda **kw: engine
    try:
        dash.render_vehicle_audio(vehicle, cfg)
    finally:
        dash.EngineAcoustics = old
    if list(contexts) != list(SCENES):
        raise ValueError("ten canonical baseline scenes required")
    binding = _read_sealed(parent / entry['directory'] / 'stage_ah_fourcar_binding.json')
    old_records = {r['scene_id']: r for r in binding['records']}
    for s, record in records.items():
        for key in ('trace_sha256', 'seed', 'flags'):
            if record[key] != old_records[s][key]:
                raise ValueError("old/new baseline context mismatch")
        prior_ir = old_records[s].get('ir_effective_sha256')
        actual_ir = hashlib.sha256(np.ascontiguousarray(engine.base.ir, dtype='<f8')).hexdigest()
        if prior_ir is not None and prior_ir != actual_ir:
            raise ValueError('old/new baseline IR mismatch')
    return engine, contexts, records, peaks


class FourCarFeedbackRenderer:
    def __init__(self, vehicle, contexts, peaks, journal: Journal | None = None):
        self.vehicle, self.contexts, self.peaks, self.journal = vehicle, contexts, dict(peaks), journal
        self.profile, _ = load_real_reference_profile(vehicle)
        self.name = REAL_REFERENCE_CHANGED_PARAMETERS[vehicle]
        raw = read(REAL_REFERENCE_BASE_PATHS[vehicle])
        self.value = float(raw['source'][self.name]['value'])
        self.baseline, self.bounds = {self.name: self.value}, {self.name: BOUNDS[vehicle]}
        self.last_records = {}
        self.ir_path = _resolve_ir_path(IR_NAMES[vehicle])
        if self.ir_path is None:
            raise FileNotFoundError("required IR")
        self.ir_sha = sha_file(self.ir_path)

    def __call__(self, parameters, scene):
        p = validate_parameters(parameters, self.bounds)
        c = self.contexts[scene]
        if sha_file(self.ir_path) != self.ir_sha:
            raise ValueError("IR changed during search")
        profile = copy.deepcopy(self.profile)
        profile.payload['source'][self.name]['value'] = p[self.name]
        engine = FourCarRealReferenceEngine(self.vehicle, profile, parent_peaks=self.peaks,
                 source_adjustment_ratio=p[self.name]/self.value, seed=20260908, output_policy=LINKED_SOFT_CEILING_V1)
        engine.set_scene_context(scene, c['trace_sha256'])
        if self.journal:
            self.journal.append('RENDER_START', {'vehicle': self.vehicle, 'scene': scene, 'parameters': p})
        pcm = engine.render_track(c['rpm'], c['throttle'], c['duration'], c['shift_events'], c['afterfire_events'], c['bov_events'])
        report = copy.deepcopy(engine.last_report)
        _bind_qualification_record(report, pcm, scene, c['trace_sha256'])
        if report['normalization_denominator'] != self.peaks[scene_trace_key(scene, c['trace_sha256'])]:
            raise ValueError("parent denominator drift")
        if report['ir_source_sha256'] != self.ir_sha:
            raise ValueError("runtime IR differs from frozen IR")
        # Estimate on the FINAL PCM, not only prequantized float.
        report['peak_estimate_4x'] = peak_estimate_4x(pcm.astype(float)/32767)
        self.last_records[scene] = report
        if self.journal:
            self.journal.append('RENDER_COMPLETE', {'vehicle': self.vehicle, 'scene': scene, 'parameters': p,
                'trace_sha256': report['trace_sha256'], 'pcm_sha256': report['final_pcm_sha256'],
                'denominator': report['normalization_denominator'], 'numeric_ok': numeric_ok(report),
                'peak_4x': report['peak_estimate_4x']['peak']})
        return Rendered(pcm, numeric_ok(report), report)


def relative_audition_check(parent: Path, entry, originals, selected):
    """Preserve the old 4-scene relative guard in addition to source-held-out validation."""
    rows = []
    for scene, name in RELATIVE_SCENES.items():
        p = parent / entry['directory'] / 'web_audio' / name
        sr, ref = wavfile.read(p)
        if sr != 48000 or sha_file(p) != entry['reference_sha256'][name]:
            raise ValueError("audition Reference drift")
        a = pcm_float(originals[scene]).mean(axis=1)
        b = pcm_float(selected[scene]).mean(axis=1)
        c = pcm_float(ref).mean(axis=1)
        before, after = fixed_reference_distance(a, c), fixed_reference_distance(b, c)
        rows.append({'scene': scene, 'reference_wav_sha256': sha_file(p), 'baseline': before,
            'selected': after, 'regression_gt_3pct': bool(after > before*1.03 + 1e-12)})
    return rows


def run(plan_path: Path, output: Path, *, config: SearchConfig = SearchConfig()):
    config.validate()
    plan, case_map, evidence, frozen = load_plan(plan_path)
    parent = Path(plan['parent_package']).resolve()
    manifest = verify_parent(parent, plan['parent_manifest_sha256'])
    entries = {e['vehicle']: e for e in manifest['vehicles']}
    runtime = _runtime_identity()
    plan_sha = sha_file(plan_path)
    output = output.resolve()
    if not ID.fullmatch(output.name):
        raise ValueError("safe fresh run identifier required")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / ('.' + output.name + '.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    staging = None
    try:
        if output.exists():
            raise FileExistsError(output)
        staging = Path(tempfile.mkdtemp(prefix='.' + output.name + '-', dir=output.parent))
        write_json(staging/'input_plan.json', plan)
        results, blocked = {}, {}
        for vehicle in case_map:
            vwork = staging / 'diagnostics' / vehicle
            vwork.mkdir(parents=True)
            base_dir, tuned_dir = staging/'baseline'/vehicle, staging/'tuned'/vehicle
            with Journal(vwork/'render_journal.jsonl') as journal:
                journal.append('VEHICLE_START', {'vehicle': vehicle, 'source_head': runtime['commit']})
                try:
                    with LOCK:
                        base_engine, contexts, records, peaks = capture_baseline(vehicle, base_dir, entries[vehicle], parent)
                    renderer = FourCarFeedbackRenderer(vehicle, contexts, peaks, journal)
                    originals = {}
                    for scene in SCENES:
                        _, originals[scene] = wavfile.read(base_dir/'web_audio'/(scene+'.wav'))
                        trial = renderer(renderer.baseline, scene)
                        if not trial.numeric_ok or not np.array_equal(trial.audio, originals[scene]):
                            raise ValueError('feedback-off PCM/numeric equivalence failed: '+scene)
                    result = optimize_reference_feedback(renderer.baseline, renderer.bounds, case_map[vehicle], renderer, config=config)
                    with Journal(vwork/'trials.jsonl') as trials:
                        for row in result['history']:
                            trials.append('MEASURED_TRIAL', row)
                        trials.append('VALIDATION_AND_SELECTION', {k: result[k] for k in
                            ('status','selected_parameters','parameter_delta','validation_baseline','validation_proposed','stop_reason')})
                    selected_audio, selected_records = {}, {}
                    for scene in SCENES:
                        trial = renderer(result['selected_parameters'], scene)
                        selected_audio[scene], selected_records[scene] = trial.audio, trial.diagnostics
                    rel = relative_audition_check(parent, entries[vehicle], originals, selected_audio)
                    failure = None
                    if not all(numeric_ok(r) for r in selected_records.values()):
                        failure = 'ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK'
                    elif any(r['regression_gt_3pct'] for r in rel):
                        failure = 'AUDITION_REFERENCE_REGRESSION_ROLLED_BACK'
                    if failure:
                        rejected_dir = vwork/'rejected'/'web_audio'
                        rejected_dir.mkdir(parents=True)
                        rejected_wav_sha256 = {}
                        for scene, pcm in selected_audio.items():
                            rejected_path = rejected_dir/(scene+'.wav')
                            wavfile.write(rejected_path, 48000, pcm)
                            rejected_wav_sha256[scene] = sha_file(rejected_path)
                        rejected_records = copy.deepcopy(selected_records)
                        result['status'] = failure
                        result['selected_parameters'] = dict(renderer.baseline)
                        result['parameter_delta'] = {k:0. for k in renderer.baseline}
                        result['selected_train_loss'] = result['baseline_train_loss']
                        selected_audio = originals
                        selected_records = records
                        failure_path = vwork/'failure.json'
                        failure_payload = {'vehicle':vehicle, 'status':failure,
                            'reason':failure, 'rejected_records':rejected_records,
                            'rejected_wav_sha256':rejected_wav_sha256,
                            'promotable':False, 'human_status':'NOT_EVALUATED'}
                        write_json(failure_path, seal_payload(
                            failure_payload, 's12.stage_ai.fourcar_vehicle_failure.v1'))
                        result['failure_receipt'] = str(failure_path.relative_to(staging))
                    tuned_dir.mkdir(parents=True)
                    (tuned_dir/'web_audio').mkdir()
                    for scene, pcm in selected_audio.items():
                        wavfile.write(tuned_dir/'web_audio'/(scene+'.wav'), 48000, pcm)
                    result.update(baseline_records=records, selected_records=selected_records,
                        source_scope=renderer.profile.vehicle_id + ':' + renderer.name,
                        baseline_wav_sha256={s:sha_file(base_dir/'web_audio'/(s+'.wav')) for s in SCENES},
                        selected_wav_sha256={s:sha_file(tuned_dir/'web_audio'/(s+'.wav')) for s in SCENES},
                        off_switch_equal_count=10, audition_reference_guard=rel,
                        ir_source_sha256=renderer.ir_sha, eligibility=fit_eligibility(result),
                        logs={'trials':str((vwork/'trials.jsonl').relative_to(staging)),
                              'renders':str((vwork/'render_journal.jsonl').relative_to(staging))})
                    journal.append('VEHICLE_COMPLETE', {'status':result['status'], 'eligibility':result['eligibility']})
                    write_json(vwork/'result.json', result)
                    results[vehicle] = result
                except (ValueError, FileNotFoundError, RuntimeError) as exc:
                    journal.append('VEHICLE_BLOCKED', {'reason':str(exc)})
                    blocked[vehicle] = {'status':'BLOCKED', 'reason':str(exc), 'promotable':False}
                    write_json(vwork/'execution_failure.json', blocked[vehicle])
        if sha_file(plan_path) != plan_sha or _runtime_identity() != runtime:
            raise ValueError('plan/source changed during run')
        verify_parent(parent, plan['parent_manifest_sha256'])
        if any(sha_file(Path(p)) != h for p,h in frozen.items()):
            raise ValueError('real source or catalog changed during run')
        summary = {'schema':RUN_SCHEMA, 'run_id':output.name, 'runtime':runtime,
            'plan_sha256':plan_sha, 'source_evidence':evidence, 'parent_package':str(parent),
            'parent_manifest_sha256':plan['parent_manifest_sha256'], 'vehicles':results, 'blocked_vehicles':blocked,
            'search_config':vars(config), 'output_policy':LINKED_SOFT_CEILING_V1,
            'promotable':False, 'human_status':'NOT_EVALUATED',
            'scope':'FOURCAR_SOURCE_PARAMETERS_ONLY; R3_RELATIVE_NOT_SIMILARITY_PERCENT'}
        write_json(staging/'summary.json', summary)
        _write_qualification(staging, summary)
        files = {p.relative_to(staging).as_posix():sha_file(p) for p in staging.rglob('*') if p.is_file()}
        write_json(staging/'ARTIFACTS.json', seal_payload({'files':files},'s12.stage_ai.feedback_artifacts.v1'))
        verify_run(staging)
        staging.rename(output)
        staging = None
        return summary
    except Exception as exc:
        # Keep diagnostics on infrastructure/interruption failures, never expose as ready.
        if staging is not None:
            write_json(staging/'INCOMPLETE.json', {'error':str(exc), 'promotable':False})
            failed = output.parent / (output.name + '-failed-' + staging.name.rsplit('-',1)[-1])
            staging.rename(failed)
            staging = None
        raise
    finally:
        if staging is not None:
            shutil.rmtree(staging)
        lock.unlink(missing_ok=True)


def _write_qualification(root: Path, summary: Mapping) -> dict:
    receipt = build_qualification_receipt(root, summary)
    write_json(root/QUALIFICATION_FILENAME, receipt)
    return receipt


def verify_run(root: Path, expected_sha: str | None = None):
    root = root.resolve()
    if expected_sha and sha_file(root/'ARTIFACTS.json') != expected_sha:
        raise ValueError('run manifest file digest mismatch')
    m = _read_sealed(root/'ARTIFACTS.json')
    if m.get('schema') != 's12.stage_ai.feedback_artifacts.v1':
        raise ValueError('wrong run manifest schema')
    files = m['files']
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != root/'ARTIFACTS.json'}
    if not files or set(files) != actual:
        raise ValueError('run artifact inventory mismatch')
    for rel, digest in files.items():
        if sha_file(_safe(root,rel)) != digest:
            raise ValueError('run artifact drift')
    summary = read(root/'summary.json')
    if summary.get('schema') != RUN_SCHEMA or summary.get('promotable') is not False:
        raise ValueError('wrong summary contract')
    qualification_path = root/QUALIFICATION_FILENAME
    if qualification_path.is_file():
        if summary.get('output_policy') != LINKED_SOFT_CEILING_V1:
            raise ValueError('four-car run output policy mismatch')
        verify_qualification_receipt(root, summary, read(qualification_path), require_pass=False)
    else:
        # Historical sealed runs predate persisted Task-1 qualification.  They
        # remain readable only when the caller binds the exact artifact SHA,
        # and must still pass a fresh independent recomputation.
        if expected_sha is None or 'output_policy' in summary:
            raise ValueError('independent qualification receipt missing')
        legacy_summary = copy.deepcopy(summary)
        legacy_summary['output_policy'] = LINKED_SOFT_CEILING_V1
        legacy_receipt = build_qualification_receipt(root, legacy_summary)
        verify_qualification_receipt(root, legacy_summary, legacy_receipt, require_pass=True)
    from .feedback_evidence import read_journal
    for v,r in summary['vehicles'].items():
        if fit_eligibility(r) != r['eligibility']:
            raise ValueError('feedback qualification drift')
        if r.get('status') == 'ALL_SCENE_NUMERIC_REJECTED_ROLLED_BACK':
            relative = r.get('failure_receipt')
            if not isinstance(relative, str):
                raise ValueError('numeric-rejected vehicle is missing failure receipt')
            failure = _read_sealed(_safe(root, relative))
            if failure.get('vehicle') != v or failure.get('status') != r['status']:
                raise ValueError('numeric-rejected vehicle failure receipt mismatch')
        if set(r['baseline_records']) != set(SCENES) or set(r['selected_records']) != set(SCENES):
            raise ValueError('incomplete per-scene records')
        for group, field in (('baseline','baseline_wav_sha256'),('tuned','selected_wav_sha256')):
            for s in SCENES:
                if sha_file(root/group/v/'web_audio'/(s+'.wav')) != r[field][s]:
                    raise ValueError('selected candidate WAV drift')
        for log in r['logs'].values():
            read_journal(_safe(root,log))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    p.add_argument('--baseline-package',type=Path,required=True)
    p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('run')
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-trials',type=int,default=25)
    p.add_argument('--allow-r3-unsynchronized',action='store_true')
    p=sub.add_parser('verify')
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    if args.command=='prepare':
        prepare(args.baseline_package,args.manifest_sha256,args.out)
    elif args.command=='run':
        if not args.allow_r3_unsynchronized:
            parser.error('explicit R3 relative-only authorization required')
        result=run(args.plan,args.out,config=SearchConfig(max_trials=args.max_trials))
        print(json.dumps({v:r['status'] for v,r in result['vehicles'].items()},ensure_ascii=False))
    else:
        verify_run(args.run,args.manifest_sha256)
        print('verified')


if __name__=='__main__':
    main()
