# Remove copied MATLAB user-profile / credential artifacts from the startup diagnostics.
# These are LOCAL-ONLY: they may contain certificates, keys, preferences and caches.
# Kept: written diagnosis, receipts, logs and crash-dump metadata.
$ErrorActionPreference = 'Stop'

$lab = 'E:\Tesla_speed\worktrees\hellcat-state-contract-20261027\reports\app8-cabin-mechanical-bank-candidate-20261030'
$labFull = [System.IO.Path]::GetFullPath($lab).TrimEnd('\')

function Assert-InLab([string]$path) {
    $full = [System.IO.Path]::GetFullPath($path)
    if (-not $full.StartsWith($labFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to act outside the lab: $full"
    }
}

# Copied user-profile / runtime trees that may contain credentials or machine state.
$sensitiveDirs = @(
    'startup-diagnostic\prefs',
    'startup-diagnostic\base_isolated',
    'startup-diagnostic\sanitized_home',
    'startup-diagnostic\sanitized_home_nouserjava_softwareopengl',
    'startup-diagnostic\sanitized_home_nouserjavapath',
    'startup-diagnostic\sanitized_home_singlethread',
    'startup-diagnostic\sanitized_home_softwareopengl',
    'startup-diagnostic\temp',
    'startup-diagnostic\__pycache__',
    'startup-recovery-20261031\__pycache__'
)

$removed = @()
foreach ($rel in $sensitiveDirs) {
    $p = Join-Path $labFull $rel
    if (Test-Path -LiteralPath $p) {
        Assert-InLab $p
        Remove-Item -LiteralPath $p -Recurse -Force
        $removed += $rel
    }
}

# Any leftover credential/key material anywhere in the lab must go.
$credPatterns = @('*.p12','*.pem','*.key','*.pfx')
$removedCreds = 0
foreach ($pat in $credPatterns) {
    foreach ($f in Get-ChildItem -LiteralPath $labFull -Recurse -File -Filter $pat -ErrorAction SilentlyContinue) {
        Assert-InLab $f.FullName
        Remove-Item -LiteralPath $f.FullName -Force
        $removedCreds++
    }
}

# Embedded-browser / MATLAB temp trees captured during the probes.
$removedTempDirs = @()
$tempDirs = Get-ChildItem -LiteralPath $labFull -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq 'temp' } |
    Sort-Object { $_.FullName.Length } -Descending
foreach ($d in $tempDirs) {
    if ($d.Name -ne 'temp') { continue }
    if (-not (Test-Path -LiteralPath $d.FullName)) { continue }
    Assert-InLab $d.FullName
    Remove-Item -LiteralPath $d.FullName -Recurse -Force
    $removedTempDirs += $d.FullName.Substring($labFull.Length)
}

$report = [pscustomobject]@{
    schema              = 'app8.cabin.lab_private_state_cleanup.v1'
    date                = (Get-Date -Format 'yyyy-MM-dd')
    removed_dirs        = $removed
    removed_credential_files = $removedCreds
    removed_temp_dirs   = $removedTempDirs
    note                = 'Copied MATLAB user-profile and credential artifacts are local-only and must never be pushed.'
}
$out = Join-Path $labFull 'research-iteration3/CLEANUP-PRIVATE-STATE.json'
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $out -Encoding UTF8
$report | Format-List
