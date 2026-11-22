function Assert-MockCasePath([string] $CaseRoot) {
    $lab = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $allowed = [IO.Path]::GetFullPath((Join-Path $lab 'mock-runs')) + [IO.Path]::DirectorySeparatorChar
    $case = [IO.Path]::GetFullPath($CaseRoot)
    if (!$case.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Mock case must stay under the mock-runs directory.'
    }

    $directory = [IO.DirectoryInfo]::new($case)
    $reachedLab = $false
    while ($null -ne $directory) {
        if (!$directory.Exists -or ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Mock path contains a missing directory or reparse point.'
        }
        if ($directory.FullName.Equals($lab, [StringComparison]::OrdinalIgnoreCase)) { $reachedLab = $true }
        $directory = $directory.Parent
    }
    if (!$reachedLab) { throw 'Mock case is outside the candidate directory.' }

    foreach ($relative in @('out', 'out/build', 'out/build/Release', 'out/smoke-2s', 'out/host-evidence',
            'out/build/CMakeCache.txt', 'out/build/Release/engine_offline.exe', 'out/smoke-2s/capture.json',
            'out/host-evidence/verification.json', 'out/host-evidence/configure.log',
            'out/host-evidence/build-release.log', 'out/host-evidence/executable-sha256.txt',
            'out/host-evidence/smoke.log', 'out/host-evidence/verify.log',
            'events.jsonl', 'wrapper-observation.json', 'mock-success-receipt.json')) {
        $path = Join-Path $case $relative
        $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        if ($null -ne $item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Mock case contains a reparse point.'
        }
    }
    return $case
}
