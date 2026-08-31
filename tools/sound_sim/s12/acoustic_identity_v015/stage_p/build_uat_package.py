"""Create the bounded, hand-off-only Jovi UAT package."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_sha256sums(destination: Path) -> Path:
    """Write a recursive checksum ledger without a self-referential entry."""
    lines = []
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        relative = path.relative_to(destination).as_posix()
        lines.append(f"{_sha(path)}  {relative}")
    checksum_path = destination / "SHA256SUMS"
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return checksum_path


def _jovi_readme(package_name: str) -> str:
    return (
        f"# S12 Stage-P Jovi UAT package\n\n"
        f"This package is a bounded UAT hand-off for `{package_name}`. It does not change vehicle sources, profiles, idle/afterfire/low-frequency/shift parameters, or any frozen runtime. The hidden reference is explicitly a synthetic Stage-K parent, **not a real vehicle recording**. Automatic metrics and fixture/browser exports are not human feedback and are not tuning authority.\n\n"
        "## Listening setup\n\n"
        "1. Use over-ear headphones or neutral near-field speakers; do not use a phone speaker.\n"
        "2. Set Windows volume to a comfortable moderate level (start around 20–30% and do not chase loudness between trials).\n"
        "3. Disable Windows spatial audio, loudness equalization, vendor EQ, enhancement, and any compressor/limiter.\n"
        "4. Listen in a quiet environment and take breaks if fatigued.\n"
        "5. Do not look up or infer vehicle names while rating; use the anonymous trial IDs and your actual acoustic impression.\n\n"
        "## Run\n\n"
        "1. `powershell -ExecutionPolicy Bypass -File .\\START_REVIEW.ps1`\n"
        "2. `powershell -ExecutionPolicy Bypass -File .\\OPEN_REVIEW.ps1`\n"
        "3. Complete every browser trial and enter your explicit Jovi listener ID.\n"
        "4. `powershell -ExecutionPolicy Bypass -File .\\CHECK_STATUS.ps1`\n"
        "5. `powershell -ExecutionPolicy Bypass -File .\\IMPORT_RESULTS.ps1`\n"
        "6. `powershell -ExecutionPolicy Bypass -File .\\STOP_REVIEW.ps1` when finished.\n\n"
        "## Deliver to the Agent\n\n"
        "Provide the current package-bound `mushra.csv`, `lss.csv`, the generated `uat_import_receipt.json`, and the listener/playback metadata. Do not rename or edit the CSV files. Expected official paths are `results/s12-stage-p-system-acceptance-v1/mushra.csv` and `results/s12-stage-p-system-acceptance-v1/lss.csv`; the package-local fixture paths are `results/mushra.csv` and `results/lss.csv`.\n\n"
        "Only an explicit Jovi submission with complete playback metadata can enter Stage O as human feedback. A fixture listener or synthetic identity is fail-closed. No profile freeze is authorized by this package.\n"
    )


def _expected_result_paths(package_name: str) -> dict[str, object]:
    return {
        "package_local": [
            f"{package_name}/results/mushra.csv",
            f"{package_name}/results/lss.csv",
            f"{package_name}/results/browser_import_receipt.json",
            f"{package_name}/results/normalized_import_result.json",
        ],
        "official_webmushra": [
            f"results/{package_name}/mushra.csv",
            f"results/{package_name}/lss.csv",
        ],
        "uat_receipt": "uat_import_receipt.json",
    }


def refresh_manifest(destination: Path, review_package: Path) -> dict[str, object]:
    """Refresh a populated UAT hand-off after browser result files arrive."""
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    package_name = review_package.name
    readme = _jovi_readme(package_name)
    (destination / "README_JOVI.md").write_text(readme, encoding="utf-8", newline="\n")
    (destination / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    files = []
    for path in sorted(destination.iterdir()):
        if path.name in {"manifest.json", "manifest.sha256", "SHA256SUMS"} or not path.is_file():
            continue
        files.append({"path": path.name, "bytes": path.stat().st_size, "sha256": _sha(path)})
    manifest.update(
        {
            "scripts": files,
            "review_package_manifest_sha256": _sha(review_package / "webmushra_package_manifest.json"),
            "study_manifest_sha256": _sha(review_package / "study_manifest.json"),
            "human_acoustic_qualification_status": "HUMAN_ACOUSTIC_QUALIFICATION_PENDING",
            "expected_result_paths": _expected_result_paths(package_name),
            "required_files": [
                "START_REVIEW.ps1",
                "STOP_REVIEW.ps1",
                "OPEN_REVIEW.ps1",
                "IMPORT_RESULTS.ps1",
                "CHECK_STATUS.ps1",
                "README_JOVI.md",
                "study_manifest.json",
                "SHA256SUMS",
            ],
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (destination / "manifest.sha256").write_text(f"{_sha(manifest_path)}  manifest.json\n", encoding="utf-8", newline="\n")
    write_sha256sums(destination)
    return manifest


def build(destination: Path, review_package: Path, repo: Path, *, webmushra_root: Path) -> dict[str, object]:
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite populated UAT package: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    package_name = review_package.name
    scripts: dict[str, str] = {
        "START_REVIEW.ps1": f'''param([string]$WebMushraRoot = "{webmushra_root}")
$ErrorActionPreference = "Stop"
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (!$docker) {{ throw "Docker CLI not found; install/start Docker Desktop before UAT." }}
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {{ throw "Docker Desktop daemon unavailable; start Docker Desktop and rerun START_REVIEW.ps1." }}
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$config = Join-Path $packageRoot "..\\{package_name}\\configs\\{package_name}.yaml"
$audio = Join-Path $packageRoot "..\\{package_name}\\audio"
$targetConfig = Join-Path $WebMushraRoot "configs\\{package_name}.yaml"
$targetAudio = Join-Path $WebMushraRoot "configs\\{package_name}\\audio"
if (!(Test-Path -LiteralPath $config)) {{ throw "review package config missing: $config" }}
if (!(Test-Path -LiteralPath $targetConfig)) {{ Copy-Item -LiteralPath $config -Destination $targetConfig }}
if (!(Test-Path -LiteralPath $targetAudio)) {{ Copy-Item -LiteralPath $audio -Destination $targetAudio -Recurse }}
$port = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($port) {{ Write-Output "Port 8000 is already listening; compose status will be verified before use." }}
Push-Location $WebMushraRoot
try {{
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) {{ throw "Docker compose configuration check failed." }}
    # Reuse the already-built official image when available; Compose still
    # builds from the checked-out Dockerfile if the image is absent.
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {{ throw "Docker compose start failed." }}
}} finally {{ Pop-Location }}
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
$bindingPath = Join-Path $packageRoot "..\\{package_name}\\webmushra_package_manifest.json"
$manifestSha = (Get-FileHash -LiteralPath $bindingPath -Algorithm SHA256).Hash.ToLower()
Write-Output "manifest SHA: $manifestSha"
$results = Join-Path $WebMushraRoot "results\\$($binding.test_id)"
$mushra = Join-Path $results "mushra.csv"
$lss = Join-Path $results "lss.csv"
Push-Location $WebMushraRoot
try {{ docker compose ps }} finally {{ Pop-Location }}
$trialCount = @($binding.trials.PSObject.Properties).Count
$mushraRows = if (Test-Path -LiteralPath $mushra) {{ @(Import-Csv $mushra).Count }} else {{ 0 }}
$lssRows = if (Test-Path -LiteralPath $lss) {{ @(Import-Csv $lss).Count }} else {{ 0 }}
Write-Output "mushra.csv: $mushraRows data rows (expected $($trialCount * 4))"
Write-Output "lss.csv: $lssRows data rows (expected $($trialCount * 10))"
if ($mushraRows -eq ($trialCount * 4) -and $lssRows -eq ($trialCount * 10)) {{ Write-Output "all trials complete: PASS" }} else {{ Write-Output "all trials complete: PENDING" }}
Write-Output "Human feedback remains pending until explicit Jovi metadata-bound submission."
''',
        "IMPORT_RESULTS.ps1": f'''param([string]$WebMushraRoot = "{webmushra_root}", [string]$Output = "uat_import_receipt.json", [string]$Python = "python", [string]$Repo = "{repo}")
$ErrorActionPreference = "Stop"
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bindingPath = Join-Path $packageRoot "..\\{package_name}\\webmushra_package_manifest.json"
$binding = Get-Content -LiteralPath $bindingPath -Raw | ConvertFrom-Json
$results = Join-Path $WebMushraRoot "results\\{package_name}"
$mushra = Join-Path $results "mushra.csv"
$lss = Join-Path $results "lss.csv"
if (!(Test-Path -LiteralPath $mushra) -or !(Test-Path -LiteralPath $lss)) {{ throw "both official mushra.csv and lss.csv are required" }}
Push-Location $Repo
try {{ & $Python -m tools.sound_sim.s12.acoustic_comparator.listening.webmushra_import --input $mushra --lss-input $lss --binding $bindingPath --output (Join-Path $packageRoot $Output) }} finally {{ Pop-Location }}
if ($LASTEXITCODE -ne 0) {{ throw "Importer failed." }}
$receiptPath = Join-Path $packageRoot $Output
$receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
$row = @($receipt.rows)[0]
$trialCount = @($binding.trials.PSObject.Properties).Count
$shaStatus = if ($row.package_manifest_sha256 -eq $binding.package_manifest_sha256) {{ "PASS" }} else {{ "FAIL" }}
Write-Output "Imported into $receiptPath"
Write-Output "status: $($receipt.status); accepted_rows: $($receipt.accepted_rows); rejected_rows: $($receipt.rejected_rows)"
Write-Output "missing/complete trial binding: accepted $($receipt.accepted_rows) of $trialCount; package SHA binding: $shaStatus"
''',
    }
    for name, content in scripts.items():
        (destination / name).write_text(content, encoding="utf-8", newline="\r\n")
    readme = _jovi_readme(package_name)
    (destination / "README_JOVI.md").write_text(readme, encoding="utf-8", newline="\n")
    # Keep the historical filename as a compatibility alias for earlier hand-offs.
    (destination / "README.md").write_text(readme, encoding="utf-8", newline="\n")
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
        "human_acoustic_qualification_status": "HUMAN_ACOUSTIC_QUALIFICATION_PENDING",
        "expected_result_paths": _expected_result_paths(package_name),
        "required_files": [
            "START_REVIEW.ps1",
            "STOP_REVIEW.ps1",
            "OPEN_REVIEW.ps1",
            "IMPORT_RESULTS.ps1",
            "CHECK_STATUS.ps1",
            "README_JOVI.md",
            "study_manifest.json",
            "SHA256SUMS",
        ],
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (destination / "manifest.sha256").write_text(f"{_sha(manifest_path)}  manifest.json\n", encoding="utf-8", newline="\n")
    write_sha256sums(destination)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--review-package", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--webmushra-root", type=Path, required=True)
    parser.add_argument("--refresh", action="store_true", help="refresh a populated hand-off after result files arrive")
    args = parser.parse_args(argv)
    if args.refresh:
        result = refresh_manifest(args.destination, args.review_package)
    else:
        result = build(args.destination, args.review_package, args.repo, webmushra_root=args.webmushra_root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
