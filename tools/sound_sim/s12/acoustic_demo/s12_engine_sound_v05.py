"""Build the deterministic S12 Engine Sound Product Vertical Slice v0.5."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess

from audio_parameter_package.package import build_audio_parameter_package
from engine_operating_points.library import load_operating_point_library
from engine_product_excitation import build_product_demo_states, generate_product_excitation
from s12_ptr_network import run_ptr_network
from sound_renderer.s12_product_renderer import render_product_wav, renderer_profile_from_library


GENERATOR_VERSION = "S12 Engine Sound Product Vertical Slice v0.5"
LABELS = ["synthetic", "uncalibrated", "offline", "not_realtime_qualified"]


@dataclass(frozen=True)
class V05Result:
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


def _write_report(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "# S12 Engine Sound Product Vertical Slice v0.5 Report",
                "",
                "Synthetic, uncalibrated, offline, and not realtime-qualified. This is not an OEM or real-vehicle clone.",
                "",
                "## Completed",
                "",
                "- v0.4 excitation-to-PTR/radiation architecture",
                "- RPM/load operating-point library",
                "- fixed-format renderer",
                "- AudioParameterPackage v0.1 with C/synthetic provenance and frozen radiation-package content pin",
                "- deterministic offline demo",
                "- future DSP interface design",
                "",
                "## Not completed",
                "",
                "- OEM calibration",
                "- real vehicle measurement",
                "- Android integration",
                "- ESP32 DSP",
                "- CAN input",
                "- realtime latency",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _current_source_commit() -> str:
    project_root = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    source_commit = result.stdout.strip()
    if len(source_commit) != 40:
        raise ValueError("current source commit is unavailable")
    return source_commit


def run_v05_demo(output_root: Path, source_commit: str | None = None) -> V05Result:
    """Render exact v0.5 product cases through excitation -> PTR -> renderer."""
    current_commit = _current_source_commit()
    if source_commit is not None and source_commit != current_commit:
        raise ValueError("caller-supplied source commit must equal current HEAD")
    source_commit = current_commit
    demo = output_root / "v05_demo"
    demo.mkdir(parents=True, exist_ok=True)
    library = load_operating_point_library()
    renderer_profile = renderer_profile_from_library(library)
    parameter_package = build_audio_parameter_package(library, renderer_profile, source_commit)
    states = build_product_demo_states(library)
    analysis = {}
    for name, state in states.items():
        excitation = generate_product_excitation(state, library)
        ptr = run_ptr_network(excitation)
        metadata = render_product_wav(
            ptr, demo / f"{name}.wav", demo / "metadata" / f"{name}.json", renderer_profile
        )
        metadata.update(
            {
                "architecture": "operating_point_to_excitation_to_ptr_to_radiation_to_renderer",
                "calibrated": False,
                "engine_excitation_hash": excitation.source_identity_sha256,
                "generator_version": GENERATOR_VERSION,
                "labels": LABELS,
                "ptr_hash": ptr.source_identity_sha256,
                "state_case": name,
            }
        )
        _write_json(demo / "metadata" / f"{name}.json", metadata)
        analysis[name] = {
            "clipping_count": metadata["clipping_count"],
            "load": [state.load[0], state.load[-1]],
            "peak": metadata["peak"],
            "rpm_range": [state.rpm[0], state.rpm[-1]],
            "sample_rate": metadata["sample_rate"],
            "synthetic": True,
        }
    _write_json(
        demo / "vehicle_state.json",
        {
            "schema": "s12.vehicle_state.v05",
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
    _write_json(demo / "audio_parameter_package.json", parameter_package)
    _write_json(
        demo / "sound_analysis.json",
        {
            "schema": "s12.sound_analysis.v05",
            "generator_version": GENERATOR_VERSION,
            "cases": analysis,
        },
    )
    report_path = _write_report(demo / "S12_Engine_Sound_Product_Vertical_Slice_v05_Report.md")
    controlled = sorted(
        path
        for path in demo.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "SHA256.txt"}
    )
    manifest_path = _write_json(
        demo / "manifest.json",
        {
            "architecture": "operating_point_to_excitation_to_ptr_to_radiation_to_renderer",
            "files": {path.relative_to(demo).as_posix(): _sha256(path) for path in controlled},
            "generator_version": GENERATOR_VERSION,
            "source_commit": source_commit,
            "synthetic": True,
        },
    )
    sha256_path = demo / "SHA256.txt"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sha256_path.write_text(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(manifest["files"].items())) + "\n",
        encoding="utf-8",
    )
    return V05Result(demo, manifest_path, sha256_path, report_path)
