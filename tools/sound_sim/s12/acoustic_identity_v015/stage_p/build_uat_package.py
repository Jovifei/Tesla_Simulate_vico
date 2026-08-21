"""Create the bounded, hand-off-only Jovi UAT package."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(destination: Path, review_package: Path, repo: Path, *, webmushra_root: Path) -> dict[str, object]:
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite populated UAT package: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    package_name = review_package.name
    scripts: dict[str, str] = {
        "START_REVIEW.ps1": f'''param([string]$WebMushraRoot = "{webmushra_root}")
$ErrorActionPreference = "Stop"
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$config = Join-Path $packageRoot "..\\{package_name}\\configs\\{package_name}.yaml"
$audio = Join-Path $packageRoot "..\\{package_name}\\audio"
$targetConfig = Join-Path $WebMushraRoot "configs\\{package_name}.yaml"
$targetAudio = Join-Path $WebMushraRoot "configs\\{package_name}\\audio"
if (!(Test-Path -LiteralPath $config)) {{ throw "review package config missing: $config" }}
if (!(Test-Path -LiteralPath $targetConfig)) {{ Copy-Item -LiteralPath $config -Destination $targetConfig }}
if (!(Test-Path -LiteralPath $targetAudio)) {{ Copy-Item -LiteralPath $audio -Destination $targetAudio -Recurse }}
Push-Location $WebMushraRoot
try {{ docker compose up --build -d }} finally {{ Pop-Location }}
Write-Output "READY http://127.0.0.1:8000/?config={package_name}.yaml"
Write-Output "Hidden reference policy: synthetic parent, not a real vehicle recording."
''',
        "STOP_REVIEW.ps1": f'''param([string]$WebMushraRoot = "{webmushra_root}")
$ErrorActionPreference = "Stop"
Push-Location $WebMushraRoot
try {{ docker compose stop }} finally {{ Pop-Location }}
Write-Output "Stopped only the official webMUSHRA compose service; result files were not deleted."
''',
        "OPEN_REVIEW.ps1": f'''param([string]$Url = "http://127.0.0.1:8000/?config={package_name}.yaml")
Start-Process $Url
Write-Output "Opened $Url"
''',
        "CHECK_STATUS.ps1": f'''param([string]$WebMushraRoot = "{webmushra_root}")
$ErrorActionPreference = "Stop"
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$binding = Get-Content (Join-Path $packageRoot "..\\{package_name}\\webmushra_package_manifest.json") -Raw | ConvertFrom-Json
$results = Join-Path $WebMushraRoot "results\\$($binding.test_id)"
$mushra = Join-Path $results "mushra.csv"
$lss = Join-Path $results "lss.csv"
Push-Location $WebMushraRoot
try {{ docker compose ps }} finally {{ Pop-Location }}
if (Test-Path -LiteralPath $mushra) {{ Write-Output "mushra.csv present: $((Import-Csv $mushra).Count) data rows" }} else {{ Write-Output "mushra.csv missing" }}
if (Test-Path -LiteralPath $lss) {{ Write-Output "lss.csv present: $((Import-Csv $lss).Count) data rows" }} else {{ Write-Output "lss.csv missing" }}
Write-Output "Human feedback remains pending until explicit Jovi metadata-bound submission."
''',
        "IMPORT_RESULTS.ps1": f'''param([string]$WebMushraRoot = "{webmushra_root}", [string]$Output = "uat_import_receipt.json", [string]$Python = "python", [string]$Repo = "{repo}")
$ErrorActionPreference = "Stop"
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$binding = Join-Path $packageRoot "..\\{package_name}\\webmushra_package_manifest.json"
$results = Join-Path $WebMushraRoot "results\\{package_name}"
$mushra = Join-Path $results "mushra.csv"
$lss = Join-Path $results "lss.csv"
if (!(Test-Path -LiteralPath $mushra) -or !(Test-Path -LiteralPath $lss)) {{ throw "both official mushra.csv and lss.csv are required" }}
Push-Location $Repo
try {{ & $Python -m tools.sound_sim.s12.acoustic_comparator.listening.webmushra_import --input $mushra --lss-input $lss --binding $binding --output (Join-Path $packageRoot $Output) }} finally {{ Pop-Location }}
Write-Output "Imported into $(Join-Path $packageRoot $Output); inspect status before any human-feedback use."
''',
    }
    for name, content in scripts.items():
        (destination / name).write_text(content, encoding="utf-8", newline="\r\n")
    (destination / "README.md").write_text(
        f"# S12 Stage-P Jovi UAT package\n\n"
        f"This package is a bounded UAT hand-off for `{package_name}`. It does not change vehicle sources, profiles, idle/afterfire/low-frequency/shift parameters, or any frozen runtime. The hidden reference is explicitly a synthetic Stage-K parent, **not a real vehicle recording**. Automatic metrics and fixture/browser exports are not human feedback and are not tuning authority.\n\n"
        "## Run\n\n"
        "1. `powershell -ExecutionPolicy Bypass -File .\\START_REVIEW.ps1`\n"
        "2. `powershell -ExecutionPolicy Bypass -File .\\OPEN_REVIEW.ps1`\n"
        "3. Complete the official browser study and enter your listener ID.\n"
        "4. `powershell -ExecutionPolicy Bypass -File .\\CHECK_STATUS.ps1`\n"
        "5. `powershell -ExecutionPolicy Bypass -File .\\IMPORT_RESULTS.ps1`\n"
        "6. `powershell -ExecutionPolicy Bypass -File .\\STOP_REVIEW.ps1` when finished.\n\n"
        "Only an explicit Jovi submission with complete playback metadata can enter Stage O as human feedback. A fixture listener or synthetic identity is fail-closed. No profile freeze is authorized by this package.\n",
        encoding="utf-8", newline="\n",
    )
    files = []
    for path in sorted(destination.iterdir()):
        if path.name in {"manifest.json", "manifest.sha256"} or not path.is_file():
            continue
        files.append({"path": path.name, "bytes": path.stat().st_size, "sha256": _sha(path)})
    manifest = {
        "schema_version": "s12-stage-p-jovi-uat-manifest-1",
        "status": "READY_FOR_JOVI_UAT",
        "review_package": str(review_package),
        "review_package_manifest_sha256": _sha(review_package / "webmushra_package_manifest.json"),
        "study_manifest_sha256": _sha(review_package / "study_manifest.json"),
        "scripts": files,
        "hidden_reference_policy": "synthetic_parent_not_real_reference",
        "human_feedback_available": False,
        "tuning_authority": False,
        "profile_freeze_ready": False,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (destination / "manifest.sha256").write_text(f"{_sha(manifest_path)}  manifest.json\n", encoding="utf-8", newline="\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--review-package", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--webmushra-root", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.destination, args.review_package, args.repo, webmushra_root=args.webmushra_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
