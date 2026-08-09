"""Deterministic, offline audition artifacts for qualified S12 boundary traces."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
import struct
import wave
import zlib


LABELS = ["synthetic", "uncalibrated", "offline", "not_realtime_qualified"]


@dataclass(frozen=True)
class PressureTrace:
    case_id: str
    time_s: list[float]
    pressure_pa: list[float]
    source_csv_sha256: str
    source_identity_sha256: str = ""
    sample_rate_hz: int | None = None
    firing_frequency_hz: float | None = None
    reference_plane: str = "bore_end"
    provenance: tuple[str, ...] = ()

    @classmethod
    def uniform(
        cls,
        case_id: str,
        samples: list[float],
        sample_rate_hz: int,
        firing_frequency_hz: float | None,
        reference_plane: str,
        provenance: tuple[str, ...],
    ) -> PressureTrace:
        sample_list = list(samples)
        if (
            sample_rate_hz <= 0
            or not sample_list
            or not all(math.isfinite(value) for value in sample_list)
        ):
            raise ValueError("uniform trace requires finite samples and a positive sample rate")
        if (
            (
                firing_frequency_hz is not None
                and (not math.isfinite(firing_frequency_hz) or firing_frequency_hz <= 0)
            )
            or not reference_plane
            or not provenance
        ):
            raise ValueError("uniform trace requires finite provenance metadata")
        identity = {
            "case_id": case_id,
            "samples": sample_list,
            "sample_rate_hz": sample_rate_hz,
            "firing_frequency_hz": firing_frequency_hz,
            "reference_plane": reference_plane,
            "provenance": list(provenance),
        }
        source_identity = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(
            case_id,
            [index / sample_rate_hz for index in range(len(sample_list))],
            sample_list,
            "",
            source_identity,
            sample_rate_hz,
            firing_frequency_hz,
            reference_plane,
            tuple(provenance),
        )


@dataclass(frozen=True)
class AuditionResult:
    sample_rate_hz: int
    clipping_count: int
    source_duration_s: float
    native_wav_duration_s: float
    native_frame_count: int
    source_pressure_csv_path: Path
    native_wav_path: Path
    looped_preview_wav_path: Path
    metadata_json_path: Path
    waveform_png_path: Path
    spectrum_png_path: Path
    manifest_path: Path


def load_trace(csv_path: Path, case_id: str) -> PressureTrace:
    """Load total boundary pressure (outgoing plus incoming) for one case."""
    csv_bytes = csv_path.read_bytes()
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["case_id"] == case_id:
                rows.append(row)
    if len(rows) < 2:
        raise ValueError(f"expected at least two rows for case_id={case_id!r}")
    time_s = [float(row["time_s"]) for row in rows]
    if any(later <= earlier for earlier, later in zip(time_s, time_s[1:])):
        raise ValueError("trace times must be strictly increasing")
    pressure_pa = [
        float(row["outgoing_pressure_pa"]) + float(row["incoming_pressure_pa"]) for row in rows
    ]
    source_csv_sha256 = hashlib.sha256(csv_bytes).hexdigest()
    return PressureTrace(
        case_id,
        time_s,
        pressure_pa,
        source_csv_sha256,
        source_csv_sha256,
        reference_plane="bore_end",
        provenance=("qualified_4d_b", "immutable_source_csv"),
    )


def resample_boxcar(trace: PressureTrace, sample_rate_hz: int) -> list[float]:
    duration_s = trace.time_s[-1] - trace.time_s[0]
    frame_count = max(1, round(duration_s * sample_rate_hz))
    values: list[float] = []
    for frame_index in range(frame_count):
        start_s = trace.time_s[0] + frame_index / sample_rate_hz
        stop_s = trace.time_s[0] + (frame_index + 1) / sample_rate_hz
        bucket = [
            pressure
            for time_s, pressure in zip(trace.time_s, trace.pressure_pa)
            if start_s <= time_s < stop_s
        ]
        values.append(sum(bucket) / len(bucket) if bucket else 0.0)
    return values


def _write_wav(path: Path, samples: list[float], sample_rate_hz: int) -> int:
    pcm = []
    clipping_count = 0
    for sample in samples:
        if sample > 1.0 or sample < -1.0:
            clipping_count += 1
        bounded = max(-1.0, min(1.0, sample))
        pcm.append(round(bounded * 32767))
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate_hz)
        writer.writeframes(struct.pack(f"<{len(pcm)}h", *pcm))
    return clipping_count


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
    path.write_bytes(content + chunk(b"IDAT", zlib.compress(raw, level=9)) + chunk(b"IEND", b""))


def _chart(samples: list[float], spectrum: bool) -> list[list[tuple[int, int, int]]]:
    width, height = 640, 240
    pixels = [[(255, 255, 255) for _ in range(width)] for _ in range(height)]
    middle = height // 2
    for x in range(width):
        pixels[middle][x] = (220, 220, 220)
    if spectrum:
        bins = min(128, max(1, len(samples) // 2))
        values = []
        for bin_index in range(bins):
            real = sum(
                value * math.cos(2 * math.pi * bin_index * index / len(samples))
                for index, value in enumerate(samples)
            )
            imag = sum(
                value * math.sin(2 * math.pi * bin_index * index / len(samples))
                for index, value in enumerate(samples)
            )
            values.append(math.hypot(real, imag))
        peak = max(values) or 1.0
        for x in range(width):
            value = values[min(bins - 1, x * bins // width)] / peak
            top = height - 1 - round(value * (height - 2))
            for y in range(top, height):
                pixels[y][x] = (33, 102, 172)
    else:
        for x in range(width):
            value = samples[min(len(samples) - 1, x * len(samples) // width)]
            y = max(0, min(height - 1, middle - round(value * (height // 2 - 2))))
            pixels[y][x] = (33, 102, 172)
    return pixels


def _write_source_pressure_csv(path: Path, trace: PressureTrace) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["time_s", "boundary_pressure_pa"])
        writer.writerows(zip(trace.time_s, trace.pressure_pa))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_controlled_artifacts(
    trace: PressureTrace,
    normalized: list[float],
    output_dir: Path,
    sample_rate_hz: int,
    gain: float,
) -> AuditionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_csv = output_dir / "source-pressure.csv"
    native_wav = output_dir / "native-duration.wav"
    preview_wav = output_dir / "looped-audition-preview.wav"
    metadata_path = output_dir / "metadata.json"
    waveform_path = output_dir / "waveform.png"
    spectrum_path = output_dir / "spectrum.png"
    manifest_path = output_dir / "sha256-manifest.json"
    _write_source_pressure_csv(source_csv, trace)
    clipping_count = _write_wav(native_wav, normalized, sample_rate_hz)
    loop_count = max(1, math.ceil(sample_rate_hz / len(normalized)))
    clipping_count += _write_wav(preview_wav, normalized * loop_count, sample_rate_hz)
    _write_png(waveform_path, _chart(normalized, spectrum=False))
    _write_png(spectrum_path, _chart(normalized, spectrum=True))
    metadata = {
        "case_id": trace.case_id,
        "clipping_count": clipping_count,
        "labels": LABELS,
        "source_duration_s": trace.time_s[-1] - trace.time_s[0],
        "native_wav_duration_s": len(normalized) / sample_rate_hz,
        "native_frame_count": len(normalized),
        "normalization_gain_per_pa": gain,
        "preview": "looped audition preview; no time scaling",
        "preview_loop_count": loop_count,
        "sample_rate_hz": sample_rate_hz,
        "source_csv_sha256": trace.source_csv_sha256,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    files = [source_csv, native_wav, preview_wav, metadata_path, waveform_path, spectrum_path]
    hashes = {path.name: _sha256(path) for path in files}
    manifest_path.write_text(
        json.dumps({"files": hashes, "sha256": hashes[native_wav.name]}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return AuditionResult(
        sample_rate_hz,
        clipping_count,
        trace.time_s[-1] - trace.time_s[0],
        len(normalized) / sample_rate_hz,
        len(normalized),
        source_csv,
        native_wav,
        preview_wav,
        metadata_path,
        waveform_path,
        spectrum_path,
        manifest_path,
    )


def render_audition(
    trace: PressureTrace, output_dir: Path, target_sample_rate_hz: int = 48000
) -> AuditionResult:
    if target_sample_rate_hz <= 0:
        raise ValueError("target_sample_rate_hz must be positive")
    raw_samples = resample_boxcar(trace, target_sample_rate_hz)
    dc_pa = sum(raw_samples) / len(raw_samples)
    dc_free = [sample - dc_pa for sample in raw_samples]
    gain = 0.70 / max(max(abs(sample) for sample in dc_free), 1e-12)
    normalized = [sample * gain for sample in dc_free]
    return write_controlled_artifacts(trace, normalized, output_dir, target_sample_rate_hz, gain)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_csv = (
        Path(__file__).resolve().parents[1]
        / "benchmark"
        / "baselines"
        / "sprint-4d-b"
        / "radiation-time-domain-traces.csv"
    )
    result = render_audition(load_trace(source_csv, args.case), args.output)
    print(f"rendered {result.native_frame_count} native frames at {result.sample_rate_hz} Hz")


if __name__ == "__main__":
    main()
