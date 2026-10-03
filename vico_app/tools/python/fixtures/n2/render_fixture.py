"""Synthetic reader-test files; not Kotlin render or reference evidence."""
import hashlib
from pathlib import Path
import struct
import subprocess

import numpy as np

from n2_reference_export import BRANCHES, CHANNELS, COLUMNS, measure


def write_fixture(root):
    root = Path(root)
    root.mkdir()
    artifact = root / "profile.bin"
    process = subprocess.run(["java", str(Path(__file__).with_name("FrozenN2ArtifactFixture.java")), str(artifact)],
                             capture_output=True, text=True, timeout=30)
    if process.returncode:
        raise AssertionError(process.stdout + process.stderr)
    identity = process.stdout.strip()
    kernels = []
    for size, offset in ((2048, 0), (12288, 0), (12288, 2), (12288, 4)):
        kernel = np.zeros(size, dtype="<f8")
        kernel[offset:offset + 2] = [2 ** -.5, -(2 ** -.5)]
        kernels.append(kernel)
    baseline = b"C63HY1V1" + struct.pack("<2i8d3q", 2048, 12288, 1, 1, .08, .2, 1, 0, 0, 0, 1, 2, 3)
    baseline += bytes(32) + b"".join(k.tobytes() for k in kernels)
    (root / "baseline.bin").write_bytes(baseline)
    utf = lambda s: struct.pack(">H", len(s)) + s.encode("ascii")
    frames = 24000
    trajectory = utf("c63.n2.trajectory.v1") + utf("synthetic-reader-test") + struct.pack(">iiB8diBBiBB",
                  1, frames, 1, 0, 3000, 100, .5, .5, .5, .5, 1, 0, 0, 0, 1, 0, 0)
    (root / "trajectory.bin").write_bytes(trajectory)
    digest = lambda b: hashlib.sha256(b).hexdigest()
    metadata = dict(schema="c63.n2.render_receipt.v1", status="RENDERED_ONLY_NOT_ACOUSTIC_QUALIFICATION",
                    profile_identity=identity, artifact_sha256=digest(artifact.read_bytes()),
                    baseline_identity=digest(baseline), baseline_artifact_sha256=digest(baseline),
                    fixture_id="synthetic-reader-test", fixture_sha256=digest(trajectory), sample_rate="48000",
                    frames=str(frames), partitions="960", tap_stage="source_before_delay_idle_shift_output_headroom",
                    tap_channels=",".join(CHANNELS))
    lines = [k + "\t" + v for k, v in metadata.items()] + ["\t".join(COLUMNS)]
    time = np.arange(frames) / 48000
    low, mid = .02 * np.sin(2*np.pi*100*time), .01 * np.sin(2*np.pi*900*time)
    for stem, (mode, audible, candidate) in BRANCHES.items():
        taps = np.zeros((frames, 9), dtype="<f8")
        taps[:, 0], taps[:, 1] = low, mid * (1.02 if mode in ("S", "SE") else 1)
        pcm = taps[:, :7].sum(axis=1).astype("<f4")
        measurements = measure(pcm)
        for suffix, x in ((".pcm.f32le", pcm), (".taps.f64le", taps)):
            name = stem + suffix
            payload = x.tobytes()
            (root / name).write_bytes(payload)
            lines.append("\t".join(map(str, (name, digest(payload), len(payload), candidate, mode, str(audible).lower(),
                                            measurements["rms"], measurements["peak"], 0, 0, 0))))
    (root / "manifest.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def rewrite_row(root, name, **changes):
    path = Path(root) / "manifest.tsv"
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        cells = line.split("\t")
        if cells[0] == name:
            for key, value in changes.items():
                cells[COLUMNS.index(key)] = str(value)
            lines[i] = "\t".join(cells)
    path.write_text("\n".join(lines) + "\n")


def replace_metadata(root, key, value):
    path = Path(root) / "manifest.tsv"
    lines = [key + "\t" + value if line.startswith(key + "\t") else line for line in path.read_text().splitlines()]
    path.write_text("\n".join(lines) + "\n")
