"""Render Stage AG legacy-vs-vehicle-identity diagnostic WAV pairs.

This is intentionally a local diagnostic tool. It does not download Reference
audio, does not perform fitting, and does not create a Human/OEM qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scipy.io import wavfile

from ..stage_af.physical_closed_loop import build_fit_scene
from .vehicle_identity import (
    IDENTITY_MODE_LEGACY,
    IDENTITY_MODE_V1,
    VehicleIdentityEngine,
    vehicle_identity_signature,
)

VEHICLES = ("hellcat", "ferrari_458", "lfa", "gtr_r35")
DEFAULT_SCENES = ("hot_idle", "steady_mid", "full_pull", "afterfire")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_probe(
    output_root: Path,
    *,
    vehicles: tuple[str, ...] = VEHICLES,
    scenes: tuple[str, ...] = DEFAULT_SCENES,
    seed: int = 20260908,
    numerical_fixes: tuple[str, ...] = (),
) -> Path:
    output_root.mkdir(parents=True, exist_ok=False)
    records = []
    for vehicle in vehicles:
        vehicle_root = output_root / vehicle
        vehicle_root.mkdir(parents=True, exist_ok=False)
        legacy = VehicleIdentityEngine(
            vehicle,
            identity_mode=IDENTITY_MODE_LEGACY,
            numerical_fixes=numerical_fixes,
            seed=seed,
        )
        identity = VehicleIdentityEngine(
            vehicle,
            identity_mode=IDENTITY_MODE_V1,
            numerical_fixes=numerical_fixes,
            seed=seed,
        )
        for scene in scenes:
            rpm, throttle, duration, shift, afterfire, bov = build_fit_scene(vehicle, scene)
            for mode, renderer in ((IDENTITY_MODE_LEGACY, legacy), (IDENTITY_MODE_V1, identity)):
                pcm = renderer.render_track(
                    rpm,
                    throttle,
                    duration,
                    shift_events=shift,
                    afterfire_events=afterfire,
                    bov_events=bov,
                )
                filename = f"{scene}__{mode}.wav"
                path = vehicle_root / filename
                wavfile.write(path, renderer.sr, pcm)
                records.append(
                    {
                        "vehicle": vehicle,
                        "scene": scene,
                        "identity_mode": mode,
                        "path": path.relative_to(output_root).as_posix(),
                        "sha256": _sha256(path),
                        "sample_rate": renderer.sr,
                    }
                )
    manifest = {
        "schema": "s12.stage_ag.vehicle_identity_probe.v1",
        "status": "DIAGNOSTIC_ONLY_WAITING_FOR_JOVI",
        "seed": seed,
        "numerical_fixes": list(numerical_fixes),
        "vehicles": {vehicle: vehicle_identity_signature(vehicle) for vehicle in vehicles},
        "artifacts": records,
        "rules": [
            "legacy is the existing EngineAcoustics baseline",
            "Hellcat identity_v1 must remain byte-identical to legacy",
            "non-Hellcat identity_v1 is an audition candidate, not a profile freeze",
            "no Reference audio is downloaded or inferred by this tool",
        ],
    }
    manifest_path = output_root / "identity_probe_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render Stage AG vehicle identity diagnostic pairs")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--vehicle", choices=["all", *VEHICLES], default="all")
    parser.add_argument("--scenes", nargs="+", choices=DEFAULT_SCENES, default=list(DEFAULT_SCENES))
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--numerical-fixes", nargs="*", default=[])
    args = parser.parse_args(argv)
    vehicles = VEHICLES if args.vehicle == "all" else (args.vehicle,)
    manifest = render_probe(
        args.output_root,
        vehicles=tuple(vehicles),
        scenes=tuple(args.scenes),
        seed=args.seed,
        numerical_fixes=tuple(args.numerical_fixes),
    )
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
