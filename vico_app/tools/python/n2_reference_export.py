"""Read actual N2 render_receipt.v1 files; never render, fit, reserve or recalibrate.

Hashes bind the bytes read, not the producer's honesty. Use trusted renderer source
and immutable exports. This reader cannot attest snapshot replay or reference rights.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import zip_longest
import math
from pathlib import Path
import re
import struct

import numpy as np

if __package__:
    from .n2_artifact_gate import CANDIDATE, _binary_identity
else:
    from n2_artifact_gate import CANDIDATE, _binary_identity

CHANNELS = ("exhaust", "bark", "intake", "mechanical", "afterfire", "body", "rumble",
            "combustion_impulse", "afterfire_impulse")
BRANCHES = {
    "t_event_on": ("T", True, CANDIDATE + "_T"),
    "s_event_on": ("S", True, CANDIDATE + "_S"),
    "e_event_on": ("E", True, CANDIDATE + "_E"),
    "e_event_off": ("E", False, CANDIDATE + "_E_EVENT_OFF"),
    "se_event_on": ("SE", True, CANDIDATE),
    "se_event_off": ("SE", False, CANDIDATE + "_SE_EVENT_OFF"),
}
FIELDS = ("schema", "status", "profile_identity", "artifact_sha256", "baseline_identity",
          "baseline_artifact_sha256", "fixture_id", "fixture_sha256", "sample_rate", "frames",
          "partitions", "tap_stage", "tap_channels")
COLUMNS = ("file", "sha256", "bytes", "candidate", "mode", "events_audible", "rms", "peak",
           "raw_arrivals", "impulse_frames", "pending_frames")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _integer(value, name, minimum=0):
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise ValueError(name + ": invalid integer")
    result = int(value)
    if result < minimum:
        raise ValueError(name + ": out of range")
    return result


def _number(value, name):
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(name + ": invalid nonnegative finite number")
    return result


def _file(root, name):
    path = root / name
    # Names are fixed by this module, never arbitrary manifest paths. Refuse symlinks
    # so a local export cannot accidentally pull in a different/private payload.
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing or non-regular export file: " + name)
    return path.read_bytes()


def measure(samples):
    """Promote Float32 before squaring; reject overflow instead of reporting Infinity."""
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError("empty or nonfinite mono samples")
    with np.errstate(over="ignore", invalid="ignore"):
        energy = float(np.sum(x * x))
    if not math.isfinite(energy):
        raise ValueError("nonfinite sample energy")
    return {"sample_count": int(x.size), "finite": True, "energy_finite": True,
            "rms": math.sqrt(energy / x.size), "peak": float(np.max(np.abs(x)))}


def _baseline_identity(data):
    """Validate C63HybridProfile.fromBytes' frozen wire constraints, without generation."""
    if len(data) != 311432 or data[:8] != b"C63HY1V1" or struct.unpack_from("<2i", data, 8) != (2048, 12288):
        raise ValueError("baseline artifact format")
    scalars = struct.unpack_from("<8d", data, 16)
    scale, event_scale, fraction, event_fraction, *weights = scalars
    if (not all(math.isfinite(v) for v in scalars) or not 0 < scale <= 1000
            or not 0 < event_scale <= 1000 or not 0 <= fraction <= .25
            or not 0 <= event_fraction <= .5 or min(weights) < 0
            or abs(sum(v*v for v in weights) - 1) >= 1e-8
            or 0 in struct.unpack_from("<3q", data, 80)):
        raise ValueError("baseline artifact scalars")
    values = np.frombuffer(data, dtype="<f8", offset=136)
    kernels = [values[:2048], *np.split(values[2048:], 3)]
    for x in kernels:
        if (not np.isfinite(x).all() or abs(float(x.sum())) >= 1e-8
                or abs(float(x @ x) - 1) >= 1e-6 or x[-1] != 0):
            raise ValueError("baseline artifact kernel")
    for i, x in enumerate(kernels[1:]):
        for y in kernels[i + 2:]:
            if abs(float(x @ y)) >= 1e-6:
                raise ValueError("baseline artifact event orthogonality")
    return sha(data)


def _trajectory(data, fixture_id, expected_frames):
    """Validate the existing JVM trajectory wire record, including unused state fields."""
    offset = 0
    def read(fmt):
        nonlocal offset
        size = struct.calcsize(fmt)
        if offset + size > len(data):
            raise ValueError("truncated trajectory")
        result = struct.unpack_from(fmt, data, offset)
        offset += size
        return result
    def utf():
        nonlocal offset
        size, = read(">H")
        if offset + size > len(data):
            raise ValueError("truncated trajectory string")
        # Both JVM strings here are contractually ASCII, a subset of modified UTF.
        value = data[offset:offset + size].decode("ascii")
        offset += size
        return value
    def boolean():
        value, = read(">B")
        if value not in (0, 1):
            raise ValueError("invalid trajectory boolean")
        return bool(value)
    if utf() != "c63.n2.trajectory.v1" or utf() != fixture_id:
        raise ValueError("trajectory identity")
    count, = read(">i")
    if not 1 <= count <= len(data) // 80:
        raise ValueError("trajectory segment count")
    total = 0
    lengths = []
    for _ in range(count):
        frames, = read(">i")
        boolean()
        state = read(">8d")
        if (frames <= 0 or not all(math.isfinite(v) for v in state)
                or not 0 <= state[1] <= 7200 or not 0 <= state[5] <= 1 or not 0 <= state[6] <= 1):
            raise ValueError("trajectory state")
        harmonics, = read(">i")
        if not 0 <= harmonics <= (len(data) - offset) // 4:
            raise ValueError("trajectory harmonics")
        if not all(math.isfinite(v) for v in read(">" + str(harmonics) + "f")):
            raise ValueError("trajectory nonfinite harmonics")
        boolean(); boolean(); read(">i"); boolean(); boolean()
        total += frames
        lengths.append(frames)
    if offset != len(data) or total != expected_frames:
        raise ValueError("trajectory length/frame count")
    return tuple(lengths)


@dataclass(frozen=True)
class RenderExport:
    metadata: dict
    manifest_sha256: str
    payload_sha256: dict
    branches: dict
    segment_frames: tuple

    @property
    def trajectory_segments(self):
        return len(self.segment_frames)


def read_export(directory):
    """Load a complete six-branch export and recompute identities and measurements."""
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("export must be a regular directory")
    manifest = _file(root, "manifest.tsv")
    lines = manifest.decode("utf-8").splitlines()
    if len(lines) != len(FIELDS) + 1 + 12:
        raise ValueError("incomplete or extra manifest entries")
    metadata = {}
    for expected, line in zip(FIELDS, lines[:len(FIELDS)]):
        cells = line.split("\t")
        if len(cells) != 2 or cells[0] != expected:
            raise ValueError("missing/duplicate/reordered manifest metadata")
        metadata[expected] = cells[1]
    if lines[len(FIELDS)].split("\t") != list(COLUMNS):
        raise ValueError("manifest columns")
    if (metadata["schema"] != "c63.n2.render_receipt.v1"
            or metadata["status"] != "RENDERED_ONLY_NOT_ACOUSTIC_QUALIFICATION"
            or metadata["sample_rate"] != "48000"
            or metadata["tap_stage"] != "source_before_delay_idle_shift_output_headroom"
            or metadata["tap_channels"] != ",".join(CHANNELS)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", metadata["fixture_id"])):
        raise ValueError("render contract metadata")
    frames = _integer(metadata["frames"], "frames", 1)
    partitions = tuple(_integer(v, "partition", 1) for v in metadata["partitions"].split(","))
    if any(v > 4800 for v in partitions):
        raise ValueError("partition exceeds renderer bound")
    hashes = {}
    blobs = {}
    for name, key in (("profile.bin", "artifact_sha256"), ("baseline.bin", "baseline_artifact_sha256"),
                      ("trajectory.bin", "fixture_sha256")):
        blobs[name] = _file(root, name)
        hashes[name] = sha(blobs[name])
        if hashes[name] != metadata[key]:
            raise ValueError(name + ": identity mismatch")
    if _binary_identity(blobs["profile.bin"]) != metadata["profile_identity"]:
        raise ValueError("profile identity mismatch")
    if _baseline_identity(blobs["baseline.bin"]) != metadata["baseline_identity"]:
        raise ValueError("baseline identity mismatch")
    segments = _trajectory(blobs["trajectory.bin"], metadata["fixture_id"], frames)
    rows = {}
    expected_files = {stem + suffix for stem in BRANCHES for suffix in (".pcm.f32le", ".taps.f64le")}
    for line in lines[len(FIELDS) + 1:]:
        values = line.split("\t")
        if len(values) != len(COLUMNS):
            raise ValueError("manifest file row shape")
        row = dict(zip(COLUMNS, values))
        name = row["file"]
        if name not in expected_files or name in rows:
            raise ValueError("unknown or duplicate payload")
        stem = name.split(".")[0]
        mode, audible, candidate = BRANCHES[stem]
        if (row["candidate"], row["mode"], row["events_audible"]) != (candidate, mode, str(audible).lower()):
            raise ValueError("branch identity mismatch")
        size = _integer(row["bytes"], "bytes", 1)
        expected_size = frames * (4 if name.endswith("f32le") else 72)
        if size != expected_size or (root / name).stat().st_size != size:
            raise ValueError("payload byte size mismatch: " + name)
        payload = _file(root, name)
        hashes[name] = sha(payload)
        if len(payload) != size or hashes[name] != row["sha256"]:
            raise ValueError("payload hash/size mismatch: " + name)
        x = np.frombuffer(payload, dtype="<f4" if name.endswith("f32le") else "<f8")
        if not np.isfinite(x).all():
            raise ValueError("nonfinite payload: " + name)
        row["samples"] = x if name.endswith("f32le") else x.reshape(frames, 9)
        for key in ("rms", "peak"):
            row[key] = _number(row[key], key)
        for key in ("raw_arrivals", "impulse_frames", "pending_frames"):
            row[key] = _integer(row[key], key)
        if row["raw_arrivals"] < row["impulse_frames"] or row["impulse_frames"] > frames:
            raise ValueError("invalid event counts")
        if row["pending_frames"] > 12288:
            raise ValueError("invalid pending frames")
        rows[name] = row
    branches = {}
    for stem in BRANCHES:
        pcm, taps = (rows[stem + suffix] for suffix in (".pcm.f32le", ".taps.f64le"))
        for key in COLUMNS[3:]:
            if pcm[key] != taps[key]:
                raise ValueError("PCM/tap metadata mismatch: " + stem)
        measured = measure(pcm["samples"])
        for key in ("rms", "peak"):
            # JVM sums sequentially; NumPy may use pairwise reduction. This only
            # tolerates reduction roundoff, never changed PCM or measurements.
            if not math.isclose(measured[key], pcm[key], rel_tol=1e-11, abs_tol=0):
                raise ValueError("reported " + key + " mismatch: " + stem)
        impulse_count = int(np.count_nonzero(taps["samples"][:, 8]))
        if impulse_count != pcm["impulse_frames"]:
            raise ValueError("event impulse frame count mismatch: " + stem)
        branches[stem] = {"pcm": pcm["samples"], "taps": taps["samples"], "measurement": measured,
                          "stem_measurements": {name: measure(taps["samples"][:, i]) for i, name in enumerate(CHANNELS)},
                          "raw_arrivals_reported": pcm["raw_arrivals"], "impulse_frames": impulse_count,
                          "pending_frames_reported": pcm["pending_frames"]}
    return RenderExport(metadata, sha(manifest), hashes, branches, segments)


def compare_partitions(first, second):
    """An observed mismatch is a failure, and identical schedules prove no partition test."""
    if {k: v for k, v in first.metadata.items() if k != "partitions"} != {
            k: v for k, v in second.metadata.items() if k != "partitions"}:
        raise ValueError("partition comparison input identity mismatch")
    def realized_blocks(export):
        partitions = tuple(int(v) for v in export.metadata["partitions"].split(","))
        index = 0
        for frames in export.segment_frames:
            while frames:
                count = min(partitions[index], frames)
                yield count
                frames -= count
                index = (index + 1) % len(partitions)
    if all(a == b for a, b in zip_longest(realized_blocks(first), realized_blocks(second))):
        raise ValueError("partition comparison requires different realized block schedules")
    if first.payload_sha256 != second.payload_sha256:
        raise ValueError("partition payload mismatch")
    for name in BRANCHES:
        for key in ("raw_arrivals_reported", "impulse_frames", "pending_frames_reported"):
            if first.branches[name][key] != second.branches[name][key]:
                raise ValueError("partition event observation mismatch")
    return True
