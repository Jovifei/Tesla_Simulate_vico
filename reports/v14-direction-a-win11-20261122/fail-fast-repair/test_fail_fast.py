"""Compare the historical wrapper and its four-guard repair using mock stages."""

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid


LAB = Path(__file__).absolute().parent
ROOT = LAB.parents[2]
HISTORICAL = LAB / "historical-step1-runbook.fixture.txt"
EXPECTED = "da5c40a2e3619955bf3cc8c886ccb07eb9060f54666e82a6c3693347752c1459"
RUNBOOK = ROOT / "direction-a-step1-20261112" / "HOST-RUNBOOK.md"
HOST_RECEIPT = LAB.parent / "host-receipt.json"
GUARDED = LAB / "step1-runbook-guarded.ps1"
STAGES = ("configure", "build", "smoke", "verify")
MESSAGES = {
    "configure": "CMake configure failed; not a build pass",
    "build": "MSVC build failed; no smoke pass",
    "smoke": "C++ smoke failed; preserve all partial output",
    "verify": "Capture data verification failed",
}
EXIT_CODES = {"configure": 31, "build": 32, "smoke": 33, "verify": 34}
ARTIFACTS = {
    "configure": ("build/CMakeCache.txt", "FAKE_STALE_CONFIGURE\n"),
    "build": ("build/Release/engine_offline.exe", "FAKE_STALE_BUILD\n"),
    "smoke": ("smoke-2s/capture.json", "FAKE_STALE_SMOKE\n"),
    "verify": ("host-evidence/verification.json", "FAKE_STALE_VERIFY_PASS\n"),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make_repair():
    original = HISTORICAL.read_bytes()
    receipt = json.loads(HOST_RECEIPT.read_text(encoding="utf-8"))
    assert sha(original) == EXPECTED == receipt["additional_local_logs"]["step1-runbook-executed.ps1"]["sha256"]
    runbook = RUNBOOK.read_text(encoding="utf-8")
    fixed = original
    for stage in STAGES:
        assignment = f"    $TaskStage.{stage} = $LASTEXITCODE".encode()
        original_guard = f"if ($LASTEXITCODE -ne 0) {{ throw '{MESSAGES[stage]}' }}"
        addition = f"    if ($TaskStage.{stage} -ne 0) {{ throw '{MESSAGES[stage]}' }}".encode()
        pattern = re.escape(assignment) + rb"(\r?\n)"
        assert len(re.findall(pattern, original)) == 1 and addition not in original
        assert runbook.count(original_guard) == 1
        fixed, count = re.subn(pattern, lambda match: match.group(0) + addition + match.group(1), fixed, count=1)
        assert count == 1
    if GUARDED.exists():
        assert GUARDED.read_bytes() == fixed
    else:
        with GUARDED.open("xb") as output:
            output.write(fixed)
    original_lines = original.decode("utf-8-sig").splitlines(keepends=True)
    fixed_lines = fixed.decode("utf-8-sig").splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(original_lines, fixed_lines, fromfile="historical/step1-runbook-executed.ps1", tofile="candidate/step1-runbook-guarded.ps1"))
    patch_file = LAB / "historical-to-candidate.diff"
    if patch_file.exists():
        assert patch_file.read_bytes() == diff.encode("utf-8")
    else:
        with patch_file.open("xb") as output:
            output.write(diff.encode("utf-8"))
    return sha(original), sha(fixed), sha(RUNBOOK.read_bytes())


def prepare_case(path):
    path.mkdir(parents=True, exist_ok=False)
    for relative, content in ARTIFACTS.values():
        target = path / "out" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")


def run_case(pwsh, root, failure, mode):
    case = root / failure / mode
    prepare_case(case)
    before = {name: sha((case / "out" / rel).read_bytes()) for name, (rel, _) in ARTIFACTS.items()}
    command = [pwsh, "-NoProfile", "-NonInteractive", "-File", str(LAB / "mock_driver.ps1"),
               "-Mode", mode, "-FailStage", failure, "-CaseRoot", str(case)]
    env = os.environ.copy()
    env.update({"TEMP": str(case), "TMP": str(case), "POWERSHELL_TELEMETRY_OPTOUT": "1", "POWERSHELL_UPDATECHECK": "Off"})
    run = subprocess.run(command, cwd=case, env=env, capture_output=True, timeout=45, check=False)
    (case / "stdout.log").write_bytes(run.stdout)
    (case / "stderr.log").write_bytes(run.stderr)
    if not (case / "wrapper-observation.json").is_file():
        raise RuntimeError(f"{failure}/{mode}: no observation; stderr={run.stderr.decode(errors='replace')[-1200:]}")
    observation = json.loads((case / "wrapper-observation.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (case / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    started = [e["stage"] for e in events if e["event"] == "stage_start"]
    native_exits = {e["stage"]: e["exit"] for e in events if e["event"] == "stage_exit"}
    stale = [e for e in events if e["event"] in {"artifact_read", "artifact_hash_read"} and e["stale"]]
    success_receipt = (case / "mock-success-receipt.json").exists()
    stale_verify = (case / "out" / ARTIFACTS["verify"][0]).read_text(encoding="utf-8").startswith("FAKE_STALE_")
    if failure == "none":
        assert run.returncode == 0 and started == list(STAGES) and success_receipt and not stale
        assert all(native_exits[s] == 0 for s in STAGES)
        later = []
    else:
        stop_index = STAGES.index(failure)
        expected_stages = list(STAGES) if mode == "old" else list(STAGES[: stop_index + 1])
        assert started == expected_stages and native_exits[failure] == EXIT_CODES[failure]
        assert observation["observed_native_exit_codes"][failure] == EXIT_CODES[failure]
        later = started[stop_index + 1:]
        if mode == "old":
            assert run.returncode == 0 and success_receipt
            if failure == "verify":
                assert stale_verify and not stale
            else:
                assert stale
        else:
            assert run.returncode == 1 and not success_receipt and not stale and not later
            assert observation["reason"] == MESSAGES[failure]
    return {
        "fixture": failure,
        "mode": mode,
        "command": command,
        "wrapper_process_exit": run.returncode,
        "native_exit_codes": native_exits,
        "steps_started": started,
        "steps_after_failure": later,
        "stale_artifact_reads": stale,
        "stale_pass_fixture_still_present": stale_verify,
        "mock_success_receipt_created": success_receipt,
        "success_claim_despite_failure": failure != "none" and success_receipt,
        "initial_fake_artifact_sha256": before,
        "stdout_sha256": sha(run.stdout),
        "stderr_sha256": sha(run.stderr),
        "events_sha256": sha((case / "events.jsonl").read_bytes()),
        "events": events,
        "wrapper_observation": observation,
        "stdout": run.stdout.decode("utf-8", errors="replace"),
        "stderr": run.stderr.decode("utf-8", errors="replace"),
    }


def check_junction_rejection(pwsh, root):
    if os.name != "nt":
        return {"status": "NOT_RUN_NON_WINDOWS"}
    target = root / "junction-test" / "target"
    (target / "case").mkdir(parents=True)
    junction = root / "junction-test" / "link"
    env = os.environ.copy()
    env.update({"MOCK_JUNCTION_PATH": str(junction), "MOCK_JUNCTION_TARGET": str(target),
                "TEMP": str(root), "TMP": str(root), "POWERSHELL_TELEMETRY_OPTOUT": "1"})
    create_command = [pwsh, "-NoProfile", "-NonInteractive", "-Command",
                      "New-Item -ItemType Junction -Path $env:MOCK_JUNCTION_PATH -Target $env:MOCK_JUNCTION_TARGET -ErrorAction Stop | Out-Null"]
    created = subprocess.run(create_command, cwd=root, env=env, capture_output=True, timeout=30, check=False)
    if created.returncode != 0:
        raise RuntimeError(f"junction fixture creation failed: {created.stderr.decode(errors='replace')[-800:]}")
    commands = {
        "driver": [pwsh, "-NoProfile", "-NonInteractive", "-File", str(LAB / "mock_driver.ps1"),
                   "-Mode", "old", "-FailStage", "none", "-CaseRoot", str(junction / "case")],
        "stage": [pwsh, "-NoProfile", "-NonInteractive", "-File", str(LAB / "mock_stage.ps1"),
                  "-Stage", "configure", "-FailStage", "none", "-CaseRoot", str(junction / "case")],
    }
    checks = {}
    for name, command in commands.items():
        run = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=30, check=False)
        assert run.returncode != 0 and b"reparse point" in run.stderr.lower()
        assert not list((target / "case").iterdir())
        checks[name] = {"command": command, "process_exit": run.returncode,
                        "stderr": run.stderr.decode("utf-8", errors="replace"),
                        "target_files_created": 0}
    return {"status": "PASS_REPARSE_REJECTED", "creation_command": create_command,
            "creation_exit": created.returncode, "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=f"fixture-{uuid.uuid4().hex[:12]}")
    run_id = parser.parse_args().run_id
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id):
        raise ValueError("run ID must contain only letters, digits, underscore or hyphen")
    if ROOT.resolve(strict=True) != ROOT.absolute() or LAB.resolve(strict=True) != LAB.absolute():
        raise ValueError("worktree and mock directory must not use a symlink or junction")
    runs = LAB / "mock-runs"
    if runs.exists() and runs.resolve(strict=True) != runs.absolute():
        raise ValueError("mock-runs must not be a symlink or junction")
    original_sha, fixed_sha, runbook_sha = make_repair()
    pwsh = shutil.which("pwsh")
    if not pwsh:
        raise RuntimeError("PowerShell is not available")
    root = runs / run_id
    root.mkdir(parents=True, exist_ok=False)
    cases = []
    for failure in (*STAGES, "none"):
        for mode in ("old", "fixed"):
            print(f"[mock {len(cases) + 1}/10] failure={failure} wrapper={mode}", flush=True)
            cases.append(run_case(pwsh, root, failure, mode))
    for i in range(0, len(cases), 2):
        assert cases[i]["initial_fake_artifact_sha256"] == cases[i + 1]["initial_fake_artifact_sha256"]
    print("[mock safety] verifying junction rejection", flush=True)
    junction_test = check_junction_rejection(pwsh, root)
    assert sha(HISTORICAL.read_bytes()) == original_sha
    source_names = ("test_fail_fast.py", "mock_driver.ps1", "mock_stage.ps1", "mock_paths.ps1",
                    "historical-step1-runbook.fixture.txt", "step1-runbook-guarded.ps1",
                    "historical-to-candidate.diff", ".gitattributes")
    result = {
        "status": "PASS_MOCK_FAILURE_GUARDS",
        "scope": "Historical four-stage block with native commands replaced by mock child processes",
        "historical_sha256": original_sha,
        "guarded_sha256": fixed_sha,
        "host_runbook_sha256": runbook_sha,
        "harness_source_sha256": {name: sha((LAB / name).read_bytes()) for name in source_names},
        "historical_line_numbers": {"configure": 52, "build": 55, "smoke": 59, "verify": 62},
        "success_receipt_semantics": "mock-only simulation of the historical outer runner's success decision",
        "cases": cases,
        "path_safety": junction_test,
        "not_run": ["engine-sim", "Windows native smoke", "audio analysis", "audio rendering", "audio playback"],
    }
    (root / "mock-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(cases)} mock cases; receipt: {root / 'mock-result.json'}")


if __name__ == "__main__":
    main()
