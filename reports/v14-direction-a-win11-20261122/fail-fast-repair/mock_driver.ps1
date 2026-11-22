param(
    [Parameter(Mandatory)] [ValidateSet('old', 'fixed')] [string] $Mode,
    [Parameter(Mandatory)] [ValidateSet('configure', 'build', 'smoke', 'verify', 'none')] [string] $FailStage,
    [Parameter(Mandatory)] [string] $CaseRoot
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
. (Join-Path $PSScriptRoot 'mock_paths.ps1')
$CaseRoot = Assert-MockCasePath $CaseRoot
$historical = Join-Path $PSScriptRoot 'historical-step1-runbook.fixture.txt'
$expected = 'da5c40a2e3619955bf3cc8c886ccb07eb9060f54666e82a6c3693347752c1459'
$actual = (Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath $historical -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw 'Historical wrapper does not match the bound receipt.' }
$source = if ($Mode -eq 'old') { $historical } else { Join-Path $PSScriptRoot 'step1-runbook-guarded.ps1' }
$text = [IO.File]::ReadAllText($source).Replace("`r`n", "`n")
$match = [regex]::Match($text, "(?ms)^    cmake -S \`$Out.*?^    Write-Host 'Basic offline sanity only\. Not OEM, acoustic, S12, or product acceptance\.'$")
if (!$match.Success) { throw 'The four-stage historical section was not found exactly.' }
$body = $match.Value

$replacements = @(
    @(@'
    cmake -S $Out -B "$Out\build" -G 'Visual Studio 17 2022' -A x64 `
        -DDTV=OFF -DDISCORD_ENABLED=OFF 2>&1 | Tee-Object "$Out\host-evidence\configure.log"
'@.TrimEnd(), '    & $MockPwsh -NoProfile -NonInteractive -File $MockScript -Stage configure -FailStage $FailStage -CaseRoot $CaseRoot 2>&1 | Tee-Object "$Out\host-evidence\configure.log"'),
    @(@'
    cmake --build "$Out\build" --config Release --target engine_offline --parallel 4 `
        2>&1 | Tee-Object "$Out\host-evidence\build-release.log"
'@.TrimEnd(), '    & $MockPwsh -NoProfile -NonInteractive -File $MockScript -Stage build -FailStage $FailStage -CaseRoot $CaseRoot 2>&1 | Tee-Object "$Out\host-evidence\build-release.log"'),
    @('    & $Exe "$Out\smoke-2s" smoke 2 2>&1 | Tee-Object "$Out\host-evidence\smoke.log"', '    & $MockPwsh -NoProfile -NonInteractive -File $MockScript -Stage smoke -FailStage $FailStage -CaseRoot $CaseRoot 2>&1 | Tee-Object "$Out\host-evidence\smoke.log"'),
    @(@'
    & $Python "$Out\verify_capture.py" "$Out\smoke-2s" --out "$Out\host-evidence\verification.json" `
        2>&1 | Tee-Object "$Out\host-evidence\verify.log"
'@.TrimEnd(), '    & $MockPwsh -NoProfile -NonInteractive -File $MockScript -Stage verify -FailStage $FailStage -CaseRoot $CaseRoot 2>&1 | Tee-Object "$Out\host-evidence\verify.log"')
)
foreach ($pair in $replacements) {
    $first = $body.IndexOf($pair[0], [StringComparison]::Ordinal)
    if ($first -lt 0 -or $body.IndexOf($pair[0], $first + $pair[0].Length, [StringComparison]::Ordinal) -ge 0) {
        throw 'A native command replacement was absent or ambiguous.'
    }
    $body = $body.Replace($pair[0], $pair[1])
}
if ($body -match '(?m)^\s*cmake\s' -or $body -match '(?m)^\s*& \$(Exe|Python)\b') {
    throw 'A real native command remained in the mock body.'
}

$Out = Join-Path $CaseRoot 'out'
$MockPwsh = Join-Path $PSHOME 'pwsh.exe'
$MockScript = Join-Path $PSScriptRoot 'mock_stage.ps1'
$TaskStage = [ordered]@{ configure = $null; build = $null; smoke = $null; verify = $null }
$trace = Join-Path $CaseRoot 'events.jsonl'
function Get-FileHash {
    param([Parameter(Position=0)] [string] $Path, [string] $Algorithm)
    $content = [IO.File]::ReadAllText($Path)
    $event = [ordered]@{ event = 'artifact_hash_read'; stage = 'before_smoke'; artifact = 'build'; stale = $content.Contains('FAKE_STALE_') }
    [IO.File]::AppendAllText($trace, (($event | ConvertTo-Json -Compress) + "`n"))
    Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath $Path -Algorithm $Algorithm
}

$status = 'RUNBOOK_COMPLETED'
$reason = $null
$processExit = 0
try {
    & ([scriptblock]::Create($body))
    # Models the prior outer runner's success decision, not a production receipt.
    [IO.File]::WriteAllText((Join-Path $CaseRoot 'mock-success-receipt.json'), '{"mock_only":true,"status":"SUCCESS"}')
} catch {
    $status = 'FAILED'
    $reason = $_.Exception.Message
    $processExit = 1
}
$observation = [ordered]@{
    mock_only = $true; mode = $Mode; failed_stage = $FailStage; status = $status
    process_exit = $processExit; observed_native_exit_codes = $TaskStage; reason = $reason
    success_receipt_exists = (Test-Path -LiteralPath (Join-Path $CaseRoot 'mock-success-receipt.json'))
}
[IO.File]::WriteAllText((Join-Path $CaseRoot 'wrapper-observation.json'), ($observation | ConvertTo-Json -Depth 5))
exit $processExit
