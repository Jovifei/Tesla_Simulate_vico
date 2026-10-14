#!/usr/bin/env python3
"""Execute exact Activity display-unit methods with controlled preferences on cached JVM dependencies.

This is source-extracted Kotlin execution, not Android/WebView or on-device persistence evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from run_preview_activity_tests import block, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    jvm = repo / "vico_app/tools/jvm"
    main_root = repo / "vico_app/Project/android/app/src/main/java/com/vico/simulator"
    activity_path = main_root / "MainActivity.kt"
    activity = activity_path.read_text(encoding="utf-8")
    bridge_path = main_root / "web/VicoBridge.kt"
    bridge = bridge_path.read_text(encoding="utf-8")
    # Assert API availability before extraction: a baseline failure is the missing migration policy.
    for signature in ("fun getDisplayUnit(): String", "fun setDisplayUnit(unit: String)"):
        assert signature in activity, f"Missing production display-unit policy: {signature}"
    methods = [block(activity, marker) for marker in ("fun getDisplayUnit(): String", "fun setDisplayUnit(unit: String)")]
    assert "@JavascriptInterface\n    fun getDisplayUnit(): String = activity.getDisplayUnit()" in bridge
    assert "@JavascriptInterface\n    fun setDisplayUnit(unit: String) = activity.setDisplayUnit(unit)" in bridge
    template = jvm / "DisplayUnitActivityHarness.kt.in"
    generated = template.read_text(encoding="utf-8").replace("// PRODUCTION_METHODS", "\n\n".join(methods))
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=False)
    harness = build / "DisplayUnitActivityHarness.kt"
    harness.write_text(generated, encoding="utf-8")
    dependency_manifest = jvm / "dependencies.json"
    dependencies = json.loads(dependency_manifest.read_text(encoding="utf-8"))
    jars = []
    for dep in dependencies:
        valid = [p.resolve() for p in args.deps.rglob(dep["file"]) if digest(p.read_bytes()) == dep["sha256"]]
        if not valid:
            parser.error(f"Missing cached SHA-pinned dependency: {dep['file']}")
        jars.append(str(valid[0]))
    receipt_paths = [activity_path, bridge_path, template, dependency_manifest, Path(__file__).resolve(), harness]
    receipt = {
        "scope": "Exact source-extracted Activity unit methods; controlled preferences; JVM only",
        "production_blocks": {body.splitlines()[0]: digest(body.encode()) for body in methods},
        "files": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in receipt_paths},
        "dependencies": dependencies,
    }
    (build / "source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    cp = os.pathsep.join(jars)
    compiled = build / "classes"
    for stage, argv in (
        ("compile", ["java", "-cp", cp, "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect", "-jvm-target", "1.8", "-classpath", cp, "-d", str(compiled), str(harness)]),
        ("junit", ["java", "-cp", os.pathsep.join([str(compiled), cp]), "org.junit.runner.JUnitCore", "com.vico.simulator.DisplayUnitActivityTest"]),
    ):
        result = subprocess.run(argv, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (build / f"{stage}.log").write_text(result.stdout, encoding="utf-8")
        print(f"{stage}: exit={result.returncode}")
        print(result.stdout, end="")
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
