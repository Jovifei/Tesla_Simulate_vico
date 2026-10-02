"""Offline N2 reference driver.
No objective, held-out scoring or install path.
"""
from pathlib import Path
import hashlib,json

MODES=("T","S","E_ON","E_OFF","SE_ON","SE_OFF")


def export_fixture(out: Path, fixture: bytes, artifact: bytes, states):
    manifest={
      "fixture_sha256":hashlib.sha256(fixture).hexdigest(),
      "artifact_sha256":hashlib.sha256(artifact).hexdigest(),
      "modes":MODES,
      "states":len(states),
      "partitions":[333,297,960]
    }
    out.mkdir(parents=True,exist_ok=True)
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest


def calibrate(unit_rms, target_rms):
    if not unit_rms or unit_rms<=0: raise ValueError("unit rms")
    return target_rms/unit_rms
