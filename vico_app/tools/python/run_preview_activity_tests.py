#!/usr/bin/env python3
"""Compile exact MainActivity method bodies and execute controlled JVM regressions.

Android Activity construction, Handler, AudioTrack and UI require Android runtime.
This harness substitutes only their collaborators, never rewrites method bodies or
branches, and is neither Android/device execution nor DSP/acoustic qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def block(source, marker):
    """Extract one brace-balanced Kotlin block while ignoring comments and literals."""
    if source.count(marker) != 1:
        raise ValueError(f"Expected exactly one production block: {marker}")
    start = source.index(marker)
    opening = source.index("{", start)
    depth, i, state = 0, opening, "code"
    while i < len(source):
        c, pair = source[i], source[i:i + 2]
        if state == "line":
            if c == "\n":
                state = "code"
        elif state == "comment":
            if pair == "*/":
                state = "code"
                i += 1
        elif state in ("string", "char"):
            if c == "\\":
                i += 1
            elif c == ('"' if state == "string" else "'"):
                state = "code"
        elif state == "triple":
            if source[i:i + 3] == '"""':
                state = "code"
                i += 2
        elif pair == "//":
            state = "line"
            i += 1
        elif pair == "/*":
            state = "comment"
            i += 1
        elif source[i:i + 3] == '"""':
            state = "triple"
            i += 2
        elif c in ('"', "'"):
            state = "string" if c == '"' else "char"
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    raise ValueError(f"Unterminated production block: {marker}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps", type=Path, required=True, help="local SHA-pinned dependency directory or cache")
    parser.add_argument("--build-dir", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    jvm = repo / "vico_app/tools/jvm"
    src = repo / "vico_app/Project/android/app/src"
    main_root = src / "main/java/com/vico/simulator"
    activity = main_root / "MainActivity.kt"
    text = activity.read_text(encoding="utf-8")
    methods = [block(text, marker) for marker in (
        "private fun startS13Review(key: String)",
        "fun previewVehicle(key: String)",
        "private fun cancelPreviewCallbacks()",
    )]
    callback = block(text, "engine.onAudioFailure =")
    epoch_source = main_root / "sound/S14TrialCoordinator.kt"
    epoch = block(epoch_source.read_text(encoding="utf-8"), "class S14CallbackEpoch")
    template = jvm / "PreviewActivityHarness.kt.in"
    generated = template.read_text(encoding="utf-8").replace("// PRODUCTION_METHODS", "\n\n".join(methods))
    generated = generated.replace("// PRODUCTION_AUDIO_FAILURE", callback) + "\n\n" + epoch + "\n"
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=False)
    harness = build / "HeadlessMainActivity.kt"
    harness.write_text(generated, encoding="utf-8")
    clock = build / "SystemClock.kt"
    clock.write_text("package android.os\nobject SystemClock {\n"
                     " fun elapsedRealtime() = 0L\n fun elapsedRealtimeNanos() = 0L\n}\n", encoding="utf-8")
    sources = [harness, clock, main_root / "sound/PreviewPlayback.kt",
               main_root / "sound/SoundProfile.kt", main_root / "vehicle/CurrentVehicleCatalog.kt",
               main_root / "state/VehicleSelectionState.kt", jvm / "PreviewActivityTest.kt",
               src / "test/java/com/vico/simulator/sound/PreviewPlaybackTest.kt"]
    dependency_manifest = jvm / "dependencies.json"
    dependencies = json.loads(dependency_manifest.read_text(encoding="utf-8"))
    jars = []
    for dep in dependencies:
        found = list(args.deps.rglob(dep["file"]))
        valid = [p.resolve() for p in found if digest(p.read_bytes()) == dep["sha256"]]
        if not valid:
            parser.error(f"Missing locally cached SHA-pinned dependency: {dep['file']}")
        jars.append(str(valid[0]))
    receipt_paths = [activity, epoch_source, template, dependency_manifest, Path(__file__).resolve(), *sources]
    receipt = {
        "scope": "Exact source-extracted Activity methods; controlled collaborators; JVM only",
        "production_blocks": {body.splitlines()[0]: digest(body.encode()) for body in [*methods, callback, epoch]},
        "files": {str(p.resolve()): digest(p.read_bytes()) for p in receipt_paths},
        "dependencies": dependencies,
    }
    (build / "source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    cp = os.pathsep.join(jars)
    compiled = build / "classes"
    commands = []

    def run(stage, argv):
        commands.append({"stage": stage, "argv": argv})
        (build / "commands.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run(argv, text=True, encoding="utf-8", errors="replace",
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (build / f"{stage}.log").write_text(result.stdout, encoding="utf-8")
        print(f"{stage}: exit={result.returncode}")
        print(result.stdout, end="")
        return result.returncode

    if run("compile", ["java", "-cp", cp, "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
                       "-no-stdlib", "-no-reflect", "-jvm-target", "17", "-classpath", cp,
                       "-d", str(compiled), *map(str, sources)]):
        return 2
    return run("junit", ["java", "-cp", os.pathsep.join([str(compiled), cp]),
                         "org.junit.runner.JUnitCore", "com.vico.simulator.sound.PreviewActivityTest",
                         "com.vico.simulator.sound.PreviewPlaybackTest"])


if __name__ == "__main__":
    sys.exit(main())
