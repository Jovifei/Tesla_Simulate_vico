"""N2 artifact-bound pre-objective gate.

This is a pre-score evidence gate. It does not score objectives and does not consume held-out data.
A trial must carry a reservation receipt, immutable artifact hashes and calibration receipt before
any later acceptance metric can be evaluated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

CANDIDATE = "C63_N2_CONTINUOUS_V1"
LIMITS = {"continuous": 48, "event": 24}
LOW_BAND_DB_LIMIT = 1.0
MID_BAND_DB_LIMIT = 1.0
SOURCE_RMS_DB_LIMIT = 1.0
SOURCE_SCALE = 13.728409855272066
LEGACY_EVENT_UNIT_ENERGY = 331.3820481828321
LEGACY_EVENT_UNIT_L2 = 18.2039020043
UNIT_PROFILE_ID = "98dec5a954e836a0105241a04e920b8209f239441a51d039a46eb6b4f8e287c0"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp)
    tmp_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def reserve(ledger: Path, trial_id: str, kind: str, profile_hash: str, prereg_hash: str, reference_hash: str):
    if kind not in LIMITS:
        raise ValueError("kind")
    state = load(ledger) if ledger.exists() else {"schema":"c63.n2.receipt.v2","candidate":CANDIDATE,"trials":[]}
    if state["candidate"] != CANDIDATE:
        raise ValueError("candidate")
    if len([x for x in state["trials"] if x["kind"] == kind]) >= LIMITS[kind]:
        raise RuntimeError("budget exhausted")
    if any(x["trial_id"] == trial_id for x in state["trials"]):
        raise ValueError("duplicate trial")
    state["trials"].append({"trial_id":trial_id,"kind":kind,"profile_hash":profile_hash,"prereg_hash":prereg_hash,"reference_hash":reference_hash})
    atomic_json(ledger, state)
    return state["trials"][-1]


def verify(result: Path, ledger: Path, artifact: Path, trial_id: str):
    r = load(result)
    receipt = load(ledger)
    trial = next((x for x in receipt["trials"] if x["trial_id"] == trial_id), None)
    reasons = []
    if trial is None:
        reasons.append("missing_reservation")
    if trial and r.get("profile_hash") != trial["profile_hash"]:
        reasons.append("profile_trial_mismatch")
    if sha256_file(artifact) != r.get("artifact_hash"):
        reasons.append("artifact_hash")
    if r.get("calibration_profile_id") != UNIT_PROFILE_ID:
        reasons.append("calibration_identity")
    if r.get("source_scale") != SOURCE_SCALE:
        reasons.append("source_scale_changed")
    c = r.get("continuous", {})
    if abs(c.get("low_max_db", 999)) > LOW_BAND_DB_LIMIT:
        reasons.append("low_band")
    if abs(c.get("mid_max_db", 999)) > MID_BAND_DB_LIMIT:
        reasons.append("mid_band")
    if abs(c.get("source_rms_db", 999)) > SOURCE_RMS_DB_LIMIT:
        reasons.append("source_rms")
    return {"feasible": not reasons, "status":"FEASIBLE" if not reasons else "REJECTED_BEFORE_SCORE", "reasons":reasons}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", type=Path)
    args = p.parse_args()
    if args.verify:
        print(json.dumps(load(args.verify)))
