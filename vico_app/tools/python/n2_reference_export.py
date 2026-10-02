"""N2 reference export runner.

Offline only. Produces deterministic branch manifests and fixture hashes.
"""
from hashlib import sha256
import json

MODES = ("T", "S", "E_ON", "E_OFF", "SE_ON", "SE_OFF")
PARTITIONS = (333, 297, 960)


def export_manifest(fixtures, artifact, profile, calibration):
    return {
        "fixtures": [sha256(x).hexdigest() for x in fixtures],
        "artifact": sha256(artifact).hexdigest(),
        "profile": profile,
        "calibration": calibration,
        "modes": MODES,
        "partitions": PARTITIONS,
        "objective": False,
        "held_out": False,
    }


def calibrated_source_scale(unit_rms, target_rms):
    if unit_rms <= 0:
        raise ValueError("unit response")
    return target_rms / unit_rms
