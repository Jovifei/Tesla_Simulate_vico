# One-shot cleanup for the isolated cabin lab.
# Deletes only regenerable bulk and superseded build attempts inside the lab.
# Original SLX, Frozen, public common source, sound bank and Android are never touched.
$ErrorActionPreference = 'Stop'

$lab = 'E:\Tesla_speed\worktrees\hellcat-state-contract-20261027\reports\app8-cabin-mechanical-bank-candidate-20261030'
$labFull = [System.IO.Path]::GetFullPath($lab).TrimEnd('\')

function Assert-InLab([string]$path) {
    $full = [System.IO.Path]::GetFullPath($path)
    if (-not $full.StartsWith($labFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to act outside the lab: $full"
    }
}

if (-not (Test-Path -LiteralPath $labFull)) { throw "Lab missing: $labFull" }

# 1. Superseded / failed SLX build attempts, keeping the final candidate and its B0 reference.
$keepModels = @(
    'S12_hellcat_cabin_event_bank_dimfix_20261031_154809_713.slx',
    'S12_hellcat_cabin_event_bank_20261031_112747_734.slx',
    'S12_hellcat_cabin_B0_reference_20261031_112747_734.slx'
)
$iso = Join-Path $labFull 'isolated'
Assert-InLab $iso
$removedModels = 0
if (Test-Path -LiteralPath $iso) {
    foreach ($f in Get-ChildItem -LiteralPath $iso -File) {
        if ($keepModels -contains $f.Name) { continue }
        Assert-InLab $f.FullName
        Remove-Item -LiteralPath $f.FullName -Force
        $removedModels++
    }
}

# 2. Regenerable bulk directories.
$bulkDirs = @('runs', 'cabin-cache', 'cabin-codegen', '__pycache__')
$removedDirs = @()
foreach ($name in $bulkDirs) {
    $p = Join-Path $labFull $name
    if (Test-Path -LiteralPath $p) {
        Assert-InLab $p
        Remove-Item -LiteralPath $p -Recurse -Force
        $removedDirs += $name
    }
}

# 3. Audition WAV bulk (large rendered audio, reproducible from receipts).
$audition = Join-Path $labFull 'audition-formal-20261031'
$removedAudition = 0
if (Test-Path -LiteralPath $audition) {
    Assert-InLab $audition
    foreach ($f in Get-ChildItem -LiteralPath $audition -Recurse -File -Filter '*.wav') {
        Assert-InLab $f.FullName
        Remove-Item -LiteralPath $f.FullName -Force
        $removedAudition++
    }
}

$report = [pscustomobject]@{
    schema               = 'app8.cabin.lab_cleanup.result.v1'
    date                 = (Get-Date -Format 'yyyy-MM-dd')
    lab                  = $labFull
    removed_slx          = $removedModels
    removed_dirs         = $removedDirs
    removed_audition_wav = $removedAudition
}
$out = Join-Path $labFull 'research-iteration3/CLEANUP-RESULT.json'
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $out -Encoding UTF8
$report | Format-List
