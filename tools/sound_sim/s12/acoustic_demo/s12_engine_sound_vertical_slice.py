"""Build the deterministic Synthetic Engine Sound Vertical Slice v0.3."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

from engine_order_model import order_frequencies_hz
from s12_engine_sound_design import load_design_parameters, load_order_profile, render_sound_design
from s12_engine_sound_renderer import EngineSoundRenderResult, render_designed_wav
from s12_engine_source import synthesize_four_stroke_trajectory
from s12_ptr_network import run_ptr_network
from vehicle_state import (
    DEFAULT_CASES,
    VehicleStateSeries,
    build_default_vehicle_state_cases,
    build_load_mapping_cases,
    write_vehicle_state_bundle,
)


GENERATOR_VERSION = "Synthetic Engine Sound Vertical Slice v0.3"
LABELS = ["synthetic", "uncalibrated", "offline", "not_realtime_qualified"]


@dataclass(frozen=True)
class CaseRender:
    state: VehicleStateSeries
    render: EngineSoundRenderResult
    engine_source_hash: str
    ptr_hash: str
    analysis: dict


@dataclass(frozen=True)
class VerticalSliceResult:
    renders: dict[str, CaseRender]
    manifest_path: Path
    sha256_path: Path
    report_path: Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_png(path: Path, pixels: list[list[tuple[int, int, int]]]) -> None:
    height, width = len(pixels), len(pixels[0])
    raw = b"".join(
        b"\x00" + bytes(component for pixel in row for component in pixel) for row in pixels
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    content = b"\x89PNG\r\n\x1a\n" + chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content + chunk(b"IDAT", zlib.compress(raw, level=9)) + chunk(b"IEND", b""))


def _bar_chart(
    values: list[float], color: tuple[int, int, int]
) -> list[list[tuple[int, int, int]]]:
    width, height = 360, 180
    pixels = [[(255, 255, 255) for _ in range(width)] for _ in range(height)]
    maximum = max(values) if values else 1.0
    bar_width = max(1, width // max(1, len(values)))
    for index, value in enumerate(values):
        top = height - 1 - round((value / max(maximum, 1.0e-12)) * (height - 20))
        for x in range(index * bar_width, min(width, (index + 1) * bar_width - 2)):
            for y in range(max(0, top), height):
                pixels[y][x] = color
    return pixels


def _write_case_images(output_dir: Path, case: str, harmonics: list[dict]) -> None:
    values = [float(item["rms"]) for item in harmonics]
    _write_png(output_dir / "analysis" / case / "spectrum.png", _bar_chart(values, (33, 102, 172)))
    spans = [
        abs(float(item["frequency_hz"][1]) - float(item["frequency_hz"][0])) for item in harmonics
    ]
    _write_png(output_dir / "analysis" / case / "order_map.png", _bar_chart(spans, (42, 140, 80)))


def _rewrite_case_metadata(render: EngineSoundRenderResult) -> None:
    metadata = json.loads(render.metadata_path.read_text(encoding="utf-8"))
    metadata["vertical_slice_generator_version"] = GENERATOR_VERSION
    metadata["vertical_slice_labels"] = LABELS
    render.metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _case_analysis(state: VehicleStateSeries, designed, source_hash: str, ptr_hash: str) -> dict:
    mono = [(left + right) / 2.0 for left, right in zip(designed.left, designed.right)]
    profile = load_order_profile()
    start = order_frequencies_hz(state.rpm[0], profile)
    stop = order_frequencies_hz(state.rpm[-1], profile)
    harmonics = [
        {
            "frequency_hz": [start[entry["name"]], stop[entry["name"]]],
            "name": entry["name"],
            "order": entry["order"],
            "rms": designed.order_spectrum_rms.get(f"order_{entry['order']:g}", 0.0),
            "source": "synthetic",
        }
        for entry in profile["orders"]
    ]
    return {
        "clipping_count": 0,
        "engine_source_hash": source_hash,
        "generator_version": GENERATOR_VERSION,
        "harmonics": harmonics,
        "load": [state.load[0], state.load[-1]],
        "peak": max(abs(value) for value in mono),
        "ptr_hash": ptr_hash,
        "rpm_range": [state.rpm[0], state.rpm[-1]],
        "rms": math.sqrt(sum(value * value for value in mono) / len(mono)),
        "sample_rate": 48000,
        "synthetic": True,
    }


def _edge_envelope(frame_count: int, fade_frames: int) -> list[float]:
    denominator = fade_frames - 1
    return [
        index / denominator
        if index < fade_frames
        else (
            (frame_count - 1 - index) / denominator if index >= frame_count - fade_frames else 1.0
        )
        for index in range(frame_count)
    ]


def _remove_dc_with_silent_edges(designed) -> object:
    """Remove PTR texture DC without disturbing the renderer's zero endpoints."""
    fade_frames = round(
        float(load_design_parameters()["parameters"]["output_edge_fade_s"]["value"])
        * designed.sample_rate_hz
    )
    envelope = _edge_envelope(len(designed.left), fade_frames)
    envelope_mean = sum(envelope) / len(envelope)
    if envelope_mean <= 0.0:
        raise ValueError("v0.3 DC envelope is empty")

    def corrected(channel: list[float]) -> list[float]:
        correction = (sum(channel) / len(channel)) / envelope_mean
        return [sample - correction * weight for sample, weight in zip(channel, envelope)]

    left = corrected(designed.left)
    right = corrected(designed.right)
    profile = load_order_profile()
    mono = [(a + b) / 2.0 for a, b in zip(left, right)]
    scale = 2.0 / len(mono)
    orders = sorted({float(entry["order"]) for entry in profile["orders"]})
    spectrum = {}
    for order in orders:
        sine = scale * sum(
            sample * math.sin(order * phase)
            for sample, phase in zip(mono, designed.fundamental_phase_rad)
        )
        cosine = scale * sum(
            sample * math.cos(order * phase)
            for sample, phase in zip(mono, designed.fundamental_phase_rad)
        )
        spectrum[f"order_{order:g}"] = math.hypot(sine, cosine) / math.sqrt(2.0)
    return replace(designed, left=left, right=right, order_spectrum_rms=spectrum)


def _render_case(
    state: VehicleStateSeries,
    output_dir: Path,
    wav_path: Path,
    metadata_path: Path,
    write_images: bool = True,
) -> CaseRender:
    state.validate()
    source = synthesize_four_stroke_trajectory(state.source_config(), state.rpm, state.load)
    ptr = run_ptr_network(source)
    designed = render_sound_design(
        ptr, state.to_order_schedule(), load_order_profile(), load_design_parameters()
    )
    designed = _remove_dc_with_silent_edges(designed)
    render = render_designed_wav(designed, wav_path, metadata_path)
    _rewrite_case_metadata(render)
    analysis = _case_analysis(
        state, designed, source.source_identity_sha256, ptr.source_identity_sha256
    )
    if write_images:
        _write_case_images(output_dir, state.case_id, analysis["harmonics"])
    return CaseRender(
        state, render, source.source_identity_sha256, ptr.source_identity_sha256, analysis
    )


def _write_rpm_trace(path: Path, cases: dict[str, VehicleStateSeries]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["case", "timestamp", "rpm", "speed", "acceleration", "load", "throttle"])
        for name, state in cases.items():
            writer.writerows(
                (name, *values)
                for values in zip(
                    state.timestamp,
                    state.rpm,
                    state.speed,
                    state.acceleration,
                    state.load,
                    state.throttle,
                )
            )
    return path


def _write_report(path: Path, renders: dict[str, CaseRender]) -> Path:
    path.write_text(
        "\n".join(
            [
                "# S12 Engine Sound Vertical Slice Report",
                "",
                f"Generator: {GENERATOR_VERSION}",
                "",
                "This is a synthetic, uncalibrated, offline prototype and is not realtime-qualified.",
                "It is not an OEM engine clone and contains no recording or real vehicle measurement.",
                "",
                "## Completed",
                "",
                "- Engine order synthesis: COMPLETED",
                "- RPM mapping: COMPLETED",
                "- Load mapping: COMPLETED",
                "- Transient processing: COMPLETED",
                "- PTR coupling: COMPLETED through the existing immutable radiation package",
                "- Offline 48 kHz WAV: COMPLETED",
                "",
                "## Not completed",
                "",
                "- OEM calibration: NOT COMPLETED",
                "- Real vehicle measurement: NOT COMPLETED",
                "- Realtime DSP: NOT COMPLETED",
                "- Phone integration: NOT COMPLETED",
                "",
                "## Cases",
                "",
                *[
                    f"- {name}: engine_source_hash={case.engine_source_hash}; ptr_hash={case.ptr_hash}"
                    for name, case in renders.items()
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_manifest(output_dir: Path, controlled: list[Path]) -> Path:
    manifest_path = output_dir / "manifest.json"
    payload = {
        path.relative_to(output_dir).as_posix(): _sha256(path)
        for path in sorted(controlled, key=lambda item: item.relative_to(output_dir).as_posix())
    }
    manifest_path.write_text(
        json.dumps(
            {
                "files": payload,
                "generator_version": GENERATOR_VERSION,
                "labels": LABELS,
                "schema": "s12.engine_sound_vertical_slice.v0.3",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _write_sha256(path: Path, manifest_path: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lines = [f"{digest}  {name}" for name, digest in sorted(manifest["files"].items())]
    lines.append(f"{_sha256(manifest_path)}  {manifest_path.name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_vertical_slice(output_dir: Path) -> VerticalSliceResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    states = build_default_vehicle_state_cases()
    renders = {
        name: _render_case(
            state,
            output_dir,
            output_dir / f"{name}.wav",
            output_dir / "metadata" / f"{name}.json",
        )
        for name, state in states.items()
    }
    for state in build_load_mapping_cases().values():
        _render_case(
            state,
            output_dir,
            output_dir / "load_map" / f"{state.case_id}.wav",
            output_dir / "load_map" / "metadata" / f"{state.case_id}.json",
            write_images=False,
        )
    vehicle_state_path = write_vehicle_state_bundle(output_dir / "vehicle_state.json", states)
    rpm_trace_path = _write_rpm_trace(output_dir / "rpm_trace.csv", states)
    analysis_path = output_dir / "sound_analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "cases": {name: case.analysis for name, case in renders.items()},
                "generator_version": GENERATOR_VERSION,
                "labels": LABELS,
                "schema": "s12.engine_sound_analysis.v1",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = _write_report(output_dir / "S12 Engine Sound Vertical Slice Report.md", renders)
    controlled = [
        vehicle_state_path,
        rpm_trace_path,
        analysis_path,
        report_path,
        *(case.render.wav_path for case in renders.values()),
        *(case.render.metadata_path for case in renders.values()),
        *(
            output_dir / "analysis" / name / image_name
            for name in DEFAULT_CASES
            for image_name in ("spectrum.png", "order_map.png")
        ),
        *(
            output_dir / "load_map" / f"{name}.wav"
            for name in ("low_load", "mid_load", "high_load")
        ),
        *(
            output_dir / "load_map" / "metadata" / f"{name}.json"
            for name in ("low_load", "mid_load", "high_load")
        ),
    ]
    manifest_path = _write_manifest(output_dir, controlled)
    sha256_path = _write_sha256(output_dir / "SHA256.txt", manifest_path)
    return VerticalSliceResult(renders, manifest_path, sha256_path, report_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_vertical_slice(args.output)
    print(f"cases={len(result.renders)} generator={GENERATOR_VERSION}")


if __name__ == "__main__":
    main()
