$ErrorActionPreference = 'Stop'
$lab = Split-Path -Parent $MyInvocation.MyCommand.Path
$diagnostic = Join-Path $lab 'startup-diagnostic'
New-Item -ItemType Directory -Force -Path (Join-Path $diagnostic 'prefs'), (Join-Path $diagnostic 'temp') | Out-Null
$env:MATLAB_PREFDIR = Join-Path $diagnostic 'prefs'
$env:TEMP = Join-Path $diagnostic 'temp'
$env:TMP = $env:TEMP
$exe = 'D:\Program Files\MATLAB\R2026a\bin\matlab.exe'
$statement = "fprintf('MINIMAL_START\n'); assert(2+2==4); fprintf('VERSION=%s\n',version); fprintf('SIMULINK_LICENSE=%d\n',license('test','Simulink')); disp('MINIMAL_DONE');"
$log = Join-Path $diagnostic 'nojvm-minimal.log'
& $exe -nojvm -batch $statement *> $log
$exitCode = $LASTEXITCODE
@{
    executable = $exe
    arguments = @('-nojvm', '-batch', $statement)
    MATLAB_PREFDIR = $env:MATLAB_PREFDIR
    TEMP = $env:TEMP
    TMP = $env:TMP
    exit_code = $exitCode
    log = $log
    completed_utc = (Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $diagnostic 'nojvm-minimal-receipt.json') -Encoding UTF8
Get-Content -LiteralPath $log
Write-Output "MATLAB_EXIT_CODE=$exitCode"
exit $exitCode
