param(
    [Parameter(Mandatory)] [ValidateSet('configure', 'build', 'smoke', 'verify')] [string] $Stage,
    [Parameter(Mandatory)] [ValidateSet('configure', 'build', 'smoke', 'verify', 'none')] [string] $FailStage,
    [Parameter(Mandatory)] [string] $CaseRoot
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'mock_paths.ps1')
$case = Assert-MockCasePath $CaseRoot
$out = Join-Path $case 'out'
$trace = Join-Path $case 'events.jsonl'

function Write-MockEvent([System.Collections.IDictionary] $event) {
    [IO.File]::AppendAllText($trace, (($event | ConvertTo-Json -Compress) + "`n"))
}

Write-MockEvent ([ordered]@{ event = 'stage_start'; stage = $Stage })
$artifacts = @{
    configure = (Join-Path $out 'build/CMakeCache.txt')
    build = (Join-Path $out 'build/Release/engine_offline.exe')
    smoke = (Join-Path $out 'smoke-2s/capture.json')
    verify = (Join-Path $out 'host-evidence/verification.json')
}
$inputForStage = @{ build = 'configure'; smoke = 'build'; verify = 'smoke' }
if ($inputForStage.ContainsKey($Stage)) {
    $inputName = $inputForStage[$Stage]
    $inputText = [IO.File]::ReadAllText($artifacts[$inputName])
    Write-MockEvent ([ordered]@{
        event = 'artifact_read'; stage = $Stage; artifact = $inputName
        stale = $inputText.Contains('FAKE_STALE_')
    })
}

$codes = @{ configure = 31; build = 32; smoke = 33; verify = 34 }
$exitCode = if ($Stage -eq $FailStage) { $codes[$Stage] } else { 0 }
if ($exitCode -eq 0) {
    [IO.File]::WriteAllText($artifacts[$Stage], "FAKE_FRESH_$($Stage.ToUpperInvariant())`n")
}
Write-MockEvent ([ordered]@{ event = 'stage_exit'; stage = $Stage; exit = $exitCode })
Write-Output "MOCK_ONLY stage=$Stage exit=$exitCode"
exit $exitCode
