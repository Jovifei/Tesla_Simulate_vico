# Host runbook: Muse's separate Windows acceptance

This runbook has **not been executed on the host**. The authoring environment is Linux x86_64, without MSVC or CMake. Its Python fixture tests are not a C++ smoke run. Do not merge or deploy after these steps.

Use PowerShell with an existing Python 3.10+, Git, CMake >= 3.20 and Visual Studio 2022 C++ workload / Windows SDK. Do not install or update anything as part of this package. No Community Edition executable or binary is used. Download/review this new directory from the exact PR head separately; do not switch, reset, merge or clean either original checkout. The commands prompt for verified existing paths instead of guessing where the original repositories are.

The required new experiment path is `E:\Tesla_speed\experiments\direction-a-step1-20261112`. It must not exist, and must be outside both original Git checkout roots and the package source directory. If an original checkout is itself `E:\Tesla_speed`, **stop**: this layout would put the experiment inside an original repository. Arrange a separately reviewed source/experiment layout before proceeding; do not bypass the check or hide changes with ignore rules.

## 1. Identify paths and capture both original repository states

```powershell
$ErrorActionPreference = 'Stop'
$Package = (Resolve-Path (Read-Host 'Path to this reviewed package directory')).Path
$ProductRepo = (Resolve-Path (Read-Host 'Existing Tesla_Simulate_vico Git root')).Path
$EngineRepo = (Resolve-Path (Read-Host 'Existing ORIGINAL MIT engine-sim Git root, not Community Edition')).Path
$SolverRepo = Join-Path $EngineRepo 'dependencies\submodules\simple-2d-constraint-solver'
$Out = 'E:\Tesla_speed\experiments\direction-a-step1-20261112'
if (Test-Path $Out) { throw 'Experiment directory already exists; preserve it and stop.' }
$Python = (Get-Command python -ErrorAction Stop).Source
& $Python -c 'import sys; assert sys.version_info >= (3,10); print(sys.version)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ required' }
git --version
cmake --version
if ($LASTEXITCODE -ne 0) { throw 'CMake is not available' }

# Acceptance checkpoint 1: both original repositories, read-only, before export.
git --no-optional-locks -C $ProductRepo status --short
if ($LASTEXITCODE -ne 0) { throw 'Invalid product Git root' }
git --no-optional-locks -C $EngineRepo status --short
if ($LASTEXITCODE -ne 0) { throw 'Invalid engine Git root' }
$ProductBefore = (git --no-optional-locks -C $ProductRepo status --porcelain=v1 --untracked-files=all | Out-String)
$EngineBefore = (git --no-optional-locks -C $EngineRepo status --porcelain=v1 --untracked-files=all | Out-String)
$ProductHeadBefore = git -C $ProductRepo rev-parse HEAD
$EngineHeadBefore = git -C $EngineRepo rev-parse HEAD
git -C $EngineRepo cat-file -e '85f7c3b959a908ed5232ede4f1a4ac7eafe6b630^{commit}'
if ($LASTEXITCODE -ne 0) { throw 'Pinned engine object is absent; do not fetch or substitute silently' }
$ActualSolver = git -C $SolverRepo rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Existing solver checkout is absent; stop for owner/Muse review' }
Write-Host "Actual solver checkout SHA: $ActualSolver"
```

Dirty original working files are never copied. The exporter reads commit objects and records dirty status; do not clean, stash or overwrite anyone's work. Concurrent changes make acceptance fail even if unrelated.

## 2. Export, build, capture, verify; always perform checkpoint 2

```powershell
try {
    $PrepareLog = & $Python "$Package\prepare_workspace.py" `
        --engine-repo $EngineRepo --product-repo $ProductRepo `
        --solver-repo $SolverRepo --out $Out 2>&1
    $PrepareExit = $LASTEXITCODE
    $PrepareLog | Write-Output
    if (Test-Path $Out) { $PrepareLog | Set-Content "$Out\prepare.log" }
    if ($PrepareExit -ne 0) { throw 'Export failed. Preserve the partial directory and receipt.' }
    $Identity = Get-Content "$Out\source-identity.json" -Raw | ConvertFrom-Json
    if ($Identity.status -ne 'EXPORTED_NOT_BUILT' -or !$Identity.solver_matches_engine_gitlink) {
        throw 'Actual solver differs from the engine gitlink or export is incomplete. Compatibility review required; do not build yet.'
    }
    if (!$Identity.original_repositories_unchanged) { throw 'Original repository state changed' }
    New-Item -ItemType Directory "$Out\host-evidence" | Out-Null
    $PSVersionTable | Out-String | Set-Content "$Out\host-evidence\powershell.txt"
    Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture | ConvertTo-Json | Set-Content "$Out\host-evidence\os.json"
    & $Python --version 2>&1 | Set-Content "$Out\host-evidence\python.txt"
    git --version | Set-Content "$Out\host-evidence\git.txt"
    cmake --version | Set-Content "$Out\host-evidence\cmake.txt"

    cmake -S $Out -B "$Out\build" -G 'Visual Studio 17 2022' -A x64 `
        -DDTV=OFF -DDISCORD_ENABLED=OFF 2>&1 | Tee-Object "$Out\host-evidence\configure.log"
    if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed; not a build pass' }
    cmake --build "$Out\build" --config Release --target engine_offline --parallel 4 `
        2>&1 | Tee-Object "$Out\host-evidence\build-release.log"
    if ($LASTEXITCODE -ne 0) { throw 'MSVC build failed; no smoke pass' }
    $Exe = "$Out\build\Release\engine_offline.exe"
    Get-FileHash $Exe -Algorithm SHA256 | Format-List | Out-String | Set-Content "$Out\host-evidence\executable-sha256.txt"
    & $Exe "$Out\smoke-2s" smoke 2 2>&1 | Tee-Object "$Out\host-evidence\smoke.log"
    if ($LASTEXITCODE -ne 0) { throw 'C++ smoke failed; preserve all partial output' }
    & $Python "$Out\verify_capture.py" "$Out\smoke-2s" --out "$Out\host-evidence\verification.json" `
        2>&1 | Tee-Object "$Out\host-evidence\verify.log"
    if ($LASTEXITCODE -ne 0) { throw 'Capture data verification failed' }
    # Expected: 20,000 physics frames, 88,200 audio frames, 70,000 total steps;
    # pressure 1,440,000 bytes, signed omega 80,000 bytes, audio 2,116,800 bytes.
    Write-Host 'Basic offline sanity only. Not OEM, acoustic, S12, or product acceptance.'
}
finally {
    # Acceptance checkpoint 2: both original repositories, even after any failure.
    git --no-optional-locks -C $ProductRepo status --short
    git --no-optional-locks -C $EngineRepo status --short
    $ProductAfter = (git --no-optional-locks -C $ProductRepo status --porcelain=v1 --untracked-files=all | Out-String)
    $EngineAfter = (git --no-optional-locks -C $EngineRepo status --porcelain=v1 --untracked-files=all | Out-String)
    $Unchanged = ($ProductBefore -ceq $ProductAfter) -and ($EngineBefore -ceq $EngineAfter) -and `
        ($ProductHeadBefore -eq (git -C $ProductRepo rev-parse HEAD)) -and `
        ($EngineHeadBefore -eq (git -C $EngineRepo rev-parse HEAD))
    $StatusReceipt = @{ product_before=$ProductBefore; product_after=$ProductAfter; engine_before=$EngineBefore; engine_after=$EngineAfter; original_repositories_unchanged=$Unchanged }
    if (Test-Path $Out) { $StatusReceipt | ConvertTo-Json | Set-Content "$Out\original-repositories-final-status.json" }
    if (!$Unchanged) { throw 'Original repository status/HEAD changed. Stop acceptance and investigate; do not reset or clean.' }
}
```

Review and retain `source-identity.json`, raw archives, pristine source manifests, `capture-patches.json`, final original-status receipt, exact executable SHA256, CMake configure/build logs and compiler identification in `build/CMakeFiles/`, smoke outputs, and `host-evidence/verification.json`. Keep failed outputs too. Do not overwrite a capture or relabel a prior run. The exporter receipt remains `build_validation: NOT_RUN` because it describes export time; the later host logs and verification file are separate evidence.

Only after successful data checks and unchanged original statuses may Muse report a Windows offline smoke pass for that exact package/compiler/solver/executable. No listening, calibration, integration, merge or deployment is authorized by this runbook.
