#!/usr/bin/env python3
"""Run real platform-independent sensor input tests with SHA-pinned JVM dependencies.

This does not compile Android adapters or validate real device/road measurements.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True, help="new directory for compiled code/receipts")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    jvm = repo / "vico_app/tools/jvm"
    dependencies = json.loads((jvm / "dependencies.json").read_text())
    jars = []
    for dep in dependencies:
        jar = args.deps.resolve() / dep["file"]
        if not jar.is_file() or hashlib.sha256(jar.read_bytes()).hexdigest() != dep["sha256"]:
            parser.error(f"Missing or mismatched {jar}; install exact bytes from {dep['url']}")
        jars.append(str(jar))
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=False)
    src = repo / "vico_app/Project/android/app/src"
    main_root = src / "main/java/com/vico/simulator/sensor"
    test_root = src / "test/java/com/vico/simulator/sensor"
    sources = [p for p in sorted(main_root.glob("*.kt")) if p.name != "SensorProvider.kt"]
    tests = sorted(test_root.glob("*Test.kt"))
    sources += tests
    # The source receipt binds the exact code compiled, not just the checkout's nominal HEAD.
    hashes = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources + [jvm / "QualificationTestRunner.java"]}
    (build / "source-sha256.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    (build / "runtime.txt").write_text(subprocess.run(["java", "-version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True).stdout)
    (build / "dependencies.json").write_text(json.dumps(dependencies, indent=2) + "\n")
    cp = os.pathsep.join(jars)
    compiled = build / "tests.jar"
    subprocess.run(["java", "-cp", cp, "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect",
                    "-jvm-target", "1.8", "-classpath", cp, "-d", str(compiled), *map(str, sources)], check=True)
    subprocess.run(["java", "com.sun.tools.javac.Main", "-proc:none", "-cp", cp, "-d", str(build), str(jvm / "QualificationTestRunner.java")], check=True)
    classes = []
    for path in tests:
        text = path.read_text()
        package = re.search(r"^package ([\w.]+)", text, re.MULTILINE).group(1)
        classes += [package + "." + name for name in re.findall(r"^class (\w+Test)\b", text, re.MULTILINE)]
    runtime = os.pathsep.join([str(compiled), str(build), cp])
    # Run from the Android project, matching the test fixtures' relative-path contracts.
    result = subprocess.run(["java", "-Xmx2g", "-cp", runtime, "QualificationTestRunner", *classes],
                            cwd=repo / "vico_app/Project/android", text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="")
    (build / "junit.log").write_text(result.stdout)
    result.check_returncode()
    summary = json.loads(result.stdout.splitlines()[-1])
    if (summary["run"] == 0 or summary["failed"] != 0 or summary["assumption_skipped"] != 0 or
            summary["ignored"] != 0 or summary["passed"] != summary["run"]):
        raise ValueError("Sensor suite must pass with no skipped, ignored, or empty tests")


if __name__ == "__main__":
    main()
