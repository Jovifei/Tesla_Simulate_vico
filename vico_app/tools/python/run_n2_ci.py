#!/usr/bin/env python3
"""Reference-free N2 CI checks, with explicit scope and no silently skipped tests.

Linux exercises actual Kotlin exports and numeric diagnostics; Windows exercises
stdlib gate/CLI/process-lock tests. Neither scope is Android or acoustic approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest
from urllib.parse import urlparse
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OPT_IN_JVM_TESTS = {
    "exportSixControlledBranchesForLocalReferenceComputation(com.vico.simulator.sound.n2.N2PcmFixtureTest)",
    "measureInitialUnitSourceBeforeObjectiveEvaluation(com.vico.simulator.sound.n2.N2UnitCalibrationTest)",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_jvm_log(text):
    skips = [line.removeprefix("ASSUMPTION_SKIPPED ") for line in text.splitlines()
             if line.startswith("ASSUMPTION_SKIPPED ")]
    summary = json.loads(text.splitlines()[-1])
    if (set(skips) != OPT_IN_JVM_TESTS or len(skips) != len(OPT_IN_JVM_TESTS)
            or summary["assumption_skipped"] != len(skips) or summary["ignored"] != 0
            or summary["failed"] != 0 or summary["passed"] <= 0
            or summary["run"] != summary["passed"] + len(skips)):
        raise ValueError("Unexpected JVM failure, skip, ignore or empty suite")
    return dict(summary, opt_in_not_run=sorted(skips))


def validate_python_result(result):
    if (not result.wasSuccessful() or result.testsRun == 0 or result.skipped
            or result.expectedFailures or result.unexpectedSuccesses):
        raise ValueError("Python suite must pass with no skips, expected failures or empty selection")
    return {"run": result.testsRun, "passed": result.testsRun, "skipped": 0, "failed": 0}


def download_dependencies(directory):
    """Explicit CI bootstrap; only the existing official Maven manifest is used."""
    directory.mkdir(parents=True, exist_ok=False)
    dependencies = json.loads((REPO / "vico_app/tools/jvm/dependencies.json").read_text())
    for dep in dependencies:
        url = urlparse(dep["url"])
        if (url.scheme != "https" or url.netloc != "repo.maven.apache.org"
                or not url.path.startswith("/maven2/") or Path(dep["file"]).name != dep["file"]):
            raise ValueError("Dependency must be a plain filename from official Maven Central")
        with urlopen(dep["url"], timeout=60) as response:
            if response.url != dep["url"]:
                raise ValueError("Unexpected Maven dependency redirect")
            data = response.read()
        if hashlib.sha256(data).hexdigest() != dep["sha256"]:
            raise ValueError("Maven dependency SHA-256 mismatch: " + dep["file"])
        with (directory / dep["file"]).open("xb") as output:
            output.write(data)
        print("verified_dependency=" + dep["file"] + " sha256=" + dep["sha256"], flush=True)


def run_python_tests(scope):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    patterns = (["test_n2_*.py", "test_build_c63_hybrid_targets.py"] if scope == "linux"
                else ["test_n2_artifact_gate.py", "test_n2_process_lock.py", "test_n2_ci.py"])
    for pattern in patterns:
        suite.addTests(loader.discover(str(HERE), pattern=pattern))
    return validate_python_result(unittest.TextTestRunner(verbosity=2).run(suite))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True, help="new output directory")
    deps = parser.add_mutually_exclusive_group()
    deps.add_argument("--deps", type=Path, help="existing SHA-pinned Maven jars (Linux)")
    deps.add_argument("--download-deps", action="store_true", help="explicitly obtain official pinned Maven jars (Linux)")
    args = parser.parse_args(argv)
    expected_platform = {"linux": "linux", "windows": "win32"}[args.platform]
    if sys.platform != expected_platform:
        parser.error(f"Expected actual {expected_platform}; running {sys.platform}")
    if args.platform == "linux" and not (args.deps or args.download_deps):
        parser.error("Linux synthetic-render checks require --deps or --download-deps")
    if args.platform == "windows" and (args.deps or args.download_deps):
        parser.error("Windows gate/locking scope does not use Kotlin dependencies")
    os.chdir(REPO)
    # Direct invocation and package CLI tests both get the same repository import root.
    sys.path.insert(0, str(REPO))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if os.environ.get("EXPECTED_HEAD", head) != head:
        raise ValueError("Checkout does not match the triggering exact commit")
    print("checked_out_head=" + head, flush=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"scope": "SYNTHETIC_SOFTWARE_CHECKS_NOT_ACOUSTIC_QUALIFICATION",
               "head": head, "platform": sys.platform, "python": platform.python_version(),
               "lock_backend": "msvcrt" if sys.platform == "win32" else "fcntl",
               "java": subprocess.run(["java", "-version"], check=True, text=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip()}
    if args.platform == "linux":
        jars = args.deps.resolve() if args.deps else output / "deps"
        if args.download_deps:
            download_dependencies(jars)
        build, export = output / "jvm", output / "export"
        subprocess.run([sys.executable, str(HERE / "run_n2_jvm_tests.py"), "--deps", str(jars),
                        "--build-dir", str(build), "--synthetic-export", str(export)], check=True)
        receipt["jvm"] = validate_jvm_log((build / "junit.log").read_text())
        execution = json.loads((export / "execution-receipt.json").read_text())
        if execution["source_receipt_sha256"] != sha256(build / "source-sha256.json"):
            raise ValueError("Compiled-source receipt hash mismatch")
        for name, digest in execution["manifests"].items():
            if digest != sha256(export / name / "manifest.tsv"):
                raise ValueError("Actual export manifest hash mismatch")
        receipt["synthetic_export"] = execution
        os.environ["VICO_N2_RENDER_EXPORT"] = str(export)
    receipt["python_tests"] = run_python_tests(args.platform)
    if args.platform == "linux":
        metrics = output / "render-metrics.json"
        subprocess.run([sys.executable, "-m", "vico_app.tools.python.n2_reference_driver",
                        "--export", str(export / "block960"), "--compare-export", str(export / "split333_297"),
                        "--out", str(metrics)], check=True)
        receipt["render_metrics_sha256"] = sha256(metrics)
        # Full diagnostic content and exact hashes remain inspectable in the job log.
        print(metrics.read_text(), flush=True)
    receipt["not_run"] = ["all-c63 legacy external-fixture suite", "full Android/Gradle build",
                          "private references", "full qualification matrix", "device", "human acceptance"]
    content = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    (output / "ci-receipt.json").write_text(content, encoding="utf-8")
    print(content, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## N2 " + args.platform + " software checks\n\n```json\n" + content + "```\n")


if __name__ == "__main__":
    main()
