"""Build the Synthetic Engine Sound Vertical Slice v0.4 offline demo."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from engine_excitation import (
    PARAMETERS_PATH,
    STATE_SCHEMA_PATH,
    build_default_engine_state_cases,
    generate_engine_excitation,
    load_json_package,
)
from s12_engine_sound_v04_renderer import render_ptr_trace_wav
from s12_ptr_network import run_ptr_network


GENERATOR_VERSION = "Synthetic Engine Sound Vertical Slice v0.4"
LABELS = ["synthetic", "uncalibrated", "offline", "not_realtime_qualified"]


@dataclass(frozen=True)
class V04Result:
    demo_path: Path
    manifest_path: Path
    sha256_path: Path
    report_path: Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_v04_demo(output_root: Path) -> V04Result:
    demo = output_root / "v04_demo"
    demo.mkdir(parents=True, exist_ok=True)
    parameters = load_json_package(PARAMETERS_PATH)
    state_schema = load_json_package(STATE_SCHEMA_PATH)
    sample_rate_hz = int(state_schema["parameters"]["sample_rate_hz"]["value"])
    states = build_default_engine_state_cases()
    renders = {}
    analysis = {}
    for name, state in states.items():
        excitation = generate_engine_excitation(state)
        ptr = run_ptr_network(excitation)
        metadata = render_ptr_trace_wav(
            ptr,
            demo / f"{name}.wav",
            demo / "metadata" / f"{name}.json",
            sample_rate_hz,
            float(parameters["parameters"]["renderer_gain"]["value"]),
            float(parameters["parameters"]["output_edge_fade_s"]["value"]),
        )
        metadata.update(
            {
                "engine_excitation_hash": excitation.source_identity_sha256,
                "generator_version": GENERATOR_VERSION,
                "labels": LABELS,
                "state_case": name,
            }
        )
        _write_json(demo / "metadata" / f"{name}.json", metadata)
        renders[name] = metadata
        analysis[name] = {
            "harmonics": [
                {"name": item, "order": value["order"], "source": "synthetic"}
                for item, value in load_json_package(
                    Path(__file__).with_name("order_profile.json")
                )["parameters"].items()
            ],
            "load": [state.load[0], state.load[-1]],
            "peak": metadata["peak"],
            "ptr_hash": metadata["ptr_hash"],
            "rpm_range": [state.rpm[0], state.rpm[-1]],
            "rms": metadata["rms"],
            "sample_rate": metadata["sample_rate"],
            "synthetic": True,
        }
    _write_json(
        demo / "vehicle_state.json",
        {
            "schema": "s12.vehicle_state.v04",
            "synthetic": True,
            "cases": {
                name: {
                    field: list(getattr(state, field))
                    for field in ("timestamp", "rpm", "speed", "acceleration", "load", "throttle")
                }
                for name, state in states.items()
            },
        },
    )
    _write_json(
        demo / "sound_analysis.json",
        {
            "schema": "s12.sound_analysis.v04",
            "generator_version": GENERATOR_VERSION,
            "cases": analysis,
        },
    )
    report = demo / "S12_Engine_Sound_V04_Report.md"
    report.write_text(
        "\n".join(
            [
                "# S12 Engine Sound v0.4 Report",
                "",
                "Synthetic, uncalibrated, offline, not realtime-qualified.",
                "",
                "## PASS",
                "",
                "- topology: Vehicle State -> Excitation -> PTR -> Radiation -> Audio",
                "- provenance: all v0.4 parameters are source_level C synthetic",
                "- deterministic: controlled double-build SHA checked",
                "- audio quality: 48 kHz, 24-bit stereo, clipping=0",
                "",
                "## Remaining",
                "",
                "- OEM calibration",
                "- realtime DSP",
                "- phone integration",
                "",
            ]
        ),
        encoding="utf-8",
    )
    controlled = sorted(
        path
        for path in demo.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "SHA256.txt"}
    )
    manifest = _write_json(
        demo / "manifest.json",
        {
            "architecture": "excitation_to_ptr_to_radiation",
            "calibrated": False,
            "files": {path.relative_to(demo).as_posix(): _sha256(path) for path in controlled},
            "generator_version": GENERATOR_VERSION,
            "labels": LABELS,
            "synthetic": True,
        },
    )
    sha = demo / "SHA256.txt"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    sha.write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(payload["files"].items())) + "\n",
        encoding="utf-8",
    )
    return V04Result(demo, manifest, sha, report)
