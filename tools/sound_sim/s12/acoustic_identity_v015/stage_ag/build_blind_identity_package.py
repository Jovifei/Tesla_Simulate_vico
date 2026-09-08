"""Create a sealed Stage AG blind vehicle-identification package.

The public package contains anonymous Car A/B/C/D audio only.  The true vehicle
mapping and source/destination PCM hashes are written to a separate private file.
The public manifest keeps only a nonce-hardened commitment to that private receipt,
so it cannot be trivially joined against the source package's candidate hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..stage_af.package_integrity import canonical_json_bytes, sha256_file

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
SCENE_FILES = {
    "hot_idle": "03_hot_idle.wav",
    "steady_mid": "09_steady_mid.wav",
    "full_pull": "02_full_pull.wav",
}
LABELS = ("Car_A", "Car_B", "Car_C", "Car_D")


def _manifest_checksum(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _vehicle_entry(manifest: Mapping[str, Any], vehicle: str) -> Mapping[str, Any]:
    for entry in manifest.get("vehicles", []):
        if entry.get("vehicle") == vehicle:
            return entry
    raise ValueError(f"source package missing vehicle: {vehicle}")


def _html(public_manifest: Mapping[str, Any]) -> str:
    manifest_json = json.dumps(public_manifest, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stage AG 车型盲听</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0b0f19;color:#e5e7eb;max-width:1100px;margin:auto;padding:24px}}
.card{{background:#111827;border:1px solid #374151;border-radius:12px;padding:16px;margin:14px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
audio{{width:100%}} input,textarea{{width:100%;box-sizing:border-box;background:#0f172a;color:#fff;border:1px solid #475569;border-radius:6px;padding:8px}}
button{{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:10px 14px;cursor:pointer}}
small{{color:#94a3b8}}
</style></head><body>
<h1>Stage AG · 车型身份盲听</h1>
<p>请不要查看 sealed mapping。先凭声音判断 Car A/B/C/D 分别更像哪辆车，并记录最容易混淆的车型。</p>
<div id="root"></div>
<button onclick="exportFeedback()">导出盲听反馈 JSON</button>
<script>
const MANIFEST={manifest_json};
const feedback={{}};
const root=document.getElementById('root');
for(const scene of MANIFEST.scenes){{
  const section=document.createElement('section'); section.className='card';
  section.innerHTML=`<h2>${{scene}}</h2><div class="grid"></div>`;
  const grid=section.querySelector('.grid');
  for(const item of MANIFEST.artifacts.filter(x=>x.scene===scene)){{
    const card=document.createElement('div'); card.className='card';
    card.innerHTML=`<strong>${{item.label.replace('_',' ')}}</strong>
      <audio controls preload="metadata" src="${{item.path}}"></audio>
      <input placeholder="你认为像哪辆车？" data-k="${{scene}}:${{item.label}}:guess">
      <textarea placeholder="机械感、车型身份、最像哪辆错误车型..." data-k="${{scene}}:${{item.label}}:notes"></textarea>`;
    grid.appendChild(card);
  }}
  root.appendChild(section);
}}
function exportFeedback(){{
  document.querySelectorAll('[data-k]').forEach(x=>feedback[x.dataset.k]=x.value);
  const payload={{
    schema:'s12.stage_ag.blind_feedback.v1',
    timestamp:new Date().toISOString(),
    blind_manifest_sha256:MANIFEST.manifest_sha256,
    mapping_commitment_sha256:MANIFEST.mapping_commitment_sha256,
    human_status:'JOVI_BLIND_FEEDBACK_SUBMITTED',
    feedback
  }};
  const blob=new Blob([JSON.stringify(payload,null,2)],{{type:'application/json'}});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='stage_ag_blind_feedback.json'; a.click(); URL.revokeObjectURL(a.href);
}}
</script></body></html>"""


def build_blind_package(
    source_package: Path,
    output_root: Path,
    mapping_output: Path,
    *,
    seed: int | None = None,
    scenes: tuple[str, ...] = tuple(SCENE_FILES),
) -> Path:
    source_package = source_package.resolve()
    output_root = output_root.resolve()
    mapping_output = mapping_output.resolve()
    if output_root.exists():
        raise FileExistsError(output_root)
    if output_root == mapping_output or output_root in mapping_output.parents:
        raise ValueError("sealed mapping must be outside the public blind package")

    source_manifest_path = source_package / "audition_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("schema") != "s12.stage_ag.package_manifest.v1":
        raise ValueError("source package is not a Stage AG identity package")
    if source_manifest.get("identity_mode") not in ("legacy", "vehicle_identity_v1"):
        raise ValueError("source package has unsupported identity mode")
    recorded_manifest_sha = str(source_manifest.get("manifest_sha256", ""))
    source_for_hash = dict(source_manifest)
    source_for_hash.pop("manifest_sha256", None)
    calculated_manifest_sha = _manifest_checksum(source_for_hash)
    if not recorded_manifest_sha or recorded_manifest_sha != calculated_manifest_sha:
        raise ValueError("source Stage AG manifest checksum mismatch")
    for vehicle in VEHICLES:
        _vehicle_entry(source_manifest, vehicle)

    rng = random.Random(int(seed)) if seed is not None else secrets.SystemRandom()
    shuffled = list(VEHICLES)
    rng.shuffle(shuffled)
    mapping = dict(zip(LABELS, shuffled))
    randomization_mode = (
        "DETERMINISTIC_DIAGNOSTIC" if seed is not None else "SYSTEM_RANDOM_BLIND"
    )

    output_root.mkdir(parents=True, exist_ok=False)
    public_artifacts: list[dict[str, str]] = []
    private_bindings: list[dict[str, str]] = []
    for scene in scenes:
        if scene not in SCENE_FILES:
            raise ValueError(f"unsupported blind scene: {scene}")
        scene_root = output_root / scene
        scene_root.mkdir()
        filename = SCENE_FILES[scene]
        for label, vehicle in mapping.items():
            entry = _vehicle_entry(source_manifest, vehicle)
            source = source_package / str(entry["directory"]) / "web_audio" / filename
            expected = str(entry.get("candidate_pcm_sha256", {}).get(filename, ""))
            actual = sha256_file(source)
            if expected and expected != actual:
                raise ValueError(f"source candidate SHA mismatch: {vehicle}/{filename}")
            destination = scene_root / f"{label}.wav"
            shutil.copyfile(source, destination)
            copied = sha256_file(destination)
            if copied != actual:
                raise RuntimeError("blind package byte copy changed candidate PCM")
            relative = destination.relative_to(output_root).as_posix()
            # Public metadata intentionally omits raw PCM hashes, because those
            # hashes could be joined against the source package to reveal labels.
            public_artifacts.append(
                {
                    "scene": scene,
                    "label": label,
                    "path": relative,
                }
            )
            private_bindings.append(
                {
                    "scene": scene,
                    "label": label,
                    "vehicle": vehicle,
                    "source_sha256": actual,
                    "blind_copy_sha256": copied,
                    "path": relative,
                }
            )

    # A random nonce makes the published commitment non-enumerable even though
    # the vehicle mapping itself has only 4! permutations.
    commitment_nonce = secrets.token_hex(32)
    private_mapping = {
        "schema": "s12.stage_ag.blind_mapping.v2",
        "status": "SEALED_UNTIL_JOVI_FEEDBACK",
        "randomization_mode": randomization_mode,
        "seed": int(seed) if seed is not None else None,
        "commitment_nonce": commitment_nonce,
        "source_package_manifest_sha256": sha256_file(source_manifest_path),
        "mapping": mapping,
        "artifact_bindings": private_bindings,
    }
    mapping_output.parent.mkdir(parents=True, exist_ok=True)
    if mapping_output.exists():
        raise FileExistsError(mapping_output)
    mapping_output.write_text(
        json.dumps(private_mapping, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    mapping_commitment = sha256_file(mapping_output)

    public = {
        "schema": "s12.stage_ag.blind_identity_manifest.v2",
        "status": "WAITING_FOR_JOVI_BLIND_IDENTITY_FEEDBACK",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "randomization_mode": randomization_mode,
        "seed_commitment_sha256": (
            hashlib.sha256(str(seed).encode()).hexdigest()
            if seed is not None
            else None
        ),
        "source_identity_mode": source_manifest["identity_mode"],
        "source_package_manifest_sha256": sha256_file(source_manifest_path),
        "mapping_commitment_sha256": mapping_commitment,
        "mapping_status": "SEALED_UNTIL_JOVI_FEEDBACK",
        "scenes": list(scenes),
        "labels": list(LABELS),
        "artifacts": public_artifacts,
        "rules": [
            "mapping and raw source/copy SHA bindings are intentionally excluded from this public package",
            "audio bytes are copied without normalization or re-rendering",
            "do not reveal mapping before Jovi submits blind feedback",
        ],
    }
    public["manifest_sha256"] = _manifest_checksum(public)
    (output_root / "blind_identity_manifest.json").write_text(
        json.dumps(public, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "index.html").write_text(_html(public), encoding="utf-8")
    return output_root / "blind_identity_manifest.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build sealed Stage AG blind identity package")
    parser.add_argument("--source-package", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--mapping-output", required=True, type=Path)
    parser.add_argument(
        "--seed",
        type=int,
        help="deterministic diagnostic only; omit for a true system-random blind mapping",
    )
    parser.add_argument("--scenes", nargs="+", choices=sorted(SCENE_FILES), default=list(SCENE_FILES))
    args = parser.parse_args(argv)
    result = build_blind_package(
        args.source_package,
        args.output_root,
        args.mapping_output,
        seed=args.seed,
        scenes=tuple(args.scenes),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
