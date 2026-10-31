$ErrorActionPreference = 'Continue'
$diagnostic = Split-Path -Parent $MyInvocation.MyCommand.Path
$matlab = 'D:\Program Files\MATLAB\R2026a\bin\matlab.exe'
$matrix = @(
    @{ Name = 'base_isolated'; Extra = @('-nojvm','-batch') ; Home = $false },
    @{ Name = 'sanitized_home'; Extra = @('-nojvm','-batch') ; Home = $true },
    @{ Name = 'sanitized_home_nouserjavapath'; Extra = @('-nojvm','-nouserjavapath','-batch') ; Home = $true },
    @{ Name = 'sanitized_home_softwareopengl'; Extra = @('-nojvm','-softwareopengl','-batch') ; Home = $true },
    @{ Name = 'sanitized_home_singlethread'; Extra = @('-nojvm','-singleCompThread','-batch') ; Home = $true },
    @{ Name = 'sanitized_home_nouserjava_softwareopengl'; Extra = @('-nojvm','-nouserjavapath','-softwareopengl','-batch') ; Home = $true }
)
$statement = "fprintf('MINIMAL_START\n'); assert(2+2==4); fprintf('VERSION=%s\n',version); fprintf('SIMULINK_LICENSE=%d\n',license('test','Simulink')); disp('MINIMAL_DONE');"
$results = @()
foreach ($case in $matrix) {
    $caseRoot = Join-Path $diagnostic $case.Name
    $pref = Join-Path $caseRoot 'prefs'
    $temp = Join-Path $caseRoot 'temp'
    New-Item -ItemType Directory -Force -Path $pref,$temp | Out-Null
    $old = @{}
    foreach ($name in @('MATLAB_PREFDIR','TEMP','TMP','HOMEDRIVE','HOMEPATH','USERPROFILE','APPDATA','LOCALAPPDATA')) {
        $old[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
    }
    $env:MATLAB_PREFDIR = $pref
    $env:TEMP = $temp
    $env:TMP = $temp
    if ($case.Home) {
        $env:HOMEDRIVE = 'C:'
        $env:HOMEPATH = '\Users\Admin'
        $env:USERPROFILE = 'C:\Users\Admin'
        $env:APPDATA = 'C:\Users\Admin\AppData\Roaming'
        $env:LOCALAPPDATA = 'C:\Users\Admin\AppData\Local'
    }
    $log = Join-Path $caseRoot 'startup.log'
    $args = @($case.Extra + $statement)
    $started = Get-Date
    & $matlab @args *> $log
    $exitCode = $LASTEXITCODE
    $finished = Get-Date
    $results += [ordered]@{
        name = $case.Name
        arguments = $args
        home_sanitized = $case.Home
        exit_code = $exitCode
        started_local = $started.ToString('o')
        finished_local = $finished.ToString('o')
        log = $log
        log_has_minimal_start = ((Get-Content -Raw $log -ErrorAction SilentlyContinue) -match 'MINIMAL_START')
        log_has_minimal_done = ((Get-Content -Raw $log -ErrorAction SilentlyContinue) -match 'MINIMAL_DONE')
    }
    foreach ($name in $old.Keys) { [Environment]::SetEnvironmentVariable($name,$old[$name],'Process') }
}
$results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $diagnostic 'startup-matrix-receipt.json') -Encoding UTF8
$results | Format-Table -AutoSize | Out-String | Set-Content -LiteralPath (Join-Path $diagnostic 'startup-matrix-summary.txt') -Encoding UTF8
$results | ConvertTo-Json -Depth 6
