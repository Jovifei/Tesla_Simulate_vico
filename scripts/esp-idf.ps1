param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $IdfArgs
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EspIdfPath = 'E:\project\ESP_IDF_support\v5.3.2\esp-idf'
$ToolsPath = 'E:\project\ESP_IDF_support\tools'
$PythonEnvPath = 'E:\project\ESP_IDF_support\tools\python_env\idf5.3_py3.14_env'

if ($IdfArgs.Count -eq 0) {
    $IdfArgs = @('build')
}

$ExportScript = Join-Path $EspIdfPath 'export.ps1'
$PythonScriptsPath = Join-Path $PythonEnvPath 'Scripts'
$BundledNinjaPath = Join-Path $ToolsPath 'tools\ninja\1.12.1'
$BundledCMakePath = Join-Path $ToolsPath 'tools\cmake\3.30.2\bin'
if (-not (Test-Path -LiteralPath $ExportScript)) {
    throw "ESP-IDF export script not found: $ExportScript"
}
if (-not (Test-Path -LiteralPath $ToolsPath)) {
    throw "ESP-IDF tools path not found: $ToolsPath"
}
if (-not (Test-Path -LiteralPath $PythonEnvPath)) {
    throw "ESP-IDF Python environment not found: $PythonEnvPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $PythonScriptsPath 'python.exe'))) {
    throw "ESP-IDF Python executable not found: $PythonScriptsPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $BundledNinjaPath 'ninja.exe'))) {
    throw "ESP-IDF bundled ninja not found: $BundledNinjaPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $BundledCMakePath 'cmake.exe'))) {
    throw "ESP-IDF bundled cmake not found: $BundledCMakePath"
}

$env:IDF_PATH = $EspIdfPath
$env:IDF_TOOLS_PATH = $ToolsPath
$env:IDF_PYTHON_ENV_PATH = $PythonEnvPath

$env:PATH = @(
    $PythonScriptsPath
    $BundledNinjaPath
    $BundledCMakePath
    (Join-Path $EspIdfPath 'tools')
    $env:PATH
) -join [System.IO.Path]::PathSeparator

Push-Location $ProjectRoot
try {
    & $ExportScript
    if ($LASTEXITCODE -ne 0) {
        throw "ESP-IDF export failed with exit code $LASTEXITCODE"
    }

    & idf.py @IdfArgs
    if ($LASTEXITCODE -ne 0) {
        throw "idf.py $($IdfArgs -join ' ') failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
