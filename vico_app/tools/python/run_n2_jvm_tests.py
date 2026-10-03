#!/usr/bin/env python3
"""Compile real N2/frozen C63 Kotlin and execute JUnit on a JDK, without Android stubs.

Dependencies are preinstalled explicitly from the pinned official Maven URLs in
../jvm/dependencies.json. This runner does not download, install, or enable N2.
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
    parser.add_argument("--suite", choices=("n2", "all-c63"), default="n2",
                        help="all-c63 also executes historical tests requiring local phone/reference files")
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True, help="new directory for compiled code/receipts")
    parser.add_argument("--synthetic-export", type=Path, help="new directory for test-only inputs and two real renders")
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
    main_root = src / "main/java/com/vico/simulator/sound"
    test_root = src / "test/java/com/vico/simulator/sound"
    sources = [main_root / name for name in ("SoundModel.kt", "SoundProfile.kt", "C63FeedbackInput.kt", "C63QualificationPcmProvider.kt")]
    for name in ("n2", "s15", "s16", "s17", "s18"):
        sources += sorted((main_root / name).rglob("*.kt"))
    tests = sorted(test_root.glob("C63*Test.kt")) + sorted((test_root / "n2").rglob("*.kt"))
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
        if args.suite == "n2" and path.parent == test_root:
            continue
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
    if args.synthetic_export:
        output = args.synthetic_export.resolve()
        output.mkdir(parents=True, exist_ok=False)
        subprocess.run(["java", "-cp", runtime, "com.vico.simulator.sound.n2.diagnostic.N2SyntheticArtifactFixture", str(output / "inputs")], check=True)
        manifests = {}
        for name, partitions in (("block960", "960"), ("split333_297", "333,297")):
            subprocess.run(["java", "-Xmx2g", "-cp", runtime, "com.vico.simulator.sound.n2.diagnostic.N2SyntheticReferenceExporter",
                            str(output / "inputs/baseline.bin"), str(output / "inputs/profile.bin"), str(output / name), partitions], check=True)
            manifests[name] = hashlib.sha256((output / name / "manifest.tsv").read_bytes()).hexdigest()
        receipt = {"status": "SYNTHETIC_RENDER_ONLY_NOT_ACOUSTIC_QUALIFICATION", "manifests": manifests,
                   "source_receipt_sha256": hashlib.sha256((build / "source-sha256.json").read_bytes()).hexdigest()}
        (output / "execution-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
