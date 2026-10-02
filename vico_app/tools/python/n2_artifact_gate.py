"""N2 receipt gate v3.

Pre-objective only: validates provenance, reservation receipts and hard feasibility.
It does not run objective scoring or held-out evaluation.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

CANDIDATE = "C63_N2_CONTINUOUS_V1"
LIMITS = {"continuous": 48, "event": 24}
LOW_DB = 1.0
MID_DB = 1.0
SOURCE_DB = 1.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(str(path) + ".lock", "a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def write_json(path: Path, value: dict):
    with NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")
        temp = f.name
    os.replace(temp, path)


def reserve(ledger: Path, trial: dict):
    with locked(ledger):
        state = json.loads(ledger.read_text()) if ledger.exists() else {
            "schema": "c63.n2.receipt.v3", "candidate": CANDIDATE, "trials": []
        }
        if state["candidate"] != CANDIDATE:
            raise ValueError("candidate mismatch")
        if any(x["trial_id"] == trial["trial_id"] for x in state["trials"]):
            raise ValueError("duplicate trial")
        count = sum(x["kind"] == trial["kind"] for x in state["trials"])
        if count >= LIMITS[trial["kind"]]:
            raise RuntimeError("budget exhausted")
        state["trials"].append(trial)
        write_json(ledger, state)
        return trial


def verify(receipt: Path, ledger: Path, artifact: Path, result: Path):
    r = json.loads(result.read_text())
    l = json.loads(ledger.read_text())
    trial = next((x for x in l["trials"] if x["trial_id"] == r["trial_id"]), None)
    reasons = []
    if trial is None:
        reasons.append("missing_receipt")
    if trial and r["profile_hash"] != trial["profile_hash"]:
        reasons.append("profile_hash")
    if sha(artifact) != r["artifact_hash"]:
        reasons.append("artifact_hash")
    metrics = r.get("hard", {})
    if abs(metrics.get("low_max_db", 999)) > LOW_DB:
        reasons.append("low")
    if abs(metrics.get("mid_max_db", 999)) > MID_DB:
        reasons.append("mid")
    if abs(metrics.get("source_rms_db", 999)) > SOURCE_DB:
        reasons.append("source")
    return {"status": "FEASIBLE" if not reasons else "REJECTED_BEFORE_SCORE", "reasons": reasons}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(json.loads(Path(args.verify).read_text())))
